"""Local Power BI-ready reporting semantic model pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.reporting.config import load_reporting_config
from grid_reliability.reporting.discovery import discover_reporting_sources
from grid_reliability.reporting.loaders import load_reporting_sources
from grid_reliability.reporting.models import ReportingError, ReportingRunResult
from grid_reliability.reporting.persistence import write_reporting_outputs
from grid_reliability.reporting.reporting import ensure_dashboard_assets, write_reporting_reports
from grid_reliability.reporting.tables import build_reporting_tables, validate_reporting_tables

EXIT_SUCCESS = 0
EXIT_CONFIGURATION_ERROR = 2
EXIT_SOURCE_ERROR = 3
EXIT_RELATIONSHIP_ERROR = 4
EXIT_PERSISTENCE_ERROR = 5


def run_reporting_pipeline(
    *,
    project_root: Path,
    config_path: Path,
    source_root: Path | None = None,
    output_root: Path | None = None,
    report_root: Path | None = None,
    run_id: str | None = None,
    component: str | None = None,
    page: str | None = None,
) -> ReportingRunResult:
    """Run reporting discovery, table generation, validation, and persistence."""

    config = load_reporting_config(config_path, project_root=project_root)
    if source_root is not None:
        config = config.__class__(
            **{**config.__dict__, "source_roots": ((project_root / source_root).resolve(),)}
        )
    if output_root is not None:
        config = config.__class__(**{**config.__dict__, "output_root": output_root})
    if report_root is not None:
        config = config.__class__(**{**config.__dict__, "report_root": report_root})
    if run_id is not None:
        config = config.__class__(**{**config.__dict__, "run_id": run_id})
    if component is not None:
        config = config.__class__(**{**config.__dict__, "included_components": (component,)})
    if page is not None:
        config = config.__class__(**{**config.__dict__, "dashboard_pages": (page,)})

    sources = discover_reporting_sources(project_root, config)
    source_data = load_reporting_sources(sources)
    tables = build_reporting_tables(source_data, config)
    validation = validate_reporting_tables(tables)
    if validation.failures:
        raise ReportingError("; ".join(validation.failures))
    ensure_dashboard_assets(project_root, config)
    result = write_reporting_outputs(
        project_root, config_path, config, source_data, tables, validation
    )
    write_reporting_reports(project_root, config, tables, validation)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Build local Power BI-ready reporting outputs.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--component")
    parser.add_argument("--page")
    args = parser.parse_args(argv)

    try:
        result = run_reporting_pipeline(
            project_root=Path.cwd(),
            config_path=args.config,
            source_root=args.source_root,
            output_root=args.output_root,
            report_root=args.report_root,
            run_id=args.run_id,
            component=args.component,
            page=args.page,
        )
    except ConfigurationError as exc:
        print(json.dumps({"run_status": "FAILED_CONFIGURATION", "error": str(exc)}))
        return EXIT_CONFIGURATION_ERROR
    except ReportingError as exc:
        print(
            json.dumps({"run_status": "FAILED_REPORTING_SOURCE_OR_RELATIONSHIP", "error": str(exc)})
        )
        return EXIT_SOURCE_ERROR
    except OSError as exc:
        print(json.dumps({"run_status": "FAILED_REPORTING_PERSISTENCE", "error": str(exc)}))
        return EXIT_PERSISTENCE_ERROR

    print(
        "Reporting run "
        f"{result.run_id}: tables={len(result.row_counts)}; "
        f"rows={sum(result.row_counts.values())}; "
        f"outputs={result.output_root}"
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
