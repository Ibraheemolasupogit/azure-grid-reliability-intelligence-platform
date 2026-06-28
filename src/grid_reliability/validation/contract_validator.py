"""Contract-driven record validation and normalisation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from grid_reliability.ingestion.records import IngestionRecord
from grid_reliability.validation.field_rules import PLAUSIBLE_RANGES, parse_field, range_issue
from grid_reliability.validation.models import RecordValidationResult, Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


def _serialise_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _record_key(record: dict[str, Any], contract: dict[str, Any]) -> str | None:
    primary_key = contract.get("primary_key")
    if isinstance(primary_key, list):
        values = [record.get(str(field)) for field in primary_key]
        return "|".join(str(value) for value in values) if all(values) else None
    if isinstance(primary_key, str):
        value = record.get(primary_key)
        return str(value) if value not in (None, "") else None
    return None


def validate_record_contract(
    ingestion_record: IngestionRecord,
    contract: dict[str, Any],
) -> RecordValidationResult:
    """Validate one parsed record against a YAML data contract."""
    issues = list(ingestion_record.parse_issues)
    if ingestion_record.parsed_record is None:
        return RecordValidationResult(None, issues)

    dataset_name = ingestion_record.dataset_name
    raw = ingestion_record.parsed_record
    normalised: dict[str, Any] = {}
    fields = contract["fields"]
    field_names = [str(field["name"]) for field in fields]

    for unexpected in sorted(set(raw) - set(field_names)):
        issues.append(
            ValidationIssue(
                IssueCode.UNEXPECTED_FIELD,
                Severity.WARNING,
                dataset_name,
                "Field is not present in the active contract.",
                field_name=unexpected,
                record_number=ingestion_record.source_record_number,
                observed_value=unexpected,
            )
        )

    record_key = _record_key(raw, contract)
    for field in fields:
        field_name = str(field["name"])
        field_type = str(field["type"])
        required = bool(field.get("required", False))
        raw_value = raw.get(field_name)
        if raw_value in (None, ""):
            if required:
                issues.append(
                    ValidationIssue(
                        IssueCode.REQUIRED_FIELD_MISSING,
                        Severity.ERROR,
                        dataset_name,
                        "Required field is missing or blank.",
                        field_name=field_name,
                        record_number=ingestion_record.source_record_number,
                        record_key=record_key,
                        expected_rule="required non-null value",
                    )
                )
            else:
                normalised[field_name] = None
            continue
        try:
            parsed = parse_field(raw_value, field_type)
        except (TypeError, ValueError):
            code = (
                IssueCode.INVALID_TIMESTAMP
                if field_type == "timestamp"
                else IssueCode.INVALID_DATE
                if field_type == "date"
                else IssueCode.INVALID_DATA_TYPE
            )
            issues.append(
                ValidationIssue(
                    code,
                    Severity.ERROR,
                    dataset_name,
                    f"{field_name} could not be parsed as {field_type}.",
                    field_name=field_name,
                    record_number=ingestion_record.source_record_number,
                    record_key=record_key,
                    observed_value=raw_value,
                    expected_rule=field_type,
                )
            )
            continue
        allowed_values = field.get("allowed_values")
        if allowed_values is not None and parsed not in allowed_values:
            issues.append(
                ValidationIssue(
                    IssueCode.INVALID_CATEGORY,
                    Severity.ERROR,
                    dataset_name,
                    "Value is outside contract allowed_values.",
                    field_name=field_name,
                    record_number=ingestion_record.source_record_number,
                    record_key=record_key,
                    observed_value=parsed,
                    expected_rule=", ".join(str(value) for value in allowed_values),
                )
            )
        if field_name == "schema_version" and parsed != contract["schema_version"]:
            issues.append(
                ValidationIssue(
                    IssueCode.SCHEMA_VERSION_MISMATCH,
                    Severity.ERROR,
                    dataset_name,
                    "Record schema_version differs from the contract.",
                    field_name=field_name,
                    record_number=ingestion_record.source_record_number,
                    record_key=record_key,
                    observed_value=parsed,
                    expected_rule=str(contract["schema_version"]),
                )
            )
        if isinstance(parsed, int | float) and field_name in PLAUSIBLE_RANGES.get(dataset_name, {}):
            lower, upper = PLAUSIBLE_RANGES[dataset_name][field_name]
            issue = range_issue(
                dataset_name=dataset_name,
                field_name=field_name,
                record_number=ingestion_record.source_record_number,
                record_key=record_key,
                value=float(parsed),
                lower=lower,
                upper=upper,
            )
            if issue:
                issues.append(issue)
        normalised[field_name] = _serialise_value(parsed)

    for field in field_names:
        normalised.setdefault(field, None)
    normalised["_ingestion"] = {
        "dataset_name": ingestion_record.dataset_name,
        "source_file": ingestion_record.source_file,
        "source_record_number": ingestion_record.source_record_number,
        "ingestion_run_id": ingestion_record.ingestion_run_id,
        "ingested_at": ingestion_record.ingested_at.isoformat().replace("+00:00", "Z"),
    }
    ordered = {field: normalised[field] for field in field_names}
    ordered["_ingestion"] = normalised["_ingestion"]
    return RecordValidationResult(ordered, issues)
