"""Load validated interim data for forecasting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.forecasting.models import ForecastingError, TargetSource

REQUIRED_SCHEMA_VERSION = "2.0.0"


def load_interim_dataset(interim_root: Path, dataset_name: str) -> list[dict[str, Any]]:
    path = interim_root / f"{dataset_name}.jsonl"
    if not path.exists():
        raise ForecastingError(f"Required interim dataset missing: {path.name}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line_number, line in enumerate(file_obj, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ForecastingError(f"{path.name}:{line_number} is not a JSON object.")
            if record.get("schema_version") != REQUIRED_SCHEMA_VERSION:
                raise ForecastingError(
                    f"{path.name}:{line_number} schema_version is not {REQUIRED_SCHEMA_VERSION}."
                )
            if "_ingestion" not in record:
                raise ForecastingError(f"{path.name}:{line_number} missing ingestion metadata.")
            records.append(record)
    if not records:
        raise ForecastingError(f"Required interim dataset is empty: {path.name}")
    return records


def load_forecasting_inputs(
    interim_root: Path,
    target_source: TargetSource,
    *,
    include_weather: bool,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    datasets = {
        target_source.value: load_interim_dataset(interim_root, target_source.value),
    }
    required = [target_source.value]
    if include_weather:
        datasets["weather_data"] = load_interim_dataset(interim_root, "weather_data")
        required.append("weather_data")
    checksums = {
        dataset_name: sha256_file(interim_root / f"{dataset_name}.jsonl")
        for dataset_name in required
    }
    return datasets, checksums
