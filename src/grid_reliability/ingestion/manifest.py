"""Synthetic source manifest verification for ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.ingestion.discovery import expected_filename
from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


@dataclass(frozen=True)
class ManifestVerification:
    manifest: dict[str, Any] | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)


def _loads_manifest(path: Path) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    duplicate_keys: list[str] = []

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                duplicate_keys.append(key)
            seen.add(key)
            result[key] = value
        return result

    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Source manifest could not be read as valid JSON.",
                observed_value=str(exc),
            )
        ]
    issues = [
        ValidationIssue(
            IssueCode.MANIFEST_DUPLICATE_ENTRY,
            Severity.ERROR,
            "manifest",
            f"Manifest contains duplicate key: {key}",
            observed_value=key,
        )
        for key in sorted(set(duplicate_keys))
    ]
    if not isinstance(raw, dict):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Source manifest must be a JSON object.",
                observed_value=type(raw).__name__,
            )
        )
        return None, issues
    return raw, issues


def verify_source_manifest(
    *,
    source_root: Path,
    manifest_filename: str,
    contracts: dict[str, dict[str, Any]],
    require_manifest: bool,
    verify_checksums: bool,
    expected_project_name: str,
) -> ManifestVerification:
    """Validate generation manifest structure and source file integrity."""
    manifest_path = source_root / manifest_filename
    if not manifest_path.exists():
        severity = Severity.ERROR if require_manifest else Severity.WARNING
        return ManifestVerification(
            None,
            [
                ValidationIssue(
                    IssueCode.MANIFEST_MISSING,
                    severity,
                    "manifest",
                    f"Source manifest missing: {manifest_filename}",
                )
            ],
        )

    manifest, issues = _loads_manifest(manifest_path)
    if manifest is None:
        return ManifestVerification(None, issues)

    if manifest.get("project_name") != expected_project_name:
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Manifest project_name does not match configured project.",
                observed_value=manifest.get("project_name"),
                expected_rule=expected_project_name,
            )
        )
    if "fictional synthetic data" not in str(manifest.get("synthetic_data_statement", "")):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Manifest synthetic-data declaration is missing or unexpected.",
            )
        )
    if not isinstance(manifest.get("schema_version"), str):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Manifest schema_version is missing.",
            )
        )

    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_MALFORMED,
                Severity.ERROR,
                "manifest",
                "Manifest datasets must be an object keyed by dataset name.",
            )
        )
        return ManifestVerification(manifest, issues)

    expected_names = set(contracts)
    observed_names = set(str(name) for name in datasets)
    for missing in sorted(expected_names - observed_names):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_DATASET_MISSING,
                Severity.ERROR,
                missing,
                "Required dataset missing from manifest.",
            )
        )
    for unexpected in sorted(observed_names - expected_names):
        issues.append(
            ValidationIssue(
                IssueCode.MANIFEST_DATASET_UNEXPECTED,
                Severity.ERROR,
                str(unexpected),
                "Unexpected dataset listed in manifest.",
                observed_value=unexpected,
            )
        )

    filenames: set[str] = set()
    for dataset_name, contract in sorted(contracts.items()):
        entry = datasets.get(dataset_name)
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        expected = expected_filename(contract)
        if filename in filenames:
            issues.append(
                ValidationIssue(
                    IssueCode.MANIFEST_DUPLICATE_ENTRY,
                    Severity.ERROR,
                    dataset_name,
                    "Duplicate filename listed in manifest.",
                    observed_value=filename,
                )
            )
        if isinstance(filename, str):
            filenames.add(filename)
        if filename != expected:
            issues.append(
                ValidationIssue(
                    IssueCode.MANIFEST_DATASET_UNEXPECTED,
                    Severity.ERROR,
                    dataset_name,
                    "Manifest filename does not match contract-derived filename.",
                    observed_value=filename,
                    expected_rule=expected,
                )
            )
            continue
        file_path = source_root / expected
        if not file_path.exists():
            continue
        if entry.get("file_size_bytes") != file_path.stat().st_size:
            issues.append(
                ValidationIssue(
                    IssueCode.MANIFEST_SIZE_MISMATCH,
                    Severity.ERROR,
                    dataset_name,
                    "Source file size differs from manifest.",
                    observed_value=file_path.stat().st_size,
                    expected_rule=str(entry.get("file_size_bytes")),
                )
            )
        if verify_checksums and entry.get("sha256") != sha256_file(file_path):
            issues.append(
                ValidationIssue(
                    IssueCode.MANIFEST_CHECKSUM_MISMATCH,
                    Severity.ERROR,
                    dataset_name,
                    "Source file SHA-256 differs from manifest.",
                    observed_value=sha256_file(file_path),
                    expected_rule=str(entry.get("sha256")),
                )
            )

    return ManifestVerification(manifest, issues)


def verify_manifest_record_counts(
    manifest: dict[str, Any] | None,
    observed_counts: dict[str, int],
) -> list[ValidationIssue]:
    if manifest is None or not isinstance(manifest.get("datasets"), dict):
        return []
    issues: list[ValidationIssue] = []
    datasets = manifest["datasets"]
    for dataset_name, observed_count in sorted(observed_counts.items()):
        entry = datasets.get(dataset_name)
        if not isinstance(entry, dict):
            continue
        expected_count = entry.get("record_count")
        if expected_count != observed_count:
            issues.append(
                ValidationIssue(
                    IssueCode.MANIFEST_COUNT_MISMATCH,
                    Severity.ERROR,
                    dataset_name,
                    "Parsed source record count differs from manifest.",
                    observed_value=observed_count,
                    expected_rule=str(expected_count),
                )
            )
    return issues
