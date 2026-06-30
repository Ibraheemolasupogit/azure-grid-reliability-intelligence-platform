"""Configuration loading for reliability analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.reliability.models import AggregationLevel, PeriodFrequency

SUPPORTED_POPULATION_METHODS = {"observed_smart_meters"}
SUPPORTED_BENCHMARK_METHODS = {"peer_median", "system_median"}


@dataclass(frozen=True)
class ReliabilityConfig:
    interim_root: Path
    output_root: Path
    report_root: Path
    assessment_start: datetime
    assessment_end: datetime
    aggregation_levels: tuple[AggregationLevel, ...]
    period_frequency: PeriodFrequency
    include_planned_outages: bool
    include_unplanned_outages: bool
    customer_population_method: str
    minimum_population: int
    minimum_outage_duration_minutes: int
    maximum_outage_duration_minutes: int
    sustained_interruption_threshold_minutes: int
    restoration_target_minutes: int
    kpi_precision: int
    score_direction: str
    component_weights: dict[str, float]
    benchmark_method: str
    benchmark_scope: str
    reliability_band_thresholds: dict[str, float]
    minimum_data_completeness: float
    schema_version: str
    run_id_strategy: str
    max_reason_codes: int
    entity_id: str | None = None
    profile: str = "default"


def load_reliability_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    interim_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    assessment_start: str | None = None,
    assessment_end: str | None = None,
    aggregation_level: str | None = None,
    entity_id: str | None = None,
    period_frequency: str | None = None,
) -> ReliabilityConfig:
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
    if assessment_start is not None:
        raw["assessment_start"] = assessment_start
    if assessment_end is not None:
        raw["assessment_end"] = assessment_end
    if aggregation_level is not None:
        raw["aggregation_levels"] = [aggregation_level]
    if entity_id is not None:
        raw["entity_id"] = entity_id
    if period_frequency is not None:
        raw["period_frequency"] = period_frequency
    config = ReliabilityConfig(
        interim_root=_safe_path(raw, "interim_root", "data/interim"),
        output_root=_safe_path(raw, "output_root", "outputs/reliability"),
        report_root=_safe_path(raw, "report_root", "reports/reliability"),
        assessment_start=_timestamp(raw.get("assessment_start"), "assessment_start"),
        assessment_end=_timestamp(raw.get("assessment_end"), "assessment_end"),
        aggregation_levels=_aggregation_levels(raw),
        period_frequency=_period_frequency(raw),
        include_planned_outages=_bool(raw, "include_planned_outages", True),
        include_unplanned_outages=_bool(raw, "include_unplanned_outages", True),
        customer_population_method=_choice(
            _string(raw, "customer_population_method", "observed_smart_meters"),
            SUPPORTED_POPULATION_METHODS,
            "customer_population_method",
        ),
        minimum_population=_positive_int(raw, "minimum_population", 1),
        minimum_outage_duration_minutes=_non_negative_int(
            raw, "minimum_outage_duration_minutes", 0
        ),
        maximum_outage_duration_minutes=_positive_int(raw, "maximum_outage_duration_minutes", 1440),
        sustained_interruption_threshold_minutes=_positive_int(
            raw, "sustained_interruption_threshold_minutes", 5
        ),
        restoration_target_minutes=_positive_int(raw, "restoration_target_minutes", 180),
        kpi_precision=_positive_int(raw, "kpi_precision", 6),
        score_direction=_choice(
            _string(raw, "score_direction", "higher_is_better"),
            {"higher_is_better"},
            "score_direction",
        ),
        component_weights=_weights(raw),
        benchmark_method=_choice(
            _string(raw, "benchmark_method", "peer_median"),
            SUPPORTED_BENCHMARK_METHODS,
            "benchmark_method",
        ),
        benchmark_scope=_choice(
            _string(raw, "benchmark_scope", "entity_type"),
            {"entity_type", "system"},
            "benchmark_scope",
        ),
        reliability_band_thresholds=_bands(raw),
        minimum_data_completeness=_rate(raw, "minimum_data_completeness", 0.5),
        schema_version=_string(raw, "schema_version", "7.0.0"),
        run_id_strategy=_choice(
            _string(raw, "run_id_strategy", "timestamp"),
            {"timestamp", "deterministic"},
            "run_id_strategy",
        ),
        max_reason_codes=_positive_int(raw, "max_reason_codes", 5),
        entity_id=str(raw["entity_id"]) if raw.get("entity_id") not in (None, "") else None,
        profile=str(raw.get("profile", "default")),
    )
    _validate(config)
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Reliability config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Reliability config must contain a mapping.")
    return raw


def _timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field_name} must be an ISO-8601 timestamp string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigurationError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    return parsed.astimezone(UTC)


def _aggregation_levels(raw: dict[str, Any]) -> tuple[AggregationLevel, ...]:
    value = raw.get("aggregation_levels", ["grid_region", "substation", "feeder"])
    if not isinstance(value, list) or not value:
        raise ConfigurationError("aggregation_levels must be a non-empty list.")
    try:
        return tuple(AggregationLevel(str(item)) for item in value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in AggregationLevel)
        raise ConfigurationError(f"aggregation_levels must contain: {allowed}.") from exc


def _period_frequency(raw: dict[str, Any]) -> PeriodFrequency:
    value = _string(raw, "period_frequency", "full")
    try:
        return PeriodFrequency(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in PeriodFrequency)
        raise ConfigurationError(f"period_frequency must be one of: {allowed}.") from exc


def _safe_path(raw: dict[str, Any], key: str, default: str) -> Path:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _weights(raw: dict[str, Any]) -> dict[str, float]:
    value = raw.get("component_weights")
    required = {
        "interruption_frequency",
        "interruption_duration",
        "restoration",
        "availability",
        "severe_weather_resilience",
        "equipment_outage",
        "data_completeness",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ConfigurationError("component_weights must contain the required components.")
    weights = {key: _mapping_rate(value, key) for key in required}
    if abs(sum(weights.values()) - 1.0) > 0.001:
        raise ConfigurationError("component_weights must sum to 1.0.")
    return dict(sorted(weights.items()))


def _bands(raw: dict[str, Any]) -> dict[str, float]:
    value = raw.get("reliability_band_thresholds")
    if not isinstance(value, dict):
        raise ConfigurationError("reliability_band_thresholds must be a mapping.")
    bands = {
        "weak_max": _mapping_rate_100(value, "weak_max"),
        "watch_max": _mapping_rate_100(value, "watch_max"),
        "stable_max": _mapping_rate_100(value, "stable_max"),
    }
    if not bands["weak_max"] < bands["watch_max"] < bands["stable_max"]:
        raise ConfigurationError("reliability_band_thresholds must be ordered.")
    return bands


def _validate(config: ReliabilityConfig) -> None:
    if config.assessment_start >= config.assessment_end:
        raise ConfigurationError("assessment_start must be before assessment_end.")
    if config.minimum_outage_duration_minutes > config.maximum_outage_duration_minutes:
        raise ConfigurationError("minimum duration cannot exceed maximum duration.")
    if config.sustained_interruption_threshold_minutes > config.maximum_outage_duration_minutes:
        raise ConfigurationError("sustained threshold cannot exceed maximum duration.")
    if not config.include_planned_outages and not config.include_unplanned_outages:
        raise ConfigurationError("At least one outage type must be included.")


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


def _non_negative_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value < 0:
        raise ConfigurationError(f"{key} must be non-negative.")
    return value


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


def _mapping_rate(raw: dict[Any, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


def _mapping_rate_100(raw: dict[Any, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 100:
        raise ConfigurationError(f"{key} must be between 0 and 100.")
    return float(value)


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value
