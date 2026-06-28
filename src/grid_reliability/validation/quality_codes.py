"""Stable data-quality issue code taxonomy for governed ingestion."""

from __future__ import annotations

from enum import StrEnum


class IssueCode(StrEnum):
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    UNEXPECTED_FIELD = "UNEXPECTED_FIELD"
    INVALID_DATA_TYPE = "INVALID_DATA_TYPE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INVALID_DATE = "INVALID_DATE"
    VALUE_OUT_OF_RANGE = "VALUE_OUT_OF_RANGE"
    INVALID_CATEGORY = "INVALID_CATEGORY"
    DUPLICATE_PRIMARY_KEY = "DUPLICATE_PRIMARY_KEY"
    DUPLICATE_NATURAL_KEY = "DUPLICATE_NATURAL_KEY"
    FOREIGN_KEY_NOT_FOUND = "FOREIGN_KEY_NOT_FOUND"
    HIERARCHY_MISMATCH = "HIERARCHY_MISMATCH"
    SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
    MALFORMED_RECORD = "MALFORMED_RECORD"
    EMPTY_FILE = "EMPTY_FILE"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    MANIFEST_MALFORMED = "MANIFEST_MALFORMED"
    MANIFEST_CHECKSUM_MISMATCH = "MANIFEST_CHECKSUM_MISMATCH"
    MANIFEST_COUNT_MISMATCH = "MANIFEST_COUNT_MISMATCH"
    MANIFEST_SIZE_MISMATCH = "MANIFEST_SIZE_MISMATCH"
    MANIFEST_DATASET_MISSING = "MANIFEST_DATASET_MISSING"
    MANIFEST_DATASET_UNEXPECTED = "MANIFEST_DATASET_UNEXPECTED"
    MANIFEST_DUPLICATE_ENTRY = "MANIFEST_DUPLICATE_ENTRY"
    FILE_MISSING = "FILE_MISSING"
    FILE_UNEXPECTED = "FILE_UNEXPECTED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    INCONSISTENT_CSV_ROW = "INCONSISTENT_CSV_ROW"
    CHRONOLOGY_INVALID = "CHRONOLOGY_INVALID"
    DERIVED_VALUE_MISMATCH = "DERIVED_VALUE_MISMATCH"


ISSUE_CODE_DESCRIPTIONS: dict[IssueCode, str] = {
    IssueCode.REQUIRED_FIELD_MISSING: "A non-nullable contract field is missing or blank.",
    IssueCode.UNEXPECTED_FIELD: "A record contains a field outside the active data contract.",
    IssueCode.INVALID_DATA_TYPE: "A field cannot be parsed as its contract data type.",
    IssueCode.INVALID_TIMESTAMP: "A timestamp field is not valid ISO-8601.",
    IssueCode.INVALID_DATE: "A date field is not valid ISO-8601 date format.",
    IssueCode.VALUE_OUT_OF_RANGE: "A numeric or temporal value is outside a plausible range.",
    IssueCode.INVALID_CATEGORY: "A controlled field contains a value outside allowed_values.",
    IssueCode.DUPLICATE_PRIMARY_KEY: "A duplicate primary key was observed in one dataset.",
    IssueCode.DUPLICATE_NATURAL_KEY: "A duplicate natural key was observed in one dataset.",
    IssueCode.FOREIGN_KEY_NOT_FOUND: (
        "A referenced asset, feeder, substation, meter, or region is unknown."
    ),
    IssueCode.HIERARCHY_MISMATCH: "Related hierarchy fields disagree across datasets.",
    IssueCode.SCHEMA_VERSION_MISMATCH: "A record schema_version differs from the contract version.",
    IssueCode.MALFORMED_RECORD: "A source line or row could not be parsed as a record.",
    IssueCode.EMPTY_FILE: "A required dataset file exists but contains no records.",
    IssueCode.MANIFEST_MISSING: "The configured source manifest is required but absent.",
    IssueCode.MANIFEST_MALFORMED: (
        "The source manifest is not valid JSON or lacks required structure."
    ),
    IssueCode.MANIFEST_CHECKSUM_MISMATCH: "A file SHA-256 does not match the manifest entry.",
    IssueCode.MANIFEST_COUNT_MISMATCH: (
        "A parsed source record count does not match the manifest entry."
    ),
    IssueCode.MANIFEST_SIZE_MISMATCH: "A file size does not match the manifest entry.",
    IssueCode.MANIFEST_DATASET_MISSING: "A required dataset is missing from the manifest.",
    IssueCode.MANIFEST_DATASET_UNEXPECTED: (
        "The manifest contains an unexpected dataset or filename."
    ),
    IssueCode.MANIFEST_DUPLICATE_ENTRY: (
        "The manifest contains duplicate dataset or filename entries."
    ),
    IssueCode.FILE_MISSING: "A required source file is missing.",
    IssueCode.FILE_UNEXPECTED: "A source directory contains a file outside the contract catalogue.",
    IssueCode.UNSUPPORTED_FORMAT: "A dataset declares a format not supported by local ingestion.",
    IssueCode.INCONSISTENT_CSV_ROW: "A CSV row has extra or missing columns.",
    IssueCode.CHRONOLOGY_INVALID: "A start/end or lifecycle chronology is inconsistent.",
    IssueCode.DERIVED_VALUE_MISMATCH: "A supplied derived value differs from recomputation.",
}


def documented_issue_codes() -> dict[str, str]:
    """Return the public issue-code documentation as stable strings."""
    return {code.value: description for code, description in ISSUE_CODE_DESCRIPTIONS.items()}
