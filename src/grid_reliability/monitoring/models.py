"""Typed records for local monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any


class MonitoringError(Exception):
    """Raised when monitoring inputs cannot be processed."""


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    HEALTHY_WITH_WARNINGS = "HEALTHY_WITH_WARNINGS"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    SUPPRESSED = "SUPPRESSED"


@dataclass(frozen=True)
class ComponentRun:
    component_name: str
    run_id: str
    run_status: str
    run_timestamp: datetime | None
    assessment_start: datetime | None
    assessment_end: datetime | None
    input_record_count: int | None
    output_record_count: int | None
    invalid_record_count: int | None
    warning_count: int | None
    error_count: int | None
    primary_metric_name: str | None
    primary_metric_value: float | None
    manifest_path: str | None
    metrics_path: str | None
    schema_version: str | None
    synthetic_data_flag: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    source_paths: tuple[str, ...] = ()
    malformed: bool = False


@dataclass(frozen=True)
class MonitoringRecord:
    component_name: str
    source_run_id: str
    scope_type: str
    scope_id: str
    monitor_type: str
    metric_name: str
    metric_value: float | str | None
    metric_unit: str
    baseline_value: float | str | None
    threshold: float | str | None
    status: HealthStatus
    severity: Severity
    reason_code: str
    sample_size: int | None = None


@dataclass(frozen=True)
class AlertEvaluation:
    alert_id: str
    component_name: str
    source_run_id: str
    scope_type: str
    scope_id: str
    metric_name: str
    observed_value: float | str | None
    threshold: float | str | None
    comparison: str
    severity: Severity
    alert_status: AlertStatus
    suppressed: bool
    suppression_reason: str | None
    reason_code: str
    message: str


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
