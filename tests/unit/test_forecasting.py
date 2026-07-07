from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grid_reliability.common import ConfigurationError
from grid_reliability.data_generation.config import load_generation_config
from grid_reliability.data_generation.pipeline import generate_datasets
from grid_reliability.forecasting.aggregation import aggregate_series
from grid_reliability.forecasting.config import load_forecasting_config
from grid_reliability.forecasting.features import build_feature_rows
from grid_reliability.forecasting.metrics import evaluate_predictions
from grid_reliability.forecasting.models import ForecastingError, PredictionRow, TimeSeriesPoint
from grid_reliability.forecasting.pipeline import main, run_forecasting
from grid_reliability.forecasting.selection import select_model
from grid_reliability.forecasting.splitting import chronological_split, rolling_origin_folds
from grid_reliability.ingestion.config import load_ingestion_config
from grid_reliability.ingestion.pipeline import run_ingestion

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_forecasting_config_validates_supported_values(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    good = _write_forecasting_config(workspace)
    config = load_forecasting_config(good, project_root=workspace)
    assert config.forecast_horizons == (1,)

    bad_target = _write_forecasting_config(workspace, target_source="outage_history")
    with pytest.raises(ConfigurationError, match="target_source"):
        load_forecasting_config(bad_target, project_root=workspace)

    bad_model = _write_forecasting_config(workspace, candidate_models=["persistence", "xgboost"])
    with pytest.raises(ConfigurationError, match="Unsupported candidate"):
        load_forecasting_config(bad_model, project_root=workspace)

    bad_path = _write_forecasting_config(workspace, interim_root="../raw")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_forecasting_config(bad_path, project_root=workspace)

    bad_interval = _write_forecasting_config(workspace, prediction_interval_level=1.2)
    with pytest.raises(ConfigurationError, match="between zero and one"):
        load_forecasting_config(bad_interval, project_root=workspace)


def test_aggregation_uses_interim_and_entity_filter(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_forecasting_config(_write_forecasting_config(workspace), project_root=workspace)
    records = {
        "smart_meter_events": _read_jsonl(workspace / "data/interim/smart_meter_events.jsonl"),
        "weather_data": _read_jsonl(workspace / "data/interim/weather_data.jsonl"),
    }
    points, missing = aggregate_series(records, config)
    assert {point.entity_id for point in points} == {"GRID-NORTH", "GRID-SOUTH"}
    assert all(point.target_unit == "kWh" for point in points)
    assert missing["missing_intervals"] == 0

    filtered = replace(config, entity_id="GRID-NORTH")
    filtered_points, _ = aggregate_series(records, filtered)
    assert {point.entity_id for point in filtered_points} == {"GRID-NORTH"}


def test_feature_lag_and_rolling_use_past_rows_only() -> None:
    config = _config_from_fixture()
    rows = build_feature_rows(_points([10, 20, 30, 40, 50, 60]), config)
    first = rows[0]
    assert first.forecast_origin == _ts(1)
    assert first.forecast_timestamp == _ts(2)
    assert first.features["lag_1"] == 20
    assert first.features["rolling_mean_2"] == 15
    assert first.actual_value == 30
    assert "weather_temperature_c" in first.features


def test_chronological_split_and_backtest_have_no_overlap() -> None:
    config = _config_from_fixture()
    rows = build_feature_rows(_points([10, 20, 30, 40, 50, 60]), config)
    train, validation, test, boundaries = chronological_split(rows, config)
    assert max(row.forecast_timestamp for row in train) < min(
        row.forecast_timestamp for row in validation
    )
    assert max(row.forecast_timestamp for row in validation) < min(
        row.forecast_timestamp for row in test
    )
    assert boundaries.test_start == "2026-01-01T05:00:00Z"
    folds = rolling_origin_folds(train, validation, test, config)
    assert len(folds) == 1
    assert folds[0][1]
    assert folds[0][2]


def test_metrics_handle_zero_actuals_without_divide_by_zero() -> None:
    prediction = PredictionRow(
        forecast_run_id="test",
        generated_at=_ts(0),
        entity_type="grid_region",
        entity_id="GRID-X",
        grid_region="GRID-X",
        forecast_origin=_ts(0),
        forecast_timestamp=_ts(1),
        forecast_horizon_intervals=1,
        target_name="active_energy_kwh",
        target_unit="kWh",
        model_name="persistence",
        predicted_value=1.0,
        prediction_lower=0.0,
        prediction_upper=2.0,
        actual_value=0.0,
        data_split="test",
    )
    metrics = evaluate_predictions([prediction], aggregation_level="grid_region")
    assert metrics[0].mape is None
    assert metrics[0].wape is None
    assert metrics[0].smape == 200.0


def test_model_selection_uses_validation_and_tie_breaks() -> None:
    predictions = [
        _prediction("persistence", "validation", actual=10, predicted=9),
        _prediction("autoregressive_linear", "validation", actual=10, predicted=10),
        _prediction("persistence", "test", actual=10, predicted=10),
        _prediction("autoregressive_linear", "test", actual=10, predicted=0),
    ]
    metrics = evaluate_predictions(predictions, aggregation_level="grid_region")
    selection = select_model(
        metrics,
        candidate_models=("persistence", "autoregressive_linear"),
        selection_metric="mae",
        excluded_models={},
    )
    assert selection.selected_model == "autoregressive_linear"
    assert selection.beats_baseline


def test_pipeline_writes_outputs_reports_and_metadata(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config_path = _write_forecasting_config(workspace)
    config = load_forecasting_config(config_path, project_root=workspace)
    result = run_forecasting(config, project_root=workspace)

    assert result.selected_model
    assert result.forecast_path.exists()
    assert result.metrics_path.exists()
    assert result.manifest_path.exists()
    assert result.model_metadata_path.exists()
    assert result.report_paths["model_card"].exists()
    assert result.forecast_row_count == 14
    forecast_text = result.forecast_path.read_text(encoding="utf-8")
    assert "forecast_run_id,generated_at,entity_type" in forecast_text
    metadata = json.loads(result.model_metadata_path.read_text(encoding="utf-8"))
    assert metadata["synthetic_data_declaration"]
    assert not any(str(workspace) in value for value in json.dumps(metadata).split())


def test_cli_success_and_insufficient_history_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config_path = _write_forecasting_config(workspace)
    monkeypatch.chdir(workspace)
    assert main(["--config", str(config_path), "--run-id", "cli-forecast"]) == 0

    bad_config = _write_forecasting_config(workspace, minimum_history_intervals=10)
    assert main(["--config", str(bad_config)]) == 3


def test_missing_interim_file_fails(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    config = load_forecasting_config(_write_forecasting_config(workspace), project_root=workspace)
    with pytest.raises(ForecastingError, match="interim dataset missing"):
        run_forecasting(config, project_root=workspace)


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    shutil.copy(PROJECT_ROOT / "configs/base.yaml", tmp_path / "configs/base.yaml")
    shutil.copytree(PROJECT_ROOT / "configs/data_contracts", tmp_path / "configs/data_contracts")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


def _generate_and_ingest(workspace: Path) -> None:
    generation_config = load_generation_config(
        PROJECT_ROOT / "configs/synthetic_data_ci.yaml",
        project_root=PROJECT_ROOT,
    )
    generate_datasets(
        replace(generation_config, output_root=Path("data/raw")), project_root=workspace
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


def _write_forecasting_config(workspace: Path, **overrides: object) -> Path:
    values = {
        "profile": "ci",
        "interim_root": "data/interim",
        "output_root": "outputs/forecasting",
        "report_root": "reports/forecasting",
        "model_root": "outputs/models/forecasting",
        "target_source": "smart_meter_events",
        "target_column": "active_energy_kwh",
        "aggregation_level": "grid_region",
        "timestamp_frequency_minutes": 60,
        "forecast_horizons": [1],
        "minimum_history_intervals": 6,
        "validation_intervals": 1,
        "test_intervals": 1,
        "backtest_folds": 1,
        "random_seed": 20260201,
        "include_weather_features": True,
        "include_calendar_features": True,
        "include_lag_features": True,
        "lag_intervals": [1],
        "rolling_windows": [2],
        "candidate_models": ["persistence", "moving_average", "autoregressive_linear"],
        "selection_metric": "mae",
        "missing_interval_policy": "drop",
        "missing_interval_limit": 2,
        "prediction_interval_level": 0.8,
        "timezone": "UTC",
    }
    values.update(overrides)
    path = workspace / "configs/forecasting_test.yaml"
    path.write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in values.items()),
        encoding="utf-8",
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _points(values: list[float]) -> list[TimeSeriesPoint]:
    return [
        TimeSeriesPoint(
            timestamp=_ts(index),
            entity_type="grid_region",
            entity_id="GRID-X",
            grid_region="GRID-X",
            substation_id=None,
            feeder_id=None,
            target_name="active_energy_kwh",
            target_unit="kWh",
            target_value=value,
            contributing_records=1,
            coverage_ratio=1.0,
            weather={"weather_temperature_c": float(index)},
        )
        for index, value in enumerate(values)
    ]


def _config_from_fixture():
    return replace(
        load_forecasting_config(
            PROJECT_ROOT / "configs/forecasting_ci.yaml",
            project_root=PROJECT_ROOT,
        ),
        include_weather_features=True,
    )


def _prediction(model_name: str, split: str, *, actual: float, predicted: float) -> PredictionRow:
    return PredictionRow(
        forecast_run_id="test",
        generated_at=_ts(0),
        entity_type="grid_region",
        entity_id="GRID-X",
        grid_region="GRID-X",
        forecast_origin=_ts(0),
        forecast_timestamp=_ts(1),
        forecast_horizon_intervals=1,
        target_name="active_energy_kwh",
        target_unit="kWh",
        model_name=model_name,
        predicted_value=predicted,
        prediction_lower=min(predicted, actual),
        prediction_upper=max(predicted, actual),
        actual_value=actual,
        data_split=split,
    )


def _ts(offset_hours: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=offset_hours)
