"""Forecasting artifact persistence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.forecasting.models import MetricResult, PredictionRow

FORECAST_COLUMNS = [
    "forecast_run_id",
    "generated_at",
    "entity_type",
    "entity_id",
    "grid_region",
    "forecast_origin",
    "forecast_timestamp",
    "forecast_horizon_intervals",
    "target_name",
    "target_unit",
    "model_name",
    "predicted_value",
    "prediction_lower",
    "prediction_upper",
    "actual_value",
    "data_split",
    "schema_version",
]


def write_forecasts(output_root: Path, rows: list[PredictionRow]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "load_forecast.csv"
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=output_root, delete=False
    ) as temp_file:
        temp_path = Path(temp_file.name)
        writer = csv.DictWriter(temp_file, fieldnames=FORECAST_COLUMNS)
        writer.writeheader()
        for row in sorted(
            rows,
            key=lambda item: (
                item.forecast_timestamp,
                item.entity_type,
                item.entity_id,
                item.model_name,
                item.forecast_horizon_intervals,
            ),
        ):
            writer.writerow(_prediction_to_row(row))
    temp_path.replace(path)
    return path


def write_metrics(output_root: Path, payload: dict[str, Any]) -> Path:
    path = output_root / "metrics.json"
    _write_json(path, payload)
    return path


def write_model_comparison(output_root: Path, metrics: list[MetricResult]) -> Path:
    path = output_root / "model_comparison.csv"
    fieldnames = [
        "model_name",
        "entity_id",
        "horizon",
        "aggregation_level",
        "split",
        "mae",
        "rmse",
        "mape",
        "smape",
        "wape",
        "bias",
        "row_count",
        "interval_coverage",
    ]
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=output_root, delete=False
    ) as temp_file:
        temp_path = Path(temp_file.name)
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        for metric in metrics:
            writer.writerow(metric.to_dict())
    temp_path.replace(path)
    return path


def write_model_metadata(model_root: Path, payload: dict[str, Any]) -> Path:
    path = model_root / "model_metadata.json"
    _write_json(path, payload)
    return path


def write_manifest(output_root: Path, payload: dict[str, Any]) -> Path:
    path = output_root / "forecast_manifest.json"
    _write_json(path, payload)
    return path


def output_checksums(paths: dict[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in sorted(paths.items())}


def _prediction_to_row(row: PredictionRow) -> dict[str, Any]:
    return {
        "forecast_run_id": row.forecast_run_id,
        "generated_at": row.generated_at.isoformat().replace("+00:00", "Z"),
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "grid_region": row.grid_region,
        "forecast_origin": row.forecast_origin.isoformat().replace("+00:00", "Z"),
        "forecast_timestamp": row.forecast_timestamp.isoformat().replace("+00:00", "Z"),
        "forecast_horizon_intervals": row.forecast_horizon_intervals,
        "target_name": row.target_name,
        "target_unit": row.target_unit,
        "model_name": row.model_name,
        "predicted_value": f"{row.predicted_value:.6f}",
        "prediction_lower": f"{row.prediction_lower:.6f}",
        "prediction_upper": f"{row.prediction_upper:.6f}",
        "actual_value": "" if row.actual_value is None else f"{row.actual_value:.6f}",
        "data_split": row.data_split,
        "schema_version": row.schema_version,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(payload, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
    temp_path.replace(path)
