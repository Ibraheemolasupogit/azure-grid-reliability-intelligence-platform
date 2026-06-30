"""Model and threshold selection."""

from __future__ import annotations

from grid_reliability.outage_prediction.metrics import overall_metric
from grid_reliability.outage_prediction.models import (
    ClassificationMetric,
    ModelSelection,
    PredictionResult,
)

METRIC_FIELDS = {
    "f1": "f1",
    "recall": "recall",
    "precision": "precision",
    "balanced_accuracy": "balanced_accuracy",
    "pr_auc": "pr_auc",
}


def select_model(
    metrics: list[ClassificationMetric],
    predictions: list[PredictionResult],
    *,
    candidate_models: tuple[str, ...],
    selection_metric: str,
    configured_threshold: float,
    failed_models: dict[str, str],
) -> ModelSelection:
    del predictions
    field = METRIC_FIELDS[selection_metric]
    available: list[tuple[float, str]] = []
    for model_name in candidate_models:
        if model_name in failed_models:
            continue
        value = overall_metric(
            metrics, model_name=model_name, split="validation", metric_name=field
        )
        if value is not None:
            available.append((value, model_name))
    if not available:
        return ModelSelection(
            selected_model="prevalence",
            selected_threshold=configured_threshold,
            selection_metric=selection_metric,
            validation_score=None,
            baseline_model="prevalence",
            baseline_score=None,
            improvement_over_baseline=None,
            failed_models=failed_models,
        )
    available.sort(key=lambda item: (-item[0], candidate_models.index(item[1])))
    selected_score, selected_model = available[0]
    baseline_score = overall_metric(
        metrics,
        model_name="prevalence",
        split="validation",
        metric_name=field,
    )
    return ModelSelection(
        selected_model=selected_model,
        selected_threshold=configured_threshold,
        selection_metric=selection_metric,
        validation_score=selected_score,
        baseline_model="prevalence",
        baseline_score=baseline_score,
        improvement_over_baseline=(
            selected_score - baseline_score if baseline_score is not None else None
        ),
        failed_models=failed_models,
    )
