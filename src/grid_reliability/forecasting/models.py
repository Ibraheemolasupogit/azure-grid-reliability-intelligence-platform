"""Forecasting domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ForecastingError(Exception):
    """Raised when forecasting cannot proceed safely."""


class TargetSource(StrEnum):
    SMART_METER_EVENTS = "smart_meter_events"
    SUBSTATION_EVENTS = "substation_events"


class AggregationLevel(StrEnum):
    GRID_REGION = "grid_region"
    SUBSTATION = "substation"
    FEEDER = "feeder"


class MissingIntervalPolicy(StrEnum):
    DROP = "drop"
    FAIL = "fail"
    FORWARD_FILL_WITH_LIMIT = "forward_fill_with_limit"


@dataclass(frozen=True)
class TimeSeriesPoint:
    timestamp: datetime
    entity_type: str
    entity_id: str
    grid_region: str
    substation_id: str | None
    feeder_id: str | None
    target_name: str
    target_unit: str
    target_value: float
    contributing_records: int
    coverage_ratio: float | None
    imputed: bool = False
    weather: dict[str, float | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureRow:
    entity_type: str
    entity_id: str
    grid_region: str
    forecast_origin: datetime
    forecast_timestamp: datetime
    forecast_horizon_intervals: int
    target_name: str
    target_unit: str
    actual_value: float
    features: dict[str, float]
    imputed: bool = False
    data_split: str = "unassigned"


@dataclass(frozen=True)
class PredictionRow:
    forecast_run_id: str
    generated_at: datetime
    entity_type: str
    entity_id: str
    grid_region: str
    forecast_origin: datetime
    forecast_timestamp: datetime
    forecast_horizon_intervals: int
    target_name: str
    target_unit: str
    model_name: str
    predicted_value: float
    prediction_lower: float
    prediction_upper: float
    actual_value: float | None
    data_split: str
    schema_version: str = "4.0.0"


@dataclass(frozen=True)
class MetricResult:
    model_name: str
    entity_id: str
    horizon: int
    aggregation_level: str
    split: str
    mae: float
    rmse: float
    mape: float | None
    smape: float | None
    wape: float | None
    bias: float
    row_count: int
    interval_coverage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "entity_id": self.entity_id,
            "horizon": self.horizon,
            "aggregation_level": self.aggregation_level,
            "split": self.split,
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "smape": self.smape,
            "wape": self.wape,
            "bias": self.bias,
            "row_count": self.row_count,
            "interval_coverage": self.interval_coverage,
        }


@dataclass(frozen=True)
class SplitBoundaries:
    training_start: str | None
    training_end: str | None
    validation_start: str | None
    validation_end: str | None
    test_start: str | None
    test_end: str | None


@dataclass(frozen=True)
class ModelSelection:
    selected_model: str
    selected_metric: str
    selected_metric_value: float
    baseline_model: str
    baseline_metric_value: float | None
    beats_baseline: bool
    excluded_models: dict[str, str]
