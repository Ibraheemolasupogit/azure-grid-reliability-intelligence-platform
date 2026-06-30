"""Deterministic autoregressive linear regression model."""

from __future__ import annotations

from dataclasses import dataclass, field

from grid_reliability.forecasting.features import feature_matrix, target_vector
from grid_reliability.forecasting.models import FeatureRow


@dataclass
class AutoregressiveLinearModel:
    ridge_alpha: float = 0.01
    name: str = "autoregressive_linear"
    coefficients: list[float] = field(default_factory=list)
    intercept: float = 0.0

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        matrix = [[1.0, *row] for row in feature_matrix(rows, feature_names)]
        target = target_vector(rows)
        if not matrix:
            raise ValueError("No training rows available.")
        xtx = _xtx(matrix, self.ridge_alpha)
        xty = _xty(matrix, target)
        solution = _solve_linear_system(xtx, xty)
        self.intercept = solution[0]
        self.coefficients = solution[1:]

    def predict(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        predictions: list[float] = []
        for row_values in feature_matrix(rows, feature_names):
            value = self.intercept + sum(
                coefficient * feature
                for coefficient, feature in zip(self.coefficients, row_values, strict=True)
            )
            predictions.append(max(0.0, value))
        return predictions

    def parameters(self) -> dict[str, object]:
        return {
            "ridge_alpha": self.ridge_alpha,
            "intercept": self.intercept,
            "coefficient_count": len(self.coefficients),
        }


def _xtx(matrix: list[list[float]], ridge_alpha: float) -> list[list[float]]:
    columns = len(matrix[0])
    result = [[0.0 for _ in range(columns)] for _ in range(columns)]
    for row in matrix:
        for i in range(columns):
            for j in range(columns):
                result[i][j] += row[i] * row[j]
    for index in range(1, columns):
        result[index][index] += ridge_alpha
    return result


def _xty(matrix: list[list[float]], target: list[float]) -> list[float]:
    columns = len(matrix[0])
    result = [0.0 for _ in range(columns)]
    for row, value in zip(matrix, target, strict=True):
        for index in range(columns):
            result[index] += row[index] * value
    return result


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [[*row[:], value] for row, value in zip(matrix, vector, strict=True)]
    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]
        pivot = augmented[pivot_index][pivot_index]
        if abs(pivot) < 1e-12:
            augmented[pivot_index][pivot_index] = 1e-12
            pivot = 1e-12
        for column in range(pivot_index, size + 1):
            augmented[pivot_index][column] /= pivot
        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            for column in range(pivot_index, size + 1):
                augmented[row_index][column] -= factor * augmented[pivot_index][column]
    return [augmented[index][size] for index in range(size)]
