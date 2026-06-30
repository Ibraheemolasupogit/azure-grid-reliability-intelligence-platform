"""Time-series alignment and aggregation for forecasting."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from grid_reliability.forecasting.config import ForecastingConfig
from grid_reliability.forecasting.models import (
    AggregationLevel,
    ForecastingError,
    MissingIntervalPolicy,
    TargetSource,
    TimeSeriesPoint,
)


def parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ForecastingError("Timestamp must be a non-empty ISO-8601 string.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def aggregate_series(
    records: dict[str, list[dict[str, Any]]],
    config: ForecastingConfig,
) -> tuple[list[TimeSeriesPoint], dict[str, int]]:
    if config.target_source == TargetSource.SMART_METER_EVENTS:
        points = _aggregate_smart_meter(records[config.target_source.value], config)
    else:
        points = _aggregate_substation(records[config.target_source.value], config)
    if config.include_weather_features and "weather_data" in records:
        points = _attach_weather(points, records["weather_data"])
    aligned, missing_counts = align_missing_intervals(points, config)
    if config.entity_id:
        aligned = [point for point in aligned if point.entity_id == config.entity_id]
        if not aligned:
            raise ForecastingError(f"No eligible series for entity_id={config.entity_id}.")
    return sorted(aligned, key=lambda point: (point.entity_id, point.timestamp)), missing_counts


def _aggregate_smart_meter(
    records: list[dict[str, Any]],
    config: ForecastingConfig,
) -> list[TimeSeriesPoint]:
    grouped: dict[tuple[datetime, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (parse_utc_timestamp(record["event_timestamp"]), _entity_id(record, config))
        grouped[key].append(record)

    expected_meters = {
        entity_id: max(
            len({str(record["meter_id"]) for record in group})
            for (timestamp, observed_entity), group in grouped.items()
            if timestamp and observed_entity == entity_id
        )
        for entity_id in {entity_id for (_, entity_id) in grouped}
    }
    points: list[TimeSeriesPoint] = []
    for (timestamp, entity_id), group in grouped.items():
        first = group[0]
        meters = {str(record["meter_id"]) for record in group}
        coverage_ratio = (
            len(meters) / expected_meters[entity_id] if expected_meters[entity_id] else None
        )
        points.append(
            TimeSeriesPoint(
                timestamp=timestamp,
                entity_type=config.aggregation_level.value,
                entity_id=entity_id,
                grid_region=str(first["grid_region"]),
                substation_id=str(first["substation_id"]) if first.get("substation_id") else None,
                feeder_id=str(first["feeder_id"]) if first.get("feeder_id") else None,
                target_name="active_energy_kwh",
                target_unit="kWh",
                target_value=sum(float(record["active_energy_kwh"]) for record in group),
                contributing_records=len(meters),
                coverage_ratio=round(coverage_ratio, 6) if coverage_ratio is not None else None,
            )
        )
    return points


def _aggregate_substation(
    records: list[dict[str, Any]],
    config: ForecastingConfig,
) -> list[TimeSeriesPoint]:
    grouped: dict[tuple[datetime, str], list[dict[str, Any]]] = defaultdict(list)
    seen_event_ids: set[str] = set()
    for record in records:
        event_id = str(record["event_id"])
        if event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)
        grouped[
            (parse_utc_timestamp(record["event_timestamp"]), _entity_id(record, config))
        ].append(record)
    points: list[TimeSeriesPoint] = []
    for (timestamp, entity_id), group in grouped.items():
        first = group[0]
        points.append(
            TimeSeriesPoint(
                timestamp=timestamp,
                entity_type=config.aggregation_level.value,
                entity_id=entity_id,
                grid_region=str(first["grid_region"]),
                substation_id=str(first["substation_id"]) if first.get("substation_id") else None,
                feeder_id=str(first["feeder_id"]) if first.get("feeder_id") else None,
                target_name="load_mw",
                target_unit="MW",
                target_value=sum(float(record["load_mw"]) for record in group),
                contributing_records=len(group),
                coverage_ratio=None,
            )
        )
    return points


def _entity_id(record: dict[str, Any], config: ForecastingConfig) -> str:
    if config.aggregation_level == AggregationLevel.GRID_REGION:
        return str(record["grid_region"])
    if config.aggregation_level == AggregationLevel.SUBSTATION:
        return str(record["substation_id"])
    return str(record["feeder_id"])


def _attach_weather(
    points: list[TimeSeriesPoint],
    weather_records: list[dict[str, Any]],
) -> list[TimeSeriesPoint]:
    weather = {
        (str(record["grid_region"]), parse_utc_timestamp(record["weather_timestamp"])): {
            "weather_temperature_c": float(record["temperature_c"]),
            "weather_humidity_pct": float(record["humidity_pct"]),
            "weather_wind_speed_mps": float(record["wind_speed_mps"]),
            "weather_precipitation_mm": float(record["precipitation_mm"]),
            "weather_severe_weather_flag": 1.0 if bool(record["severe_weather_flag"]) else 0.0,
        }
        for record in weather_records
    }
    return [
        TimeSeriesPoint(
            **{
                **point.__dict__,
                "weather": weather.get((point.grid_region, point.timestamp), {}),
            }
        )
        for point in points
    ]


def align_missing_intervals(
    points: list[TimeSeriesPoint],
    config: ForecastingConfig,
) -> tuple[list[TimeSeriesPoint], dict[str, int]]:
    by_entity: dict[str, list[TimeSeriesPoint]] = defaultdict(list)
    for point in points:
        by_entity[point.entity_id].append(point)
    aligned: list[TimeSeriesPoint] = []
    missing_counts = {"missing_intervals": 0, "imputed_intervals": 0, "dropped_intervals": 0}
    step = timedelta(minutes=config.timestamp_frequency_minutes)
    for entity_id, entity_points in sorted(by_entity.items()):
        ordered = sorted(entity_points, key=lambda point: point.timestamp)
        observed = {point.timestamp: point for point in ordered}
        current = ordered[0].timestamp
        end = ordered[-1].timestamp
        last_observed: TimeSeriesPoint | None = None
        while current <= end:
            observed_point = observed.get(current)
            if observed_point is not None:
                aligned.append(observed_point)
                last_observed = observed_point
            else:
                missing_counts["missing_intervals"] += 1
                if config.missing_interval_policy == MissingIntervalPolicy.FAIL:
                    raise ForecastingError(
                        f"Missing interval for {entity_id} at {current.isoformat()}."
                    )
                if config.missing_interval_policy == MissingIntervalPolicy.FORWARD_FILL_WITH_LIMIT:
                    filled = _forward_fill_point(
                        last_observed, current, config.missing_interval_limit
                    )
                    if filled is not None:
                        aligned.append(filled)
                        missing_counts["imputed_intervals"] += 1
                    else:
                        missing_counts["dropped_intervals"] += 1
                else:
                    missing_counts["dropped_intervals"] += 1
            current += step
    return aligned, missing_counts


def _forward_fill_point(
    point: TimeSeriesPoint | None,
    timestamp: datetime,
    limit: int,
) -> TimeSeriesPoint | None:
    if point is None:
        return None
    age_intervals = int((timestamp - point.timestamp).total_seconds() // 3600)
    if age_intervals > limit:
        return None
    return TimeSeriesPoint(
        timestamp=timestamp,
        entity_type=point.entity_type,
        entity_id=point.entity_id,
        grid_region=point.grid_region,
        substation_id=point.substation_id,
        feeder_id=point.feeder_id,
        target_name=point.target_name,
        target_unit=point.target_unit,
        target_value=point.target_value,
        contributing_records=point.contributing_records,
        coverage_ratio=point.coverage_ratio,
        imputed=True,
        weather=point.weather,
    )
