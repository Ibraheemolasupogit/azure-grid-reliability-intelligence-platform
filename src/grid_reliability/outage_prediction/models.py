"""Shared models for local outage prediction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any


class OutagePredictionError(RuntimeError):
    """Raised when outage prediction cannot complete."""


class EntityType(StrEnum):
    FEEDER = "feeder"
    SUBSTATION = "substation"
    PRIMARY_ASSET = "primary_asset"


class RiskBand(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class Entity:
    entity_type: EntityType
    entity_id: str
    grid_region: str
    substation_id: str
    feeder_id: str | None = None
    primary_asset_id: str | None = None


@dataclass(frozen=True)
class PanelRow:
    entity: Entity
    observation_timestamp: datetime
    available_history_intervals: int
    expected_history_intervals: int
    data_completeness_ratio: float
    missing_interval_count: int


@dataclass(frozen=True)
class LabelledRow:
    panel: PanelRow
    label: int
    label_window_start: datetime
    label_window_end: datetime
    label_source_outage_id: str | None
    label_linkage: str


@dataclass(frozen=True)
class FeatureRow:
    labelled: LabelledRow
    features: dict[str, float]
    categorical_features: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SplitBoundaries:
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime
    purge_intervals: int


@dataclass(frozen=True)
class SplitRows:
    train: list[FeatureRow]
    validation: list[FeatureRow]
    test: list[FeatureRow]
    boundaries: SplitBoundaries


@dataclass(frozen=True)
class PredictionResult:
    run_id: str
    row: FeatureRow
    model_name: str
    risk_score: float
    risk_band: RiskBand
    predicted_outage_flag: bool
    classification_threshold: float
    data_split: str
    reason_codes: tuple[str, ...]

    def primary_reason_code(self) -> str:
        return self.reason_codes[0] if self.reason_codes else ""


@dataclass(frozen=True)
class ClassificationMetric:
    model_name: str
    split: str
    entity_type: str
    grid_region: str
    prediction_horizon_intervals: int
    row_count: int
    positive_count: int
    negative_count: int
    prevalence: float
    threshold: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float | None
    recall: float | None
    f1: float | None
    specificity: float | None
    balanced_accuracy: float | None
    roc_auc: float | None
    pr_auc: float | None
    brier_score: float | None
    log_loss: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None


@dataclass(frozen=True)
class ModelSelection:
    selected_model: str
    selected_threshold: float
    selection_metric: str
    validation_score: float | None
    baseline_model: str
    baseline_score: float | None
    improvement_over_baseline: float | None
    failed_models: dict[str, str]


ReasonDescription: dict[str, str] = {
    "RECENT_UNPLANNED_OUTAGE": "Entity has a prior unplanned outage inside the lookback window.",
    "REPEATED_OPERATIONAL_ALARMS": "Recent telemetry contains repeated alarm events.",
    "SUSTAINED_HIGH_UTILISATION": "Recent telemetry shows high utilisation.",
    "PEAK_TEMPERATURE_STRESS": "Recent telemetry shows high transformer temperature.",
    "RECENT_OFFLINE_STATE": "Recent telemetry includes offline state.",
    "RECENT_CONSTRAINED_STATE": "Recent telemetry includes constrained state.",
    "SEVERE_WEATHER_EXPOSURE": "Recent or current weather indicates severe weather.",
    "HIGH_WIND_EXPOSURE": "Recent weather includes high wind gusts.",
    "HEAVY_PRECIPITATION_EXPOSURE": "Recent weather includes heavy precipitation.",
    "INSPECTION_OVERDUE": "Entity asset evidence indicates overdue inspection.",
    "RECENT_CORRECTIVE_MAINTENANCE": "Recent corrective maintenance is present.",
    "RECENT_EMERGENCY_MAINTENANCE": "Recent emergency maintenance is present.",
    "DEFERRED_MAINTENANCE": "Deferred maintenance is present.",
    "FOLLOW_UP_WORK_OUTSTANDING": "Maintenance follow-up is outstanding.",
    "AGE_NEAR_EXPECTED_LIFE": "Asset age is near expected life.",
    "AGE_BEYOND_EXPECTED_LIFE": "Asset age exceeds expected life.",
    "POOR_DATA_COMPLETENESS": "Historical feature evidence is incomplete.",
    "LOW_RECENT_STRESS": "Recent telemetry and weather stress are low.",
}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return value
