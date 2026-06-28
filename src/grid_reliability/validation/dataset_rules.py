"""Dataset-level validation rules that do not calculate analytics outputs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from grid_reliability.validation.field_rules import parse_timestamp
from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


def primary_key_fields(contract: dict[str, Any]) -> list[str]:
    primary_key = contract.get("primary_key")
    if isinstance(primary_key, list):
        return [str(field) for field in primary_key]
    if isinstance(primary_key, str):
        return [primary_key]
    return []


def key_for(record: dict[str, Any], fields: list[str]) -> str | None:
    values = [record.get(field) for field in fields]
    if not fields or any(value in (None, "") for value in values):
        return None
    return "|".join(str(value) for value in values)


def duplicate_issues(
    dataset_name: str,
    records: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[int, list[ValidationIssue]]:
    issues: dict[int, list[ValidationIssue]] = defaultdict(list)
    key_fields = primary_key_fields(contract)
    seen: dict[str, int] = {}
    for index, record in enumerate(records):
        key = key_for(record, key_fields)
        if key is None:
            continue
        if key in seen:
            issues[index].append(
                ValidationIssue(
                    IssueCode.DUPLICATE_PRIMARY_KEY,
                    Severity.ERROR,
                    dataset_name,
                    "Duplicate primary key detected.",
                    record_key=key,
                    observed_value=key,
                    expected_rule="unique primary key",
                )
            )
            issues[seen[key]].append(
                ValidationIssue(
                    IssueCode.DUPLICATE_PRIMARY_KEY,
                    Severity.ERROR,
                    dataset_name,
                    "Earlier record shares a duplicate primary key.",
                    record_key=key,
                    observed_value=key,
                    expected_rule="unique primary key",
                )
            )
        else:
            seen[key] = index
    return issues


def chronology_issues(
    dataset_name: str,
    records: list[dict[str, Any]],
) -> dict[int, list[ValidationIssue]]:
    issues: dict[int, list[ValidationIssue]] = defaultdict(list)
    for index, record in enumerate(records):
        if dataset_name == "smart_meter_events":
            event = _timestamp(record.get("event_timestamp"))
            ingested = _timestamp(record.get("ingested_at"))
            if event and ingested and ingested < event:
                issues[index].append(
                    _chronology_issue(dataset_name, "ingested_at", ">= event_timestamp")
                )
        elif dataset_name == "substation_events":
            event = _timestamp(record.get("event_timestamp"))
            ingested = _timestamp(record.get("ingested_at"))
            if event and ingested and ingested < event:
                issues[index].append(
                    _chronology_issue(dataset_name, "ingested_at", ">= event_timestamp")
                )
            _utilisation_check(record, index, issues)
        elif dataset_name == "asset_inventory":
            commissioned = _date(record.get("commissioned_date"))
            last = _date(record.get("last_inspection_date"))
            next_due = _date(record.get("next_inspection_due"))
            if commissioned and last and last < commissioned:
                issues[index].append(
                    _chronology_issue(dataset_name, "last_inspection_date", ">= commissioned_date")
                )
            if last and next_due and next_due < last:
                issues[index].append(
                    _chronology_issue(
                        dataset_name, "next_inspection_due", ">= last_inspection_date"
                    )
                )
            if record.get("asset_type") == "primary_substation" and record.get("feeder_id"):
                issues[index].append(
                    ValidationIssue(
                        IssueCode.HIERARCHY_MISMATCH,
                        Severity.ERROR,
                        dataset_name,
                        "Primary substation assets must not carry a feeder_id.",
                        field_name="feeder_id",
                        observed_value=record.get("feeder_id"),
                    )
                )
        elif dataset_name == "maintenance_logs":
            scheduled = _timestamp(record.get("scheduled_start"))
            actual = _timestamp(record.get("actual_start"))
            completed = _timestamp(record.get("completed_at"))
            if actual and scheduled and actual < scheduled:
                issues[index].append(
                    ValidationIssue(
                        IssueCode.CHRONOLOGY_INVALID,
                        Severity.WARNING,
                        dataset_name,
                        "actual_start is before scheduled_start; retained as an "
                        "early-start warning.",
                        field_name="actual_start",
                        expected_rule="documented schedule variance",
                    )
                )
            if completed and actual and completed < actual:
                issues[index].append(
                    _chronology_issue(dataset_name, "completed_at", ">= actual_start")
                )
            if record.get("maintenance_status") == "completed" and (not actual or not completed):
                issues[index].append(
                    ValidationIssue(
                        IssueCode.REQUIRED_FIELD_MISSING,
                        Severity.ERROR,
                        dataset_name,
                        "Completed maintenance requires actual_start and completed_at.",
                        expected_rule="completed records include actual_start and completed_at",
                    )
                )
            if record.get("maintenance_status") in {"scheduled", "cancelled"} and record.get(
                "downtime_minutes"
            ) not in {0, "0"}:
                issues[index].append(
                    ValidationIssue(
                        IssueCode.VALUE_OUT_OF_RANGE,
                        Severity.WARNING,
                        dataset_name,
                        "Scheduled or cancelled work should not report downtime.",
                        field_name="downtime_minutes",
                        observed_value=record.get("downtime_minutes"),
                        expected_rule="0",
                    )
                )
        elif dataset_name == "outage_history":
            start = _timestamp(record.get("outage_start"))
            restored = _timestamp(record.get("restoration_time"))
            duration = record.get("duration_minutes")
            if start and restored and restored <= start:
                issues[index].append(
                    _chronology_issue(dataset_name, "restoration_time", "> outage_start")
                )
            if start and restored and isinstance(duration, int | float):
                observed = int((restored - start).total_seconds() // 60)
                if abs(observed - int(duration)) > 1:
                    issues[index].append(
                        ValidationIssue(
                            IssueCode.DERIVED_VALUE_MISMATCH,
                            Severity.ERROR,
                            dataset_name,
                            "duration_minutes is inconsistent with outage timestamps.",
                            field_name="duration_minutes",
                            observed_value=duration,
                            expected_rule=str(observed),
                        )
                    )
            if bool(record.get("planned_flag")) != (record.get("outage_type") == "planned"):
                issues[index].append(
                    ValidationIssue(
                        IssueCode.DERIVED_VALUE_MISMATCH,
                        Severity.ERROR,
                        dataset_name,
                        "planned_flag is inconsistent with outage_type.",
                        field_name="planned_flag",
                    )
                )
    return issues


def validate_dataset_rules(
    dataset_name: str,
    records: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[int, list[ValidationIssue]]:
    issues = duplicate_issues(dataset_name, records, contract)
    chronology = chronology_issues(dataset_name, records)
    for index, index_issues in chronology.items():
        issues[index].extend(index_issues)
    return issues


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return parse_timestamp(value)
    except ValueError:
        return None


def _date(value: Any) -> Any | None:
    if value in (None, ""):
        return None
    try:
        from datetime import date

        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _chronology_issue(dataset_name: str, field_name: str, expected_rule: str) -> ValidationIssue:
    return ValidationIssue(
        IssueCode.CHRONOLOGY_INVALID,
        Severity.ERROR,
        dataset_name,
        f"{field_name} violates expected chronology.",
        field_name=field_name,
        expected_rule=expected_rule,
    )


def _utilisation_check(
    record: dict[str, Any],
    index: int,
    issues: dict[int, list[ValidationIssue]],
) -> None:
    load = record.get("load_mw")
    capacity = record.get("capacity_mva")
    utilisation = record.get("utilisation_pct")
    if (
        not isinstance(load, int | float)
        or not isinstance(capacity, int | float)
        or not isinstance(utilisation, int | float)
    ):
        return
    if capacity <= 0:
        return
    expected = load / capacity * 100
    if abs(expected - utilisation) > 0.75:
        issues[index].append(
            ValidationIssue(
                IssueCode.DERIVED_VALUE_MISMATCH,
                Severity.ERROR,
                "substation_events",
                "utilisation_pct is inconsistent with load_mw and capacity_mva.",
                field_name="utilisation_pct",
                observed_value=utilisation,
                expected_rule=f"{expected:.2f}",
            )
        )
