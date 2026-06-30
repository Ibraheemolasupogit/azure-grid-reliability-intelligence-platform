"""Persistence for asset-health outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.asset_health.models import (
    AssetFeatures,
    AssetHealthResult,
    ReasonDescription,
    to_jsonable,
)
from grid_reliability.data_generation.writers import sha256_file

SCORE_COLUMNS = [
    "asset_health_run_id",
    "assessment_timestamp",
    "asset_id",
    "asset_type",
    "asset_name",
    "grid_region",
    "substation_id",
    "feeder_id",
    "criticality_tier",
    "operational_status",
    "asset_age_years",
    "expected_life_years",
    "age_to_expected_life_ratio",
    "data_completeness_ratio",
    "health_score",
    "health_band",
    "maintenance_priority",
    "age_component_score",
    "inspection_component_score",
    "maintenance_component_score",
    "telemetry_stress_component_score",
    "alarm_component_score",
    "outage_component_score",
    "primary_reason_code",
    "reason_codes",
    "maintenance_overdue_flag",
    "direct_unplanned_outage_count",
    "alarm_event_count",
    "schema_version",
]


def write_outputs(
    output_root: Path,
    run_id: str,
    results: list[AssetHealthResult],
    fleet_summary: dict[str, Any],
    metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Path]:
    run_root = output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "asset_health_scores": run_root / "asset_health_scores.csv",
        "asset_health_components": run_root / "asset_health_components.csv",
        "asset_health_reasons": run_root / "asset_health_reasons.csv",
        "maintenance_priorities": run_root / "maintenance_priorities.csv",
        "fleet_summary": run_root / "fleet_summary.json",
        "metrics": run_root / "metrics.json",
        "manifest": run_root / "asset_health_manifest.json",
    }
    _write_csv(
        paths["asset_health_scores"],
        SCORE_COLUMNS,
        [_score_row(run_id, result) for result in results],
    )
    _write_csv(
        paths["asset_health_components"], _component_columns(), _component_rows(run_id, results)
    )
    _write_csv(paths["asset_health_reasons"], _reason_columns(), _reason_rows(run_id, results))
    _write_csv(
        paths["maintenance_priorities"], _priority_columns(), _priority_rows(run_id, results)
    )
    _write_json(paths["fleet_summary"], fleet_summary)
    _write_json(paths["metrics"], metrics)
    manifest_with_outputs = {
        **manifest,
        "output_files": {name: path.name for name, path in sorted(paths.items())},
    }
    _write_json(paths["manifest"], manifest_with_outputs)
    manifest_with_outputs["output_checksums"] = {
        name: sha256_file(path) for name, path in sorted(paths.items()) if name != "manifest"
    }
    _write_json(paths["manifest"], manifest_with_outputs)
    return paths


def _score_row(run_id: str, result: AssetHealthResult) -> dict[str, Any]:
    asset = result.asset
    features = result.features
    components = result.components
    return {
        "asset_health_run_id": run_id,
        "assessment_timestamp": to_jsonable(result.assessment_timestamp),
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "asset_name": asset.asset_name,
        "grid_region": asset.grid_region,
        "substation_id": asset.substation_id,
        "feeder_id": asset.feeder_id or "",
        "criticality_tier": asset.criticality_tier,
        "operational_status": asset.operational_status,
        "asset_age_years": features.asset_age_years,
        "expected_life_years": features.expected_life_years,
        "age_to_expected_life_ratio": features.age_to_expected_life_ratio,
        "data_completeness_ratio": features.data_completeness_ratio,
        "health_score": result.health_score,
        "health_band": result.health_band.value,
        "maintenance_priority": result.maintenance_priority.value,
        "age_component_score": components.age_component_score,
        "inspection_component_score": components.inspection_component_score,
        "maintenance_component_score": components.maintenance_component_score,
        "telemetry_stress_component_score": components.telemetry_stress_component_score,
        "alarm_component_score": components.alarm_component_score,
        "outage_component_score": components.outage_component_score,
        "primary_reason_code": result.primary_reason_code(),
        "reason_codes": "|".join(result.reason_codes),
        "maintenance_overdue_flag": features.maintenance_overdue_flag,
        "direct_unplanned_outage_count": features.direct_unplanned_outage_count,
        "alarm_event_count": features.alarm_event_count,
        "schema_version": result.schema_version,
    }


def _component_columns() -> list[str]:
    return [
        "asset_health_run_id",
        "asset_id",
        *list(asdict(_empty_features()).keys()),
        "age_component_score",
        "inspection_component_score",
        "maintenance_component_score",
        "telemetry_stress_component_score",
        "alarm_component_score",
        "outage_component_score",
        "age_contribution",
        "inspection_contribution",
        "maintenance_contribution",
        "telemetry_stress_contribution",
        "alarm_contribution",
        "outage_contribution",
    ]


def _component_rows(run_id: str, results: list[AssetHealthResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        row = {
            "asset_health_run_id": run_id,
            "asset_id": result.asset.asset_id,
            **asdict(result.features),
            **result.components.as_dict(),
        }
        row.update(
            {
                f"{name}_contribution": value
                for name, value in result.component_contributions.items()
            }
        )
        rows.append(row)
    return rows


def _reason_columns() -> list[str]:
    return ["asset_health_run_id", "asset_id", "reason_code", "description", "reason_rank"]


def _reason_rows(run_id: str, results: list[AssetHealthResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for rank, code in enumerate(result.reason_codes, start=1):
            rows.append(
                {
                    "asset_health_run_id": run_id,
                    "asset_id": result.asset.asset_id,
                    "reason_code": code,
                    "description": ReasonDescription.get(code, code.replace("_", " ").title()),
                    "reason_rank": rank,
                }
            )
    return rows


def _priority_columns() -> list[str]:
    return [
        "asset_health_run_id",
        "asset_id",
        "priority",
        "health_band",
        "criticality_tier",
        "primary_reason",
        "supporting_reasons",
        "review_recommended",
    ]


def _priority_rows(run_id: str, results: list[AssetHealthResult]) -> list[dict[str, Any]]:
    return [
        {
            "asset_health_run_id": run_id,
            "asset_id": result.asset.asset_id,
            "priority": result.maintenance_priority.value,
            "health_band": result.health_band.value,
            "criticality_tier": result.asset.criticality_tier,
            "primary_reason": result.priority_reason_codes[0]
            if result.priority_reason_codes
            else "",
            "supporting_reasons": "|".join(result.priority_reason_codes),
            "review_recommended": result.maintenance_priority.value != "P4_ROUTINE",
        }
        for result in results
    ]


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


def _empty_features() -> AssetFeatures:
    return AssetFeatures(
        asset_age_years=0,
        expected_life_years=1,
        age_to_expected_life_ratio=0,
        remaining_expected_life_years=0,
        beyond_expected_life_flag=False,
        days_since_last_inspection=0,
        days_until_next_inspection=0,
        inspection_overdue_days=0,
        inspection_overdue_flag=False,
    )
