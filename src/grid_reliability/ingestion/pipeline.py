"""Governed local ingestion and validation pipeline."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.contracts import load_contracts
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.ingestion.audit import (
    write_audit_manifest,
    write_metrics_report,
    write_quality_report,
)
from grid_reliability.ingestion.config import IngestionConfig, load_ingestion_config
from grid_reliability.ingestion.discovery import discover_sources
from grid_reliability.ingestion.manifest import (
    verify_manifest_record_counts,
    verify_source_manifest,
)
from grid_reliability.ingestion.metrics import DatasetMetrics, RunMetrics, RunStatus, classify_issue
from grid_reliability.ingestion.normalisation import WrittenOutput, write_interim_dataset
from grid_reliability.ingestion.quarantine import (
    QuarantineEntry,
    WrittenQuarantine,
    write_quarantine_dataset,
)
from grid_reliability.ingestion.readers import read_dataset
from grid_reliability.ingestion.records import IngestionRecord
from grid_reliability.validation.contract_validator import validate_record_contract
from grid_reliability.validation.dataset_rules import validate_dataset_rules
from grid_reliability.validation.models import RecordValidationResult, Severity, ValidationIssue
from grid_reliability.validation.relationship_rules import validate_relationships


@dataclass
class ProcessedRecord:
    source: IngestionRecord
    validation: RecordValidationResult
    additional_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def issues(self) -> list[ValidationIssue]:
        return [*self.validation.issues, *self.additional_issues]

    @property
    def normalised_record(self) -> dict[str, Any] | None:
        return self.validation.normalised_record

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == Severity.WARNING for issue in self.issues)


@dataclass(frozen=True)
class IngestionResult:
    run_id: str
    status: RunStatus
    metrics_path: Path
    audit_manifest_path: Path
    quality_report_path: Path
    interim_outputs: dict[str, WrittenOutput]
    quarantine_outputs: dict[str, WrittenQuarantine]
    metrics: RunMetrics


def build_run_id(strategy: str, provided: str | None = None) -> str:
    if provided:
        return provided
    if strategy == "deterministic":
        return "local-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_ingestion(
    config: IngestionConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
) -> IngestionResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config.run_id_strategy, run_id)
    ingested_at = datetime.now(tz=UTC)
    source_root = root / config.source_root
    interim_root = root / config.interim_root
    quarantine_root = root / config.quarantine_root
    report_root = root / config.report_root
    contract_root = root / config.contract_root
    contracts = load_contracts(contract_root)
    metrics = RunMetrics(effective_run_id)

    manifest_result = verify_source_manifest(
        source_root=source_root,
        manifest_filename=config.manifest_filename,
        contracts=contracts,
        require_manifest=config.require_manifest,
        verify_checksums=config.verify_manifest_checksums,
        expected_project_name=settings.project_name,
    )
    metrics.issues.extend(manifest_result.issues)
    manifest_failed = manifest_result.has_errors
    if manifest_failed and config.fail_on_contract_error:
        return _write_failure_reports(
            config=config,
            contracts=contracts,
            input_checksums={},
            manifest=manifest_result.manifest,
            manifest_failed=True,
            metrics=metrics,
            project_name=settings.project_name,
            report_root=report_root,
            run_id=effective_run_id,
            status=RunStatus.FAILED_MANIFEST,
        )

    discovery = discover_sources(
        source_root=source_root,
        contracts=contracts,
        fail_on_missing_dataset=config.fail_on_missing_dataset,
        manifest_filename=config.manifest_filename,
    )
    metrics.issues.extend(discovery.issues)
    if discovery.has_errors and config.fail_on_contract_error:
        return _write_failure_reports(
            config=config,
            contracts=contracts,
            input_checksums={},
            manifest=manifest_result.manifest,
            manifest_failed=True,
            metrics=metrics,
            project_name=settings.project_name,
            report_root=report_root,
            run_id=effective_run_id,
            status=RunStatus.FAILED_MANIFEST,
        )

    processed_by_dataset: dict[str, list[ProcessedRecord]] = {}
    observed_counts: dict[str, int] = {}
    input_checksums: dict[str, str] = {}
    for source_dataset in discovery.datasets:
        started = perf_counter()
        dataset_metrics = metrics.datasets.setdefault(source_dataset.dataset_name, DatasetMetrics())
        input_checksums[source_dataset.dataset_name] = sha256_file(source_dataset.path)
        processed: list[ProcessedRecord] = []
        for ingestion_record in read_dataset(
            source_dataset,
            ingestion_run_id=effective_run_id,
            ingested_at=ingested_at,
        ):
            if ingestion_record.source_record_number > 0:
                dataset_metrics.source_records_discovered += 1
            if ingestion_record.parsed_record is not None:
                dataset_metrics.records_parsed += 1
            validation = validate_record_contract(ingestion_record, source_dataset.contract)
            processed.append(ProcessedRecord(ingestion_record, validation))
        observed_counts[source_dataset.dataset_name] = dataset_metrics.source_records_discovered
        dataset_metrics.elapsed_processing_seconds = round(perf_counter() - started, 6)
        processed_by_dataset[source_dataset.dataset_name] = processed

    count_issues = verify_manifest_record_counts(manifest_result.manifest, observed_counts)
    metrics.issues.extend(count_issues)
    manifest_failed = manifest_failed or any(
        issue.severity == Severity.ERROR for issue in count_issues
    )
    if manifest_failed and config.fail_on_contract_error:
        return _write_failure_reports(
            config=config,
            contracts=contracts,
            input_checksums=input_checksums,
            manifest=manifest_result.manifest,
            manifest_failed=True,
            metrics=metrics,
            project_name=settings.project_name,
            report_root=report_root,
            run_id=effective_run_id,
            status=RunStatus.FAILED_MANIFEST,
        )

    _apply_dataset_and_relationship_rules(processed_by_dataset, contracts)
    interim_outputs: dict[str, WrittenOutput] = {}
    quarantine_outputs: dict[str, WrittenQuarantine] = {}

    for dataset_name, processed_records in sorted(processed_by_dataset.items()):
        dataset_metrics = metrics.datasets.setdefault(dataset_name, DatasetMetrics())
        valid_records: list[dict[str, Any]] = []
        quarantine_entries: list[QuarantineEntry] = []
        contract = contracts[dataset_name]
        schema_version = str(contract["schema_version"])
        for processed_record in processed_records:
            issues = processed_record.issues
            metrics.issues.extend(issues)
            for issue in issues:
                classify_issue(dataset_metrics, issue)
            if processed_record.has_errors:
                dataset_metrics.invalid_records += 1
                quarantine_entries.append(
                    QuarantineEntry(processed_record.source, issues, schema_version)
                )
            elif processed_record.normalised_record is not None:
                valid_records.append(processed_record.normalised_record)
                dataset_metrics.valid_records += 1
                if processed_record.has_warnings:
                    dataset_metrics.warning_records += 1
        output = write_interim_dataset(
            interim_root=interim_root,
            dataset_name=dataset_name,
            records=valid_records,
        )
        dataset_metrics.output_record_count = output.record_count
        interim_outputs[dataset_name] = output
        quarantine = write_quarantine_dataset(
            quarantine_root=quarantine_root,
            run_id=effective_run_id,
            dataset_name=dataset_name,
            entries=quarantine_entries,
            quarantined_at=ingested_at,
        )
        if quarantine:
            dataset_metrics.quarantined_records = quarantine.record_count
            quarantine_outputs[dataset_name] = quarantine

    status = metrics.status(
        maximum_error_rate=config.maximum_error_rate,
        manifest_failed=manifest_failed,
    )
    metrics_path = write_metrics_report(
        report_root=report_root,
        run_id=effective_run_id,
        metrics=metrics,
        status=status,
        maximum_error_rate=config.maximum_error_rate,
    )
    audit_path = write_audit_manifest(
        report_root=report_root,
        run_id=effective_run_id,
        config=config,
        status=status,
        source_manifest=manifest_result.manifest,
        contracts=contracts,
        input_checksums=input_checksums,
        outputs=interim_outputs,
        quarantines=quarantine_outputs,
        metrics=metrics,
        project_name=settings.project_name,
    )
    quality_path = write_quality_report(
        report_root=report_root,
        run_id=effective_run_id,
        status=status,
        metrics=metrics,
        issues=metrics.issues,
        manifest_failed=manifest_failed,
        maximum_error_rate=config.maximum_error_rate,
    )
    return IngestionResult(
        effective_run_id,
        status,
        metrics_path,
        audit_path,
        quality_path,
        interim_outputs,
        quarantine_outputs,
        metrics,
    )


def _apply_dataset_and_relationship_rules(
    processed_by_dataset: dict[str, list[ProcessedRecord]],
    contracts: dict[str, dict[str, Any]],
) -> None:
    valid_candidates: dict[str, list[dict[str, Any]]] = {}
    candidate_indexes: dict[str, list[int]] = {}
    for dataset_name, processed_records in processed_by_dataset.items():
        valid_candidates[dataset_name] = []
        candidate_indexes[dataset_name] = []
        for index, processed in enumerate(processed_records):
            if not processed.has_errors and processed.normalised_record is not None:
                valid_candidates[dataset_name].append(processed.normalised_record)
                candidate_indexes[dataset_name].append(index)

    for dataset_name, records in valid_candidates.items():
        dataset_issues = validate_dataset_rules(dataset_name, records, contracts[dataset_name])
        for candidate_index, issues in dataset_issues.items():
            original_index = candidate_indexes[dataset_name][candidate_index]
            processed_by_dataset[dataset_name][original_index].additional_issues.extend(issues)

    relationship_issues = validate_relationships(valid_candidates)
    for dataset_name, issues_by_index in relationship_issues.items():
        for candidate_index, issues in issues_by_index.items():
            original_index = candidate_indexes[dataset_name][candidate_index]
            processed_by_dataset[dataset_name][original_index].additional_issues.extend(issues)


def _write_failure_reports(
    *,
    config: IngestionConfig,
    contracts: dict[str, dict[str, Any]],
    input_checksums: dict[str, str],
    manifest: dict[str, Any] | None,
    manifest_failed: bool,
    metrics: RunMetrics,
    project_name: str,
    report_root: Path,
    run_id: str,
    status: RunStatus,
) -> IngestionResult:
    metrics_path = write_metrics_report(
        report_root=report_root,
        run_id=run_id,
        metrics=metrics,
        status=status,
        maximum_error_rate=config.maximum_error_rate,
    )
    audit_path = write_audit_manifest(
        report_root=report_root,
        run_id=run_id,
        config=config,
        status=status,
        source_manifest=manifest,
        contracts=contracts,
        input_checksums=input_checksums,
        outputs={},
        quarantines={},
        metrics=metrics,
        project_name=project_name,
    )
    quality_path = write_quality_report(
        report_root=report_root,
        run_id=run_id,
        status=status,
        metrics=metrics,
        issues=metrics.issues,
        manifest_failed=manifest_failed,
        maximum_error_rate=config.maximum_error_rate,
    )
    return IngestionResult(run_id, status, metrics_path, audit_path, quality_path, {}, {}, metrics)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest and validate fictional synthetic grid data."
    )
    parser.add_argument("--config", default="configs/ingestion.yaml")
    parser.add_argument("--source-root")
    parser.add_argument("--interim-root")
    parser.add_argument("--quarantine-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = resolve_project_root()
    try:
        config = load_ingestion_config(
            args.config,
            project_root=project_root,
            source_root=args.source_root,
            interim_root=args.interim_root,
            quarantine_root=args.quarantine_root,
            report_root=args.report_root,
            strict=True if args.strict else None,
        )
        result = run_ingestion(config, project_root=project_root, run_id=args.run_id)
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except Exception as exc:
        print(json.dumps({"run_status": RunStatus.FAILED_PROCESSING.value, "error": str(exc)}))
        return 1

    totals = result.metrics.total_metrics()
    print(
        "Ingestion run "
        f"{result.run_id}: {result.status.value}; "
        f"valid={totals.valid_records}; invalid={totals.invalid_records}; "
        f"warnings={totals.warning_records}; report={result.quality_report_path}"
    )
    return 0 if result.status in {RunStatus.PASSED, RunStatus.PASSED_WITH_WARNINGS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
