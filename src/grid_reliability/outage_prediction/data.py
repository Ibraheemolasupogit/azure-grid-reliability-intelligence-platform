"""Validated interim data loading for outage prediction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.models import OutagePredictionError

REQUIRED_DATASETS = (
    "asset_inventory",
    "maintenance_logs",
    "outage_history",
    "smart_meter_events",
    "substation_events",
    "weather_data",
)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)


def parse_optional_timestamp(value: object) -> datetime | None:
    return parse_timestamp(str(value)) if value not in (None, "") else None


def load_inputs(
    interim_root: Path,
    config: OutagePredictionConfig,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    del config
    if not interim_root.exists():
        raise OutagePredictionError(f"Interim root does not exist: {interim_root}")
    datasets: dict[str, list[dict[str, Any]]] = {}
    checksums: dict[str, str] = {}
    for name in REQUIRED_DATASETS:
        path = interim_root / f"{name}.jsonl"
        if not path.exists():
            raise OutagePredictionError(f"Required interim dataset is missing: {name}")
        records = _read_jsonl(path)
        if not records:
            raise OutagePredictionError(f"Required interim dataset is empty: {name}")
        _validate_schema(name, records)
        datasets[name] = sorted(records, key=lambda item: json.dumps(item, sort_keys=True))
        checksums[name] = sha256_file(path)
    return datasets, checksums


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise OutagePredictionError(f"{path.name}:{line_number} is not a JSON object.")
            rows.append(payload)
    return rows


def _validate_schema(name: str, records: list[dict[str, Any]]) -> None:
    for index, record in enumerate(records, start=1):
        if record.get("schema_version") != "2.0.0":
            raise OutagePredictionError(f"{name} record {index} has unsupported schema_version.")
        if "_ingestion" not in record:
            raise OutagePredictionError(f"{name} record {index} is not a validated interim record.")
