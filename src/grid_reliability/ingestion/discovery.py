"""Source discovery driven by data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.ingestion.records import SourceDataset
from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode

SUPPORTED_FORMAT_EXTENSIONS = {"csv": ".csv", "jsonl": ".jsonl"}


@dataclass(frozen=True)
class DiscoveryResult:
    datasets: list[SourceDataset]
    issues: list[ValidationIssue] = field(default_factory=list)
    unexpected_files: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)


def expected_filename(contract: dict[str, Any]) -> str:
    dataset = str(contract["dataset"])
    file_format = str(contract["format"])
    if file_format not in SUPPORTED_FORMAT_EXTENSIONS:
        raise ConfigurationError(f"Unsupported format in contract {dataset}: {file_format}")
    return f"{dataset}{SUPPORTED_FORMAT_EXTENSIONS[file_format]}"


def discover_sources(
    *,
    source_root: Path,
    contracts: dict[str, dict[str, Any]],
    fail_on_missing_dataset: bool,
    manifest_filename: str,
) -> DiscoveryResult:
    """Discover expected source datasets without ingesting unexpected files."""
    issues: list[ValidationIssue] = []
    datasets: list[SourceDataset] = []
    expected_files: set[str] = {manifest_filename}

    for dataset_name, contract in sorted(contracts.items()):
        file_format = str(contract["format"])
        if file_format not in SUPPORTED_FORMAT_EXTENSIONS:
            issues.append(
                ValidationIssue(
                    IssueCode.UNSUPPORTED_FORMAT,
                    Severity.ERROR,
                    dataset_name,
                    f"Unsupported source format: {file_format}",
                    expected_rule="csv or jsonl",
                )
            )
            continue
        filename = expected_filename(contract)
        expected_files.add(filename)
        path = source_root / filename
        if path.is_symlink():
            issues.append(
                ValidationIssue(
                    IssueCode.FILE_UNEXPECTED,
                    Severity.ERROR,
                    dataset_name,
                    "Source dataset is a symbolic link and will not be followed.",
                    observed_value=filename,
                    expected_rule="regular file",
                )
            )
            continue
        if not path.exists():
            issues.append(
                ValidationIssue(
                    IssueCode.FILE_MISSING,
                    Severity.ERROR if fail_on_missing_dataset else Severity.WARNING,
                    dataset_name,
                    f"Required source file missing: {filename}",
                    observed_value=filename,
                )
            )
            continue
        if not path.is_file():
            issues.append(
                ValidationIssue(
                    IssueCode.FILE_UNEXPECTED,
                    Severity.ERROR,
                    dataset_name,
                    f"Source path is not a regular file: {filename}",
                    observed_value=filename,
                )
            )
            continue
        datasets.append(SourceDataset(dataset_name, filename, path, file_format, contract))

    unexpected_files: list[str] = []
    if source_root.exists():
        for item in sorted(source_root.iterdir(), key=lambda value: value.name):
            if item.name.startswith("."):
                continue
            if item.name not in expected_files:
                unexpected_files.append(item.name)
                issues.append(
                    ValidationIssue(
                        IssueCode.FILE_UNEXPECTED,
                        Severity.WARNING,
                        "source_discovery",
                        f"Unexpected file will not be ingested: {item.name}",
                        observed_value=item.name,
                    )
                )
    return DiscoveryResult(datasets=datasets, issues=issues, unexpected_files=unexpected_files)
