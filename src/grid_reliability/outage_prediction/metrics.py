"""Classification metrics for rare outage-risk prediction."""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import pairwise

from grid_reliability.outage_prediction.models import ClassificationMetric, PredictionResult


def evaluate_predictions(
    predictions: list[PredictionResult],
    *,
    threshold: float,
    horizon: int,
) -> list[ClassificationMetric]:
    grouped: dict[tuple[str, str, str], list[PredictionResult]] = defaultdict(list)
    for prediction in predictions:
        grouped[
            (
                prediction.model_name,
                prediction.data_split,
                prediction.row.labelled.panel.entity.grid_region,
            )
        ].append(prediction)
    metrics: list[ClassificationMetric] = []
    for (model_name, split, region), rows in sorted(grouped.items()):
        metrics.append(_metric(model_name, split, region, rows, threshold, horizon))
    return metrics


def overall_metric(
    metrics: list[ClassificationMetric],
    *,
    model_name: str,
    split: str,
    metric_name: str,
) -> float | None:
    selected = [item for item in metrics if item.model_name == model_name and item.split == split]
    weighted_total = sum(item.row_count for item in selected)
    if not selected or weighted_total == 0:
        return None
    total = 0.0
    for item in selected:
        value = getattr(item, metric_name)
        if value is None:
            return None
        total += float(value) * item.row_count
    return total / weighted_total


def _metric(
    model_name: str,
    split: str,
    region: str,
    rows: list[PredictionResult],
    threshold: float,
    horizon: int,
) -> ClassificationMetric:
    actual = [row.row.labelled.label for row in rows]
    scores = [row.risk_score for row in rows]
    predicted = [1 if score >= threshold else 0 for score in scores]
    tp = sum(1 for y, p in zip(actual, predicted, strict=True) if y == 1 and p == 1)
    fp = sum(1 for y, p in zip(actual, predicted, strict=True) if y == 0 and p == 1)
    tn = sum(1 for y, p in zip(actual, predicted, strict=True) if y == 0 and p == 0)
    fn = sum(1 for y, p in zip(actual, predicted, strict=True) if y == 1 and p == 0)
    positive = sum(actual)
    negative = len(actual) - positive
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    specificity = _divide(tn, tn + fp)
    f1 = (
        _divide(2 * precision * recall, precision + recall)
        if precision is not None and recall is not None
        else None
    )
    return ClassificationMetric(
        model_name=model_name,
        split=split,
        entity_type=rows[0].row.labelled.panel.entity.entity_type.value if rows else "",
        grid_region=region,
        prediction_horizon_intervals=horizon,
        row_count=len(rows),
        positive_count=positive,
        negative_count=negative,
        prevalence=positive / len(rows) if rows else 0.0,
        threshold=threshold,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        specificity=specificity,
        balanced_accuracy=_balanced(recall, specificity),
        roc_auc=_roc_auc(actual, scores),
        pr_auc=_pr_auc(actual, scores),
        brier_score=sum((score - y) ** 2 for score, y in zip(scores, actual, strict=True))
        / len(rows)
        if rows
        else None,
        log_loss=_log_loss(actual, scores),
        false_positive_rate=_divide(fp, fp + tn),
        false_negative_rate=_divide(fn, fn + tp),
    )


def _divide(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _balanced(recall: float | None, specificity: float | None) -> float | None:
    if recall is None or specificity is None:
        return None
    return (recall + specificity) / 2


def _roc_auc(actual: list[int], scores: list[float]) -> float | None:
    positives = [score for score, label in zip(scores, actual, strict=True) if label == 1]
    negatives = [score for score, label in zip(scores, actual, strict=True) if label == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _pr_auc(actual: list[int], scores: list[float]) -> float | None:
    if sum(actual) == 0:
        return None
    pairs = sorted(zip(scores, actual, strict=True), reverse=True)
    tp = 0
    fp = 0
    points: list[tuple[float, float]] = [(0.0, 1.0)]
    positives = sum(actual)
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / positives
        precision = tp / (tp + fp)
        points.append((recall, precision))
    area = 0.0
    for (r0, p0), (r1, p1) in pairwise(points):
        area += (r1 - r0) * ((p0 + p1) / 2)
    return area


def _log_loss(actual: list[int], scores: list[float]) -> float | None:
    if not actual:
        return None
    total = 0.0
    for label, score in zip(actual, scores, strict=True):
        clipped = min(0.999999, max(0.000001, score))
        total += label * math.log(clipped) + (1 - label) * math.log(1 - clipped)
    return -total / len(actual)
