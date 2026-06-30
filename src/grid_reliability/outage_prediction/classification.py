"""Deterministic lightweight classification models."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from grid_reliability.outage_prediction.features import feature_matrix, labels
from grid_reliability.outage_prediction.models import FeatureRow


@dataclass
class LogisticRegressionModel:
    positive_class_weight: float
    learning_rate: float = 0.05
    iterations: int = 400
    l2: float = 0.01
    name: str = "logistic_regression"
    coefficients: list[float] = field(default_factory=list)
    intercept: float = 0.0
    means: list[float] = field(default_factory=list)
    scales: list[float] = field(default_factory=list)

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        y = labels(rows)
        if len(set(y)) < 2:
            raise ValueError("logistic_regression requires both classes in training data.")
        x_raw = feature_matrix(rows, feature_names)
        self.means, self.scales = _standardisation(x_raw)
        x = _standardise(x_raw, self.means, self.scales)
        self.coefficients = [0.0 for _ in feature_names]
        self.intercept = _logit(sum(y) / len(y))
        for _ in range(self.iterations):
            grad = [0.0 for _ in feature_names]
            intercept_grad = 0.0
            for row, target in zip(x, y, strict=True):
                prediction = _sigmoid(
                    self.intercept
                    + sum(coef * value for coef, value in zip(self.coefficients, row, strict=True))
                )
                weight = self.positive_class_weight if target == 1 else 1.0
                error = (prediction - target) * weight
                intercept_grad += error
                for index, value in enumerate(row):
                    grad[index] += error * value
            count = max(1, len(x))
            self.intercept -= self.learning_rate * intercept_grad / count
            for index, value in enumerate(grad):
                penalty = self.l2 * self.coefficients[index]
                self.coefficients[index] -= self.learning_rate * (value / count + penalty)

    def predict_proba(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        x = _standardise(feature_matrix(rows, feature_names), self.means, self.scales)
        return [
            _sigmoid(
                self.intercept
                + sum(coef * value for coef, value in zip(self.coefficients, row, strict=True))
            )
            for row in x
        ]

    def parameters(self) -> dict[str, object]:
        return {
            "learning_rate": self.learning_rate,
            "iterations": self.iterations,
            "l2": self.l2,
            "positive_class_weight": self.positive_class_weight,
            "intercept": self.intercept,
            "coefficient_count": len(self.coefficients),
        }


def _standardisation(matrix: list[list[float]]) -> tuple[list[float], list[float]]:
    if not matrix:
        return [], []
    columns = len(matrix[0])
    means: list[float] = []
    scales: list[float] = []
    for index in range(columns):
        values = [row[index] for row in matrix]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        means.append(mean)
        scales.append(math.sqrt(variance) or 1.0)
    return means, scales


def _standardise(
    matrix: list[list[float]], means: list[float], scales: list[float]
) -> list[list[float]]:
    return [
        [(value - means[index]) / scales[index] for index, value in enumerate(row)]
        for row in matrix
    ]


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def _logit(rate: float) -> float:
    clipped = min(0.999, max(0.001, rate))
    return math.log(clipped / (1 - clipped))
