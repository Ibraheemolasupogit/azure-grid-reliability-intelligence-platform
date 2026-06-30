"""Configuration loading for local asset-health analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root

SUPPORTED_ASSET_TYPES = {
    "primary_substation",
    "secondary_substation",
    "transformer",
    "circuit_breaker",
    "feeder",
    "switchgear",
    "protection_relay",
    "smart_meter",
}
SUPPORTED_SCORE_DIRECTIONS = {"higher_is_better"}
SUPPORTED_MISSING_POLICIES = {"neutral", "penalize"}
COMPONENT_NAMES = (
    "age",
    "inspection",
    "maintenance",
    "telemetry_stress",
    "alarm",
    "outage",
)


@dataclass(frozen=True)
class AssetHealthConfig:
    interim_root: Path
    output_root: Path
    report_root: Path
    assessment_timestamp: datetime
    included_asset_types: tuple[str, ...]
    minimum_data_completeness: float
    lookback_days_maintenance: int
    lookback_days_telemetry: int
    lookback_days_outages: int
    health_score_direction: str
    health_band_thresholds: dict[str, float]
    priority_thresholds: dict[str, float]
    component_weights: dict[str, float]
    missing_data_policy: str
    criticality_mapping: dict[str, int]
    status_mapping: dict[str, int]
    schema_version: str
    run_id_strategy: str
    max_reason_codes: int
    asset_id: str | None = None
    asset_type: str | None = None
    profile: str = "default"


def load_asset_health_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    interim_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    assessment_timestamp: str | None = None,
    asset_id: str | None = None,
    asset_type: str | None = None,
) -> AssetHealthConfig:
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
    if assessment_timestamp is not None:
        raw["assessment_timestamp"] = assessment_timestamp
    if asset_id is not None:
        raw["asset_id"] = asset_id
    if asset_type is not None:
        raw["asset_type"] = asset_type

    included = _string_tuple(raw, "included_asset_types")
    unsupported = sorted(set(included) - SUPPORTED_ASSET_TYPES)
    if unsupported:
        raise ConfigurationError(f"Unsupported asset type(s): {', '.join(unsupported)}")
    selected_asset_type = raw.get("asset_type")
    if selected_asset_type not in (None, "") and str(selected_asset_type) not in included:
        raise ConfigurationError("asset_type filter must be included in included_asset_types.")

    config = AssetHealthConfig(
        interim_root=_safe_relative_path(raw, "interim_root", "data/interim"),
        output_root=_safe_relative_path(raw, "output_root", "outputs/asset_health"),
        report_root=_safe_relative_path(raw, "report_root", "reports/asset_health"),
        assessment_timestamp=_timestamp(raw.get("assessment_timestamp")),
        included_asset_types=included,
        minimum_data_completeness=_rate(raw, "minimum_data_completeness", 0.4),
        lookback_days_maintenance=_positive_int(raw, "lookback_days_maintenance", 365),
        lookback_days_telemetry=_positive_int(raw, "lookback_days_telemetry", 90),
        lookback_days_outages=_positive_int(raw, "lookback_days_outages", 365),
        health_score_direction=_choice(
            str(raw.get("health_score_direction", "higher_is_better")),
            SUPPORTED_SCORE_DIRECTIONS,
            "health_score_direction",
        ),
        health_band_thresholds=_thresholds(raw, "health_band_thresholds"),
        priority_thresholds=_thresholds(raw, "priority_thresholds"),
        component_weights=_weights(raw),
        missing_data_policy=_choice(
            str(raw.get("missing_data_policy", "neutral")),
            SUPPORTED_MISSING_POLICIES,
            "missing_data_policy",
        ),
        criticality_mapping=_int_mapping(raw, "criticality_mapping"),
        status_mapping=_int_mapping(raw, "status_mapping"),
        schema_version=str(raw.get("schema_version", "5.0.0")),
        run_id_strategy=str(raw.get("run_id_strategy", "timestamp")),
        max_reason_codes=_positive_int(raw, "max_reason_codes", 5),
        asset_id=str(raw["asset_id"]) if raw.get("asset_id") not in (None, "") else None,
        asset_type=str(selected_asset_type) if selected_asset_type not in (None, "") else None,
        profile=str(raw.get("profile", "default")),
    )
    if config.run_id_strategy not in {"timestamp", "deterministic"}:
        raise ConfigurationError("run_id_strategy must be timestamp or deterministic.")
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Asset-health config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Asset-health config must contain a mapping.")
    return raw


def _safe_relative_path(raw: dict[str, Any], key: str, default: str) -> Path:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("assessment_timestamp must be an ISO-8601 string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigurationError("assessment_timestamp must be valid ISO-8601.") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ConfigurationError(f"{key} must be a non-empty list of strings.")
    return tuple(value)


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value


def _weights(raw: dict[str, Any]) -> dict[str, float]:
    value = raw.get("component_weights")
    if not isinstance(value, dict):
        raise ConfigurationError("component_weights must be a mapping.")
    weights: dict[str, float] = {}
    for name in COMPONENT_NAMES:
        item = value.get(name)
        if not isinstance(item, int | float) or not 0 <= float(item) <= 1:
            raise ConfigurationError(f"component weight {name} must be between zero and one.")
        weights[name] = float(item)
    if abs(sum(weights.values()) - 1.0) > 0.001:
        raise ConfigurationError("component_weights must sum to 1.0.")
    return weights


def _thresholds(raw: dict[str, Any], key: str) -> dict[str, float]:
    value = raw.get(key)
    if not isinstance(value, dict) or not value:
        raise ConfigurationError(f"{key} must be a mapping.")
    thresholds: dict[str, float] = {}
    previous = -1.0
    for name, threshold in value.items():
        if not isinstance(threshold, int | float) or not 0 <= float(threshold) <= 100:
            raise ConfigurationError(f"{key}.{name} must be between 0 and 100.")
        current = float(threshold)
        if current < previous:
            raise ConfigurationError(f"{key} thresholds must be ordered ascending.")
        thresholds[str(name)] = current
        previous = current
    return thresholds


def _int_mapping(raw: dict[str, Any], key: str) -> dict[str, int]:
    value = raw.get(key)
    if not isinstance(value, dict) or not value:
        raise ConfigurationError(f"{key} must be a mapping.")
    result: dict[str, int] = {}
    for name, score in value.items():
        if not isinstance(score, int):
            raise ConfigurationError(f"{key}.{name} must be an integer.")
        result[str(name)] = score
    return result
