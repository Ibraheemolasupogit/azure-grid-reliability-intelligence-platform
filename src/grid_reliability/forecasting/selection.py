"""Model selection based on validation metrics."""

from __future__ import annotations

from grid_reliability.forecasting.metrics import overall_metric
from grid_reliability.forecasting.models import MetricResult, ModelSelection


def select_model(
    metrics: list[MetricResult],
    *,
    candidate_models: tuple[str, ...],
    selection_metric: str,
    excluded_models: dict[str, str],
) -> ModelSelection:
    eligible = [model for model in candidate_models if model not in excluded_models]
    scored: list[tuple[float, str]] = []
    for model_name in eligible:
        value = overall_metric(
            metrics,
            model_name=model_name,
            split="validation",
            metric_name=selection_metric,
        )
        if value is not None:
            scored.append((abs(value) if selection_metric == "bias" else value, model_name))
    if not scored:
        raise ValueError("No eligible models produced validation metrics.")
    scored.sort(key=lambda item: (item[0], item[1]))
    selected_value, selected_name = scored[0]
    baseline_value = overall_metric(
        metrics,
        model_name="persistence",
        split="validation",
        metric_name=selection_metric,
    )
    beats_baseline = baseline_value is not None and selected_value < baseline_value
    return ModelSelection(
        selected_model=selected_name,
        selected_metric=selection_metric,
        selected_metric_value=selected_value,
        baseline_model="persistence",
        baseline_metric_value=baseline_value,
        beats_baseline=beats_baseline,
        excluded_models=excluded_models,
    )
