"""Electricity demand forecasting pipeline and CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.metadata import __version__
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.forecasting.aggregation import aggregate_series
from grid_reliability.forecasting.baselines import (
    ForecastModel,
    MovingAverageModel,
    PersistenceModel,
    SeasonalNaiveModel,
    residual_quantiles,
)
from grid_reliability.forecasting.config import ForecastingConfig, load_forecasting_config
from grid_reliability.forecasting.data import load_forecasting_inputs
from grid_reliability.forecasting.features import build_feature_rows, feature_names
from grid_reliability.forecasting.metrics import evaluate_predictions, overall_metric
from grid_reliability.forecasting.models import (
    ForecastingError,
    MetricResult,
    ModelSelection,
    PredictionRow,
    SplitBoundaries,
)
from grid_reliability.forecasting.persistence import (
    output_checksums,
    write_forecasts,
    write_manifest,
    write_metrics,
    write_model_comparison,
    write_model_metadata,
)
from grid_reliability.forecasting.regression import AutoregressiveLinearModel
from grid_reliability.forecasting.reporting import write_reports
from grid_reliability.forecasting.selection import select_model
from grid_reliability.forecasting.splitting import chronological_split, rolling_origin_folds


@dataclass(frozen=True)
class ForecastingResult:
    run_id: str
    selected_model: str
    forecast_path: Path
    metrics_path: Path
    manifest_path: Path
    model_metadata_path: Path
    report_paths: dict[str, Path]
    metrics: list[MetricResult]
    forecast_row_count: int


def build_run_id(provided: str | None = None, *, profile: str = "default") -> str:
    if provided:
        return provided
    if profile == "ci":
        return "forecast-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_forecasting(
    config: ForecastingConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
) -> ForecastingResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(run_id, profile=config.profile)
    generated_at = datetime.now(tz=UTC)
    output_root = root / config.output_root / effective_run_id
    report_root = root / config.report_root
    model_root = root / config.model_root / effective_run_id
    output_root.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    inputs, input_checksums = load_forecasting_inputs(
        root / config.interim_root,
        config.target_source,
        include_weather=config.include_weather_features,
    )
    points, missing_counts = aggregate_series(inputs, config)
    rows = build_feature_rows(points, config)
    train_rows, validation_rows, test_rows, boundaries = chronological_split(rows, config)
    names = feature_names(rows)

    model_instances, excluded = _build_models(config)
    predictions: list[PredictionRow] = []
    trained_parameters: dict[str, dict[str, object]] = {}
    for model_name, model in model_instances.items():
        try:
            model.fit(train_rows, names)
            trained_parameters[model_name] = model.parameters()
            train_predictions = model.predict(train_rows, names)
            residual_lower, residual_upper = residual_quantiles(
                train_rows,
                train_predictions,
                config.prediction_interval_level,
            )
            predictions.extend(
                _predict_rows(
                    model,
                    validation_rows,
                    names,
                    effective_run_id,
                    generated_at,
                    residual_lower,
                    residual_upper,
                )
            )
            predictions.extend(
                _predict_rows(
                    model,
                    test_rows,
                    names,
                    effective_run_id,
                    generated_at,
                    residual_lower,
                    residual_upper,
                )
            )
        except (ValueError, ArithmeticError) as exc:
            excluded[model_name] = str(exc)

    metrics = evaluate_predictions(predictions, aggregation_level=config.aggregation_level.value)
    selection = select_model(
        metrics,
        candidate_models=config.candidate_models,
        selection_metric=config.selection_metric,
        excluded_models=excluded,
    )
    fold_predictions = _backtest_predictions(
        config=config,
        model_name=selection.selected_model,
        train_rows=train_rows,
        validation_rows=validation_rows,
        test_rows=test_rows,
        feature_names=names,
        run_id=effective_run_id,
        generated_at=generated_at,
    )
    predictions.extend(fold_predictions)
    metrics = evaluate_predictions(predictions, aggregation_level=config.aggregation_level.value)

    forecast_path = write_forecasts(output_root, predictions)
    comparison_path = write_model_comparison(output_root, metrics)
    metrics_path = write_metrics(
        output_root,
        _metrics_payload(
            effective_run_id,
            config,
            selection,
            metrics,
            missing_counts,
            len(train_rows),
            len(validation_rows),
            len(test_rows),
            excluded,
        ),
    )
    metadata_path = write_model_metadata(
        model_root,
        _metadata_payload(
            settings.project_name,
            effective_run_id,
            config,
            selection,
            metrics,
            boundaries,
            names,
            input_checksums,
            trained_parameters,
        ),
    )
    output_paths = {
        "forecast_csv": forecast_path,
        "metrics_json": metrics_path,
        "model_comparison_csv": comparison_path,
        "model_metadata_json": metadata_path,
    }
    manifest_path = write_manifest(
        output_root,
        _manifest_payload(
            settings.project_name,
            effective_run_id,
            config,
            selection,
            boundaries,
            input_checksums,
            output_paths,
            len(predictions),
            len(metrics),
            excluded,
        ),
    )
    output_paths["forecast_manifest_json"] = manifest_path
    report_paths = write_reports(
        report_root=report_root,
        run_id=effective_run_id,
        target_name=config.target_column,
        target_unit="kWh" if config.target_column == "active_energy_kwh" else "MW",
        aggregation_level=config.aggregation_level.value,
        boundaries=boundaries,
        metrics=metrics,
        selection=selection,
        feature_names=names,
        weather_enabled=config.include_weather_features,
    )
    return ForecastingResult(
        effective_run_id,
        selection.selected_model,
        forecast_path,
        metrics_path,
        manifest_path,
        metadata_path,
        report_paths,
        metrics,
        len(predictions),
    )


def _build_models(config: ForecastingConfig) -> tuple[dict[str, ForecastModel], dict[str, str]]:
    models: dict[str, ForecastModel] = {}
    excluded: dict[str, str] = {}
    for model_name in config.candidate_models:
        if model_name == "persistence":
            models[model_name] = PersistenceModel()
        elif model_name == "moving_average":
            window = min(config.rolling_windows) if config.rolling_windows else 2
            models[model_name] = MovingAverageModel(window=window)
        elif model_name == "seasonal_naive":
            seasonal_period = 24
            if seasonal_period not in config.lag_intervals:
                excluded[model_name] = "seasonal lag 24 is not configured or supported by history"
            else:
                models[model_name] = SeasonalNaiveModel(seasonal_period=seasonal_period)
        elif model_name == "autoregressive_linear":
            models[model_name] = AutoregressiveLinearModel()
    return models, excluded


def _predict_rows(
    model: ForecastModel,
    rows: list[Any],
    names: list[str],
    run_id: str,
    generated_at: datetime,
    residual_lower: float,
    residual_upper: float,
) -> list[PredictionRow]:
    predicted = model.predict(rows, names)
    output: list[PredictionRow] = []
    for row, value in zip(rows, predicted, strict=True):
        lower = max(0.0, min(value, value + residual_lower))
        upper = max(value, value + residual_upper, lower)
        output.append(
            PredictionRow(
                forecast_run_id=run_id,
                generated_at=generated_at,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                grid_region=row.grid_region,
                forecast_origin=row.forecast_origin,
                forecast_timestamp=row.forecast_timestamp,
                forecast_horizon_intervals=row.forecast_horizon_intervals,
                target_name=row.target_name,
                target_unit=row.target_unit,
                model_name=model.name,
                predicted_value=value,
                prediction_lower=lower,
                prediction_upper=upper,
                actual_value=row.actual_value,
                data_split=row.data_split,
            )
        )
    return output


def _backtest_predictions(
    *,
    config: ForecastingConfig,
    model_name: str,
    train_rows: list[Any],
    validation_rows: list[Any],
    test_rows: list[Any],
    feature_names: list[str],
    run_id: str,
    generated_at: datetime,
) -> list[PredictionRow]:
    predictions: list[PredictionRow] = []
    folds = rolling_origin_folds(train_rows, validation_rows, test_rows, config)
    for fold_number, fold_train, fold_eval, cutoff in folds:
        model = _build_models_for_name(model_name)
        model.fit(fold_train, feature_names)
        train_predictions = model.predict(fold_train, feature_names)
        residual_lower, residual_upper = residual_quantiles(
            fold_train,
            train_predictions,
            config.prediction_interval_level,
        )
        for prediction in _predict_rows(
            model,
            fold_eval,
            feature_names,
            run_id,
            generated_at,
            residual_lower,
            residual_upper,
        ):
            predictions.append(
                PredictionRow(
                    **{
                        **prediction.__dict__,
                        "model_name": f"{model.name}_backtest_fold_{fold_number}",
                        "data_split": f"backtest_cutoff_{cutoff.isoformat()}",
                    }
                )
            )
    return predictions


def _build_models_for_name(model_name: str) -> ForecastModel:
    if model_name == "persistence":
        return PersistenceModel()
    if model_name == "moving_average":
        return MovingAverageModel()
    if model_name == "seasonal_naive":
        return SeasonalNaiveModel(seasonal_period=24)
    return AutoregressiveLinearModel()


def _metrics_payload(
    run_id: str,
    config: ForecastingConfig,
    selection: ModelSelection,
    metrics: list[MetricResult],
    missing_counts: dict[str, int],
    train_count: int,
    validation_count: int,
    test_count: int,
    excluded: dict[str, str],
) -> dict[str, Any]:
    return {
        "forecast_run_id": run_id,
        "selected_model": selection.selected_model,
        "selection_metric": selection.selected_metric,
        "baseline_improvement": selection.beats_baseline,
        "metrics": [metric.to_dict() for metric in metrics],
        "selected_model_test_mae": overall_metric(
            metrics,
            model_name=selection.selected_model,
            split="test",
            metric_name="mae",
        ),
        "missing_interval_counts": missing_counts,
        "training_row_count": train_count,
        "validation_row_count": validation_count,
        "test_row_count": test_count,
        "skipped_entities": [],
        "failed_model_attempts": excluded,
        "target": config.target_column,
        "aggregation_level": config.aggregation_level.value,
    }


def _metadata_payload(
    project_name: str,
    run_id: str,
    config: ForecastingConfig,
    selection: ModelSelection,
    metrics: list[MetricResult],
    boundaries: SplitBoundaries,
    names: list[str],
    input_checksums: dict[str, str],
    trained_parameters: dict[str, dict[str, object]],
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "run_id": run_id,
        "model_name": selection.selected_model,
        "model_version": "4.0.0",
        "model_parameters": trained_parameters.get(selection.selected_model, {}),
        "random_seed": config.random_seed,
        "split_boundaries": boundaries.__dict__,
        "target": config.target_column,
        "unit": "kWh" if config.target_column == "active_energy_kwh" else "MW",
        "entity_grain": config.aggregation_level.value,
        "feature_list": names,
        "lag_intervals": config.lag_intervals,
        "rolling_windows": config.rolling_windows,
        "weather_feature_assumption": (
            "observed weather at forecast origin is used for local evaluation"
            if config.include_weather_features
            else "weather features disabled"
        ),
        "selected_metric": config.selection_metric,
        "validation_metrics": [
            metric.to_dict()
            for metric in metrics
            if metric.model_name == selection.selected_model and metric.split == "validation"
        ],
        "test_metrics": [
            metric.to_dict()
            for metric in metrics
            if metric.model_name == selection.selected_model and metric.split == "test"
        ],
        "package_versions": {"grid_reliability": __version__, "python_stack": "standard-library"},
        "input_checksums": input_checksums,
        "synthetic_data_declaration": (
            "Forecasting uses fictional synthetic validated interim data."
        ),
        "limitations": [
            "Not calibrated for real grid operations.",
            "No Azure Machine Learning resources are deployed.",
            "Short CI profile supports only short-horizon forecasts.",
        ],
    }


def _manifest_payload(
    project_name: str,
    run_id: str,
    config: ForecastingConfig,
    selection: ModelSelection,
    boundaries: SplitBoundaries,
    input_checksums: dict[str, str],
    output_paths: dict[str, Path],
    forecast_count: int,
    metric_count: int,
    excluded: dict[str, str],
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "forecast_run_id": run_id,
        "input_files": sorted(input_checksums),
        "input_checksums": input_checksums,
        "configuration_checksum": sha256_file(Path("configs/forecasting_ci.yaml"))
        if config.profile == "ci" and Path("configs/forecasting_ci.yaml").exists()
        else None,
        "model_candidates": config.candidate_models,
        "selected_model": selection.selected_model,
        "split_boundaries": boundaries.__dict__,
        "output_files": {name: path.name for name, path in sorted(output_paths.items())},
        "output_checksums": output_checksums(output_paths),
        "forecast_row_count": forecast_count,
        "evaluation_row_count": metric_count,
        "skipped_entities": [],
        "failed_model_attempts": excluded,
        "synthetic_data_declaration": "All inputs are fictional synthetic data.",
        "component_version": __version__,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local electricity-demand forecasting.")
    parser.add_argument("--config", default="configs/forecasting.yaml")
    parser.add_argument("--interim-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--aggregation-level")
    parser.add_argument("--entity-id")
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--seed", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = resolve_project_root()
    try:
        config = load_forecasting_config(
            args.config,
            project_root=project_root,
            interim_root=args.interim_root,
            output_root=args.output_root,
            report_root=args.report_root,
            run_aggregation_level=args.aggregation_level,
            entity_id=args.entity_id,
            horizon=args.horizon,
            seed=args.seed,
        )
        result = run_forecasting(config, project_root=project_root, run_id=args.run_id)
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except ForecastingError as exc:
        print(json.dumps({"run_status": "FAILED_DATA_SUFFICIENCY", "error": str(exc)}))
        return 3
    except Exception as exc:
        print(json.dumps({"run_status": "FAILED_FORECASTING", "error": str(exc)}))
        return 1

    print(
        "Forecasting run "
        f"{result.run_id}: selected_model={result.selected_model}; "
        f"forecast_rows={result.forecast_row_count}; forecast={result.forecast_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
