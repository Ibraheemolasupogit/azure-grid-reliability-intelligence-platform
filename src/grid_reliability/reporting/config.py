"""Configuration loading for the local reporting semantic layer."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.reporting.models import ReportingConfig

SUPPORTED_COMPONENTS = {
    "forecasting",
    "asset_health",
    "outage_prediction",
    "reliability",
    "monitoring",
    "genai",
}
SUPPORTED_EXPORT_FORMATS = {"csv"}
SUPPORTED_FACT_GRAINS = {
    "forecast_entity_timestamp_model",
    "asset_assessment",
    "outage_entity_timestamp_model",
    "reliability_entity_period",
    "monitoring_check",
    "monitoring_alert",
    "assistant_response",
    "maintenance_priority",
}
SUPPORTED_DIMENSIONS = {
    "date",
    "time",
    "grid_region",
    "substation",
    "feeder",
    "asset",
    "model",
    "component_run",
    "alert_reason",
    "metric",
}
DEFAULT_PAGES = (
    "01_executive_overview",
    "02_grid_operations",
    "03_demand_forecasting",
    "04_asset_health",
    "05_outage_risk",
    "06_reliability",
    "07_data_model_monitoring",
    "08_grid_operations_assistant",
    "09_governance_and_lineage",
)


def load_reporting_config(path: Path, *, project_root: Path | None = None) -> ReportingConfig:
    """Load and validate reporting YAML configuration."""

    root = project_root or Path.cwd()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    source_roots = tuple(_safe_path(item, "source_roots") for item in raw.get("source_roots", ()))
    if not source_roots:
        raise ConfigurationError("source_roots must contain at least one path.")

    output_root = _safe_path(raw.get("output_root", "outputs/reporting"), "output_root")
    report_root = _safe_path(raw.get("report_root", "reports/reporting"), "report_root")
    _reject_source_overlap(source_roots, output_root, "output_root")
    _reject_source_overlap(source_roots, report_root, "report_root")

    included_components = tuple(raw.get("included_components", sorted(SUPPORTED_COMPONENTS)))
    unknown_components = sorted(set(included_components) - SUPPORTED_COMPONENTS)
    if unknown_components:
        raise ConfigurationError(f"Unsupported reporting component(s): {unknown_components}")

    export_format = str(raw.get("export_format", "csv"))
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise ConfigurationError(f"Unsupported export_format: {export_format}")

    fact_grains = tuple(raw.get("fact_grains", sorted(SUPPORTED_FACT_GRAINS)))
    unknown_grains = sorted(set(fact_grains) - SUPPORTED_FACT_GRAINS)
    if unknown_grains:
        raise ConfigurationError(f"Unsupported fact_grains: {unknown_grains}")

    dimensions = tuple(raw.get("dimension_inclusion", sorted(SUPPORTED_DIMENSIONS)))
    unknown_dimensions = sorted(set(dimensions) - SUPPORTED_DIMENSIONS)
    if unknown_dimensions:
        raise ConfigurationError(f"Unsupported dimension_inclusion: {unknown_dimensions}")

    start = _date(raw.get("date_dimension_start", "2026-01-01"), "date_dimension_start")
    end = _date(raw.get("date_dimension_end", "2026-01-02"), "date_dimension_end")
    if start > end:
        raise ConfigurationError(
            "date_dimension_start must be before or equal to date_dimension_end."
        )

    minimum = float(raw.get("minimum_data_completeness", 0.0))
    if minimum < 0.0 or minimum > 1.0:
        raise ConfigurationError("minimum_data_completeness must be between 0 and 1.")

    timezone = str(raw.get("reporting_timezone", "UTC"))
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"Unsupported reporting_timezone: {timezone}") from exc

    pages = tuple(raw.get("dashboard_pages", DEFAULT_PAGES))
    if not pages:
        raise ConfigurationError("dashboard_pages must contain at least one page.")

    return ReportingConfig(
        source_roots=tuple((root / item).resolve() for item in source_roots),
        output_root=output_root,
        report_root=report_root,
        run_id=str(raw.get("run_id", "reporting-local")),
        included_components=included_components,
        reporting_timezone=timezone,
        date_dimension_start=start.isoformat(),
        date_dimension_end=end.isoformat(),
        fact_grains=fact_grains,
        dimension_inclusion=dimensions,
        default_currency=str(raw.get("default_currency", "GBP")),
        schema_version=str(raw.get("schema_version", "10.0.0")),
        minimum_data_completeness=minimum,
        include_assistant_outputs=bool(raw.get("include_assistant_outputs", True)),
        include_monitoring_outputs=bool(raw.get("include_monitoring_outputs", True)),
        dashboard_pages=pages,
        export_format=export_format,
    )


def _safe_path(value: object, field_name: str) -> Path:
    text = str(value)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{field_name} must be a safe relative path.")
    return path


def _date(value: object, field_name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigurationError(f"{field_name} must be an ISO date.") from exc


def _reject_source_overlap(source_roots: tuple[Path, ...], target: Path, name: str) -> None:
    target_parts = target.parts
    for source in source_roots:
        if (
            source.parts[: len(target_parts)] == target_parts
            or target_parts[: len(source.parts)] == source.parts
        ):
            raise ConfigurationError(f"source_roots must not overlap {name}.")
