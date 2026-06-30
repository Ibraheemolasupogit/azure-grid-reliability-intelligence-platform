from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from grid_reliability.asset_health.config import load_asset_health_config
from grid_reliability.asset_health.data import eligible_assets, load_inputs
from grid_reliability.asset_health.features import derive_features
from grid_reliability.asset_health.models import AssetFeatures, AssetRecord, HealthBand
from grid_reliability.asset_health.pipeline import main, run_asset_health
from grid_reliability.asset_health.scoring import assess_asset, classify_health, component_scores
from grid_reliability.common import ConfigurationError
from grid_reliability.data_generation.config import load_generation_config
from grid_reliability.data_generation.pipeline import generate_datasets
from grid_reliability.ingestion.config import load_ingestion_config
from grid_reliability.ingestion.pipeline import run_ingestion

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_asset_health_config_validates_weights_thresholds_and_paths(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    good = _write_asset_health_config(workspace)
    config = load_asset_health_config(good, project_root=workspace)
    assert config.run_id_strategy == "deterministic"

    bad_weight = _write_asset_health_config(workspace, component_weights={**_weights(), "age": 1.2})
    with pytest.raises(ConfigurationError, match="component weight"):
        load_asset_health_config(bad_weight, project_root=workspace)

    bad_sum = _write_asset_health_config(workspace, component_weights={**_weights(), "age": 0.2})
    with pytest.raises(ConfigurationError, match=r"sum to 1\.0"):
        load_asset_health_config(bad_sum, project_root=workspace)

    bad_thresholds = _write_asset_health_config(
        workspace,
        health_band_thresholds={"critical_max": 60, "degraded_max": 40, "watch_max": 75},
    )
    with pytest.raises(ConfigurationError, match="ordered"):
        load_asset_health_config(bad_thresholds, project_root=workspace)

    bad_path = _write_asset_health_config(workspace, interim_root="../raw")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_asset_health_config(bad_path, project_root=workspace)

    bad_asset_type = _write_asset_health_config(workspace, included_asset_types=["unknown"])
    with pytest.raises(ConfigurationError, match="Unsupported asset"):
        load_asset_health_config(bad_asset_type, project_root=workspace)


def test_loading_filters_population_and_excludes_smart_meters(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_asset_health_config(_write_asset_health_config(workspace), project_root=workspace)
    datasets, checksums, missing = load_inputs(workspace / config.interim_root, config)
    assets, excluded = eligible_assets(datasets["asset_inventory"], config)

    assert checksums["asset_inventory"]
    assert missing == []
    assert len(assets) == 14
    assert excluded == 6
    assert all(asset.asset_type != "smart_meter" for asset in assets)


def test_features_link_direct_and_contextual_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_asset_health_config(_write_asset_health_config(workspace), project_root=workspace)
    datasets, _, _ = load_inputs(workspace / config.interim_root, config)
    assets, _ = eligible_assets(datasets["asset_inventory"], config)
    asset = next(item for item in assets if item.asset_type == "feeder")
    features = derive_features(asset, datasets, config)

    assert features.asset_age_years >= 0
    assert features.telemetry_observation_count > 0
    assert features.data_completeness_ratio >= 0.4
    assert features.direct_outage_count + features.contextual_outage_count >= 0


def test_component_scores_are_bounded_and_classification_boundaries(tmp_path: Path) -> None:
    config = load_asset_health_config(
        _write_asset_health_config(_workspace(tmp_path)),
        project_root=tmp_path,
    )
    features = _features(age_ratio=1.2, overdue_days=30, maintenance_count=1)
    components = component_scores(features, config)
    assert 0 <= components.age_component_score <= 100
    assert 0 <= components.inspection_component_score <= 100
    assert classify_health(34.9, False, config) == HealthBand.CRITICAL
    assert classify_health(35.1, False, config) == HealthBand.DEGRADED
    assert classify_health(80, True, config) == HealthBand.INSUFFICIENT_DATA


def test_reason_codes_and_priority_rules_are_deterministic(tmp_path: Path) -> None:
    config = load_asset_health_config(
        _write_asset_health_config(_workspace(tmp_path)),
        project_root=tmp_path,
    )
    asset = _asset(criticality_tier="tier_1")
    features = _features(
        age_ratio=1.1,
        overdue_days=20,
        maintenance_count=2,
        deferred=1,
        direct_unplanned=1,
    )
    result = assess_asset(asset, features, config)
    assert result.reason_codes[0] == "AGE_BEYOND_EXPECTED_LIFE"
    assert "INSPECTION_OVERDUE" in result.reason_codes
    assert result.maintenance_priority.value in {"P1_IMMEDIATE_REVIEW", "P2_HIGH"}


def test_pipeline_writes_scores_metrics_manifest_and_reports(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_asset_health_config(_write_asset_health_config(workspace), project_root=workspace)
    result = run_asset_health(config, project_root=workspace)

    assert len(result.results) == 14
    assert result.score_path.exists()
    assert result.metrics_path.exists()
    assert result.manifest_path.exists()
    assert result.report_paths["asset_health_report"].exists()
    assert "asset_health_run_id,assessment_timestamp,asset_id" in result.score_path.read_text(
        encoding="utf-8"
    )
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["eligible_assets"] == 14
    assert metrics["excluded_assets"] == 6


def test_cli_success_filter_and_missing_input_failure(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config_path = _write_asset_health_config(workspace)
    assert main(["--config", str(config_path), "--run-id", "cli-health"]) == 0
    assert (
        main(["--config", str(config_path), "--asset-type", "feeder", "--run-id", "feeders"]) == 0
    )

    assert main(["--config", str(config_path), "--interim-root", "data/not-present"]) == 3


def _workspace(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs").mkdir(exist_ok=True)
    shutil.copy(PROJECT_ROOT / "configs/base.yaml", tmp_path / "configs/base.yaml")
    shutil.copytree(
        PROJECT_ROOT / "configs/data_contracts",
        tmp_path / "configs/data_contracts",
        dirs_exist_ok=True,
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


def _generate_and_ingest(workspace: Path) -> None:
    generation_config = load_generation_config(
        PROJECT_ROOT / "configs/synthetic_data_ci.yaml",
        project_root=PROJECT_ROOT,
    )
    generate_datasets(
        replace(generation_config, output_root=Path("data/raw")),
        project_root=workspace,
    )
    ingestion_config_path = _write_ingestion_config(workspace)
    ingestion_config = load_ingestion_config(ingestion_config_path, project_root=workspace)
    run_ingestion(ingestion_config, project_root=workspace)


def _write_ingestion_config(workspace: Path) -> Path:
    path = workspace / "configs/ingestion_test.yaml"
    path.write_text(
        "\n".join(
            [
                "profile: test",
                "source_root: data/raw",
                "interim_root: data/interim",
                "quarantine_root: data/quarantine",
                "report_root: reports/ingestion",
                "contract_root: configs/data_contracts",
                "manifest_filename: _manifest.json",
                "verify_manifest_checksums: true",
                "require_manifest: true",
                "fail_on_missing_dataset: true",
                "fail_on_contract_error: true",
                "maximum_error_rate: 0.0",
                "batch_size: 25",
                "timezone: UTC",
                "normalised_timestamp_format: iso8601_utc",
                "run_id_strategy: deterministic",
                "write_format: jsonl",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_asset_health_config(workspace: Path, **overrides: object) -> Path:
    values = {
        "profile": "ci",
        "interim_root": "data/interim",
        "output_root": "outputs/asset_health",
        "report_root": "reports/asset_health",
        "assessment_timestamp": "2026-01-01T06:00:00Z",
        "included_asset_types": [
            "primary_substation",
            "secondary_substation",
            "transformer",
            "circuit_breaker",
            "feeder",
            "switchgear",
            "protection_relay",
        ],
        "minimum_data_completeness": 0.4,
        "lookback_days_maintenance": 365,
        "lookback_days_telemetry": 365,
        "lookback_days_outages": 365,
        "health_score_direction": "higher_is_better",
        "health_band_thresholds": {"critical_max": 35, "degraded_max": 55, "watch_max": 75},
        "priority_thresholds": {"p1_max": 35, "p2_max": 55, "p3_max": 75},
        "component_weights": _weights(),
        "missing_data_policy": "neutral",
        "criticality_mapping": {"tier_1": 3, "tier_2": 2, "tier_3": 1},
        "status_mapping": {"active": 0, "standby": 1, "maintenance": 2, "retired": 3},
        "schema_version": "5.0.0",
        "run_id_strategy": "deterministic",
        "max_reason_codes": 5,
    }
    values.update(overrides)
    path = workspace / "configs/asset_health_test.yaml"
    path.write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in values.items()),
        encoding="utf-8",
    )
    return path


def _weights() -> dict[str, float]:
    return {
        "age": 0.18,
        "inspection": 0.17,
        "maintenance": 0.20,
        "telemetry_stress": 0.20,
        "alarm": 0.10,
        "outage": 0.15,
    }


def _asset(criticality_tier: str = "tier_2") -> AssetRecord:
    return AssetRecord(
        asset_id="AST-X",
        asset_type="transformer",
        asset_name="Synthetic transformer",
        grid_region="GRID-X",
        substation_id="SUB-X",
        feeder_id="FDR-X",
        commissioned_date=date(2000, 1, 1),
        expected_life_years=20,
        criticality_tier=criticality_tier,
        operational_status="active",
        last_inspection_date=date(2025, 1, 1),
        next_inspection_due=date(2025, 12, 1),
        rated_capacity=1.0,
        capacity_unit="MVA",
        schema_version="2.0.0",
    )


def _features(
    *,
    age_ratio: float,
    overdue_days: int = 0,
    maintenance_count: int = 0,
    deferred: int = 0,
    direct_unplanned: int = 0,
) -> AssetFeatures:
    return AssetFeatures(
        asset_age_years=age_ratio * 20,
        expected_life_years=20,
        age_to_expected_life_ratio=age_ratio,
        remaining_expected_life_years=20 - age_ratio * 20,
        beyond_expected_life_flag=age_ratio > 1,
        days_since_last_inspection=200,
        days_until_next_inspection=-overdue_days,
        inspection_overdue_days=overdue_days,
        inspection_overdue_flag=overdue_days > 0,
        maintenance_count=maintenance_count,
        corrective_maintenance_count=maintenance_count,
        deferred_maintenance_count=deferred,
        direct_unplanned_outage_count=direct_unplanned,
        direct_outage_count=direct_unplanned,
        telemetry_observation_count=1,
        mean_utilisation_pct=80,
        maximum_utilisation_pct=90,
        expected_evidence_sources=5,
        available_evidence_sources=5,
        data_completeness_ratio=1.0,
        insufficient_data_flag=False,
    )
