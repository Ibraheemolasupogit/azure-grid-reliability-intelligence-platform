"""Validated interim data loading for asset-health analytics."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from grid_reliability.asset_health.config import AssetHealthConfig
from grid_reliability.asset_health.models import AssetHealthError, AssetRecord
from grid_reliability.data_generation.writers import sha256_file

SCHEMA_VERSION = "2.0.0"
REQUIRED_DATASETS = ("asset_inventory",)
OPTIONAL_DATASETS = ("maintenance_logs", "substation_events", "outage_history")


def load_inputs(
    interim_root: Path,
    config: AssetHealthConfig,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str], list[str]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    checksums: dict[str, str] = {}
    missing_optional: list[str] = []
    for dataset_name in (*REQUIRED_DATASETS, *OPTIONAL_DATASETS):
        path = interim_root / f"{dataset_name}.jsonl"
        if not path.exists():
            if dataset_name in REQUIRED_DATASETS:
                raise AssetHealthError(f"Required interim dataset missing: {path.name}")
            missing_optional.append(dataset_name)
            datasets[dataset_name] = []
            continue
        records = _load_jsonl(path)
        if not records and dataset_name in REQUIRED_DATASETS:
            raise AssetHealthError(f"Required interim dataset is empty: {path.name}")
        datasets[dataset_name] = [
            record for record in records if _record_timestamp(record) <= config.assessment_timestamp
        ]
        checksums[dataset_name] = sha256_file(path)
    return datasets, checksums, missing_optional


def eligible_assets(
    records: list[dict[str, Any]],
    config: AssetHealthConfig,
) -> tuple[list[AssetRecord], int]:
    assets: list[AssetRecord] = []
    seen: set[str] = set()
    excluded = 0
    for record in sorted(records, key=lambda item: str(item["asset_id"])):
        asset_id = str(record["asset_id"])
        if asset_id in seen:
            raise AssetHealthError(f"Duplicate asset_id in interim inventory: {asset_id}")
        seen.add(asset_id)
        asset_type = str(record["asset_type"])
        if asset_type not in config.included_asset_types:
            excluded += 1
            continue
        if config.asset_id and asset_id != config.asset_id:
            continue
        if config.asset_type and asset_type != config.asset_type:
            continue
        commissioned = _date(record["commissioned_date"])
        if commissioned > config.assessment_timestamp.date():
            raise AssetHealthError(f"Asset {asset_id} commissioned after assessment timestamp.")
        expected_life = int(record["expected_life_years"])
        if expected_life <= 0:
            raise AssetHealthError(f"Asset {asset_id} expected_life_years must be positive.")
        assets.append(
            AssetRecord(
                asset_id=asset_id,
                asset_type=asset_type,
                asset_name=str(record["asset_name"]),
                grid_region=str(record["grid_region"]),
                substation_id=str(record["substation_id"]),
                feeder_id=str(record["feeder_id"]) if record.get("feeder_id") else None,
                commissioned_date=commissioned,
                expected_life_years=expected_life,
                criticality_tier=str(record["criticality_tier"]),
                operational_status=str(record["operational_status"]),
                last_inspection_date=_date(record["last_inspection_date"]),
                next_inspection_due=_date(record["next_inspection_due"]),
                rated_capacity=float(record["rated_capacity"]),
                capacity_unit=str(record["capacity_unit"]),
                schema_version=str(record["schema_version"]),
            )
        )
    if config.asset_id and not assets:
        raise AssetHealthError(f"No eligible asset found for asset_id={config.asset_id}.")
    return assets, excluded


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise AssetHealthError("Timestamp value must be a non-empty ISO-8601 string.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line_number, line in enumerate(file_obj, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise AssetHealthError(f"{path.name}:{line_number} is not a JSON object.")
            if record.get("schema_version") != SCHEMA_VERSION:
                raise AssetHealthError(f"{path.name}:{line_number} schema_version mismatch.")
            if "_ingestion" not in record:
                raise AssetHealthError(f"{path.name}:{line_number} missing ingestion metadata.")
            records.append(record)
    return records


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise AssetHealthError("Date value must be an ISO-8601 string.")
    return date.fromisoformat(value)


def _record_timestamp(record: dict[str, Any]) -> datetime:
    for key in (
        "completed_at",
        "actual_start",
        "scheduled_start",
        "event_timestamp",
        "outage_start",
    ):
        value = record.get(key)
        if value:
            return parse_timestamp(value)
    return datetime.min.replace(tzinfo=UTC)
