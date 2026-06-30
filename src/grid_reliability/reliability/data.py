"""Validated interim loading for reliability analytics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.models import ReliabilityError

REQUIRED_DATASETS = ("asset_inventory", "outage_history")
OPTIONAL_DATASETS = ("smart_meter_events", "substation_events")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def load_inputs(
    interim_root: Path,
    config: ReliabilityConfig,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str], list[str]]:
    if not interim_root.exists():
        raise ReliabilityError(f"Interim root does not exist: {interim_root}")
    datasets: dict[str, list[dict[str, Any]]] = {}
    checksums: dict[str, str] = {}
    missing_optional: list[str] = []
    for name in (*REQUIRED_DATASETS, *OPTIONAL_DATASETS):
        path = interim_root / f"{name}.jsonl"
        if not path.exists():
            if name in REQUIRED_DATASETS:
                raise ReliabilityError(f"Required interim dataset is missing: {name}")
            missing_optional.append(name)
            datasets[name] = []
            continue
        rows = _read_jsonl(path)
        if not rows and name in REQUIRED_DATASETS:
            raise ReliabilityError(f"Required interim dataset is empty: {name}")
        _validate_schema(name, rows)
        datasets[name] = _filter_assessment(rows, name, config)
        checksums[name] = sha256_file(path)
    return datasets, checksums, missing_optional


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ReliabilityError(f"{path.name}:{line_number} is not a JSON object.")
            rows.append(payload)
    return rows


def _validate_schema(name: str, rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        if row.get("schema_version") != "2.0.0":
            raise ReliabilityError(f"{name} record {index} has unsupported schema_version.")
        if "_ingestion" not in row:
            raise ReliabilityError(f"{name} record {index} is not validated interim data.")


def _filter_assessment(
    rows: list[dict[str, Any]],
    name: str,
    config: ReliabilityConfig,
) -> list[dict[str, Any]]:
    timestamp_field = {
        "outage_history": "outage_start",
        "smart_meter_events": "event_timestamp",
        "substation_events": "event_timestamp",
    }.get(name)
    if timestamp_field is None:
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
    filtered = [
        row
        for row in rows
        if config.assessment_start
        <= parse_timestamp(str(row[timestamp_field]))
        < config.assessment_end
    ]
    return sorted(
        filtered, key=lambda row: (str(row[timestamp_field]), json.dumps(row, sort_keys=True))
    )
