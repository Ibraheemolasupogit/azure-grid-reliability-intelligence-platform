"""Calibration metadata for outage prediction."""

from __future__ import annotations

from grid_reliability.outage_prediction.models import PredictionResult


def calibration_metadata(
    method: str, validation_predictions: list[PredictionResult]
) -> dict[str, object]:
    positives = sum(row.row.labelled.label for row in validation_predictions)
    return {
        "method": method,
        "trained_on_validation": method != "raw",
        "validation_rows": len(validation_predictions),
        "validation_positive_rows": positives,
        "limitations": "Raw scores are retained; CI data is too small for reliable calibration.",
    }
