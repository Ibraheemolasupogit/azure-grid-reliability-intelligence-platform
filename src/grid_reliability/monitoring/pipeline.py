"""Operational monitoring pipeline and CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.monitoring.checks import (
    analytical_health_records,
    data_freshness_records,
    data_volume_records,
    distribution_drift_records,
    evaluate_alerts,
    model_health_records,
    pipeline_health_records,
    quality_trend_records,
    schema_drift_records,
)
from grid_reliability.monitoring.config import MonitoringConfig, load_monitoring_config
from grid_reliability.monitoring.discovery import discover_component_runs
from grid_reliability.monitoring.models import (
    AlertEvaluation,
    ComponentRun,
    MonitoringError,
    MonitoringRecord,
)
from grid_reliability.monitoring.persistence import (
    build_manifest,
    build_metrics,
    write_monitoring_outputs,
)
from grid_reliability.monitoring.reporting import write_reports


@dataclass(frozen=True)
class MonitoringPipelineResult:
    run_id: str
    output_paths: dict[str, Path]
    report_paths: dict[str, Path]
    records: dict[str, list[MonitoringRecord]]
    alerts: list[AlertEvaluation]
    metrics: dict[str, object]


def build_run_id(config: MonitoringConfig, provided: str | None = None) -> str:
    if provided:
        return provided
    if config.run_id_strategy == "deterministic":
        return "monitoring-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_monitoring(
    config: MonitoringConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
    config_path: Path | None = None,
) -> MonitoringPipelineResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config, run_id)
    timestamp = config.monitoring_timestamp.isoformat().replace("+00:00", "Z")
    runs = discover_component_runs(root, config)
    records = {
        "pipeline_health": pipeline_health_records(root, config, runs),
        "data_freshness": data_freshness_records(root, config),
        "data_volume": data_volume_records(root, config),
        "data_quality_trends": quality_trend_records(config, runs),
        "schema_drift": schema_drift_records(root, config),
        "distribution_drift": distribution_drift_records(root, config),
        "model_health": model_health_records(config, runs),
        "analytical_health": analytical_health_records(config, runs),
    }
    all_records = [row for rows in records.values() for row in rows]
    alerts = evaluate_alerts(effective_run_id, config.monitoring_timestamp, all_records, config)
    metrics = build_metrics(records, alerts)
    source_files = sorted({path for run in runs for path in run.source_paths})
    source_checksums = _checksums(root, source_files)
    baseline_files = _baseline_files(root, config)
    manifest = build_manifest(
        project_name=settings.project_name,
        run_id=effective_run_id,
        monitoring_timestamp=timestamp,
        config_checksum=sha256_file(config_path) if config_path and config_path.exists() else None,
        source_files=source_files,
        source_checksums=source_checksums,
        source_run_ids=_source_run_ids(runs),
        baseline_files=baseline_files,
        baseline_checksums=_checksums(root, baseline_files),
        checks_executed=sorted(records),
        metrics=metrics,
    )
    output_paths = write_monitoring_outputs(
        project_root=root,
        output_root=config.output_root,
        run_id=effective_run_id,
        monitoring_timestamp=timestamp,
        schema_version=config.schema_version,
        records=records,
        alerts=alerts,
        metrics=metrics,
        manifest=manifest,
    )
    report_paths = write_reports(
        project_root=root,
        report_root=config.report_root,
        run_id=effective_run_id,
        records=records,
        alerts=alerts,
        metrics=metrics,
    )
    return MonitoringPipelineResult(
        effective_run_id, output_paths, report_paths, records, alerts, metrics
    )


def _source_run_ids(runs: list[ComponentRun]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for run in runs:
        output.setdefault(run.component_name, []).append(run.run_id)
    return {name: sorted(set(values)) for name, values in sorted(output.items())}


def _baseline_files(root: Path, config: MonitoringConfig) -> list[str]:
    if not config.baseline_root:
        return []
    base = root / config.baseline_root
    if not base.exists():
        return []
    files = [
        path
        for path in base.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() in {".json", ".csv", ".yaml", ".yml", ".jsonl"}
    ]
    return sorted(_relative(root, path) for path in files)


def _checksums(root: Path, relative_paths: list[str]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for relative in relative_paths:
        path = root / relative
        if path.exists() and path.is_file() and not path.is_symlink():
            checksums[relative] = sha256_file(path)
    return dict(sorted(checksums.items()))


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local platform monitoring.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--baseline-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--monitoring-timestamp")
    parser.add_argument("--component")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = resolve_project_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    try:
        config = load_monitoring_config(
            config_path,
            project_root=root,
            source_root=args.source_root,
            baseline_root=args.baseline_root,
            output_root=args.output_root,
            report_root=args.report_root,
            monitoring_timestamp=args.monitoring_timestamp,
            component=args.component,
        )
        result = run_monitoring(
            config,
            project_root=root,
            run_id=args.run_id,
            config_path=config_path,
        )
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except MonitoringError as exc:
        print(json.dumps({"run_status": "FAILED_MONITORING_SOURCE", "error": str(exc)}))
        return 3
    except Exception as exc:
        print(json.dumps({"run_status": "FAILED_MONITORING_PROCESSING", "error": str(exc)}))
        return 1
    print(
        f"Monitoring run {result.run_id}: checks={result.metrics['checks_executed']}; "
        f"alerts={len(result.alerts)}; summary={result.output_paths['monitoring_summary']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
