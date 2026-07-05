# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.reporting.config import load_reporting_config
from grid_reliability.reporting.pipeline import main, run_reporting_pipeline
from grid_reliability.reporting.tables import stable_key


def test_reporting_config_validation(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_reporting_config(config_path, project_root=tmp_path)
    assert config.run_id == "reporting-ci"

    invalid_component = config_path.read_text(encoding="utf-8").replace(
        "- genai", "- unknown_component"
    )
    invalid_component_path = tmp_path / "invalid-component.yaml"
    invalid_component_path.write_text(invalid_component, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Unsupported reporting component"):
        load_reporting_config(invalid_component_path, project_root=tmp_path)

    invalid_range = config_path.read_text(encoding="utf-8").replace(
        'date_dimension_end: "2026-01-02"', 'date_dimension_end: "2025-12-31"'
    )
    invalid_range_path = tmp_path / "invalid-range.yaml"
    invalid_range_path.write_text(invalid_range, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="before or equal"):
        load_reporting_config(invalid_range_path, project_root=tmp_path)

    unsafe = config_path.read_text(encoding="utf-8").replace(
        "output_root: outputs/reporting", "output_root: ../outside"
    )
    unsafe_path = tmp_path / "unsafe.yaml"
    unsafe_path.write_text(unsafe, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_reporting_config(unsafe_path, project_root=tmp_path)


def test_stable_reporting_keys() -> None:
    assert stable_key("AST", "AST-1") == stable_key("AST", "AST-1")
    assert stable_key("AST", "AST-1") != stable_key("AST", "AST-2")
    assert stable_key("AST", "") == "SK_UNKNOWN"


def test_reporting_pipeline_outputs_and_determinism(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_sources(tmp_path)
    config_path = _write_config(tmp_path)
    result = run_reporting_pipeline(project_root=tmp_path, config_path=config_path)
    assert result.run_id == "reporting-ci"
    assert result.validation.orphan_foreign_key_count == 0
    assert result.row_counts["fact_demand_forecast"] == 1
    assert result.row_counts["fact_asset_health"] == 1
    assert result.row_counts["fact_assistant_response"] == 1

    manifest = json.loads((result.output_root / "reporting_manifest.json").read_text())
    assert "fact_demand_forecast" in manifest["fact_tables"]
    assert "Power BI workspace" in manifest["limitations"][0]
    assert (result.output_root / "relationships.json").exists()
    assert (result.output_root / "kpi_catalogue.csv").exists()
    assert (tmp_path / "dashboard/dax/measures.dax").exists()
    assert (tmp_path / "dashboard/wireframes/01_executive_overview.md").exists()

    first = (result.output_root / "fact_demand_forecast.csv").read_text(encoding="utf-8")
    result2 = run_reporting_pipeline(project_root=tmp_path, config_path=config_path)
    assert (result2.output_root / "fact_demand_forecast.csv").read_text(encoding="utf-8") == first

    monkeypatch.chdir(tmp_path)
    assert main(["--config", str(config_path)]) == 0

    missing = tmp_path / "missing.yaml"
    assert main(["--config", str(missing)]) == 5


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "reporting.yaml"
    path.write_text(
        """
source_roots:
  - data/interim
  - outputs/forecasting
  - outputs/asset_health
  - outputs/outage_prediction
  - outputs/reliability
  - outputs/monitoring
  - outputs/genai
output_root: outputs/reporting
report_root: reports/reporting
run_id: reporting-ci
included_components:
  - forecasting
  - asset_health
  - outage_prediction
  - reliability
  - monitoring
  - genai
reporting_timezone: UTC
date_dimension_start: "2026-01-01"
date_dimension_end: "2026-01-02"
fact_grains:
  - forecast_entity_timestamp_model
  - asset_assessment
  - outage_entity_timestamp_model
  - reliability_entity_period
  - monitoring_check
  - monitoring_alert
  - assistant_response
  - maintenance_priority
dimension_inclusion:
  - date
  - time
  - grid_region
  - substation
  - feeder
  - asset
  - model
  - component_run
  - alert_reason
  - metric
default_currency: GBP
schema_version: "10.0.0"
minimum_data_completeness: 0.0
include_assistant_outputs: true
include_monitoring_outputs: true
dashboard_pages:
  - 01_executive_overview
export_format: csv
""",
        encoding="utf-8",
    )
    return path


def _write_sources(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "data/interim/asset_inventory.jsonl",
        [
            {
                "asset_id": "AST-SUB-1",
                "asset_name": "Synthetic substation",
                "asset_type": "primary_substation",
                "grid_region": "GRID-NORTH",
                "substation_id": "SUB-1",
                "feeder_id": None,
                "manufacturer": "Synthetic",
                "model": "SYN-1",
                "commissioned_date": "2020-01-01",
                "expected_life_years": 30,
                "criticality_tier": "tier_1",
                "operational_status": "active",
                "rated_capacity": 32,
            },
            {
                "asset_id": "AST-FDR-1",
                "asset_name": "Synthetic feeder",
                "asset_type": "feeder",
                "grid_region": "GRID-NORTH",
                "substation_id": "SUB-1",
                "feeder_id": "FDR-1",
                "manufacturer": "Synthetic",
                "model": "SYN-F",
                "commissioned_date": "2021-01-01",
                "expected_life_years": 20,
                "criticality_tier": "tier_2",
                "operational_status": "active",
                "rated_capacity": 10,
            },
        ],
    )
    _write_csv(
        tmp_path / "outputs/forecasting/forecast-ci/load_forecast.csv",
        "forecast_run_id,entity_type,entity_id,grid_region,forecast_origin,forecast_timestamp,forecast_horizon_intervals,target_name,target_unit,model_name,predicted_value,prediction_lower,prediction_upper,actual_value,data_split\n"
        "forecast-ci,grid_region,GRID-NORTH,GRID-NORTH,2026-01-01T00:00:00Z,2026-01-01T01:00:00Z,1,active_energy_kwh,kWh,persistence,10,9,11,10,validation\n",
    )
    _write_json(tmp_path / "outputs/forecasting/forecast-ci/metrics.json", {"mae": 1})
    _write_json(
        tmp_path / "outputs/forecasting/forecast-ci/forecast_manifest.json",
        {"forecast_run_id": "forecast-ci"},
    )
    _write_csv(
        tmp_path / "outputs/asset_health/asset-health-ci/asset_health_scores.csv",
        "asset_health_run_id,assessment_timestamp,asset_id,asset_type,asset_name,grid_region,substation_id,feeder_id,criticality_tier,operational_status,data_completeness_ratio,health_score,health_band,maintenance_priority,age_component_score,inspection_component_score,maintenance_component_score,telemetry_stress_component_score,alarm_component_score,outage_component_score,primary_reason_code,reason_codes\n"
        "asset-health-ci,2026-01-01T00:00:00Z,AST-FDR-1,feeder,Synthetic feeder,GRID-NORTH,SUB-1,FDR-1,tier_2,active,1.0,80,HEALTHY,P2_HIGH,90,90,70,80,100,70,LOW_OPERATIONAL_STRESS,LOW_OPERATIONAL_STRESS\n",
    )
    _write_csv(
        tmp_path / "outputs/asset_health/asset-health-ci/asset_health_components.csv",
        "asset_health_run_id,asset_id,age_component_score,inspection_component_score,maintenance_component_score,telemetry_stress_component_score,alarm_component_score,outage_component_score\n"
        "asset-health-ci,AST-FDR-1,90,90,70,80,100,70\n",
    )
    _write_csv(
        tmp_path / "outputs/asset_health/asset-health-ci/maintenance_priorities.csv",
        "asset_health_run_id,asset_id,priority,health_band,criticality_tier,primary_reason,supporting_reasons,review_recommended\n"
        "asset-health-ci,AST-FDR-1,P2_HIGH,HEALTHY,tier_2,LOW_OPERATIONAL_STRESS,LOW_OPERATIONAL_STRESS,True\n",
    )
    _write_json(
        tmp_path / "outputs/asset_health/asset-health-ci/asset_health_manifest.json",
        {"run_id": "asset-health-ci", "assessment_timestamp": "2026-01-01T00:00:00Z"},
    )
    _write_csv(
        tmp_path / "outputs/outage_prediction/outage-prediction-ci/outage_risk_predictions.csv",
        "outage_prediction_run_id,observation_timestamp,prediction_window_start,prediction_window_end,entity_type,entity_id,grid_region,substation_id,feeder_id,model_name,risk_score,risk_band,predicted_outage_flag,classification_threshold,actual_outage_flag,data_split,data_completeness_ratio,primary_reason_code\n"
        "outage-prediction-ci,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,2026-01-01T01:00:00Z,feeder,FDR-1,GRID-NORTH,SUB-1,FDR-1,prevalence,0.2,LOW,False,0.5,0,test,1.0,LOW_RECENT_STRESS\n",
    )
    _write_json(
        tmp_path / "outputs/outage_prediction/outage-prediction-ci/outage_prediction_manifest.json",
        {"run_id": "outage-prediction-ci"},
    )
    _write_csv(
        tmp_path / "outputs/reliability/reliability-ci/reliability_kpis.csv",
        "reliability_run_id,period_start,period_end,entity_type,entity_id,grid_region,substation_id,feeder_id,population_denominator,outage_count,planned_outage_count,unplanned_outage_count,customer_interruptions,customer_interruption_minutes,saifi,saidi_minutes,caidi_minutes,asai,asui,reliability_score,reliability_band,data_completeness_ratio,primary_reason_code\n"
        "reliability-ci,2026-01-01T00:00:00Z,2026-01-02T00:00:00Z,feeder,FDR-1,GRID-NORTH,SUB-1,FDR-1,10,1,0,1,2,60,0.2,6,30,0.99,0.01,80,STABLE,1.0,LOW_SERVICE_AVAILABILITY\n",
    )
    _write_csv(
        tmp_path / "outputs/reliability/reliability-ci/reliability_reasons.csv",
        "reliability_run_id,entity_type,entity_id,period_start,reason_code,description,reason_rank\n"
        "reliability-ci,feeder,FDR-1,2026-01-01T00:00:00Z,LOW_SERVICE_AVAILABILITY,Availability review,1\n",
    )
    _write_json(
        tmp_path / "outputs/reliability/reliability-ci/reliability_manifest.json",
        {"run_id": "reliability-ci", "assessment_start": "2026-01-01T00:00:00Z"},
    )
    _write_csv(
        tmp_path / "outputs/monitoring/monitoring_summary.csv",
        "monitoring_run_id,component_name,source_run_id,scope_type,scope_id,monitor_type,metric_name,metric_value,metric_unit,baseline_value,threshold,status,severity,reason_code,sample_size\n"
        "monitoring-ci,forecasting,forecast-ci,run,forecast-ci,pipeline_health,run_status,PASSED,status,,complete,HEALTHY,INFO,COMPONENT_HEALTHY,1\n",
    )
    _write_csv(
        tmp_path / "outputs/monitoring/alerts.csv",
        "alert_id,monitoring_run_id,component_name,scope_type,scope_id,metric_name,observed_value,threshold,severity,alert_status,suppressed,suppression_reason,reason_code,source_run_id\n"
        "ALT-1,monitoring-ci,forecasting,run,forecast-ci,run_status,1,1,INFO,SUPPRESSED,True,INFO_ALERT_SUPPRESSED,COMPONENT_HEALTHY,forecast-ci\n",
    )
    _write_json(
        tmp_path / "outputs/monitoring/monitoring-ci/monitoring_manifest.json",
        {"monitoring_run_id": "monitoring-ci", "monitoring_timestamp": "2026-01-01T00:00:00Z"},
    )
    _write_jsonl(
        tmp_path / "outputs/genai/grid_operations_responses.jsonl",
        [
            {
                "assistant_run_id": "assistant-ci",
                "query_id": "Q1",
                "query_category": "forecast_summary",
                "response_status": "GROUNDED",
                "retrieval_score": 1.0,
                "grounding_coverage": 1.0,
                "citation_coverage": 1.0,
                "response_confidence": 0.9,
                "safety_reason_code": None,
                "citation_ids": ["SRC-001"],
            }
        ],
    )
    _write_json(
        tmp_path / "outputs/genai/assistant-ci/assistant_manifest.json",
        {"assistant_run_id": "assistant-ci"},
    )


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
