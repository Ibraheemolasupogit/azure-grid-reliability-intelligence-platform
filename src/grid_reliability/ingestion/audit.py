"""Machine-readable audit manifests and human-readable quality reports."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.common.metadata import __version__
from grid_reliability.ingestion.config import IngestionConfig
from grid_reliability.ingestion.metrics import (
    RunMetrics,
    RunStatus,
    issue_counts_by_code,
    issue_counts_by_dataset,
)
from grid_reliability.ingestion.normalisation import WrittenOutput
from grid_reliability.ingestion.quarantine import WrittenQuarantine
from grid_reliability.validation.models import ValidationIssue


def write_metrics_report(
    *,
    report_root: Path,
    run_id: str,
    metrics: RunMetrics,
    status: RunStatus,
    maximum_error_rate: float,
) -> Path:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / "metrics.json"
    _write_json(path, metrics.to_dict(status=status, maximum_error_rate=maximum_error_rate))
    return path


def write_audit_manifest(
    *,
    report_root: Path,
    run_id: str,
    config: IngestionConfig,
    status: RunStatus,
    source_manifest: dict[str, Any] | None,
    contracts: dict[str, dict[str, Any]],
    input_checksums: dict[str, str],
    outputs: dict[str, WrittenOutput],
    quarantines: dict[str, WrittenQuarantine],
    metrics: RunMetrics,
    project_name: str,
) -> Path:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / "ingestion_manifest.json"
    payload: dict[str, Any] = {
        "project_name": project_name,
        "ingestion_run_id": run_id,
        "ingestion_mode": "local_batch",
        "source_manifest_identity": {
            "present": source_manifest is not None,
            "schema_version": source_manifest.get("schema_version") if source_manifest else None,
            "generator_version": source_manifest.get("generator_version")
            if source_manifest
            else None,
        },
        "configuration_profile": config.profile,
        "contract_versions": {
            name: contract["schema_version"] for name, contract in sorted(contracts.items())
        },
        "input_datasets": sorted(input_checksums),
        "input_checksums": input_checksums,
        "output_datasets": {name: output.__dict__ for name, output in sorted(outputs.items())},
        "quarantine_files": {
            name: quarantine.__dict__ for name, quarantine in sorted(quarantines.items())
        },
        "record_counts": metrics.to_dict(
            status=status, maximum_error_rate=config.maximum_error_rate
        ),
        "run_status": status.value,
        "quality_threshold_result": {
            "maximum_error_rate": config.maximum_error_rate,
            "observed_error_rate": metrics.total_metrics().error_rate,
            "passed": status in {RunStatus.PASSED, RunStatus.PASSED_WITH_WARNINGS},
        },
        "synthetic_data_declaration": (
            "Local ingestion expects fictional synthetic data only; "
            "no Azure resources are deployed."
        ),
        "generator_schema_version": source_manifest.get("schema_version")
        if source_manifest
        else None,
        "ingestion_component_version": __version__,
    }
    _write_json(path, payload)
    return path


def write_quality_report(
    *,
    report_root: Path,
    run_id: str,
    status: RunStatus,
    metrics: RunMetrics,
    issues: list[ValidationIssue],
    manifest_failed: bool,
    maximum_error_rate: float,
) -> Path:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / "data_quality_report.md"
    totals = metrics.total_metrics()
    lines = [
        "# Data Quality Report",
        "",
        "## Executive Summary",
        "",
        f"- Run status: `{status.value}`",
        f"- Records discovered: {totals.source_records_discovered}",
        f"- Valid records: {totals.valid_records}",
        f"- Invalid records: {totals.invalid_records}",
        f"- Warning records: {totals.warning_records}",
        f"- Error rate: {totals.error_rate:.6f}",
        f"- Maximum configured error rate: {maximum_error_rate:.6f}",
        "",
        "## Datasets Processed",
        "",
        "| Dataset | Source | Valid | Warnings | Invalid | Quarantined | Error rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for dataset, dataset_metrics in sorted(metrics.datasets.items()):
        lines.append(
            "| "
            f"{dataset} | {dataset_metrics.source_records_discovered} | "
            f"{dataset_metrics.valid_records} | {dataset_metrics.warning_records} | "
            f"{dataset_metrics.invalid_records} | {dataset_metrics.quarantined_records} | "
            f"{dataset_metrics.error_rate:.6f} |"
        )
    lines.extend(["", "## Issue Counts By Code", ""])
    for code, count in issue_counts_by_code(issues).items():
        lines.append(f"- `{code}`: {count}")
    if not issue_counts_by_code(issues):
        lines.append("- None")
    lines.extend(["", "## Issue Counts By Dataset", ""])
    for dataset, count in issue_counts_by_dataset(issues).items():
        lines.append(f"- `{dataset}`: {count}")
    if not issue_counts_by_dataset(issues):
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Manifest Verification",
            "",
            "- Result: " + ("failed" if manifest_failed else "passed or not required"),
            "",
            "## Cross-Dataset Relationship Result",
            "",
            f"- Relationship violations: {totals.relationship_violations}",
            "",
            "## Quarantine Summary",
            "",
            f"- Quarantined records: {totals.quarantined_records}",
            "",
            "## Threshold Decision",
            "",
            f"- Observed error rate `{totals.error_rate:.6f}` "
            f"against threshold `{maximum_error_rate:.6f}`.",
            "",
            "## Limitations",
            "",
            "- This is a deterministic local batch ingestion and validation workflow.",
            "- Event-oriented reading is finite and local; it is not a live Event Hubs stream.",
            "- Azure Monitor, Purview, ADLS Gen2, Stream Analytics, and Event Hubs "
            "are architectural mappings only.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(payload, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
    temp_path.replace(path)
