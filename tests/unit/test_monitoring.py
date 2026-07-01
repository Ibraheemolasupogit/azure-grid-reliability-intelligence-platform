from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.monitoring.checks import (
    data_freshness_records,
    data_volume_records,
    distribution_drift_records,
    evaluate_alerts,
    pipeline_health_records,
    quality_trend_records,
    schema_drift_records,
)
from grid_reliability.monitoring.config import load_monitoring_config
from grid_reliability.monitoring.discovery import discover_component_runs
from grid_reliability.monitoring.models import AlertStatus, HealthStatus
from grid_reliability.monitoring.pipeline import main, run_monitoring


def test_monitoring_config_validation(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_monitoring_config(config_path, project_root=tmp_path)
    assert config.run_id_strategy == "deterministic"
    assert "ingestion" in config.component_inclusion

    bad_component = config_path.read_text(encoding="utf-8").replace(
        "- ingestion", "- missing_component"
    )
    bad_path = tmp_path / "bad-component.yaml"
    bad_path.write_text(bad_component, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Unknown monitoring component"):
        load_monitoring_config(bad_path, project_root=tmp_path)

    bad_threshold = config_path.read_text(encoding="utf-8").replace(
        "quality_error_rate_threshold: 0.01", "quality_error_rate_threshold: 2"
    )
    bad_threshold_path = tmp_path / "bad-threshold.yaml"
    bad_threshold_path.write_text(bad_threshold, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        load_monitoring_config(bad_threshold_path, project_root=tmp_path)

    bad_severity = config_path.read_text(encoding="utf-8").replace("HIGH", "SEVERE")
    bad_severity_path = tmp_path / "bad-severity.yaml"
    bad_severity_path.write_text(bad_severity, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid alert severity"):
        load_monitoring_config(bad_severity_path, project_root=tmp_path)

    unsafe = config_path.read_text(encoding="utf-8").replace(
        "output_root: outputs/monitoring", "output_root: ../outside"
    )
    unsafe_path = tmp_path / "unsafe.yaml"
    unsafe_path.write_text(unsafe, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_monitoring_config(unsafe_path, project_root=tmp_path)


def test_discovery_pipeline_health_and_alerts(tmp_path: Path) -> None:
    config = load_monitoring_config(_write_config(tmp_path), project_root=tmp_path)
    _write_base_config(tmp_path)
    _write_ingestion_run(tmp_path, status="PASSED_WITH_WARNINGS", warnings=2)
    _write_forecast_run(tmp_path)
    runs = discover_component_runs(tmp_path, config)
    assert [run.component_name for run in runs] == ["forecasting", "ingestion"]
    assert runs[0].run_id == "forecast-ci"
    assert runs[1].run_status == "PASSED_WITH_WARNINGS"

    records = pipeline_health_records(tmp_path, config, runs)
    statuses = {row.component_name: row.status for row in records}
    assert statuses["forecasting"] == HealthStatus.HEALTHY
    assert statuses["ingestion"] == HealthStatus.HEALTHY_WITH_WARNINGS

    alerts = evaluate_alerts(
        "monitoring-ci",
        config.monitoring_timestamp,
        records,
        config,
    )
    assert {alert.alert_status for alert in alerts} == {AlertStatus.SUPPRESSED}
    assert all(alert.suppression_reason == "INFO_ALERT_SUPPRESSED" for alert in alerts)


def test_data_freshness_volume_quality_schema_and_drift(tmp_path: Path) -> None:
    config = load_monitoring_config(_write_config(tmp_path), project_root=tmp_path)
    _write_interim_dataset(
        tmp_path,
        "smart_meter_events",
        [{"reading_timestamp": "2026-01-01T23:00:00Z", "active_energy_kwh": 1.0}],
    )
    _write_interim_dataset(
        tmp_path,
        "substation_events",
        [{"event_timestamp": "2025-12-30T00:00:00Z", "load_mw": 2.0}],
    )
    _write_interim_dataset(tmp_path, "weather_data", [{"temperature_c": 20.0}])
    for dataset in ("asset_inventory", "maintenance_logs", "outage_history"):
        _write_interim_dataset(tmp_path, dataset, [])

    freshness = data_freshness_records(tmp_path, config)
    by_dataset = {row.scope_id: row for row in freshness}
    assert by_dataset["smart_meter_events"].reason_code == "DATA_FRESH"
    assert by_dataset["substation_events"].reason_code == "DATA_VERY_STALE"
    assert by_dataset["weather_data"].reason_code == "EVENT_TIMESTAMP_MISSING"
    assert by_dataset["asset_inventory"].reason_code == "DATASET_EMPTY"

    volume = {row.scope_id: row for row in data_volume_records(tmp_path, config)}
    assert volume["smart_meter_events"].status == HealthStatus.HEALTHY
    assert volume["substation_events"].status == HealthStatus.DEGRADED

    _write_ingestion_run(tmp_path, status="PASSED", invalid=1, warnings=3, discovered=10)
    quality = quality_trend_records(config, discover_component_runs(tmp_path, config))
    assert {row.reason_code for row in quality} == {
        "ERROR_RATE_THRESHOLD_EXCEEDED",
        "WARNING_RATE_THRESHOLD_EXCEEDED",
    }

    _write_contract_pair(tmp_path)
    schema = schema_drift_records(tmp_path, config)
    assert any(row.reason_code == "BREAKING_SCHEMA_DRIFT" for row in schema)
    assert any(row.reason_code == "NON_BREAKING_SCHEMA_DRIFT" for row in schema)

    _write_distribution_pair(tmp_path)
    drift = distribution_drift_records(tmp_path, config)
    assert any(row.reason_code == "NUMERIC_DISTRIBUTION_DRIFT" for row in drift)
    assert any(row.reason_code == "CATEGORICAL_DISTRIBUTION_DRIFT" for row in drift)


def test_run_monitoring_persists_outputs_and_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_base_config(tmp_path)
    config_path = _write_config(tmp_path)
    config = load_monitoring_config(config_path, project_root=tmp_path)
    _write_ingestion_run(tmp_path, status="PASSED", discovered=3)
    _write_forecast_run(tmp_path)
    _write_interim_dataset(
        tmp_path,
        "smart_meter_events",
        [{"reading_timestamp": "2026-01-01T23:00:00Z"}],
    )
    for dataset in (
        "asset_inventory",
        "maintenance_logs",
        "outage_history",
        "substation_events",
        "weather_data",
    ):
        _write_interim_dataset(tmp_path, dataset, [{"event_timestamp": "2026-01-01T23:00:00Z"}])

    result = run_monitoring(config, project_root=tmp_path, config_path=config_path)
    assert result.run_id == "monitoring-ci"
    assert (tmp_path / "outputs/monitoring/monitoring_summary.csv").exists()
    assert (tmp_path / "outputs/monitoring/alerts.csv").exists()
    assert (tmp_path / "outputs/monitoring/monitoring-ci/monitoring_manifest.json").exists()
    assert (tmp_path / "reports/monitoring/monitoring-ci/alert_summary.md").exists()

    first = (tmp_path / "outputs/monitoring/monitoring-ci/metrics.json").read_text(encoding="utf-8")
    second_result = run_monitoring(config, project_root=tmp_path, config_path=config_path)
    second = (tmp_path / "outputs/monitoring/monitoring-ci/metrics.json").read_text(
        encoding="utf-8"
    )
    assert second_result.run_id == result.run_id
    assert first == second

    monkeypatch.chdir(tmp_path)
    assert main(["--config", str(config_path), "--run-id", "cli-run"]) == 0
    assert (tmp_path / "outputs/monitoring/cli-run/metrics.json").exists()
    with pytest.raises(SystemExit) as exc:
        main(["--config", str(tmp_path / "missing.yaml")])
    assert exc.value.code == 2


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "monitoring.yaml"
    path.write_text(
        """
profile: ci
source_roots:
  ingestion: reports/ingestion
  forecasting: outputs/forecasting
  data_generation: data/raw
  asset_health: outputs/asset_health
  outage_prediction: outputs/outage_prediction
  reliability: outputs/reliability
output_root: outputs/monitoring
report_root: reports/monitoring
baseline_root: baseline
component_inclusion:
  - ingestion
  - forecasting
required_components:
  - ingestion
freshness_thresholds:
  smart_meter_events: 120
  substation_events: 120
  weather_data: 120
  asset_inventory: 120
  maintenance_logs: 120
  outage_history: 120
minimum_expected_records:
  smart_meter_events: 1
  substation_events: 2
  weather_data: 1
  asset_inventory: 0
  maintenance_logs: 0
  outage_history: 0
maximum_expected_records:
  smart_meter_events: 3
  substation_events: 3
  weather_data: 3
  asset_inventory: 3
  maintenance_logs: 3
  outage_history: 3
quality_error_rate_threshold: 0.01
quality_warning_rate_threshold: 0.1
schema_drift_policy: warn
distribution_drift_method: standardised_mean_difference
distribution_drift_threshold: 0.2
forecast_mae_threshold: 10.0
forecast_wape_threshold: 0.5
forecast_bias_threshold: 10.0
outage_precision_threshold: 0.2
outage_recall_threshold: 0.2
outage_brier_threshold: 0.4
asset_health_distribution_threshold: 5.0
reliability_distribution_threshold: 5.0
alert_severity_mapping:
  DATA_VERY_STALE: HIGH
alert_suppression_rules:
  suppress_info_alerts: true
  suppress_repeated_alert_for_same_run: true
  suppress_insufficient_sample_alerts: true
minimum_sample_size: 2
comparison_window: 1
schema_version: 8.0.0
run_id_strategy: deterministic
monitoring_timestamp: "2026-01-02T00:00:00Z"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_base_config(tmp_path: Path) -> None:
    base = tmp_path / "configs/base.yaml"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(
        """
project:
  name: azure-grid-reliability-intelligence-platform
runtime:
  environment: local
  timezone: UTC
  random_seed: 42
paths:
  data_root: data
  output_root: outputs
  raw_data: data/raw
  interim_data: data/interim
  processed_data: data/processed
  reports: reports
logging:
  level: INFO
  json: false
pipeline_components:
  planned: []
azure_service_mapping: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_ingestion_run(
    tmp_path: Path,
    *,
    status: str,
    invalid: int = 0,
    warnings: int = 0,
    discovered: int = 10,
) -> None:
    root = tmp_path / "reports/ingestion/local-ci"
    root.mkdir(parents=True, exist_ok=True)
    metrics = {
        "ingestion_run_id": "local-ci",
        "run_status": status,
        "totals": {
            "source_records_discovered": discovered,
            "valid_records": discovered - invalid,
            "invalid_records": invalid,
            "warning_records": warnings,
            "error_rate": invalid / discovered if discovered else 0,
        },
    }
    manifest = {
        "ingestion_run_id": "local-ci",
        "run_status": status,
        "output_files": {},
        "output_checksums": {},
        "synthetic_data_declaration": "Synthetic only.",
    }
    _write_json(root / "metrics.json", metrics)
    _write_json(root / "ingestion_manifest.json", manifest)


def _write_forecast_run(tmp_path: Path) -> None:
    root = tmp_path / "outputs/forecasting/forecast-ci"
    root.mkdir(parents=True, exist_ok=True)
    forecast = root / "load_forecast.csv"
    forecast.write_text("forecast_run_id,predicted_value\nforecast-ci,1\n", encoding="utf-8")
    metrics = {
        "forecast_run_id": "forecast-ci",
        "selected_model": "persistence",
        "metrics": [
            {
                "model_name": "persistence",
                "split": "test",
                "mae": 1.0,
                "wape": 0.1,
                "bias": 0.1,
            }
        ],
    }
    manifest = {
        "forecast_run_id": "forecast-ci",
        "output_files": {"forecast_csv": "load_forecast.csv"},
        "output_checksums": {"forecast_csv": _sha(forecast)},
        "synthetic_data_declaration": "Synthetic only.",
    }
    _write_json(root / "metrics.json", metrics)
    _write_json(root / "forecast_manifest.json", manifest)


def _write_interim_dataset(tmp_path: Path, dataset: str, rows: list[dict[str, object]]) -> None:
    root = tmp_path / "data/interim"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{dataset}.jsonl"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_contract_pair(tmp_path: Path) -> None:
    current = tmp_path / "configs/data_contracts"
    baseline = tmp_path / "baseline/configs/data_contracts"
    current.mkdir(parents=True, exist_ok=True)
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / "smart_meter_events.yaml").write_text(
        """
schema_version: 1
fields:
  meter_id:
    type: string
    required: true
  active_energy_kwh:
    type: number
    required: false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (current / "smart_meter_events.yaml").write_text(
        """
schema_version: 2
fields:
  meter_id:
    type: string
    required: true
  active_energy_kwh:
    type: string
    required: false
  new_optional:
    type: string
    required: false
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_distribution_pair(tmp_path: Path) -> None:
    current = tmp_path / "outputs/asset_health/asset-health-ci"
    baseline = tmp_path / "baseline/outputs/asset_health/asset-health-ci"
    current.mkdir(parents=True, exist_ok=True)
    baseline.mkdir(parents=True, exist_ok=True)
    _write_csv(
        current / "asset_health_scores.csv",
        ["health_score", "health_band"],
        [
            {"health_score": "90", "health_band": "HEALTHY"},
            {"health_score": "95", "health_band": "HEALTHY"},
        ],
    )
    _write_csv(
        baseline / "asset_health_scores.csv",
        ["health_score", "health_band"],
        [
            {"health_score": "10", "health_band": "POOR"},
            {"health_score": "15", "health_band": "POOR"},
        ],
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
