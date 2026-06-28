"""Ingestion metrics models and threshold status logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


class RunStatus(StrEnum):
    PASSED = "PASSED"
    PASSED_WITH_WARNINGS = "PASSED_WITH_WARNINGS"
    FAILED_QUALITY_THRESHOLD = "FAILED_QUALITY_THRESHOLD"
    FAILED_MANIFEST = "FAILED_MANIFEST"
    FAILED_CONFIGURATION = "FAILED_CONFIGURATION"
    FAILED_PROCESSING = "FAILED_PROCESSING"


@dataclass
class DatasetMetrics:
    source_records_discovered: int = 0
    records_parsed: int = 0
    valid_records: int = 0
    warning_records: int = 0
    invalid_records: int = 0
    quarantined_records: int = 0
    malformed_records: int = 0
    duplicate_records: int = 0
    contract_violations: int = 0
    relationship_violations: int = 0
    output_record_count: int = 0
    elapsed_processing_seconds: float = 0.0

    @property
    def error_rate(self) -> float:
        if self.source_records_discovered == 0:
            return 0.0
        return self.invalid_records / self.source_records_discovered

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_records_discovered": self.source_records_discovered,
            "records_parsed": self.records_parsed,
            "valid_records": self.valid_records,
            "warning_records": self.warning_records,
            "invalid_records": self.invalid_records,
            "quarantined_records": self.quarantined_records,
            "malformed_records": self.malformed_records,
            "duplicate_records": self.duplicate_records,
            "contract_violations": self.contract_violations,
            "relationship_violations": self.relationship_violations,
            "error_rate": self.error_rate,
            "output_record_count": self.output_record_count,
            "elapsed_processing_seconds": self.elapsed_processing_seconds,
        }


@dataclass
class RunMetrics:
    run_id: str
    datasets: dict[str, DatasetMetrics] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    def status(self, *, maximum_error_rate: float, manifest_failed: bool) -> RunStatus:
        if manifest_failed:
            return RunStatus.FAILED_MANIFEST
        total = self.total_metrics()
        if total.error_rate > maximum_error_rate:
            return RunStatus.FAILED_QUALITY_THRESHOLD
        if (
            any(issue.severity == Severity.WARNING for issue in self.issues)
            or total.warning_records
        ):
            return RunStatus.PASSED_WITH_WARNINGS
        return RunStatus.PASSED

    def total_metrics(self) -> DatasetMetrics:
        total = DatasetMetrics()
        for metrics in self.datasets.values():
            total.source_records_discovered += metrics.source_records_discovered
            total.records_parsed += metrics.records_parsed
            total.valid_records += metrics.valid_records
            total.warning_records += metrics.warning_records
            total.invalid_records += metrics.invalid_records
            total.quarantined_records += metrics.quarantined_records
            total.malformed_records += metrics.malformed_records
            total.duplicate_records += metrics.duplicate_records
            total.contract_violations += metrics.contract_violations
            total.relationship_violations += metrics.relationship_violations
            total.output_record_count += metrics.output_record_count
            total.elapsed_processing_seconds += metrics.elapsed_processing_seconds
        return total

    def to_dict(self, *, status: RunStatus, maximum_error_rate: float) -> dict[str, Any]:
        return {
            "ingestion_run_id": self.run_id,
            "run_status": status.value,
            "maximum_error_rate": maximum_error_rate,
            "totals": self.total_metrics().to_dict(),
            "datasets": {
                dataset: metrics.to_dict() for dataset, metrics in sorted(self.datasets.items())
            },
            "issue_counts_by_code": issue_counts_by_code(self.issues),
            "issue_counts_by_dataset": issue_counts_by_dataset(self.issues),
        }


def issue_counts_by_code(issues: list[ValidationIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.issue_code.value] = counts.get(issue.issue_code.value, 0) + 1
    return dict(sorted(counts.items()))


def issue_counts_by_dataset(issues: list[ValidationIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.dataset_name] = counts.get(issue.dataset_name, 0) + 1
    return dict(sorted(counts.items()))


def classify_issue(metrics: DatasetMetrics, issue: ValidationIssue) -> None:
    if issue.issue_code == IssueCode.MALFORMED_RECORD:
        metrics.malformed_records += 1
    if issue.issue_code == IssueCode.DUPLICATE_PRIMARY_KEY:
        metrics.duplicate_records += 1
    if issue.issue_code in {
        IssueCode.FOREIGN_KEY_NOT_FOUND,
        IssueCode.HIERARCHY_MISMATCH,
    }:
        metrics.relationship_violations += 1
    if issue.issue_code not in {
        IssueCode.FOREIGN_KEY_NOT_FOUND,
        IssueCode.HIERARCHY_MISMATCH,
        IssueCode.MANIFEST_CHECKSUM_MISMATCH,
        IssueCode.MANIFEST_COUNT_MISMATCH,
        IssueCode.MANIFEST_DATASET_MISSING,
        IssueCode.MANIFEST_DATASET_UNEXPECTED,
        IssueCode.MANIFEST_DUPLICATE_ENTRY,
        IssueCode.MANIFEST_MALFORMED,
        IssueCode.MANIFEST_MISSING,
        IssueCode.MANIFEST_SIZE_MISMATCH,
    }:
        metrics.contract_violations += 1
