from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from grid_reliability.common import ConfigurationError
from grid_reliability.data_generation.config import load_generation_config
from grid_reliability.data_generation.pipeline import generate_datasets
from grid_reliability.ingestion.config import load_ingestion_config
from grid_reliability.ingestion.pipeline import run_ingestion
from grid_reliability.outage_prediction.config import load_outage_prediction_config
from grid_reliability.outage_prediction.data import load_inputs
from grid_reliability.outage_prediction.explainability import classify_risk, reason_codes
from grid_reliability.outage_prediction.features import build_feature_rows
from grid_reliability.outage_prediction.labels import apply_labels
from grid_reliability.outage_prediction.metrics import evaluate_predictions
from grid_reliability.outage_prediction.models import (
    Entity,
    EntityType,
    FeatureRow,
    LabelledRow,
    PanelRow,
    PredictionResult,
    RiskBand,
)
from grid_reliability.outage_prediction.panel import build_panel
from grid_reliability.outage_prediction.pipeline import main, run_outage_prediction
from grid_reliability.outage_prediction.splitting import chronological_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_outage_prediction_config_validation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    good = _write_prediction_config(workspace)
    config = load_outage_prediction_config(good, project_root=workspace)
    assert config.entity_type.value == "feeder"

    with pytest.raises(ConfigurationError, match="entity_type"):
        load_outage_prediction_config(
            _write_prediction_config(workspace, entity_type="meter"),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="prediction_horizon_intervals"):
        load_outage_prediction_config(
            _write_prediction_config(workspace, prediction_horizon_intervals=0),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="Unsupported candidate"):
        load_outage_prediction_config(
            _write_prediction_config(workspace, candidate_models=["prevalence", "xgboost"]),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_outage_prediction_config(
            _write_prediction_config(workspace, interim_root="../raw"),
            project_root=workspace,
        )


def test_panel_labels_boundaries_and_planned_outage_exclusion(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_outage_prediction_config(
        _write_prediction_config(workspace), project_root=workspace
    )
    datasets, _ = load_inputs(workspace / config.interim_root, config)
    panel = build_panel(datasets, config)
    labelled = apply_labels(panel, datasets["outage_history"], config)

    assert len(panel) == 10
    assert sum(row.label for row in labelled) == 2
    south_positive = next(
        row
        for row in labelled
        if row.panel.entity.entity_id == "FDR-SOUTH-001-01"
        and row.panel.observation_timestamp == datetime(2026, 1, 1, 0, tzinfo=UTC)
    )
    assert south_positive.label == 1
    assert south_positive.label_source_outage_id == "OUT-4B5A3F17E6"

    planned = dict(datasets["outage_history"][0])
    planned["outage_id"] = "OUT-PLANNED"
    planned["outage_type"] = "planned"
    planned["planned_flag"] = True
    planned_only = apply_labels(panel, [planned], config)
    assert sum(row.label for row in planned_only) == 0


def test_features_are_past_only_and_exclude_label_source(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_outage_prediction_config(
        _write_prediction_config(workspace), project_root=workspace
    )
    datasets, _ = load_inputs(workspace / config.interim_root, config)
    labelled = apply_labels(build_panel(datasets, config), datasets["outage_history"], config)
    features = build_feature_rows(labelled, datasets, config)

    assert features
    assert all("label_source_outage_id" not in row.features for row in features)
    positive = next(row for row in features if row.labelled.label == 1)
    assert positive.labelled.label_source_outage_id
    assert positive.features["telemetry_observation_count"] >= 1
    assert positive.features["historical_outage_duration_minutes"] == 0


def test_chronological_split_purges_and_preserves_test(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_outage_prediction_config(
        _write_prediction_config(workspace), project_root=workspace
    )
    datasets, _ = load_inputs(workspace / config.interim_root, config)
    rows = build_feature_rows(
        apply_labels(build_panel(datasets, config), datasets["outage_history"], config),
        datasets,
        config,
    )
    splits = chronological_split(rows, config)

    assert len(splits.train) == 4
    assert len(splits.validation) == 2
    assert len(splits.test) == 2
    assert splits.boundaries.train_end < splits.boundaries.validation_start
    assert sum(row.labelled.label for row in splits.train) == 1
    assert sum(row.labelled.label for row in splits.test) == 1


def test_metrics_reason_codes_and_risk_bands(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    config = load_outage_prediction_config(
        _write_prediction_config(workspace), project_root=workspace
    )
    result = _prediction_result(config, score=0.8, label=1)
    metric = evaluate_predictions([result], threshold=0.5, horizon=1)[0]
    assert metric.true_positive == 1
    assert metric.recall == 1
    assert classify_risk(0.8, result.row, config) == RiskBand.CRITICAL
    assert reason_codes(result.row, config)[0] == "RECENT_UNPLANNED_OUTAGE"


def test_pipeline_writes_outputs_metadata_manifest_and_reports(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_outage_prediction_config(
        _write_prediction_config(workspace), project_root=workspace
    )
    result = run_outage_prediction(config, project_root=workspace)

    assert result.selected_model == "prevalence"
    assert result.prediction_path.exists()
    assert result.metrics_path.exists()
    assert result.manifest_path.exists()
    assert result.model_metadata_path.exists()
    assert result.report_paths["evaluation"].exists()
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["class_counts"]["overall"]["positive_count"] == 2
    assert metrics["class_counts"]["overall"]["negative_count"] == 8


def test_cli_success_filter_and_missing_input_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    monkeypatch.chdir(workspace)
    config_path = _write_prediction_config(workspace)
    assert main(["--config", str(config_path), "--run-id", "cli-outage"]) == 0
    assert (
        main(
            [
                "--config",
                str(config_path),
                "--entity-id",
                "FDR-SOUTH-001-01",
                "--run-id",
                "south-only",
            ]
        )
        == 0
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


def _write_prediction_config(workspace: Path, **overrides: object) -> Path:
    values = {
        "profile": "ci",
        "interim_root": "data/interim",
        "asset_health_root": "outputs/asset_health",
        "output_root": "outputs/outage_prediction",
        "report_root": "reports/outage_prediction",
        "model_root": "outputs/models/outage_prediction",
        "entity_type": "feeder",
        "observation_frequency_minutes": 60,
        "prediction_horizon_intervals": 1,
        "feature_lookback_intervals": 2,
        "minimum_history_intervals": 1,
        "validation_intervals": 1,
        "test_intervals": 1,
        "backtest_folds": 1,
        "candidate_models": [
            "prevalence",
            "recent_outage_heuristic",
            "operational_warning_heuristic",
            "logistic_regression",
        ],
        "selection_metric": "f1",
        "positive_class_weight": 3.0,
        "classification_threshold": 0.5,
        "calibration_method": "raw",
        "random_seed": 20260201,
        "include_weather_features": True,
        "include_asset_features": True,
        "include_maintenance_features": True,
        "include_asset_health_features": False,
        "include_smart_meter_features": True,
        "include_substation_features": True,
        "minimum_positive_examples": 1,
        "minimum_negative_examples": 1,
        "risk_band_thresholds": {"moderate_min": 0.25, "high_min": 0.5, "critical_min": 0.75},
        "schema_version": "6.0.0",
        "run_id_strategy": "deterministic",
        "max_reason_codes": 5,
    }
    values.update(overrides)
    path = workspace / "configs/outage_prediction_test.yaml"
    path.write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in values.items()),
        encoding="utf-8",
    )
    return path


def _prediction_result(config: object, *, score: float, label: int) -> PredictionResult:
    del config
    entity = Entity(
        EntityType.FEEDER,
        "FDR-X",
        "GRID-X",
        "SUB-X",
        "FDR-X",
    )
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    panel = PanelRow(entity, timestamp, 2, 2, 1.0, 0)
    labelled = LabelledRow(panel, label, timestamp, timestamp, "OUT-X", "feeder")
    row = FeatureRow(
        labelled,
        {
            "prior_unplanned_outage_count": 1,
            "data_completeness_ratio": 1.0,
        },
    )
    return PredictionResult("run", row, "model", score, RiskBand.CRITICAL, True, 0.5, "test", ())
