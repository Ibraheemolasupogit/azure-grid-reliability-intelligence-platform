"""Configuration loading for synthetic data generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from grid_reliability.common.exceptions import ConfigurationError

SUPPORTED_INTERVALS = {5, 10, 15, 30, 60}


@dataclass(frozen=True)
class SyntheticDataConfig:
    random_seed: int
    start_timestamp: datetime
    end_timestamp: datetime
    timezone: str
    meter_interval_minutes: int
    substation_interval_minutes: int
    number_of_regions: int
    substations_per_region: int
    feeders_per_substation: int
    meters_per_feeder: int
    weather_interval_minutes: int
    target_anomaly_rate: float
    target_missing_reading_rate: float
    output_root: Path
    schema_version: str
    profile: str = "default"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Synthetic data config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Synthetic data config must contain a mapping.")
    return raw


def _parse_timestamp(value: Any, *, field_name: str, timezone_name: str) -> datetime:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field_name} must be an ISO-8601 timestamp string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(f"{field_name} is not a valid ISO-8601 timestamp.") from exc
    timezone = ZoneInfo(timezone_name)
    return parsed.replace(tzinfo=timezone) if parsed.tzinfo is None else parsed.astimezone(timezone)


def _positive_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _rate(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between 0 and 1.")
    return float(value)


def _interval(raw: dict[str, Any], key: str) -> int:
    value = _positive_int(raw, key)
    if value not in SUPPORTED_INTERVALS:
        supported = ", ".join(str(item) for item in sorted(SUPPORTED_INTERVALS))
        raise ConfigurationError(f"{key} must be one of: {supported}.")
    return value


def _validate_timezone(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("timezone must be a non-empty IANA timezone string.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"Unsupported timezone: {value}") from exc
    return value


def _validate_output_root(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("output_root must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError("output_root must be a safe relative path.")
    return path


def load_generation_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    output_root: str | None = None,
    seed: int | None = None,
    start: str | None = None,
    end: str | None = None,
    profile: str | None = None,
) -> SyntheticDataConfig:
    """Load and validate synthetic data generation configuration."""
    root = (project_root or Path.cwd()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    raw = _read_yaml(path)

    timezone = _validate_timezone(raw.get("timezone", "Europe/London"))
    if start is not None:
        raw["start_timestamp"] = start
    if end is not None:
        raw["end_timestamp"] = end

    start_timestamp = _parse_timestamp(
        raw.get("start_timestamp"), field_name="start_timestamp", timezone_name=timezone
    )
    end_timestamp = _parse_timestamp(
        raw.get("end_timestamp"), field_name="end_timestamp", timezone_name=timezone
    )
    if start_timestamp >= end_timestamp:
        raise ConfigurationError("start_timestamp must be before end_timestamp.")

    selected_output_root = _validate_output_root(output_root or raw.get("output_root", "data/raw"))
    selected_seed = int(seed if seed is not None else raw.get("random_seed", 42))

    config = SyntheticDataConfig(
        random_seed=selected_seed,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        timezone=timezone,
        meter_interval_minutes=_interval(raw, "meter_interval_minutes"),
        substation_interval_minutes=_interval(raw, "substation_interval_minutes"),
        number_of_regions=_positive_int(raw, "number_of_regions"),
        substations_per_region=_positive_int(raw, "substations_per_region"),
        feeders_per_substation=_positive_int(raw, "feeders_per_substation"),
        meters_per_feeder=_positive_int(raw, "meters_per_feeder"),
        weather_interval_minutes=_interval(raw, "weather_interval_minutes"),
        target_anomaly_rate=_rate(raw, "target_anomaly_rate"),
        target_missing_reading_rate=_rate(raw, "target_missing_reading_rate"),
        output_root=selected_output_root,
        schema_version=str(raw.get("schema_version", "2.0.0")),
        profile=str(raw.get("profile", "default")),
    )
    return replace(config, profile=profile) if profile else config
