"""Configuration loading for local electricity-demand forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.forecasting.models import (
    AggregationLevel,
    MissingIntervalPolicy,
    TargetSource,
)

SUPPORTED_MODELS = {"persistence", "seasonal_naive", "moving_average", "autoregressive_linear"}
SUPPORTED_SELECTION_METRICS = {"mae", "rmse", "wape", "smape", "bias"}
SUPPORTED_TARGET_COLUMNS = {"active_energy_kwh", "load_mw"}


@dataclass(frozen=True)
class ForecastingConfig:
    interim_root: Path
    output_root: Path
    report_root: Path
    model_root: Path
    target_source: TargetSource
    target_column: str
    aggregation_level: AggregationLevel
    timestamp_frequency_minutes: int
    forecast_horizons: tuple[int, ...]
    minimum_history_intervals: int
    validation_intervals: int
    test_intervals: int
    backtest_folds: int
    random_seed: int
    include_weather_features: bool
    include_calendar_features: bool
    include_lag_features: bool
    lag_intervals: tuple[int, ...]
    rolling_windows: tuple[int, ...]
    candidate_models: tuple[str, ...]
    selection_metric: str
    missing_interval_policy: MissingIntervalPolicy
    missing_interval_limit: int
    prediction_interval_level: float
    timezone: str
    entity_id: str | None = None
    profile: str = "default"


def load_forecasting_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    interim_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    run_aggregation_level: str | None = None,
    entity_id: str | None = None,
    horizon: int | None = None,
    seed: int | None = None,
) -> ForecastingConfig:
    root = (project_root or resolve_project_root()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    raw = _read_yaml(path)
    if interim_root is not None:
        raw["interim_root"] = interim_root
    if output_root is not None:
        raw["output_root"] = output_root
    if report_root is not None:
        raw["report_root"] = report_root
    if run_aggregation_level is not None:
        raw["aggregation_level"] = run_aggregation_level
    if entity_id is not None:
        raw["entity_id"] = entity_id
    if horizon is not None:
        raw["forecast_horizons"] = [horizon]
    if seed is not None:
        raw["random_seed"] = seed

    target_source = _enum_choice(raw, "target_source", "smart_meter_events", TargetSource)
    target_column = _string(raw, "target_column", "active_energy_kwh")
    if target_column not in SUPPORTED_TARGET_COLUMNS:
        raise ConfigurationError("target_column is not supported.")
    if target_source == TargetSource.SMART_METER_EVENTS and target_column != "active_energy_kwh":
        raise ConfigurationError("smart_meter_events supports active_energy_kwh only.")
    if target_source == TargetSource.SUBSTATION_EVENTS and target_column != "load_mw":
        raise ConfigurationError("substation_events supports load_mw only.")

    config = ForecastingConfig(
        interim_root=_safe_relative_path(raw, "interim_root", "data/interim"),
        output_root=_safe_relative_path(raw, "output_root", "outputs/forecasting"),
        report_root=_safe_relative_path(raw, "report_root", "reports/forecasting"),
        model_root=_safe_relative_path(raw, "model_root", "outputs/models/forecasting"),
        target_source=target_source,
        target_column=target_column,
        aggregation_level=_enum_choice(raw, "aggregation_level", "grid_region", AggregationLevel),
        timestamp_frequency_minutes=_positive_int(raw, "timestamp_frequency_minutes", 60),
        forecast_horizons=_positive_tuple(raw, "forecast_horizons", [1]),
        minimum_history_intervals=_positive_int(raw, "minimum_history_intervals", 6),
        validation_intervals=_positive_int(raw, "validation_intervals", 1),
        test_intervals=_positive_int(raw, "test_intervals", 1),
        backtest_folds=_positive_int(raw, "backtest_folds", 1),
        random_seed=int(raw.get("random_seed", 20260201)),
        include_weather_features=_bool(raw, "include_weather_features", True),
        include_calendar_features=_bool(raw, "include_calendar_features", True),
        include_lag_features=_bool(raw, "include_lag_features", True),
        lag_intervals=_positive_tuple(raw, "lag_intervals", [1]),
        rolling_windows=_positive_tuple(raw, "rolling_windows", [2]),
        candidate_models=_model_tuple(
            raw, "candidate_models", ["persistence", "autoregressive_linear"]
        ),
        selection_metric=_choice(
            _string(raw, "selection_metric", "mae"), SUPPORTED_SELECTION_METRICS, "selection_metric"
        ),
        missing_interval_policy=_enum_choice(
            raw, "missing_interval_policy", "drop", MissingIntervalPolicy
        ),
        missing_interval_limit=_positive_int(raw, "missing_interval_limit", 2),
        prediction_interval_level=_rate(raw, "prediction_interval_level", 0.8),
        timezone=_timezone(raw),
        entity_id=str(raw["entity_id"]) if raw.get("entity_id") not in (None, "") else None,
        profile=str(raw.get("profile", "default")),
    )
    _validate_split_design(config)
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Forecasting config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Forecasting config must contain a mapping.")
    return raw


def _safe_relative_path(raw: dict[str, Any], key: str, default: str) -> Path:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _string(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty string.")
    return value


def _bool(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{key} must be true or false.")
    return value


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _positive_tuple(raw: dict[str, Any], key: str, default: list[int]) -> tuple[int, ...]:
    value = raw.get(key, default)
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{key} must be a non-empty list of positive integers.")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or item <= 0:
            raise ConfigurationError(f"{key} must contain positive integers.")
        result.append(item)
    return tuple(sorted(set(result)))


def _model_tuple(raw: dict[str, Any], key: str, default: list[str]) -> tuple[str, ...]:
    value = raw.get(key, default)
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{key} must be a non-empty model list.")
    models = tuple(str(item) for item in value)
    unsupported = sorted(set(models) - SUPPORTED_MODELS)
    if unsupported:
        raise ConfigurationError(f"Unsupported candidate model(s): {', '.join(unsupported)}")
    if "persistence" not in models:
        raise ConfigurationError("candidate_models must include persistence baseline.")
    return models


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or not 0 < float(value) < 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value


def _enum_choice(
    raw: dict[str, Any],
    key: str,
    default: str,
    enum_type: type[Any],
) -> Any:
    value = raw.get(key, default)
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ConfigurationError(f"{key} must be one of: {allowed}.") from exc


def _timezone(raw: dict[str, Any]) -> str:
    value = raw.get("timezone", "UTC")
    if not isinstance(value, str) or not value:
        raise ConfigurationError("timezone must be a non-empty IANA timezone string.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"Unsupported timezone: {value}") from exc
    return value


def _validate_split_design(config: ForecastingConfig) -> None:
    max_horizon = max(config.forecast_horizons)
    max_lag = max(config.lag_intervals, default=0) if config.include_lag_features else 0
    max_rolling = max(config.rolling_windows, default=0)
    usable_requirement = (
        max(max_lag, max_rolling - 1)
        + max_horizon
        + config.validation_intervals
        + config.test_intervals
    )
    if config.minimum_history_intervals < usable_requirement:
        raise ConfigurationError(
            "minimum_history_intervals is too small for configured lags, rolling windows, "
            "horizons, validation, and test windows."
        )
