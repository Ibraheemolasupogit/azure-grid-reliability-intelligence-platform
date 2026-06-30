"""Reliability analytics pipeline and CLI."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.metadata import __version__
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.reliability.aggregation import calculate_results
from grid_reliability.reliability.benchmarks import BenchmarkRow, calculate_benchmarks
from grid_reliability.reliability.config import ReliabilityConfig, load_reliability_config
from grid_reliability.reliability.data import load_inputs
from grid_reliability.reliability.models import ReliabilityError, ReliabilityResult
from grid_reliability.reliability.outage_classification import classify_outages
from grid_reliability.reliability.persistence import write_outputs
from grid_reliability.reliability.population import build_population
from grid_reliability.reliability.reporting import write_reports
from grid_reliability.reliability.trends import TrendRow, calculate_trends


@dataclass(frozen=True)
class ReliabilityPipelineResult:
    run_id: str
    kpi_path: Path
    metrics_path: Path
    manifest_path: Path
    report_paths: dict[str, Path]
    result_count: int
    system_summary: dict[str, Any]


def build_run_id(config: ReliabilityConfig, provided: str | None = None) -> str:
    if provided:
        return provided
    if config.run_id_strategy == "deterministic":
        return "reliability-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_reliability(
    config: ReliabilityConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
) -> ReliabilityPipelineResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config, run_id)
    datasets, input_checksums, missing_optional = load_inputs(root / config.interim_root, config)
    populations = build_population(datasets, config)
    outages, excluded_outages = classify_outages(datasets["outage_history"], config)
    results = calculate_results(populations, outages, config, effective_run_id)
    trends = calculate_trends(results)
    benchmarks = calculate_benchmarks(results, config.benchmark_method)
    system_summary = _system_summary(results, outages)
    metrics = _metrics(results, outages, excluded_outages, missing_optional, trends, benchmarks)
    manifest = _manifest(
        settings.project_name,
        root,
        effective_run_id,
        config,
        input_checksums,
        results,
        outages,
        excluded_outages,
        metrics,
    )
    paths = write_outputs(
        root / config.output_root,
        effective_run_id,
        results,
        trends,
        benchmarks,
        outages,
        {
            "system_summary": system_summary,
            "metrics": metrics,
            "manifest": manifest,
        },
    )
    report_paths = write_reports(
        root / config.report_root,
        effective_run_id,
        config,
        results,
        system_summary,
    )
    return ReliabilityPipelineResult(
        run_id=effective_run_id,
        kpi_path=paths["kpis"],
        metrics_path=paths["metrics"],
        manifest_path=paths["manifest"],
        report_paths=report_paths,
        result_count=len(results),
        system_summary=system_summary,
    )


def _system_summary(
    results: list[ReliabilityResult],
    outages: list[Any],
) -> dict[str, Any]:
    region_rows = [row for row in results if row.entity.entity_type.value == "grid_region"]
    population = sum(row.population_denominator for row in region_rows)
    interruptions = sum(row.customer_interruptions for row in region_rows)
    interruption_minutes = sum(row.customer_interruption_minutes for row in region_rows)
    period_minutes = (
        (region_rows[0].period_end - region_rows[0].period_start).total_seconds() / 60
        if region_rows
        else 0
    )
    saifi = interruptions / population if population else None
    saidi = interruption_minutes / population if population else None
    caidi = interruption_minutes / interruptions if interruptions else None
    asai = (
        1 - min(interruption_minutes, population * period_minutes) / (population * period_minutes)
        if population and period_minutes
        else None
    )
    band_counts = _counts(row.reliability_band.value for row in results)
    lowest = sorted(
        [row for row in results if row.reliability_score is not None],
        key=lambda row: (float(row.reliability_score or 0), row.entity.entity_id),
    )[:5]
    return {
        "entities_assessed": len(results),
        "entities_with_insufficient_data": sum(
            1 for row in results if row.reliability_band.value == "INSUFFICIENT_DATA"
        ),
        "population_denominator": population,
        "total_outages": len(outages),
        "total_unplanned_outages": sum(
            1 for outage in outages if outage.outage_type == "unplanned"
        ),
        "customer_interruptions": interruptions,
        "system_saifi": saifi,
        "system_saidi_minutes": saidi,
        "system_caidi_minutes": caidi,
        "system_asai": asai,
        "reliability_band_counts": band_counts,
        "lowest_reliability_entities": [
            {
                "entity_type": row.entity.entity_type.value,
                "entity_id": row.entity.entity_id,
                "reliability_score": row.reliability_score,
            }
            for row in lowest
        ],
        "severe_weather_event_count": sum(1 for outage in outages if outage.severe_weather_related),
        "equipment_related_outage_count": sum(1 for outage in outages if outage.equipment_related),
        "synthetic_data_declaration": "Reliability analytics use fictional synthetic data only.",
    }


def _metrics(
    results: list[ReliabilityResult],
    outages: list[Any],
    excluded_outages: int,
    missing_optional: list[str],
    trends: list[TrendRow],
    benchmarks: list[BenchmarkRow],
) -> dict[str, Any]:
    return {
        "entities_discovered": len(results),
        "entities_assessed": len(results),
        "insufficient_data_entities": sum(
            1 for row in results if row.reliability_band.value == "INSUFFICIENT_DATA"
        ),
        "outage_records_included": len(outages),
        "outages_excluded": excluded_outages,
        "planned_outage_count": sum(1 for outage in outages if outage.outage_type == "planned"),
        "unplanned_outage_count": sum(1 for outage in outages if outage.outage_type == "unplanned"),
        "population_coverage": _coverage(results),
        "kpi_availability_counts": _kpi_availability(results),
        "counts_by_reliability_band": _counts(row.reliability_band.value for row in results),
        "reason_code_counts": _counts(code for row in results for code in row.reason_codes),
        "trend_rows": len(trends),
        "benchmark_rows": len(benchmarks),
        "overlap_count": sum(row.overlap_count for row in results),
        "missing_denominator_count": sum(1 for row in results if row.population_denominator == 0),
        "null_kpi_counts": _null_kpis(results),
        "missing_optional_inputs": missing_optional,
    }


def _manifest(
    project_name: str,
    root: Path,
    run_id: str,
    config: ReliabilityConfig,
    input_checksums: dict[str, str],
    results: list[ReliabilityResult],
    outages: list[Any],
    excluded_outages: int,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    config_path = root / "configs" / f"reliability{'_ci' if config.profile == 'ci' else ''}.yaml"
    return {
        "project": project_name,
        "run_id": run_id,
        "assessment_start": config.assessment_start,
        "assessment_end": config.assessment_end,
        "aggregation_levels": [level.value for level in config.aggregation_levels],
        "period_frequency": config.period_frequency.value,
        "kpi_version": __version__,
        "score_version": config.schema_version,
        "input_files": {name: f"{name}.jsonl" for name in sorted(input_checksums)},
        "input_checksums": input_checksums,
        "configuration_checksum": sha256_file(config_path) if config_path.exists() else None,
        "population_method": config.customer_population_method,
        "planned_unplanned_policy": {
            "include_planned_outages": config.include_planned_outages,
            "include_unplanned_outages": config.include_unplanned_outages,
        },
        "sustained_interruption_threshold_minutes": config.sustained_interruption_threshold_minutes,
        "component_weights": config.component_weights,
        "band_thresholds": config.reliability_band_thresholds,
        "entity_counts": _counts(row.entity.entity_type.value for row in results),
        "outage_counts": {
            "included": len(outages),
            "excluded": excluded_outages,
        },
        "null_kpi_counts": metrics["null_kpi_counts"],
        "repository_revision": _repo_revision(root),
        "assumptions": [
            "Population denominator is observed unique smart meters during the assessment period.",
            "CTAIDI and CAIFI are not calculated because distinct interrupted customer IDs "
            "are absent.",
            "SAIDI and SAIFI use event-level customer interruption values.",
            "Availability overlap handling uses merged outage windows for entity outage time.",
        ],
        "limitations": [
            "Synthetic data only.",
            "Not a regulatory submission.",
            "No Azure resources, dashboards, optimisation, or automated control.",
        ],
        "synthetic_data_declaration": "Reliability analytics use fictional synthetic data only.",
    }


def _coverage(results: list[ReliabilityResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for row in results if row.population_denominator > 0) / len(results)


def _kpi_availability(results: list[ReliabilityResult]) -> dict[str, int]:
    names = ("saifi", "saidi_minutes", "caidi_minutes", "asai", "asui")
    return {name: sum(1 for row in results if getattr(row, name) is not None) for name in names}


def _null_kpis(results: list[ReliabilityResult]) -> dict[str, int]:
    names = ("saifi", "saidi_minutes", "caidi_minutes", "asai", "asui", "ctaidi_minutes", "caifi")
    return {name: sum(1 for row in results if getattr(row, name) is None) for name in names}


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _repo_revision(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate local reliability analytics.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--interim-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--assessment-start")
    parser.add_argument("--assessment-end")
    parser.add_argument("--aggregation-level")
    parser.add_argument("--entity-id")
    parser.add_argument("--period-frequency")
    args = parser.parse_args(argv)
    try:
        config = load_reliability_config(
            args.config,
            interim_root=args.interim_root,
            output_root=args.output_root,
            report_root=args.report_root,
            assessment_start=args.assessment_start,
            assessment_end=args.assessment_end,
            aggregation_level=args.aggregation_level,
            entity_id=args.entity_id,
            period_frequency=args.period_frequency,
        )
        result = run_reliability(config, run_id=args.run_id)
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except ReliabilityError as exc:
        print({"status": "failed", "error": str(exc)})
        return 3
    except Exception as exc:
        print({"status": "failed", "error": str(exc)})
        return 1
    print(
        f"Reliability run {result.run_id}: entities={result.result_count}; "
        f"kpis={result.kpi_path}; report={result.report_paths['performance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
