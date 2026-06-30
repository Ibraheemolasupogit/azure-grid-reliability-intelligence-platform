"""Transparent outage-risk baselines."""

from __future__ import annotations

from dataclasses import dataclass

from grid_reliability.outage_prediction.models import FeatureRow


@dataclass
class PrevalenceBaseline:
    name: str = "prevalence"
    prevalence: float = 0.0

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        del feature_names
        self.prevalence = sum(row.labelled.label for row in rows) / len(rows) if rows else 0.0

    def predict_proba(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        del feature_names
        return [self.prevalence for _ in rows]

    def parameters(self) -> dict[str, float]:
        return {"training_prevalence": self.prevalence}


@dataclass
class RecentOutageHeuristic:
    name: str = "recent_outage_heuristic"

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        del rows, feature_names

    def predict_proba(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        del feature_names
        scores: list[float] = []
        for row in rows:
            prior = row.features.get("prior_unplanned_outage_count", 0.0)
            days = row.features.get("days_since_previous_unplanned_outage", 999.0)
            scores.append(0.75 if prior > 0 and days <= 7 else 0.15)
        return scores

    def parameters(self) -> dict[str, float]:
        return {"recent_days": 7.0, "recent_score": 0.75, "default_score": 0.15}


@dataclass
class OperationalWarningHeuristic:
    name: str = "operational_warning_heuristic"

    def fit(self, rows: list[FeatureRow], feature_names: list[str]) -> None:
        del rows, feature_names

    def predict_proba(self, rows: list[FeatureRow], feature_names: list[str]) -> list[float]:
        del feature_names
        scores: list[float] = []
        for row in rows:
            warning = 0.0
            warning += min(0.25, row.features.get("alarm_count", 0.0) * 0.10)
            warning += min(0.20, row.features.get("high_utilisation_share", 0.0) * 0.20)
            warning += 0.15 if row.features.get("temperature_warning_count", 0.0) > 0 else 0.0
            warning += 0.15 if row.features.get("severe_weather_flag", 0.0) > 0 else 0.0
            warning += 0.10 if row.features.get("constrained_count", 0.0) > 0 else 0.0
            warning += 0.10 if row.features.get("offline_count", 0.0) > 0 else 0.0
            scores.append(min(0.95, 0.10 + warning))
        return scores

    def parameters(self) -> dict[str, str]:
        return {"strategy": "rule-based recent operational and weather warnings"}
