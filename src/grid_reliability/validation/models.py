"""Shared validation result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from grid_reliability.validation.quality_codes import IssueCode


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationIssue:
    issue_code: IssueCode
    severity: Severity
    dataset_name: str
    message: str
    field_name: str | None = None
    record_number: int | None = None
    record_key: str | None = None
    observed_value: Any | None = None
    expected_rule: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_code": self.issue_code.value,
            "severity": self.severity.value,
            "dataset_name": self.dataset_name,
            "field_name": self.field_name,
            "record_number": self.record_number,
            "record_key": self.record_key,
            "message": self.message,
            "observed_value": self.observed_value,
            "expected_rule": self.expected_rule,
        }


@dataclass
class RecordValidationResult:
    normalised_record: dict[str, Any] | None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == Severity.WARNING for issue in self.issues)
