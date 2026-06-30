"""Forecasting metric calculations."""

from __future__ import annotations

import math
from collections import defaultdict

from grid_reliability.forecasting.models import MetricResult, PredictionRow


def evaluate_predictions(
    predictions: list[PredictionRow],
    *,
    aggregation_level: str,
) -> list[MetricResult]:
    grouped: dict[tuple[str, str, int, str], list[PredictionRow]] = defaultdict(list)
    for prediction in predictions:
        if prediction.actual_value is None:
            continue
        grouped[
            (
                prediction.model_name,
                prediction.entity_id,
                prediction.forecast_horizon_intervals,
                prediction.data_split,
            )
        ].append(prediction)
    results: list[MetricResult] = []
    for (model_name, entity_id, horizon, split), rows in sorted(grouped.items()):
        results.append(
            _metric_result(model_name, entity_id, horizon, split, rows, aggregation_level)
        )
    return results


def overall_metric(
    metrics: list[MetricResult],
    *,
    model_name: str,
    split: str,
    metric_name: str,
) -> float | None:
    selected = [
        metric for metric in metrics if metric.model_name == model_name and metric.split == split
    ]
    if not selected:
        return None
    total_rows = sum(metric.row_count for metric in selected)
    if total_rows == 0:
        return None
    weighted = 0.0
    for metric in selected:
        value = getattr(metric, metric_name)
        if value is None:
            return None
        weighted += float(value) * metric.row_count
    return weighted / total_rows


def _metric_result(
    model_name: str,
    entity_id: str,
    horizon: int,
    split: str,
    rows: list[PredictionRow],
    aggregation_level: str,
) -> MetricResult:
    errors = [
        row.predicted_value - float(row.actual_value)
        for row in rows
        if row.actual_value is not None
    ]
    actuals = [float(row.actual_value) for row in rows if row.actual_value is not None]
    predictions = [row.predicted_value for row in rows if row.actual_value is not None]
    absolute_errors = [abs(error) for error in errors]
    mae = sum(absolute_errors) / len(absolute_errors)
    rmse = math.sqrt(sum(error**2 for error in errors) / len(errors))
    non_zero_actuals = [abs(actual) for actual in actuals if actual != 0]
    mape = (
        sum(
            abs(error) / abs(actual)
            for error, actual in zip(errors, actuals, strict=True)
            if actual != 0
        )
        / len(non_zero_actuals)
        * 100
        if non_zero_actuals
        else None
    )
    smape_terms = [
        abs(predicted - actual) / ((abs(actual) + abs(predicted)) / 2)
        for predicted, actual in zip(predictions, actuals, strict=True)
        if (abs(actual) + abs(predicted)) > 0
    ]
    smape = sum(smape_terms) / len(smape_terms) * 100 if smape_terms else None
    actual_sum = sum(abs(actual) for actual in actuals)
    wape = sum(absolute_errors) / actual_sum * 100 if actual_sum > 0 else None
    bias = sum(errors) / len(errors)
    covered = [
        row
        for row in rows
        if row.actual_value is not None
        and row.prediction_lower <= float(row.actual_value) <= row.prediction_upper
    ]
    return MetricResult(
        model_name=model_name,
        entity_id=entity_id,
        horizon=horizon,
        aggregation_level=aggregation_level,
        split=split,
        mae=mae,
        rmse=rmse,
        mape=mape,
        smape=smape,
        wape=wape,
        bias=bias,
        row_count=len(rows),
        interval_coverage=len(covered) / len(rows) if rows else None,
    )
