"""Shared reliability analytics models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any


class ReliabilityError(RuntimeError):
    """Raised when reliability analytics cannot complete."""


class AggregationLevel(StrEnum):
    GRID_REGION = "grid_region"
    SUBSTATION = "substation"
    FEEDER = "feeder"


class PeriodFrequency(StrEnum):
    FULL = "full"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReliabilityBand(StrEnum):
    STRONG = "STRONG"
    STABLE = "STABLE"
    WATCH = "WATCH"
    WEAK = "WEAK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ReliabilityEntity:
    entity_type: AggregationLevel
    entity_id: str
    grid_region: str
    substation_id: str | None = None
    feeder_id: str | None = None


@dataclass(frozen=True)
class PopulationRecord:
    entity: ReliabilityEntity
    observed_meter_count: int
    estimated_customer_population: int
    population_method: str
    population_completeness_ratio: float


@dataclass(frozen=True)
class ClassifiedOutage:
    outage_id: str
    outage_start: datetime
    restoration_time: datetime
    duration_minutes: int
    grid_region: str
    substation_id: str
    feeder_id: str
    primary_asset_id: str
    outage_type: str
    cause_category: str
    customers_interrupted: int
    estimated_load_lost_mw: float
    planned_flag: bool
    severe_weather_related: bool
    equipment_related: bool
    duration_class: str
    assessment_period_start: datetime
    assessment_period_end: datetime


@dataclass(frozen=True)
class ReliabilityResult:
    run_id: str
    assessment_start: datetime
    assessment_end: datetime
    period_start: datetime
    period_end: datetime
    period_frequency: str
    entity: ReliabilityEntity
    population_denominator: int
    population_method: str
    outage_count: int
    planned_outage_count: int
    unplanned_outage_count: int
    severe_weather_outage_count: int
    equipment_failure_outage_count: int
    customer_interruptions: int
    customer_interruption_minutes: float
    total_outage_duration_minutes: float
    mean_outage_duration_minutes: float | None
    median_outage_duration_minutes: float | None
    maximum_outage_duration_minutes: float | None
    estimated_load_lost_mw_total: float
    restoration_within_target_rate: float | None
    merged_outage_minutes: float
    overlap_count: int
    saifi: float | None
    saidi_minutes: float | None
    caidi_minutes: float | None
    asai: float | None
    asui: float | None
    ctaidi_minutes: float | None
    caifi: float | None
    reliability_score: float | None
    reliability_band: ReliabilityBand
    component_scores: dict[str, float]
    component_contributions: dict[str, float]
    reason_codes: tuple[str, ...]
    data_completeness_ratio: float
    schema_version: str

    def primary_reason_code(self) -> str:
        return self.reason_codes[0] if self.reason_codes else ""


ReasonDescription: dict[str, str] = {
    "HIGH_INTERRUPTION_FREQUENCY": "SAIFI is elevated for the assessed entity and period.",
    "HIGH_INTERRUPTION_DURATION": "SAIDI is elevated for the assessed entity and period.",
    "LONG_RESTORATION_TIME": "Mean restoration duration exceeds the configured target.",
    "LOW_SERVICE_AVAILABILITY": "ASAI is below the configured strong-service threshold.",
    "REPEATED_UNPLANNED_OUTAGES": "More than one unplanned outage is present.",
    "SEVERE_WEATHER_OUTAGE_EXPOSURE": "Severe-weather-related outage evidence is present.",
    "EQUIPMENT_FAILURE_OUTAGE_CONCENTRATION": "Equipment-failure outage evidence is present.",
    "HIGH_CUSTOMER_INTERRUPTION_VOLUME": "Customer interruption volume exceeds population.",
    "PROLONGED_OUTAGE_EVENT": "At least one outage is classified as prolonged.",
    "PLANNED_OUTAGE_CONCENTRATION": "Planned outages are present in the period.",
    "IMPROVING_SAIDI_TREND": "SAIDI improved versus the previous period.",
    "IMPROVING_SAIFI_TREND": "SAIFI improved versus the previous period.",
    "STRONG_SERVICE_AVAILABILITY": "ASAI is close to one.",
    "NO_UNPLANNED_OUTAGES": "No unplanned outages are present.",
    "INSUFFICIENT_POPULATION_DATA": "Population denominator is unavailable or below minimum.",
    "INSUFFICIENT_OUTAGE_HISTORY": "No outage events are available for comparison.",
    "LOW_DATA_COMPLETENESS": "Population or optional evidence is incomplete.",
}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return value
