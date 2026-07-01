"""Rule-driven local monitoring checks."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.monitoring.config import MonitoringConfig
from grid_reliability.monitoring.discovery import duplicate_run_ids
from grid_reliability.monitoring.models import (
    AlertEvaluation,
    AlertStatus,
    ComponentRun,
    HealthStatus,
    MonitoringRecord,
    Severity,
    parse_timestamp,
)

TIMESTAMP_FIELDS = (
    "reading_timestamp",
    "event_timestamp",
    "weather_timestamp",
    "timestamp",
    "outage_start",
    "restoration_time",
    "maintenance_date",
    "actual_start",
    "scheduled_start",
    "completed_at",
    "commissioned_date",
)


def pipeline_health_records(
    project_root: Path, config: MonitoringConfig, runs: list[ComponentRun]
) -> list[MonitoringRecord]:
    duplicates = duplicate_run_ids(runs)
    records: list[MonitoringRecord] = []
    for run in runs:
        status, severity, reasons = _pipeline_status(project_root, run)
        if (run.component_name, run.run_id) in duplicates:
            status = HealthStatus.DEGRADED
            severity = Severity.WARNING
            reasons.append("DUPLICATE_RUN_ID")
        if (
            run.component_name in config.required_components
            and status == HealthStatus.NOT_AVAILABLE
        ):
            status = HealthStatus.FAILED
            severity = Severity.CRITICAL
            reasons.append("MISSING_REQUIRED_COMPONENT")
        records.append(
            MonitoringRecord(
                component_name=run.component_name,
                source_run_id=run.run_id,
                scope_type="run",
                scope_id=run.run_id,
                monitor_type="pipeline_health",
                metric_name="run_status",
                metric_value=run.run_status,
                metric_unit="status",
                baseline_value=None,
                threshold="component must complete",
                status=status,
                severity=severity,
                reason_code="|".join(dict.fromkeys(reasons)) or "COMPONENT_HEALTHY",
                sample_size=run.output_record_count,
            )
        )
    return sorted_records(records)


def data_freshness_records(project_root: Path, config: MonitoringConfig) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    interim_root = project_root / "data/interim"
    raw_root = project_root / "data/raw"
    for dataset in _datasets():
        path = interim_root / f"{dataset}.jsonl"
        latest, count, missing_timestamp = _latest_jsonl_timestamp(path)
        if count == 0:
            raw_csv = raw_root / f"{dataset}.csv"
            raw_jsonl = raw_root / f"{dataset}.jsonl"
            latest, count, missing_timestamp = _latest_raw_timestamp(raw_csv, raw_jsonl)
        threshold = config.freshness_thresholds.get(dataset, 1440)
        if count == 0:
            status, reason, severity, age = (
                HealthStatus.NOT_AVAILABLE,
                "DATASET_EMPTY",
                Severity.WARNING,
                None,
            )
        elif missing_timestamp or latest is None:
            status, reason, severity, age = (
                HealthStatus.DEGRADED,
                "EVENT_TIMESTAMP_MISSING",
                Severity.WARNING,
                None,
            )
        else:
            age = (config.monitoring_timestamp - latest).total_seconds() / 60
            if age <= threshold:
                status, reason, severity = HealthStatus.HEALTHY, "DATA_FRESH", Severity.INFO
            elif age <= threshold * 2:
                status, reason, severity = HealthStatus.DEGRADED, "DATA_STALE", Severity.WARNING
            else:
                status, reason, severity = HealthStatus.FAILED, "DATA_VERY_STALE", Severity.HIGH
        rows.append(
            MonitoringRecord(
                "ingestion",
                "current-datasets",
                "dataset",
                dataset,
                "data_freshness",
                "freshness_age_minutes",
                round(age, 6) if age is not None else None,
                "minutes",
                None,
                threshold,
                status,
                severity,
                reason,
                count,
            )
        )
    return sorted_records(rows)


def data_volume_records(project_root: Path, config: MonitoringConfig) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    for dataset in _datasets():
        count = _dataset_count(project_root, dataset)
        baseline = _baseline_count(project_root, config, dataset)
        minimum = config.minimum_expected_records.get(dataset, 0)
        maximum = config.maximum_expected_records.get(dataset, 1_000_000)
        status = HealthStatus.HEALTHY
        severity = Severity.INFO
        reason = "VOLUME_WITHIN_EXPECTATION"
        if count < minimum:
            status, severity, reason = (
                HealthStatus.DEGRADED,
                Severity.WARNING,
                "BELOW_MINIMUM_VOLUME",
            )
        elif count > maximum:
            status, severity, reason = (
                HealthStatus.DEGRADED,
                Severity.WARNING,
                "ABOVE_MAXIMUM_VOLUME",
            )
        elif baseline is None:
            reason = "NO_BASELINE_AVAILABLE"
        elif baseline > 0:
            change = (count - baseline) / baseline
            if change <= -0.5:
                status, severity, reason = HealthStatus.DEGRADED, Severity.WARNING, "VOLUME_DROP"
            elif change >= 0.5:
                status, severity, reason = HealthStatus.DEGRADED, Severity.WARNING, "VOLUME_SPIKE"
        rows.append(
            MonitoringRecord(
                "ingestion",
                "current-datasets",
                "dataset",
                dataset,
                "data_volume",
                "record_count",
                count,
                "records",
                baseline,
                f"{minimum}-{maximum}",
                status,
                severity,
                reason,
                count,
            )
        )
    return sorted_records(rows)


def quality_trend_records(
    config: MonitoringConfig, runs: list[ComponentRun]
) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    for run in runs:
        if run.component_name != "ingestion":
            continue
        totals = run.metrics.get("totals", {})
        if not isinstance(totals, dict):
            totals = {}
        source = _as_float(totals.get("source_records_discovered")) or 0
        invalid = _as_float(totals.get("invalid_records")) or 0
        warnings = _as_float(totals.get("warning_records")) or 0
        error_rate = (invalid / source) if source else None
        warning_rate = (warnings / source) if source else None
        rows.append(
            _threshold_record(
                run,
                "data_quality",
                "overall",
                "invalid_record_rate",
                error_rate,
                config.quality_error_rate_threshold,
                "ERROR_RATE_THRESHOLD_EXCEEDED",
                "QUALITY_STABLE",
                sample_size=int(source),
            )
        )
        rows.append(
            _threshold_record(
                run,
                "data_quality",
                "overall",
                "warning_record_rate",
                warning_rate,
                config.quality_warning_rate_threshold,
                "WARNING_RATE_THRESHOLD_EXCEEDED",
                "QUALITY_STABLE",
                sample_size=int(source),
            )
        )
    return sorted_records(rows)


def schema_drift_records(project_root: Path, config: MonitoringConfig) -> list[MonitoringRecord]:
    current_root = project_root / "configs/data_contracts"
    baseline_root = (
        project_root / config.baseline_root / "configs/data_contracts"
        if config.baseline_root
        else None
    )
    rows: list[MonitoringRecord] = []
    for current_path in sorted(current_root.glob("*.yaml")):
        dataset = current_path.stem
        current = _read_yaml(current_path)
        baseline = _read_yaml(baseline_root / current_path.name) if baseline_root else {}
        if not baseline:
            rows.append(
                _schema_row(dataset, "__schema__", "baseline", "BASELINE_MISSING", Severity.INFO)
            )
            continue
        rows.extend(_compare_contract(dataset, baseline, current, config))
    return sorted_records(rows)


def distribution_drift_records(
    project_root: Path, config: MonitoringConfig
) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    specs = [
        ("asset_health", "asset_health_scores.csv", "health_score", "health_band"),
        ("outage_prediction", "outage_risk_predictions.csv", "risk_score", "risk_band"),
        ("reliability", "reliability_kpis.csv", "reliability_score", "reliability_band"),
    ]
    for component, filename, numeric_field, categorical_field in specs:
        current_path = _latest_component_csv(project_root, config, component, filename)
        if current_path is None:
            rows.append(_drift_missing(component, numeric_field, "CURRENT_DISTRIBUTION_MISSING"))
            continue
        current_rows = _read_csv(current_path)
        baseline_rows = _baseline_rows(project_root, config, current_path)
        if baseline_rows is None:
            rows.append(_drift_missing(component, numeric_field, "BASELINE_MISSING"))
            continue
        rows.append(
            _numeric_drift_record(component, numeric_field, current_rows, baseline_rows, config)
        )
        rows.append(
            _categorical_drift_record(
                component, categorical_field, current_rows, baseline_rows, config
            )
        )
    return sorted_records(rows)


def model_health_records(
    config: MonitoringConfig, runs: list[ComponentRun]
) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    for run in runs:
        if run.component_name == "forecasting":
            rows.extend(_forecast_records(config, run))
        elif run.component_name == "outage_prediction":
            rows.extend(_outage_records(config, run))
    return sorted_records(rows)


def analytical_health_records(
    config: MonitoringConfig, runs: list[ComponentRun]
) -> list[MonitoringRecord]:
    rows: list[MonitoringRecord] = []
    for run in runs:
        if run.component_name == "asset_health":
            rows.extend(_asset_health_records(config, run))
        elif run.component_name == "reliability":
            rows.extend(_reliability_records(config, run))
    return sorted_records(rows)


def evaluate_alerts(
    monitoring_run_id: str,
    detected_at: datetime,
    records: list[MonitoringRecord],
    config: MonitoringConfig,
) -> list[AlertEvaluation]:
    alerts: list[AlertEvaluation] = []
    seen: set[str] = set()
    for record in sorted_records(records):
        triggered = record.status in {HealthStatus.DEGRADED, HealthStatus.FAILED}
        severity = _mapped_severity(record, config)
        suppressed = False
        suppression_reason = None
        if config.alert_suppression_rules.get("suppress_info_alerts") and severity == Severity.INFO:
            suppressed, suppression_reason = True, "INFO_ALERT_SUPPRESSED"
        if (
            config.alert_suppression_rules.get("suppress_insufficient_sample_alerts")
            and record.sample_size is not None
            and record.sample_size < config.minimum_sample_size
        ):
            suppressed, suppression_reason = True, "INSUFFICIENT_SAMPLE_SUPPRESSED"
        alert_id = _alert_id(monitoring_run_id, record)
        if config.alert_suppression_rules.get("suppress_repeated_alert_for_same_run"):
            if alert_id in seen:
                suppressed, suppression_reason = True, "DUPLICATE_ALERT_SUPPRESSED"
            seen.add(alert_id)
        status = (
            AlertStatus.SUPPRESSED
            if suppressed
            else AlertStatus.TRIGGERED
            if triggered
            else AlertStatus.NOT_TRIGGERED
        )
        alerts.append(
            AlertEvaluation(
                alert_id=alert_id,
                component_name=record.component_name,
                source_run_id=record.source_run_id,
                scope_type=record.scope_type,
                scope_id=record.scope_id,
                metric_name=record.metric_name,
                observed_value=record.metric_value,
                threshold=record.threshold,
                comparison="configured_rule",
                severity=severity,
                alert_status=status,
                suppressed=suppressed,
                suppression_reason=suppression_reason,
                reason_code=record.reason_code,
                message=_alert_message(record, detected_at),
            )
        )
    return sorted(alerts, key=lambda row: row.alert_id)


def sorted_records(records: list[MonitoringRecord]) -> list[MonitoringRecord]:
    return sorted(
        records,
        key=lambda row: (
            row.component_name,
            row.source_run_id,
            row.monitor_type,
            row.scope_type,
            row.scope_id,
            row.metric_name,
        ),
    )


def _pipeline_status(
    project_root: Path, run: ComponentRun
) -> tuple[HealthStatus, Severity, list[str]]:
    reasons: list[str] = []
    status = str(run.run_status).upper()
    if run.malformed:
        return HealthStatus.FAILED, Severity.CRITICAL, ["MALFORMED_JSON"]
    if status in {"NOT_AVAILABLE"}:
        return HealthStatus.NOT_AVAILABLE, Severity.INFO, ["COMPONENT_NOT_AVAILABLE"]
    if "FAILED" in status:
        return HealthStatus.FAILED, Severity.CRITICAL, ["COMPONENT_RUN_FAILED"]
    if "WARNING" in status:
        reasons.append("COMPONENT_RUN_WARNING")
    if run.manifest_path is None and run.component_name != "data_generation":
        reasons.append("MANIFEST_MISSING")
    if run.metrics_path is None and run.component_name != "data_generation":
        reasons.append("METRICS_MISSING")
    checksum_reason = _checksum_reason(project_root, run)
    if checksum_reason:
        reasons.append(checksum_reason)
    if any(reason.endswith("MISSING") or reason == "CHECKSUM_MISMATCH" for reason in reasons):
        return HealthStatus.DEGRADED, Severity.WARNING, reasons
    if reasons:
        return HealthStatus.HEALTHY_WITH_WARNINGS, Severity.INFO, reasons
    return HealthStatus.HEALTHY, Severity.INFO, ["COMPONENT_HEALTHY"]


def _checksum_reason(project_root: Path, run: ComponentRun) -> str | None:
    checksums = run.manifest.get("output_checksums", {})
    files = run.manifest.get("output_files", {})
    if not isinstance(checksums, dict) or not isinstance(files, dict):
        return None
    base = project_root / Path(run.manifest_path or ".").parent
    for name, expected in sorted(checksums.items()):
        filename = files.get(name)
        if not isinstance(filename, str):
            continue
        candidate = _output_candidate(project_root, base, run, filename)
        if not candidate.exists():
            return "OUTPUT_MISSING"
        if sha256_file(candidate) != expected:
            return "CHECKSUM_MISMATCH"
    return None


def _output_candidate(project_root: Path, base: Path, run: ComponentRun, filename: str) -> Path:
    candidate = base / filename
    if candidate.exists():
        return candidate
    model_roots = {
        "forecasting": project_root / "outputs/models/forecasting" / run.run_id,
        "outage_prediction": project_root / "outputs/models/outage_prediction" / run.run_id,
    }
    model_root = model_roots.get(run.component_name)
    if model_root:
        model_candidate = model_root / filename
        if model_candidate.exists():
            return model_candidate
    return candidate


def _threshold_record(
    run: ComponentRun,
    monitor_type: str,
    scope_id: str,
    metric_name: str,
    value: float | None,
    threshold: float,
    fail_reason: str,
    pass_reason: str,
    *,
    sample_size: int | None,
) -> MonitoringRecord:
    if value is None:
        status, severity, reason = HealthStatus.NOT_AVAILABLE, Severity.INFO, "METRIC_UNAVAILABLE"
    elif value > threshold:
        status, severity, reason = HealthStatus.DEGRADED, Severity.WARNING, fail_reason
    else:
        status, severity, reason = HealthStatus.HEALTHY, Severity.INFO, pass_reason
    return MonitoringRecord(
        run.component_name,
        run.run_id,
        "component",
        scope_id,
        monitor_type,
        metric_name,
        value,
        "ratio",
        None,
        threshold,
        status,
        severity,
        reason,
        sample_size,
    )


def _forecast_records(config: MonitoringConfig, run: ComponentRun) -> list[MonitoringRecord]:
    selected = str(run.metrics.get("selected_model", ""))
    metrics = [
        row
        for row in run.metrics.get("metrics", [])
        if isinstance(row, dict)
        and row.get("model_name") == selected
        and row.get("split") == "test"
    ]
    rows: list[MonitoringRecord] = []
    for metric in metrics[:1]:
        rows.append(
            _metric_max(
                run,
                "model_health",
                "mae",
                metric.get("mae"),
                config.forecast_mae_threshold,
                "FORECAST_MAE_HIGH",
            )
        )
        rows.append(
            _metric_max(
                run,
                "model_health",
                "wape",
                metric.get("wape"),
                config.forecast_wape_threshold,
                "FORECAST_WAPE_HIGH",
            )
        )
        rows.append(
            _metric_abs(
                run,
                "model_health",
                "bias",
                metric.get("bias"),
                config.forecast_bias_threshold,
                "FORECAST_BIAS_HIGH",
            )
        )
    if not rows:
        rows.append(
            _unavailable(run, "model_health", "forecast_metrics", "FORECAST_SAMPLE_TOO_SMALL")
        )
    return rows


def _outage_records(config: MonitoringConfig, run: ComponentRun) -> list[MonitoringRecord]:
    selected = str(run.metrics.get("selected_model", ""))
    metrics = [
        row
        for row in run.metrics.get("metrics", [])
        if isinstance(row, dict)
        and row.get("model_name") == selected
        and row.get("split") == "test"
    ]
    rows: list[MonitoringRecord] = []
    for metric in metrics[:1]:
        positives = _as_float(metric.get("positive_count")) or 0
        if positives == 0:
            rows.append(
                _unavailable(
                    run, "model_health", "positive_examples", "OUTAGE_VALIDATION_NO_POSITIVES"
                )
            )
        rows.append(
            _metric_min(
                run,
                "model_health",
                "precision",
                metric.get("precision"),
                config.outage_precision_threshold,
                "OUTAGE_PRECISION_LOW",
            )
        )
        rows.append(
            _metric_min(
                run,
                "model_health",
                "recall",
                metric.get("recall"),
                config.outage_recall_threshold,
                "OUTAGE_RECALL_LOW",
            )
        )
        rows.append(
            _metric_max(
                run,
                "model_health",
                "brier_score",
                metric.get("brier_score"),
                config.outage_brier_threshold,
                "OUTAGE_BRIER_HIGH",
            )
        )
    if not rows:
        rows.append(_unavailable(run, "model_health", "outage_metrics", "OUTAGE_SAMPLE_TOO_SMALL"))
    return rows


def _asset_health_records(config: MonitoringConfig, run: ComponentRun) -> list[MonitoringRecord]:
    scored = _as_float(run.metrics.get("assets_scored")) or 0
    insufficient = _as_float(run.metrics.get("insufficient_data_assets")) or 0
    rate = insufficient / scored if scored else None
    return [
        MonitoringRecord(
            run.component_name,
            run.run_id,
            "component",
            "asset_health",
            "analytical_health",
            "insufficient_data_rate",
            rate,
            "ratio",
            None,
            0.25,
            HealthStatus.DEGRADED if rate is not None and rate > 0.25 else HealthStatus.HEALTHY,
            Severity.WARNING if rate is not None and rate > 0.25 else Severity.INFO,
            "ASSET_HEALTH_INSUFFICIENT_DATA_INCREASE"
            if rate is not None and rate > 0.25
            else "ASSET_HEALTH_DISTRIBUTION_STABLE",
            int(scored),
        )
    ]


def _reliability_records(config: MonitoringConfig, run: ComponentRun) -> list[MonitoringRecord]:
    null_counts = run.metrics.get("null_kpi_counts", {})
    unavailable = sum(null_counts.values()) if isinstance(null_counts, dict) else 0
    coverage = _as_float(run.metrics.get("population_coverage"))
    rows = [
        _metric_min(
            run,
            "analytical_health",
            "population_coverage",
            coverage,
            0.8,
            "POPULATION_DENOMINATOR_SHIFT",
        )
    ]
    rows.append(
        MonitoringRecord(
            run.component_name,
            run.run_id,
            "component",
            "reliability",
            "analytical_health",
            "null_kpi_count",
            unavailable,
            "count",
            None,
            0,
            HealthStatus.DEGRADED if unavailable else HealthStatus.HEALTHY,
            Severity.WARNING if unavailable else Severity.INFO,
            "RELIABILITY_KPI_UNAVAILABLE" if unavailable else "RELIABILITY_STABLE",
            _as_int(run.metrics.get("entities_assessed")),
        )
    )
    return rows


def _metric_max(
    run: ComponentRun, monitor: str, name: str, value: Any, threshold: float, reason: str
) -> MonitoringRecord:
    parsed = _as_float(value)
    bad = parsed is not None and parsed > threshold
    return _metric_record(run, monitor, name, parsed, threshold, bad, reason)


def _metric_min(
    run: ComponentRun, monitor: str, name: str, value: Any, threshold: float, reason: str
) -> MonitoringRecord:
    parsed = _as_float(value)
    bad = parsed is not None and parsed < threshold
    return _metric_record(run, monitor, name, parsed, threshold, bad, reason)


def _metric_abs(
    run: ComponentRun, monitor: str, name: str, value: Any, threshold: float, reason: str
) -> MonitoringRecord:
    parsed = _as_float(value)
    bad = parsed is not None and abs(parsed) > threshold
    return _metric_record(run, monitor, name, parsed, threshold, bad, reason)


def _metric_record(
    run: ComponentRun,
    monitor: str,
    name: str,
    value: float | None,
    threshold: float,
    bad: bool,
    reason: str,
) -> MonitoringRecord:
    if value is None:
        status, severity, code = HealthStatus.NOT_AVAILABLE, Severity.INFO, "METRIC_UNAVAILABLE"
    elif bad:
        status, severity, code = HealthStatus.DEGRADED, Severity.WARNING, reason
    else:
        status, severity, code = (
            HealthStatus.HEALTHY,
            Severity.INFO,
            f"{run.component_name.upper()}_ACCEPTABLE",
        )
    return MonitoringRecord(
        run.component_name,
        run.run_id,
        "component",
        run.component_name,
        monitor,
        name,
        value,
        "metric",
        None,
        threshold,
        status,
        severity,
        code,
        run.output_record_count,
    )


def _unavailable(run: ComponentRun, monitor: str, metric: str, reason: str) -> MonitoringRecord:
    return MonitoringRecord(
        run.component_name,
        run.run_id,
        "component",
        run.component_name,
        monitor,
        metric,
        None,
        "metric",
        None,
        None,
        HealthStatus.NOT_AVAILABLE,
        Severity.INFO,
        reason,
        run.output_record_count,
    )


def _latest_jsonl_timestamp(path: Path) -> tuple[datetime | None, int, bool]:
    if not path.exists():
        return None, 0, False
    latest: datetime | None = None
    count = 0
    missing = False
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            count += 1
            payload = json.loads(line)
            timestamp = _first_timestamp(payload)
            if timestamp is None:
                missing = True
            elif latest is None or timestamp > latest:
                latest = timestamp
    return latest, count, missing


def _latest_raw_timestamp(csv_path: Path, jsonl_path: Path) -> tuple[datetime | None, int, bool]:
    if jsonl_path.exists():
        return _latest_jsonl_timestamp(jsonl_path)
    if not csv_path.exists():
        return None, 0, False
    rows = _read_csv(csv_path)
    timestamps = [_first_timestamp(row) for row in rows]
    valid = [item for item in timestamps if item is not None]
    return (max(valid) if valid else None, len(rows), len(valid) != len(rows))


def _first_timestamp(payload: dict[str, Any]) -> datetime | None:
    for field in TIMESTAMP_FIELDS:
        parsed = parse_timestamp(payload.get(field))
        if parsed is not None:
            return parsed
    return None


def _dataset_count(project_root: Path, dataset: str) -> int:
    path = project_root / "data/interim" / f"{dataset}.jsonl"
    if path.exists():
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    csv_path = project_root / "data/raw" / f"{dataset}.csv"
    jsonl_path = project_root / "data/raw" / f"{dataset}.jsonl"
    if csv_path.exists():
        return len(_read_csv(csv_path))
    if jsonl_path.exists():
        return sum(
            1 for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    return 0


def _baseline_count(project_root: Path, config: MonitoringConfig, dataset: str) -> int | None:
    if not config.baseline_root:
        return None
    return _dataset_count(project_root / config.baseline_root, dataset)


def _datasets() -> tuple[str, ...]:
    return (
        "asset_inventory",
        "maintenance_logs",
        "outage_history",
        "smart_meter_events",
        "substation_events",
        "weather_data",
    )


def _schema_row(
    dataset: str, field: str, change: str, reason: str, severity: Severity
) -> MonitoringRecord:
    status = HealthStatus.HEALTHY if reason == "NO_SCHEMA_DRIFT" else HealthStatus.DEGRADED
    if reason == "BASELINE_MISSING":
        status = HealthStatus.NOT_AVAILABLE
    return MonitoringRecord(
        "ingestion",
        "contracts",
        "dataset",
        dataset,
        "schema_drift",
        field,
        change,
        "schema_change",
        None,
        None,
        status,
        severity,
        reason,
        None,
    )


def _compare_contract(
    dataset: str, baseline: dict[str, Any], current: dict[str, Any], config: MonitoringConfig
) -> list[MonitoringRecord]:
    old_fields = _contract_fields(baseline)
    new_fields = _contract_fields(current)
    rows: list[MonitoringRecord] = []
    for name in sorted(set(old_fields) | set(new_fields)):
        if name not in old_fields:
            required = bool(new_fields[name].get("required"))
            rows.append(
                _schema_row(
                    dataset,
                    name,
                    "field_added",
                    "BREAKING_SCHEMA_DRIFT" if required else "NON_BREAKING_SCHEMA_DRIFT",
                    Severity.WARNING if required else Severity.INFO,
                )
            )
        elif name not in new_fields:
            rows.append(
                _schema_row(dataset, name, "field_removed", "BREAKING_SCHEMA_DRIFT", Severity.HIGH)
            )
        elif old_fields[name] != new_fields[name]:
            rows.append(
                _schema_row(dataset, name, "field_changed", "BREAKING_SCHEMA_DRIFT", Severity.HIGH)
            )
    if baseline.get("schema_version") != current.get("schema_version"):
        rows.append(
            _schema_row(
                dataset,
                "__schema_version__",
                "version_changed",
                "NON_BREAKING_SCHEMA_DRIFT",
                Severity.INFO,
            )
        )
    if not rows:
        rows.append(
            _schema_row(dataset, "__schema__", "no_change", "NO_SCHEMA_DRIFT", Severity.INFO)
        )
    return rows


def _contract_fields(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = contract.get("fields", {})
    if isinstance(fields, list):
        return {str(row.get("name")): row for row in fields if isinstance(row, dict)}
    if isinstance(fields, dict):
        return {str(name): item for name, item in fields.items() if isinstance(item, dict)}
    return {}


def _latest_component_csv(
    project_root: Path, config: MonitoringConfig, component: str, filename: str
) -> Path | None:
    root = project_root / config.source_roots[component]
    candidates = sorted(root.glob(f"*/{filename}")) if root.exists() else []
    return candidates[-1] if candidates else None


def _baseline_rows(
    project_root: Path, config: MonitoringConfig, current_path: Path
) -> list[dict[str, str]] | None:
    if not config.baseline_root:
        return None
    try:
        relative = current_path.relative_to(project_root)
    except ValueError:
        return None
    baseline_path = project_root / config.baseline_root / relative
    return _read_csv(baseline_path) if baseline_path.exists() else None


def _numeric_drift_record(
    component: str,
    field: str,
    current: list[dict[str, str]],
    baseline: list[dict[str, str]],
    config: MonitoringConfig,
) -> MonitoringRecord:
    current_values = [_as_float(row.get(field)) for row in current]
    baseline_values = [_as_float(row.get(field)) for row in baseline]
    current_clean = [value for value in current_values if value is not None]
    baseline_clean = [value for value in baseline_values if value is not None]
    if (
        len(current_clean) < config.minimum_sample_size
        or len(baseline_clean) < config.minimum_sample_size
    ):
        return _drift_missing(component, field, "INSUFFICIENT_SAMPLE_FOR_DRIFT")
    distance = abs(mean(current_clean) - mean(baseline_clean))
    bad = distance > config.distribution_drift_threshold
    return MonitoringRecord(
        component,
        "latest",
        "component",
        component,
        "distribution_drift",
        field,
        round(distance, 6),
        "absolute_mean_shift",
        round(mean(baseline_clean), 6),
        config.distribution_drift_threshold,
        HealthStatus.DEGRADED if bad else HealthStatus.HEALTHY,
        Severity.WARNING if bad else Severity.INFO,
        "NUMERIC_DISTRIBUTION_DRIFT" if bad else "NO_DISTRIBUTION_DRIFT",
        len(current_clean),
    )


def _categorical_drift_record(
    component: str,
    field: str,
    current: list[dict[str, str]],
    baseline: list[dict[str, str]],
    config: MonitoringConfig,
) -> MonitoringRecord:
    if len(current) < config.minimum_sample_size or len(baseline) < config.minimum_sample_size:
        return _drift_missing(component, field, "INSUFFICIENT_SAMPLE_FOR_DRIFT")
    distance = _total_variation(
        [row.get(field, "") for row in current], [row.get(field, "") for row in baseline]
    )
    bad = distance > config.distribution_drift_threshold
    return MonitoringRecord(
        component,
        "latest",
        "component",
        component,
        "distribution_drift",
        field,
        round(distance, 6),
        "total_variation_distance",
        None,
        config.distribution_drift_threshold,
        HealthStatus.DEGRADED if bad else HealthStatus.HEALTHY,
        Severity.WARNING if bad else Severity.INFO,
        "CATEGORICAL_DISTRIBUTION_DRIFT" if bad else "NO_DISTRIBUTION_DRIFT",
        len(current),
    )


def _drift_missing(component: str, field: str, reason: str) -> MonitoringRecord:
    return MonitoringRecord(
        component,
        "latest",
        "component",
        component,
        "distribution_drift",
        field,
        None,
        "drift_score",
        None,
        None,
        HealthStatus.NOT_AVAILABLE,
        Severity.INFO,
        reason,
        None,
    )


def _total_variation(current: list[str], baseline: list[str]) -> float:
    current_counts = Counter(current)
    baseline_counts = Counter(baseline)
    keys = set(current_counts) | set(baseline_counts)
    current_total = len(current) or 1
    baseline_total = len(baseline) or 1
    return 0.5 * sum(
        abs(current_counts[key] / current_total - baseline_counts[key] / baseline_total)
        for key in keys
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    return payload if isinstance(payload, dict) else {}


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    parsed = _as_float(value)
    return int(parsed) if parsed is not None else None


def _mapped_severity(record: MonitoringRecord, config: MonitoringConfig) -> Severity:
    return Severity(config.alert_severity_mapping.get(record.reason_code, record.severity.value))


def _alert_id(monitoring_run_id: str, record: MonitoringRecord) -> str:
    value = "|".join(
        [
            monitoring_run_id,
            record.component_name,
            record.source_run_id,
            record.scope_type,
            record.scope_id,
            record.monitor_type,
            record.metric_name,
            record.reason_code,
        ]
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _alert_message(record: MonitoringRecord, detected_at: datetime) -> str:
    timestamp = detected_at.isoformat().replace("+00:00", "Z")
    return (
        f"{record.reason_code} for {record.component_name} "
        f"{record.scope_type}:{record.scope_id} at {timestamp}."
    )
