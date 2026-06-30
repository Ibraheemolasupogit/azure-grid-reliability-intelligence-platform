"""Class-imbalance summaries."""

from __future__ import annotations

from grid_reliability.outage_prediction.models import FeatureRow


def class_summary(rows: list[FeatureRow]) -> dict[str, float | int]:
    positives = sum(row.labelled.label for row in rows)
    negatives = len(rows) - positives
    return {
        "rows": len(rows),
        "positive_count": positives,
        "negative_count": negatives,
        "positive_prevalence": positives / len(rows) if rows else 0.0,
    }
