"""Shared forecasting model interfaces and lightweight baselines."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from grid_reliability.forecasting.models import FeatureRow


class ForecastModel(Protocol):
    name: str

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None: ...

    def predict(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]: ...

    def parameters(self) -> dict[str, object]: ...


@dataclass
class PersistenceModel:
    name: str = "persistence"

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        return None

    def predict(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        return [max(0.0, row.features.get("target_latest", 0.0)) for row in rows]

    def parameters(self) -> dict[str, object]:
        return {"rule": "forecast equals latest observed target at forecast origin"}


@dataclass
class MovingAverageModel:
    window: int = 2
    name: str = "moving_average"

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        return None

    def predict(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        feature = f"rolling_mean_{self.window}"
        return [
            max(0.0, row.features.get(feature, row.features.get("target_latest", 0.0)))
            for row in rows
        ]

    def parameters(self) -> dict[str, object]:
        return {"window": self.window}


@dataclass
class SeasonalNaiveModel:
    seasonal_period: int
    name: str = "seasonal_naive"

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        return None

    def predict(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        feature = f"lag_{self.seasonal_period}"
        if any(feature not in row.features for row in rows):
            raise ValueError(f"Seasonal lag {self.seasonal_period} is not available.")
        return [max(0.0, row.features[feature]) for row in rows]

    def parameters(self) -> dict[str, object]:
        return {"seasonal_period": self.seasonal_period}


def residual_quantiles(
    rows: list[FeatureRow],
    predictions: list[float],
    interval_level: float,
) -> tuple[float, float]:
    residuals = sorted(
        row.actual_value - prediction for row, prediction in zip(rows, predictions, strict=True)
    )
    if not residuals:
        return 0.0, 0.0
    alpha = 1 - interval_level
    lower_index = int((alpha / 2) * (len(residuals) - 1))
    upper_index = int((1 - alpha / 2) * (len(residuals) - 1))
    return residuals[lower_index], residuals[upper_index]


def entity_recent_values(rows: list[FeatureRow], limit: int) -> dict[str, list[float]]:
    values: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=limit))
    for row in sorted(rows, key=lambda item: (item.forecast_origin, item.entity_id)):
        values[row.entity_id].append(row.actual_value)
    return {entity: list(entity_values) for entity, entity_values in values.items()}
