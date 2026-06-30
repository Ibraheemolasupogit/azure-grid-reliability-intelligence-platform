"""Leakage-safe feature construction."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta

from grid_reliability.forecasting.config import ForecastingConfig
from grid_reliability.forecasting.models import FeatureRow, ForecastingError, TimeSeriesPoint


def build_feature_rows(
    points: list[TimeSeriesPoint], config: ForecastingConfig
) -> list[FeatureRow]:
    by_entity: dict[str, list[TimeSeriesPoint]] = defaultdict(list)
    for point in points:
        by_entity[point.entity_id].append(point)
    rows: list[FeatureRow] = []
    required_history = max(
        max(config.lag_intervals, default=0) if config.include_lag_features else 0,
        max(config.rolling_windows, default=1) - 1,
    )
    step = timedelta(minutes=config.timestamp_frequency_minutes)
    for entity_id, entity_points in sorted(by_entity.items()):
        ordered = sorted(entity_points, key=lambda point: point.timestamp)
        if len(ordered) < config.minimum_history_intervals:
            raise ForecastingError(
                f"Entity {entity_id} has {len(ordered)} intervals; "
                f"requires {config.minimum_history_intervals}."
            )
        timestamp_index = {point.timestamp: index for index, point in enumerate(ordered)}
        for origin_index, origin in enumerate(ordered):
            if origin_index < required_history:
                continue
            for horizon in config.forecast_horizons:
                forecast_timestamp = origin.timestamp + step * horizon
                target_index = timestamp_index.get(forecast_timestamp)
                if target_index is None:
                    continue
                features = _features_for_origin(ordered, origin_index, config)
                rows.append(
                    FeatureRow(
                        entity_type=origin.entity_type,
                        entity_id=origin.entity_id,
                        grid_region=origin.grid_region,
                        forecast_origin=origin.timestamp,
                        forecast_timestamp=forecast_timestamp,
                        forecast_horizon_intervals=horizon,
                        target_name=origin.target_name,
                        target_unit=origin.target_unit,
                        actual_value=ordered[target_index].target_value,
                        features=features,
                        imputed=origin.imputed or ordered[target_index].imputed,
                    )
                )
    if not rows:
        raise ForecastingError("No forecastable rows after feature construction.")
    return sorted(
        rows,
        key=lambda row: (
            row.forecast_timestamp,
            row.entity_id,
            row.forecast_horizon_intervals,
        ),
    )


def feature_names(rows: list[FeatureRow]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        names.update(row.features)
    return sorted(names)


def feature_matrix(rows: list[FeatureRow], names: list[str]) -> list[list[float]]:
    return [[float(row.features.get(name, 0.0)) for name in names] for row in rows]


def target_vector(rows: list[FeatureRow]) -> list[float]:
    return [row.actual_value for row in rows]


def _features_for_origin(
    points: list[TimeSeriesPoint],
    origin_index: int,
    config: ForecastingConfig,
) -> dict[str, float]:
    origin = points[origin_index]
    features: dict[str, float] = {
        "target_latest": origin.target_value,
        "contributing_records": float(origin.contributing_records),
        "imputed_indicator": 1.0 if origin.imputed else 0.0,
    }
    if origin.coverage_ratio is not None:
        features["coverage_ratio"] = origin.coverage_ratio
    if config.include_calendar_features:
        hour_angle = origin.timestamp.hour / 24 * math.tau
        weekday_angle = origin.timestamp.weekday() / 7 * math.tau
        features.update(
            {
                "hour": float(origin.timestamp.hour),
                "day_of_week": float(origin.timestamp.weekday()),
                "is_weekend": 1.0 if origin.timestamp.weekday() >= 5 else 0.0,
                "month": float(origin.timestamp.month),
                "day_of_year": float(origin.timestamp.timetuple().tm_yday),
                "hour_sin": math.sin(hour_angle),
                "hour_cos": math.cos(hour_angle),
                "weekday_sin": math.sin(weekday_angle),
                "weekday_cos": math.cos(weekday_angle),
            }
        )
    if config.include_lag_features:
        for lag in config.lag_intervals:
            lag_index = origin_index - lag + 1
            if lag_index >= 0:
                features[f"lag_{lag}"] = points[lag_index].target_value
    for window in config.rolling_windows:
        start = origin_index - window + 1
        if start < 0:
            continue
        values = [point.target_value for point in points[start : origin_index + 1]]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        features[f"rolling_mean_{window}"] = mean
        features[f"rolling_std_{window}"] = math.sqrt(variance)
        features[f"rolling_min_{window}"] = min(values)
        features[f"rolling_max_{window}"] = max(values)
    if config.include_weather_features:
        for name, value in sorted(origin.weather.items()):
            features[name] = float(value)
    return features
