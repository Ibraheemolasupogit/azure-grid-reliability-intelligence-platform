"""Contract field parsing and plausible ranges."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode

PLAUSIBLE_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "smart_meter_events": {
        "reading_interval_minutes": (1, 1440),
        "active_energy_kwh": (0, 10000),
        "reactive_energy_kvarh": (0, 10000),
        "voltage_v": (100, 300),
        "current_a": (0, 10000),
        "power_factor": (0, 1),
        "frequency_hz": (45, 55),
    },
    "substation_events": {
        "load_mw": (0, 10000),
        "capacity_mva": (0.001, 10000),
        "utilisation_pct": (0, 150),
        "voltage_kv": (0.1, 1000),
        "frequency_hz": (45, 55),
        "transformer_temperature_c": (-50, 160),
        "oil_temperature_c": (-50, 160),
        "ambient_temperature_c": (-50, 60),
    },
    "weather_data": {
        "temperature_c": (-50, 60),
        "feels_like_c": (-70, 70),
        "humidity_pct": (0, 100),
        "wind_speed_mps": (0, 80),
        "wind_gust_mps": (0, 100),
        "precipitation_mm": (0, 500),
        "pressure_hpa": (850, 1100),
    },
    "asset_inventory": {
        "expected_life_years": (1, 100),
        "rated_capacity": (0, 100000),
    },
    "maintenance_logs": {
        "downtime_minutes": (0, 100000),
        "maintenance_cost_gbp": (0, 10000000),
    },
    "outage_history": {
        "duration_minutes": (0, 100000),
        "customers_interrupted": (0, 10000000),
        "estimated_load_lost_mw": (0, 10000),
    },
}


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def parse_date(value: Any) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError("date must be a non-empty string")
    return date.fromisoformat(value)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    raise ValueError("boolean value expected")


def parse_field(value: Any, field_type: str) -> Any:
    if field_type == "string":
        if isinstance(value, str):
            return value
        raise ValueError("string value expected")
    if field_type == "integer":
        if isinstance(value, bool):
            raise ValueError("integer value expected")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            return int(value)
        raise ValueError("integer value expected")
    if field_type == "number":
        if isinstance(value, bool):
            raise ValueError("number value expected")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("finite number expected")
        return parsed
    if field_type == "boolean":
        return parse_bool(value)
    if field_type == "timestamp":
        return parse_timestamp(value)
    if field_type == "date":
        return parse_date(value)
    raise ValueError(f"unsupported field type {field_type}")


def range_issue(
    *,
    dataset_name: str,
    field_name: str,
    record_number: int | None,
    record_key: str | None,
    value: float,
    lower: float,
    upper: float,
) -> ValidationIssue | None:
    if lower <= value <= upper:
        return None
    return ValidationIssue(
        IssueCode.VALUE_OUT_OF_RANGE,
        Severity.ERROR,
        dataset_name,
        f"{field_name} is outside the documented plausible range.",
        field_name=field_name,
        record_number=record_number,
        record_key=record_key,
        observed_value=value,
        expected_rule=f"{lower} <= value <= {upper}",
    )
