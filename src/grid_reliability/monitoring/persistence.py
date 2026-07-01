"""Persistence for monitoring outputs."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.common.metadata import __version__
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.monitoring.models import AlertEvaluation, MonitoringRecord, to_jsonable

SUMMARY_COLUMNS = [
    "monitoring_run_id",
    "monitoring_timestamp",
    "component_name",
    "source_run_id",
    "scope_type",
    "scope_id",
    "monitor_type",
    "metric_name",
    "metric_value",
    "metric_unit",
    "baseline_value",
    "threshold",
    "status",
    "severity",
    "reason_code",
    "sample_size",
    "schema_version",
]

ALERT_COLUMNS = [
    "alert_id",
    "monitoring_run_id",
    "component_name",
    "scope_type",
    "scope_id",
    "metric_name",
    "observed_value",
    "threshold",
    "severity",
    "alert_status",
    "suppressed",
    "suppression_reason",
    "reason_code",
    "message",
    "source_run_id",
    "schema_version",
]


def write_monitoring_outputs(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    monitoring_timestamp: str,
    schema_version: str,
    records: dict[str, list[MonitoringRecord]],
    alerts: list[AlertEvaluation],
    metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Path]:
    root = project_root / output_root
    run_root = root / run_id
    root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    all_records = [row for rows in records.values() for row in rows]
    paths = {
        "monitoring_summary": root / "monitoring_summary.csv",
        "alerts": root / "alerts.csv",
        "pipeline_health": run_root / "pipeline_health.csv",
        "data_freshness": run_root / "data_freshness.csv",
        "data_volume": run_root / "data_volume.csv",
        "data_quality_trends": run_root / "data_quality_trends.csv",
        "schema_drift": run_root / "schema_drift.csv",
        "distribution_drift": run_root / "distribution_drift.csv",
        "model_health": run_root / "model_health.csv",
        "analytical_health": run_root / "analytical_health.csv",
        "alert_evaluations": run_root / "alert_evaluations.csv",
        "metrics": run_root / "metrics.json",
        "manifest": run_root / "monitoring_manifest.json",
    }
    _write_csv(
        paths["monitoring_summary"],
        SUMMARY_COLUMNS,
        [_record_row(run_id, monitoring_timestamp, schema_version, row) for row in all_records],
    )
    _write_csv(
        paths["alerts"],
        ALERT_COLUMNS,
        [_alert_row(run_id, schema_version, row) for row in alerts],
    )
    for name, rows in records.items():
        _write_csv(
            paths[name],
            SUMMARY_COLUMNS,
            [_record_row(run_id, monitoring_timestamp, schema_version, row) for row in rows],
        )
    _write_csv(
        paths["alert_evaluations"],
        ALERT_COLUMNS,
        [_alert_row(run_id, schema_version, row) for row in alerts],
    )
    _write_json(paths["metrics"], metrics)
    manifest_payload = {
        **manifest,
        "component_version": __version__,
        "repository_revision": _repo_revision(project_root),
        "output_files": {
            name: _relative(project_root, path) for name, path in sorted(paths.items())
        },
    }
    _write_json(paths["manifest"], manifest_payload)
    manifest_payload["output_checksums"] = {
        name: sha256_file(path) for name, path in sorted(paths.items()) if name != "manifest"
    }
    _write_json(paths["manifest"], manifest_payload)
    return paths


def build_metrics(
    records: dict[str, list[MonitoringRecord]], alerts: list[AlertEvaluation]
) -> dict[str, Any]:
    all_records = [row for rows in records.values() for row in rows]
    pipeline_records = records.get("pipeline_health", [])
    status_counts = _counts(row.status.value for row in all_records)
    alert_counts = _counts(
        row.severity.value for row in alerts if row.alert_status.value == "TRIGGERED"
    )
    return {
        "checks_executed": len(all_records),
        "passed_checks": status_counts.get("HEALTHY", 0)
        + status_counts.get("HEALTHY_WITH_WARNINGS", 0),
        "warning_checks": status_counts.get("DEGRADED", 0),
        "failed_checks": status_counts.get("FAILED", 0),
        "not_available_checks": status_counts.get("NOT_AVAILABLE", 0),
        "alerts_by_severity": alert_counts,
        "suppressed_alerts": sum(1 for row in alerts if row.suppressed),
        "stale_datasets": _reason_count(all_records, "DATA_STALE")
        + _reason_count(all_records, "DATA_VERY_STALE"),
        "volume_anomalies": _reason_count(all_records, "VOLUME_DROP")
        + _reason_count(all_records, "VOLUME_SPIKE"),
        "quality_degradations": _reason_count(all_records, "ERROR_RATE_THRESHOLD_EXCEEDED")
        + _reason_count(all_records, "WARNING_RATE_THRESHOLD_EXCEEDED"),
        "schema_drift_counts": _monitor_count(all_records, "schema_drift", degraded=True),
        "distribution_drift_counts": _monitor_count(
            all_records, "distribution_drift", degraded=True
        ),
        "model_performance_alerts": _monitor_count(all_records, "model_health", degraded=True),
        "analytical_health_alerts": _monitor_count(all_records, "analytical_health", degraded=True),
        "insufficient_sample_checks": _reason_count(all_records, "INSUFFICIENT_SAMPLE_FOR_DRIFT"),
        "components_discovered": sorted({row.component_name for row in pipeline_records}),
        "components_monitored": sorted(
            {row.component_name for row in pipeline_records if row.status.value != "NOT_AVAILABLE"}
        ),
        "unavailable_components": sorted(
            {row.component_name for row in pipeline_records if row.status.value == "NOT_AVAILABLE"}
        ),
    }


def build_manifest(
    *,
    project_name: str,
    run_id: str,
    monitoring_timestamp: str,
    config_checksum: str | None,
    source_files: list[str],
    source_checksums: dict[str, str],
    source_run_ids: dict[str, list[str]],
    baseline_files: list[str],
    baseline_checksums: dict[str, str],
    checks_executed: list[str],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "monitoring_run_id": run_id,
        "monitoring_timestamp": monitoring_timestamp,
        "component_version": __version__,
        "configuration_checksum": config_checksum,
        "source_files": source_files,
        "source_checksums": source_checksums,
        "source_run_ids": source_run_ids,
        "baseline_files": baseline_files,
        "baseline_checksums": baseline_checksums,
        "checks_executed": checks_executed,
        "alert_counts": metrics.get("alerts_by_severity", {}),
        "schema_drift_counts": metrics.get("schema_drift_counts", 0),
        "distribution_drift_counts": metrics.get("distribution_drift_counts", 0),
        "unavailable_component_counts": len(metrics.get("unavailable_components", [])),
        "synthetic_data_declaration": (
            "Monitoring uses local fictional synthetic runtime evidence only."
        ),
        "limitations": [
            "No Azure Monitor, Application Insights, Log Analytics, Purview, "
            "or Power BI resources are deployed.",
            "Alerts are local records only; no external notification delivery occurs.",
            "Small CI samples are not production stability evidence.",
        ],
    }


def _record_row(
    run_id: str, timestamp: str, schema_version: str, row: MonitoringRecord
) -> dict[str, Any]:
    return {
        "monitoring_run_id": run_id,
        "monitoring_timestamp": timestamp,
        "component_name": row.component_name,
        "source_run_id": row.source_run_id,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
        "monitor_type": row.monitor_type,
        "metric_name": row.metric_name,
        "metric_value": row.metric_value,
        "metric_unit": row.metric_unit,
        "baseline_value": row.baseline_value,
        "threshold": row.threshold,
        "status": row.status.value,
        "severity": row.severity.value,
        "reason_code": row.reason_code,
        "sample_size": row.sample_size,
        "schema_version": schema_version,
    }


def _alert_row(run_id: str, schema_version: str, row: AlertEvaluation) -> dict[str, Any]:
    return {
        "alert_id": row.alert_id,
        "monitoring_run_id": run_id,
        "component_name": row.component_name,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
        "metric_name": row.metric_name,
        "observed_value": row.observed_value,
        "threshold": row.threshold,
        "severity": row.severity.value,
        "alert_status": row.alert_status.value,
        "suppressed": row.suppressed,
        "suppression_reason": row.suppression_reason,
        "reason_code": row.reason_code,
        "message": row.message,
        "source_run_id": row.source_run_id,
        "schema_version": schema_version,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: [str(item.get(name, "")) for name in fieldnames]):
            writer.writerow({key: _cell(value) for key, value in row.items()})
    temp_path.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        json.dump(to_jsonable(payload), temp, indent=2, sort_keys=True)
        temp.write("\n")
    temp_path.replace(path)


def _cell(value: Any) -> Any:
    converted = to_jsonable(value)
    if converted is None:
        return ""
    if isinstance(converted, (dict, list)):
        return json.dumps(converted, sort_keys=True)
    return converted


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _reason_count(rows: list[MonitoringRecord], reason: str) -> int:
    return sum(1 for row in rows if reason in row.reason_code)


def _monitor_count(rows: list[MonitoringRecord], monitor_type: str, *, degraded: bool) -> int:
    statuses = {"DEGRADED", "FAILED"} if degraded else {"HEALTHY", "HEALTHY_WITH_WARNINGS"}
    return sum(
        1 for row in rows if row.monitor_type == monitor_type and row.status.value in statuses
    )


def _repo_revision(project_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name
