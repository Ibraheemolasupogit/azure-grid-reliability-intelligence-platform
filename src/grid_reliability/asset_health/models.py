"""Asset-health domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class AssetHealthError(Exception):
    """Raised when asset-health assessment cannot proceed."""


class HealthBand(StrEnum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MaintenancePriority(StrEnum):
    P1_IMMEDIATE_REVIEW = "P1_IMMEDIATE_REVIEW"
    P2_HIGH = "P2_HIGH"
    P3_MEDIUM = "P3_MEDIUM"
    P4_ROUTINE = "P4_ROUTINE"
    DATA_REVIEW_REQUIRED = "DATA_REVIEW_REQUIRED"


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    asset_type: str
    asset_name: str
    grid_region: str
    substation_id: str
    feeder_id: str | None
    commissioned_date: date
    expected_life_years: int
    criticality_tier: str
    operational_status: str
    last_inspection_date: date
    next_inspection_due: date
    rated_capacity: float
    capacity_unit: str
    schema_version: str


@dataclass(frozen=True)
class AssetFeatures:
    asset_age_years: float
    expected_life_years: int
    age_to_expected_life_ratio: float
    remaining_expected_life_years: float
    beyond_expected_life_flag: bool
    days_since_last_inspection: int
    days_until_next_inspection: int
    inspection_overdue_days: int
    inspection_overdue_flag: bool
    maintenance_count: int = 0
    preventive_maintenance_count: int = 0
    corrective_maintenance_count: int = 0
    emergency_maintenance_count: int = 0
    deferred_maintenance_count: int = 0
    cancelled_maintenance_count: int = 0
    days_since_last_completed_maintenance: int | None = None
    maintenance_overdue_flag: bool = False
    total_recent_downtime_minutes: int = 0
    recent_maintenance_cost_gbp: float = 0.0
    follow_up_required_count: int = 0
    telemetry_observation_count: int = 0
    mean_utilisation_pct: float | None = None
    maximum_utilisation_pct: float | None = None
    high_utilisation_event_count: int = 0
    high_utilisation_share: float | None = None
    mean_transformer_temperature_c: float | None = None
    maximum_transformer_temperature_c: float | None = None
    temperature_exceedance_count: int = 0
    temperature_exceedance_share: float | None = None
    alarm_event_count: int = 0
    offline_or_constrained_count: int = 0
    direct_outage_count: int = 0
    contextual_outage_count: int = 0
    direct_unplanned_outage_count: int = 0
    total_outage_duration_minutes: int = 0
    maximum_outage_duration_minutes: int = 0
    customers_interrupted_total: int = 0
    severe_weather_outage_count: int = 0
    equipment_failure_outage_count: int = 0
    days_since_last_direct_outage: int | None = None
    expected_evidence_sources: int = 5
    available_evidence_sources: int = 2
    data_completeness_ratio: float = 0.4
    insufficient_data_flag: bool = False


@dataclass(frozen=True)
class ComponentScores:
    age_component_score: float
    inspection_component_score: float
    maintenance_component_score: float
    telemetry_stress_component_score: float
    alarm_component_score: float
    outage_component_score: float
    missing_components: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, float]:
        return {
            "age_component_score": self.age_component_score,
            "inspection_component_score": self.inspection_component_score,
            "maintenance_component_score": self.maintenance_component_score,
            "telemetry_stress_component_score": self.telemetry_stress_component_score,
            "alarm_component_score": self.alarm_component_score,
            "outage_component_score": self.outage_component_score,
        }


@dataclass(frozen=True)
class AssetHealthResult:
    asset: AssetRecord
    assessment_timestamp: datetime
    features: AssetFeatures
    components: ComponentScores
    health_score: float
    health_band: HealthBand
    maintenance_priority: MaintenancePriority
    reason_codes: tuple[str, ...]
    priority_reason_codes: tuple[str, ...]
    component_contributions: dict[str, float] = field(default_factory=dict)
    schema_version: str = "5.0.0"

    def primary_reason_code(self) -> str:
        return self.reason_codes[0] if self.reason_codes else "NO_MAJOR_ADVERSE_DRIVER"


ReasonDescription: dict[str, str] = {
    "AGE_NEAR_EXPECTED_LIFE": "Asset is approaching its configured expected life.",
    "AGE_BEYOND_EXPECTED_LIFE": "Asset is beyond configured expected life.",
    "INSPECTION_OVERDUE": "Inspection due date is before the assessment timestamp.",
    "MAINTENANCE_DEFERRED": "Recent deferred maintenance exists.",
    "HIGH_CORRECTIVE_MAINTENANCE_SHARE": "Corrective maintenance share is elevated.",
    "RECENT_EMERGENCY_MAINTENANCE": "Recent emergency maintenance exists.",
    "SUSTAINED_HIGH_UTILISATION": "Recent telemetry shows sustained high utilisation.",
    "PEAK_TEMPERATURE_STRESS": "Recent telemetry shows transformer temperature stress.",
    "REPEATED_OPERATIONAL_ALARMS": "Recent telemetry contains repeated alarms.",
    "RECENT_DIRECT_UNPLANNED_OUTAGE": "Asset was the primary asset in a recent unplanned outage.",
    "EQUIPMENT_FAILURE_OUTAGE_HISTORY": "Outage history includes equipment-failure causes.",
    "FOLLOW_UP_WORK_OUTSTANDING": "Maintenance records indicate follow-up work.",
    "INSUFFICIENT_TELEMETRY": "No telemetry context was available in the lookback window.",
    "INSUFFICIENT_MAINTENANCE_HISTORY": "No direct maintenance history was available.",
    "GOOD_RECENT_INSPECTION": "Inspection evidence is current.",
    "LOW_OPERATIONAL_STRESS": "Telemetry stress indicators are low.",
}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value
