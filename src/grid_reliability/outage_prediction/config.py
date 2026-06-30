"""Configuration for deterministic outage prediction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.outage_prediction.models import EntityType

SUPPORTED_MODELS = {
    "prevalence",
    "recent_outage_heuristic",
    "operational_warning_heuristic",
    "logistic_regression",
}
SUPPORTED_SELECTION_METRICS = {"f1", "recall", "precision", "balanced_accuracy", "pr_auc"}
SUPPORTED_CALIBRATION = {"raw"}
SUPPORTED_FREQUENCIES = {15, 30, 60}


@dataclass(frozen=True)
class OutagePredictionConfig:
    interim_root: Path
    asset_health_root: Path
    output_root: Path
    report_root: Path
    model_root: Path
    entity_type: EntityType
    observation_frequency_minutes: int
    prediction_horizon_intervals: int
    feature_lookback_intervals: int
    minimum_history_intervals: int
    validation_intervals: int
    test_intervals: int
    backtest_folds: int
    candidate_models: tuple[str, ...]
    selection_metric: str
    positive_class_weight: float
    classification_threshold: float
    calibration_method: str
    random_seed: int
    include_weather_features: bool
    include_asset_features: bool
    include_maintenance_features: bool
    include_asset_health_features: bool
    include_smart_meter_features: bool
    include_substation_features: bool
    minimum_positive_examples: int
    minimum_negative_examples: int
    risk_band_thresholds: dict[str, float]
    schema_version: str
    run_id_strategy: str
    max_reason_codes: int
    entity_id: str | None = None
    profile: str = "default"


def load_outage_prediction_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    interim_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    run_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    prediction_horizon: int | None = None,
    classification_threshold: float | None = None,
    seed: int | None = None,
) -> OutagePredictionConfig:
    del run_id
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
    if entity_type is not None:
        raw["entity_type"] = entity_type
    if entity_id is not None:
        raw["entity_id"] = entity_id
    if prediction_horizon is not None:
        raw["prediction_horizon_intervals"] = prediction_horizon
    if classification_threshold is not None:
        raw["classification_threshold"] = classification_threshold
    if seed is not None:
        raw["random_seed"] = seed

    config = OutagePredictionConfig(
        interim_root=_safe_path(raw, "interim_root", "data/interim"),
        asset_health_root=_safe_path(raw, "asset_health_root", "outputs/asset_health"),
        output_root=_safe_path(raw, "output_root", "outputs/outage_prediction"),
        report_root=_safe_path(raw, "report_root", "reports/outage_prediction"),
        model_root=_safe_path(raw, "model_root", "outputs/models/outage_prediction"),
        entity_type=_entity_type(raw),
        observation_frequency_minutes=_frequency(raw),
        prediction_horizon_intervals=_positive_int(raw, "prediction_horizon_intervals", 1),
        feature_lookback_intervals=_positive_int(raw, "feature_lookback_intervals", 4),
        minimum_history_intervals=_positive_int(raw, "minimum_history_intervals", 1),
        validation_intervals=_positive_int(raw, "validation_intervals", 1),
        test_intervals=_positive_int(raw, "test_intervals", 1),
        backtest_folds=_positive_int(raw, "backtest_folds", 1),
        candidate_models=_model_tuple(raw),
        selection_metric=_choice(
            _string(raw, "selection_metric", "f1"),
            SUPPORTED_SELECTION_METRICS,
            "selection_metric",
        ),
        positive_class_weight=_positive_float(raw, "positive_class_weight", 1.0),
        classification_threshold=_rate(raw, "classification_threshold", 0.5, inclusive=True),
        calibration_method=_choice(
            _string(raw, "calibration_method", "raw"),
            SUPPORTED_CALIBRATION,
            "calibration_method",
        ),
        random_seed=int(raw.get("random_seed", 20260201)),
        include_weather_features=_bool(raw, "include_weather_features", True),
        include_asset_features=_bool(raw, "include_asset_features", True),
        include_maintenance_features=_bool(raw, "include_maintenance_features", True),
        include_asset_health_features=_bool(raw, "include_asset_health_features", False),
        include_smart_meter_features=_bool(raw, "include_smart_meter_features", True),
        include_substation_features=_bool(raw, "include_substation_features", True),
        minimum_positive_examples=_positive_int(raw, "minimum_positive_examples", 1),
        minimum_negative_examples=_positive_int(raw, "minimum_negative_examples", 1),
        risk_band_thresholds=_risk_thresholds(raw),
        schema_version=_string(raw, "schema_version", "6.0.0"),
        run_id_strategy=_choice(
            _string(raw, "run_id_strategy", "timestamp"),
            {"timestamp", "deterministic"},
            "run_id_strategy",
        ),
        max_reason_codes=_positive_int(raw, "max_reason_codes", 5),
        entity_id=str(raw["entity_id"]) if raw.get("entity_id") not in (None, "") else None,
        profile=str(raw.get("profile", "default")),
    )
    _validate_windows(config)
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Outage prediction config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Outage prediction config must contain a mapping.")
    return raw


def _safe_path(raw: dict[str, Any], key: str, default: str) -> Path:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _entity_type(raw: dict[str, Any]) -> EntityType:
    value = _string(raw, "entity_type", "feeder")
    try:
        return EntityType(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in EntityType)
        raise ConfigurationError(f"entity_type must be one of: {allowed}.") from exc


def _frequency(raw: dict[str, Any]) -> int:
    value = _positive_int(raw, "observation_frequency_minutes", 60)
    if value not in SUPPORTED_FREQUENCIES:
        raise ConfigurationError("observation_frequency_minutes is not supported.")
    return value


def _model_tuple(raw: dict[str, Any]) -> tuple[str, ...]:
    value = raw.get("candidate_models", ["prevalence", "logistic_regression"])
    if not isinstance(value, list) or not value:
        raise ConfigurationError("candidate_models must be a non-empty list.")
    models = tuple(str(item) for item in value)
    unsupported = sorted(set(models) - SUPPORTED_MODELS)
    if unsupported:
        raise ConfigurationError(f"Unsupported candidate model(s): {', '.join(unsupported)}")
    if "prevalence" not in models:
        raise ConfigurationError("candidate_models must include prevalence baseline.")
    return models


def _risk_thresholds(raw: dict[str, Any]) -> dict[str, float]:
    value = raw.get(
        "risk_band_thresholds",
        {"moderate_min": 0.25, "high_min": 0.5, "critical_min": 0.75},
    )
    if not isinstance(value, dict):
        raise ConfigurationError("risk_band_thresholds must be a mapping.")
    thresholds = {
        "moderate_min": _mapping_rate(value, "moderate_min"),
        "high_min": _mapping_rate(value, "high_min"),
        "critical_min": _mapping_rate(value, "critical_min"),
    }
    if not thresholds["moderate_min"] < thresholds["high_min"] < thresholds["critical_min"]:
        raise ConfigurationError("risk_band_thresholds must be ordered and non-overlapping.")
    return thresholds


def _validate_windows(config: OutagePredictionConfig) -> None:
    if config.minimum_history_intervals > config.feature_lookback_intervals:
        raise ConfigurationError(
            "minimum_history_intervals cannot exceed feature_lookback_intervals."
        )
    required = (
        config.minimum_history_intervals
        + config.validation_intervals
        + config.test_intervals
        + config.prediction_horizon_intervals
    )
    if required < 4:
        raise ConfigurationError("split and horizon settings are too small for validation.")


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _positive_float(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or float(value) <= 0:
        raise ConfigurationError(f"{key} must be greater than zero.")
    return float(value)


def _rate(raw: dict[str, Any], key: str, default: float, *, inclusive: bool) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float):
        raise ConfigurationError(f"{key} must be numeric.")
    number = float(value)
    valid = 0 <= number <= 1 if inclusive else 0 < number < 1
    if not valid:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return number


def _mapping_rate(raw: dict[Any, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


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


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value
