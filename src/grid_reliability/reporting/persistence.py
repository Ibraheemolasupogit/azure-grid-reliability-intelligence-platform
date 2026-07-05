"""Persistence for reporting semantic outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from grid_reliability.reporting.models import (
    ReportingConfig,
    ReportingRunResult,
    ReportingTables,
    SourceData,
    ValidationResult,
)


def write_reporting_outputs(
    project_root: Path,
    config_path: Path,
    config: ReportingConfig,
    sources: SourceData,
    tables: ReportingTables,
    validation: ValidationResult,
) -> ReportingRunResult:
    """Write dimensions, facts, bridges, semantic metadata, manifest, and metrics."""

    run_root = project_root / config.output_root / config.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}

    for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items():
        output_paths[table_name] = _write_csv(run_root / f"{table_name}.csv", rows)

    relationships = [relationship.__dict__ for relationship in tables.relationships]
    output_paths["relationships"] = _write_json(run_root / "relationships.json", relationships)
    output_paths["kpi_catalogue"] = _write_csv(run_root / "kpi_catalogue.csv", tables.kpis)
    output_paths["metrics"] = _write_json(
        run_root / "metrics.json",
        _metrics(sources, tables, validation, config),
    )
    output_paths["manifest"] = _write_json(
        run_root / "reporting_manifest.json",
        _manifest(project_root, config_path, config, sources, tables, validation, output_paths),
    )

    row_counts = {
        table_name: len(rows)
        for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items()
    }
    return ReportingRunResult(
        config.run_id,
        run_root,
        project_root / config.report_root / config.run_id,
        row_counts,
        validation,
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for column in row:
            if column not in fieldnames:
                fieldnames.append(column)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _metrics(
    sources: SourceData,
    tables: ReportingTables,
    validation: ValidationResult,
    config: ReportingConfig,
) -> dict[str, object]:
    row_counts = {
        table_name: len(rows)
        for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items()
    }
    return {
        "sources_discovered": len(sources.files),
        "sources_loaded": len(sources.csv_tables)
        + len(sources.json_docs)
        + len(sources.jsonl_tables),
        "source_failures": 0,
        "dimensions_created": len(tables.dimensions),
        "facts_created": len(tables.facts),
        "bridge_tables_created": len(tables.bridges),
        "total_rows_by_table": row_counts,
        "duplicate_key_count": validation.duplicate_key_count,
        "orphan_foreign_key_count": validation.orphan_foreign_key_count,
        "unknown_member_count": validation.unknown_member_count,
        "null_critical_field_count": validation.null_critical_field_count,
        "relationship_validation_failures": len(validation.failures),
        "kpi_definitions_created": len(tables.kpis),
        "dashboard_pages_specified": len(config.dashboard_pages),
        "source_run_coverage": _source_runs(sources),
        "data_completeness_summary": _completeness(tables),
    }


def _manifest(
    project_root: Path,
    config_path: Path,
    config: ReportingConfig,
    sources: SourceData,
    tables: ReportingTables,
    validation: ValidationResult,
    output_paths: dict[str, Path],
) -> dict[str, object]:
    return {
        "project_name": "azure-grid-reliability-intelligence-platform",
        "reporting_run_id": config.run_id,
        "component_version": "0.1.0",
        "source_runs": _source_runs(sources),
        "source_files": [str(source.path.relative_to(project_root)) for source in sources.files],
        "source_checksums": {
            str(source.path.relative_to(project_root)): source.checksum for source in sources.files
        },
        "configuration_checksum": _sha256(config_path),
        "dimension_tables": sorted(tables.dimensions),
        "fact_tables": sorted(tables.facts),
        "bridge_tables": sorted(tables.bridges),
        "row_counts": {
            table_name: len(rows)
            for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items()
        },
        "primary_keys": _primary_keys(tables),
        "foreign_keys": [relationship.__dict__ for relationship in tables.relationships],
        "relationship_definitions": [
            relationship.__dict__ for relationship in tables.relationships
        ],
        "kpi_catalogue_checksum": _sha256(output_paths["kpi_catalogue"]),
        "dax_definition_checksum": _optional_sha256(project_root / "dashboard/dax/measures.dax"),
        "output_files": {
            name: str(path.relative_to(project_root)) for name, path in sorted(output_paths.items())
        },
        "output_checksums": {
            name: _sha256(path) for name, path in sorted(output_paths.items()) if name != "manifest"
        },
        "synthetic_data_declaration": (
            "All reporting outputs use fictional synthetic repository-local data."
        ),
        "repository_revision": _repository_revision(project_root),
        "validation_failures": list(validation.failures),
        "limitations": [
            "No .pbix, .pbit, Power BI workspace, Fabric workspace, gateway, "
            "or scheduled refresh is deployed.",
            "CSV outputs and DAX definitions are local Power BI-ready artifacts only.",
            "No Azure, Fabric, or Power BI credentials are used.",
        ],
    }


def _source_runs(sources: SourceData) -> dict[str, list[str]]:
    runs: dict[str, set[str]] = {}
    for source in sources.files:
        if source.component_name == "interim":
            continue
        runs.setdefault(source.component_name, set()).add(source.source_run_id)
    return {component: sorted(values) for component, values in sorted(runs.items())}


def _completeness(tables: ReportingTables) -> dict[str, object]:
    summary: dict[str, object] = {}
    for table_name, rows in tables.facts.items():
        values = [
            float(str(row["data_completeness_ratio"]))
            for row in rows
            if str(row.get("data_completeness_ratio", "")).replace(".", "", 1).isdigit()
        ]
        if values:
            summary[table_name] = {
                "minimum": min(values),
                "maximum": max(values),
                "average": round(sum(values) / len(values), 6),
            }
    return summary


def _primary_keys(tables: ReportingTables) -> dict[str, str]:
    keys: dict[str, str] = {}
    for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items():
        if rows:
            keys[table_name] = next(
                column
                for column in rows[0]
                if column.endswith("_key")
                or column.endswith("_fact_id")
                or column.startswith("bridge_")
            )
    return keys


def _repository_revision(project_root: Path) -> str:
    head = project_root / ".git/HEAD"
    if not head.exists():
        return "unknown"
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = project_root / ".git" / value.removeprefix("ref: ")
        return ref.read_text(encoding="utf-8").strip() if ref.exists() else "unknown"
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _optional_sha256(path: Path) -> str:
    return _sha256(path) if path.exists() else ""


def to_jsonable(value: object) -> Any:
    """Return a JSON-compatible value."""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return value
