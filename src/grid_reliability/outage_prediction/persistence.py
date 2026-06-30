"""Persistence for outage prediction outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.outage_prediction.models import (
    ClassificationMetric,
    ModelSelection,
    PredictionResult,
    ReasonDescription,
    to_jsonable,
)

PREDICTION_COLUMNS = [
    "outage_prediction_run_id",
    "observation_timestamp",
    "prediction_window_start",
    "prediction_window_end",
    "entity_type",
    "entity_id",
    "grid_region",
    "substation_id",
    "feeder_id",
    "model_name",
    "risk_score",
    "risk_band",
    "predicted_outage_flag",
    "classification_threshold",
    "actual_outage_flag",
    "data_split",
    "data_completeness_ratio",
    "primary_reason_code",
    "reason_codes",
    "schema_version",
]


def write_outputs(
    output_root: Path,
    model_root: Path,
    run_id: str,
    predictions: list[PredictionResult],
    metrics: list[ClassificationMetric],
    selection: ModelSelection,
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Path]:
    run_root = output_root / run_id
    model_run_root = model_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    model_run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "predictions": run_root / "outage_risk_predictions.csv",
        "metrics": run_root / "metrics.json",
        "model_comparison": run_root / "model_comparison.csv",
        "threshold_analysis": run_root / "threshold_analysis.csv",
        "confusion_matrix": run_root / "confusion_matrix.csv",
        "manifest": run_root / "outage_prediction_manifest.json",
        "model_metadata": model_run_root / "model_metadata.json",
        "feature_schema": model_run_root / "feature_schema.json",
        "preprocessing_metadata": model_run_root / "preprocessing_metadata.json",
    }
    _write_csv(
        paths["predictions"], PREDICTION_COLUMNS, [_prediction_row(row) for row in predictions]
    )
    _write_csv(paths["model_comparison"], _metric_columns(), [_metric_row(row) for row in metrics])
    _write_csv(
        paths["confusion_matrix"], _confusion_columns(), [_confusion_row(row) for row in metrics]
    )
    _write_csv(
        paths["threshold_analysis"], _threshold_columns(), _threshold_rows(predictions, selection)
    )
    _write_json(paths["metrics"], payloads["metrics"])
    _write_json(paths["model_metadata"], payloads["model_metadata"])
    _write_json(paths["feature_schema"], payloads["feature_schema"])
    _write_json(paths["preprocessing_metadata"], payloads["preprocessing_metadata"])
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


def _prediction_row(result: PredictionResult) -> dict[str, Any]:
    labelled = result.row.labelled
    entity = labelled.panel.entity
    return {
        "outage_prediction_run_id": result.run_id,
        "observation_timestamp": labelled.panel.observation_timestamp,
        "prediction_window_start": labelled.label_window_start,
        "prediction_window_end": labelled.label_window_end,
        "entity_type": entity.entity_type.value,
        "entity_id": entity.entity_id,
        "grid_region": entity.grid_region,
        "substation_id": entity.substation_id,
        "feeder_id": entity.feeder_id or "",
        "model_name": result.model_name,
        "risk_score": result.risk_score,
        "risk_band": result.risk_band.value,
        "predicted_outage_flag": result.predicted_outage_flag,
        "classification_threshold": result.classification_threshold,
        "actual_outage_flag": labelled.label,
        "data_split": result.data_split,
        "data_completeness_ratio": labelled.panel.data_completeness_ratio,
        "primary_reason_code": result.primary_reason_code(),
        "reason_codes": "|".join(result.reason_codes),
        "schema_version": "6.0.0",
    }


def _metric_columns() -> list[str]:
    return list(asdict(_empty_metric()).keys())


def _metric_row(metric: ClassificationMetric) -> dict[str, Any]:
    return asdict(metric)


def _confusion_columns() -> list[str]:
    return [
        "model_name",
        "split",
        "grid_region",
        "true_positive",
        "false_positive",
        "true_negative",
        "false_negative",
    ]


def _confusion_row(metric: ClassificationMetric) -> dict[str, Any]:
    return {
        "model_name": metric.model_name,
        "split": metric.split,
        "grid_region": metric.grid_region,
        "true_positive": metric.true_positive,
        "false_positive": metric.false_positive,
        "true_negative": metric.true_negative,
        "false_negative": metric.false_negative,
    }


def _threshold_columns() -> list[str]:
    return ["model_name", "threshold", "split", "predicted_positive_count", "row_count"]


def _threshold_rows(
    predictions: list[PredictionResult],
    selection: ModelSelection,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_name in sorted({row.model_name for row in predictions}):
        for split in ("validation", "test"):
            selected = [
                row
                for row in predictions
                if row.model_name == model_name and row.data_split == split
            ]
            rows.append(
                {
                    "model_name": model_name,
                    "threshold": selection.selected_threshold,
                    "split": split,
                    "predicted_positive_count": sum(
                        1 for row in selected if row.risk_score >= selection.selected_threshold
                    ),
                    "row_count": len(selected),
                }
            )
    return rows


def reason_code_rows() -> list[dict[str, str]]:
    return [
        {"reason_code": code, "description": description}
        for code, description in sorted(ReasonDescription.items())
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


def _empty_metric() -> ClassificationMetric:
    return ClassificationMetric(
        model_name="",
        split="",
        entity_type="",
        grid_region="",
        prediction_horizon_intervals=1,
        row_count=0,
        positive_count=0,
        negative_count=0,
        prevalence=0,
        threshold=0,
        true_positive=0,
        false_positive=0,
        true_negative=0,
        false_negative=0,
        precision=None,
        recall=None,
        f1=None,
        specificity=None,
        balanced_accuracy=None,
        roc_auc=None,
        pr_auc=None,
        brier_score=None,
        log_loss=None,
        false_positive_rate=None,
        false_negative_rate=None,
    )
