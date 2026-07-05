"""Typed models for Power BI-ready reporting outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class ReportingError(Exception):
    """Raised when reporting model generation cannot continue."""


@dataclass(frozen=True)
class ReportingConfig:
    """Validated reporting pipeline configuration."""

    source_roots: tuple[Path, ...]
    output_root: Path
    report_root: Path
    run_id: str
    included_components: tuple[str, ...]
    reporting_timezone: str
    date_dimension_start: str
    date_dimension_end: str
    fact_grains: tuple[str, ...]
    dimension_inclusion: tuple[str, ...]
    default_currency: str
    schema_version: str
    minimum_data_completeness: float
    include_assistant_outputs: bool
    include_monitoring_outputs: bool
    dashboard_pages: tuple[str, ...]
    export_format: str


@dataclass(frozen=True)
class SourceFile:
    """Discovered governed source file."""

    component_name: str
    source_run_id: str
    kind: str
    path: Path
    checksum: str


@dataclass
class SourceData:
    """Loaded source records used by reporting table builders."""

    files: list[SourceFile] = field(default_factory=list)
    csv_tables: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    json_docs: dict[str, dict[str, object]] = field(default_factory=dict)
    jsonl_tables: dict[str, list[dict[str, object]]] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipDefinition:
    """Power BI-style relationship metadata."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str
    cross_filter_direction: str
    active: bool
    description: str


@dataclass
class ReportingTables:
    """Built reporting semantic tables."""

    dimensions: dict[str, list[dict[str, object]]]
    facts: dict[str, list[dict[str, object]]]
    bridges: dict[str, list[dict[str, object]]]
    relationships: list[RelationshipDefinition]
    kpis: list[dict[str, object]]


@dataclass(frozen=True)
class ValidationResult:
    """Relationship and key validation summary."""

    duplicate_key_count: int
    orphan_foreign_key_count: int
    unknown_member_count: int
    null_critical_field_count: int
    failures: tuple[str, ...]


@dataclass(frozen=True)
class ReportingRunResult:
    """Summary of a reporting pipeline run."""

    run_id: str
    output_root: Path
    report_root: Path
    row_counts: dict[str, int]
    validation: ValidationResult
