"""Persistence for reliability analytics outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.reliability.benchmarks import BenchmarkRow
from grid_reliability.reliability.models import (
    ClassifiedOutage,
    ReasonDescription,
    ReliabilityResult,
    to_jsonable,
)
from grid_reliability.reliability.trends import TrendRow

KPI_COLUMNS = [
    "reliability_run_id",
    "assessment_start",
    "assessment_end",
    "period_start",
    "period_end",
    "period_frequency",
    "entity_type",
    "entity_id",
    "grid_region",
    "substation_id",
    "feeder_id",
    "population_denominator",
    "population_method",
    "outage_count",
    "planned_outage_count",
    "unplanned_outage_count",
    "customer_interruptions",
    "customer_interruption_minutes",
    "saifi",
    "saidi_minutes",
    "caidi_minutes",
    "asai",
    "asui",
    "mean_restoration_minutes",
    "maximum_restoration_minutes",
    "severe_weather_outage_count",
    "equipment_failure_outage_count",
    "reliability_score",
    "reliability_band",
    "primary_reason_code",
    "reason_codes",
    "data_completeness_ratio",
    "schema_version",
]


def write_outputs(
    output_root: Path,
    run_id: str,
    results: list[ReliabilityResult],
    trends: list[TrendRow],
    benchmarks: list[BenchmarkRow],
    outages: list[ClassifiedOutage],
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Path]:
    run_root = output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "kpis": run_root / "reliability_kpis.csv",
        "components": run_root / "reliability_components.csv",
        "trends": run_root / "reliability_trends.csv",
        "benchmarks": run_root / "reliability_benchmarks.csv",
        "reasons": run_root / "reliability_reasons.csv",
        "events": run_root / "outage_event_summary.csv",
        "system_summary": run_root / "system_summary.json",
        "metrics": run_root / "metrics.json",
        "manifest": run_root / "reliability_manifest.json",
    }
    _write_csv(paths["kpis"], KPI_COLUMNS, [_kpi_row(row) for row in results])
    _write_csv(paths["components"], _component_columns(), _component_rows(results))
    _write_csv(
        paths["trends"], list(asdict(_empty_trend()).keys()), [asdict(row) for row in trends]
    )
    _write_csv(
        paths["benchmarks"],
        list(asdict(_empty_benchmark()).keys()),
        [asdict(row) for row in benchmarks],
    )
    _write_csv(paths["reasons"], _reason_columns(), _reason_rows(results))
    _write_csv(paths["events"], _event_columns(), [_event_row(row) for row in outages])
    _write_json(paths["system_summary"], payloads["system_summary"])
    _write_json(paths["metrics"], payloads["metrics"])
    manifest = {
        **payloads["manifest"],
        "output_files": {name: path.name for name, path in sorted(paths.items())},
    }
    _write_json(paths["manifest"], manifest)
    manifest["output_checksums"] = {
        name: sha256_file(path) for name, path in sorted(paths.items()) if name != "manifest"
    }
    _write_json(paths["manifest"], manifest)
    return paths


def _kpi_row(row: ReliabilityResult) -> dict[str, Any]:
    return {
        "reliability_run_id": row.run_id,
        "assessment_start": row.assessment_start,
        "assessment_end": row.assessment_end,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "period_frequency": row.period_frequency,
        "entity_type": row.entity.entity_type.value,
        "entity_id": row.entity.entity_id,
        "grid_region": row.entity.grid_region,
        "substation_id": row.entity.substation_id or "",
        "feeder_id": row.entity.feeder_id or "",
        "population_denominator": row.population_denominator,
        "population_method": row.population_method,
        "outage_count": row.outage_count,
        "planned_outage_count": row.planned_outage_count,
        "unplanned_outage_count": row.unplanned_outage_count,
        "customer_interruptions": row.customer_interruptions,
        "customer_interruption_minutes": row.customer_interruption_minutes,
        "saifi": row.saifi,
        "saidi_minutes": row.saidi_minutes,
        "caidi_minutes": row.caidi_minutes,
        "asai": row.asai,
        "asui": row.asui,
        "mean_restoration_minutes": row.mean_outage_duration_minutes,
        "maximum_restoration_minutes": row.maximum_outage_duration_minutes,
        "severe_weather_outage_count": row.severe_weather_outage_count,
        "equipment_failure_outage_count": row.equipment_failure_outage_count,
        "reliability_score": row.reliability_score,
        "reliability_band": row.reliability_band.value,
        "primary_reason_code": row.primary_reason_code(),
        "reason_codes": "|".join(row.reason_codes),
        "data_completeness_ratio": row.data_completeness_ratio,
        "schema_version": row.schema_version,
    }


def _component_columns() -> list[str]:
    return [
        "reliability_run_id",
        "entity_type",
        "entity_id",
        "period_start",
        "component_name",
        "component_score",
        "component_contribution",
    ]


def _component_rows(results: list[ReliabilityResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for name, score in result.component_scores.items():
            rows.append(
                {
                    "reliability_run_id": result.run_id,
                    "entity_type": result.entity.entity_type.value,
                    "entity_id": result.entity.entity_id,
                    "period_start": result.period_start,
                    "component_name": name,
                    "component_score": score,
                    "component_contribution": result.component_contributions.get(name, 0),
                }
            )
    return rows


def _reason_columns() -> list[str]:
    return [
        "reliability_run_id",
        "entity_type",
        "entity_id",
        "period_start",
        "reason_code",
        "description",
        "reason_rank",
    ]


def _reason_rows(results: list[ReliabilityResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for rank, code in enumerate(result.reason_codes, start=1):
            rows.append(
                {
                    "reliability_run_id": result.run_id,
                    "entity_type": result.entity.entity_type.value,
                    "entity_id": result.entity.entity_id,
                    "period_start": result.period_start,
                    "reason_code": code,
                    "description": ReasonDescription.get(code, code.replace("_", " ").title()),
                    "reason_rank": rank,
                }
            )
    return rows


def _event_columns() -> list[str]:
    return [
        "outage_id",
        "outage_start",
        "restoration_time",
        "duration_minutes",
        "grid_region",
        "substation_id",
        "feeder_id",
        "primary_asset_id",
        "outage_type",
        "cause_category",
        "duration_class",
        "customers_interrupted",
        "estimated_load_lost_mw",
        "severe_weather_related",
        "equipment_related",
    ]


def _event_row(row: ClassifiedOutage) -> dict[str, Any]:
    return {
        "outage_id": row.outage_id,
        "outage_start": row.outage_start,
        "restoration_time": row.restoration_time,
        "duration_minutes": row.duration_minutes,
        "grid_region": row.grid_region,
        "substation_id": row.substation_id,
        "feeder_id": row.feeder_id,
        "primary_asset_id": row.primary_asset_id,
        "outage_type": row.outage_type,
        "cause_category": row.cause_category,
        "duration_class": row.duration_class,
        "customers_interrupted": row.customers_interrupted,
        "estimated_load_lost_mw": row.estimated_load_lost_mw,
        "severe_weather_related": row.severe_weather_related,
        "equipment_related": row.equipment_related,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: to_jsonable(value) for key, value in row.items()})
    temp_path.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        json.dump(payload, temp, indent=2, sort_keys=True, default=to_jsonable)
        temp.write("\n")
    temp_path.replace(path)


def _empty_trend() -> TrendRow:
    return TrendRow("", "", "", "", None, None, None, None, "")


def _empty_benchmark() -> BenchmarkRow:
    return BenchmarkRow("", "", "", "", "", "", None, None, None, None, None, "")
