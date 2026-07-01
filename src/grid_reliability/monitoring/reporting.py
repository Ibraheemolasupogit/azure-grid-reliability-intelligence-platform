"""Markdown reports for local monitoring."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.monitoring.models import AlertEvaluation, MonitoringRecord


def write_reports(
    *,
    project_root: Path,
    report_root: Path,
    run_id: str,
    records: dict[str, list[MonitoringRecord]],
    alerts: list[AlertEvaluation],
    metrics: dict[str, Any],
) -> dict[str, Path]:
    root = project_root / report_root / run_id
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "operational_health": root / "operational_health_report.md",
        "data_quality": root / "data_quality_monitoring_report.md",
        "model_monitoring": root / "model_monitoring_report.md",
        "alert_summary": root / "alert_summary.md",
        "executive_summary": root / "executive_monitoring_summary.md",
    }
    _write(paths["operational_health"], _operational(records, metrics))
    _write(paths["data_quality"], _data_quality(records))
    _write(paths["model_monitoring"], _model(records))
    _write(paths["alert_summary"], _alerts(alerts))
    _write(paths["executive_summary"], _executive(metrics, alerts))
    return paths


def _operational(records: dict[str, list[MonitoringRecord]], metrics: dict[str, Any]) -> list[str]:
    lines = [
        "# Operational Health Report",
        "",
        "## Components Monitored",
        "",
    ]
    for component in metrics.get("components_discovered", []):
        lines.append(f"- `{component}`")
    lines.extend(
        [
            "",
            "## Pipeline Health",
            "",
            "| Component | Run | Status | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in records.get("pipeline_health", []):
        lines.append(
            f"| {row.component_name} | {row.source_run_id} | "
            f"{row.status.value} | {row.reason_code} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This report is generated from local runtime manifests and metrics only.",
            "- No Azure Monitor, Application Insights, Log Analytics, or "
            "alert-delivery resource is deployed.",
        ]
    )
    return lines


def _data_quality(records: dict[str, list[MonitoringRecord]]) -> list[str]:
    lines = [
        "# Data Quality Monitoring Report",
        "",
        "## Freshness, Volume, Quality, Schema, and Drift",
        "",
        "| Monitor | Scope | Metric | Value | Status | Reason |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for key in (
        "data_freshness",
        "data_volume",
        "data_quality_trends",
        "schema_drift",
        "distribution_drift",
    ):
        for row in records.get(key, []):
            lines.append(
                f"| {row.monitor_type} | {row.scope_id} | {row.metric_name} | "
                f"{row.metric_value if row.metric_value is not None else ''} | "
                f"{row.status.value} | {row.reason_code} |"
            )
    lines.extend(
        [
            "",
            "## Baseline Limitations",
            "",
            "- First-run monitoring reports missing baselines explicitly instead of "
            "assuming stability.",
            "- Schema drift compares machine-readable local contracts only; no migration "
            "is performed.",
        ]
    )
    return lines


def _model(records: dict[str, list[MonitoringRecord]]) -> list[str]:
    lines = [
        "# Model Monitoring Report",
        "",
        "## Forecasting and Outage Prediction",
        "",
        "| Component | Metric | Value | Threshold | Status | Reason |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in records.get("model_health", []):
        lines.append(
            f"| {row.component_name} | {row.metric_name} | "
            f"{row.metric_value if row.metric_value is not None else ''} | "
            f"{row.threshold if row.threshold is not None else ''} | "
            f"{row.status.value} | {row.reason_code} |"
        )
    lines.extend(
        [
            "",
            "## Operational Boundary",
            "",
            "- Monitoring does not retrain, retune thresholds, deploy models, or replace models.",
            "- Null metrics remain unavailable when the validation sample cannot support them.",
        ]
    )
    return lines


def _alerts(alerts: list[AlertEvaluation]) -> list[str]:
    lines = [
        "# Alert Summary",
        "",
        "Alerts are local records for human review. No external delivery was attempted.",
        "",
        "| Severity | Status | Component | Scope | Metric | Reason | Suppressed |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for alert in alerts:
        lines.append(
            f"| {alert.severity.value} | {alert.alert_status.value} | {alert.component_name} | "
            f"{alert.scope_type}:{alert.scope_id} | {alert.metric_name} | "
            f"{alert.reason_code} | {alert.suppressed} |"
        )
    return lines


def _executive(metrics: dict[str, Any], alerts: list[AlertEvaluation]) -> list[str]:
    high = sum(
        1
        for alert in alerts
        if alert.alert_status.value == "TRIGGERED" and alert.severity.value in {"HIGH", "CRITICAL"}
    )
    return [
        "# Executive Monitoring Summary",
        "",
        f"- Checks executed: {metrics.get('checks_executed', 0)}",
        f"- Passed checks: {metrics.get('passed_checks', 0)}",
        f"- Warning checks: {metrics.get('warning_checks', 0)}",
        f"- Failed checks: {metrics.get('failed_checks', 0)}",
        f"- High or critical triggered alerts: {high}",
        f"- Unavailable components: "
        f"{', '.join(metrics.get('unavailable_components', [])) or 'none'}",
        "",
        "Monitoring is local and deterministic. It does not provide live telemetry, "
        "external alert delivery, Power BI dashboards, or Azure deployment.",
    ]


def _write(path: Path, lines: list[str]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write("\n".join(lines) + "\n")
    temp_path.replace(path)
