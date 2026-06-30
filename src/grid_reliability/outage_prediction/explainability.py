"""Rule-based reason codes and risk bands."""

from __future__ import annotations

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.models import FeatureRow, RiskBand


def classify_risk(score: float, row: FeatureRow, config: OutagePredictionConfig) -> RiskBand:
    if row.labelled.panel.data_completeness_ratio < (
        config.minimum_history_intervals / config.feature_lookback_intervals
    ):
        return RiskBand.INSUFFICIENT_DATA
    thresholds = config.risk_band_thresholds
    if score >= thresholds["critical_min"]:
        return RiskBand.CRITICAL
    if score >= thresholds["high_min"]:
        return RiskBand.HIGH
    if score >= thresholds["moderate_min"]:
        return RiskBand.MODERATE
    return RiskBand.LOW


def reason_codes(row: FeatureRow, config: OutagePredictionConfig) -> tuple[str, ...]:
    features = row.features
    reasons: list[tuple[int, str]] = []
    if features.get("prior_unplanned_outage_count", 0) > 0:
        reasons.append((100, "RECENT_UNPLANNED_OUTAGE"))
    if features.get("alarm_count", 0) >= 2:
        reasons.append((90, "REPEATED_OPERATIONAL_ALARMS"))
    if features.get("high_utilisation_share", 0) >= 0.5:
        reasons.append((85, "SUSTAINED_HIGH_UTILISATION"))
    if features.get("temperature_warning_count", 0) > 0:
        reasons.append((80, "PEAK_TEMPERATURE_STRESS"))
    if features.get("offline_count", 0) > 0:
        reasons.append((78, "RECENT_OFFLINE_STATE"))
    if features.get("constrained_count", 0) > 0:
        reasons.append((76, "RECENT_CONSTRAINED_STATE"))
    if (
        features.get("severe_weather_flag", 0) > 0
        or features.get("recent_severe_weather_count", 0) > 0
    ):
        reasons.append((74, "SEVERE_WEATHER_EXPOSURE"))
    if features.get("recent_maximum_wind_gust", 0) >= 15:
        reasons.append((72, "HIGH_WIND_EXPOSURE"))
    if features.get("recent_precipitation_total", 0) >= 8:
        reasons.append((70, "HEAVY_PRECIPITATION_EXPOSURE"))
    if features.get("inspection_overdue_flag", 0) > 0:
        reasons.append((68, "INSPECTION_OVERDUE"))
    if features.get("recent_corrective_maintenance_count", 0) > 0:
        reasons.append((66, "RECENT_CORRECTIVE_MAINTENANCE"))
    if features.get("recent_emergency_maintenance_count", 0) > 0:
        reasons.append((64, "RECENT_EMERGENCY_MAINTENANCE"))
    if features.get("deferred_maintenance_count", 0) > 0:
        reasons.append((62, "DEFERRED_MAINTENANCE"))
    if features.get("follow_up_required_count", 0) > 0:
        reasons.append((60, "FOLLOW_UP_WORK_OUTSTANDING"))
    if features.get("age_to_expected_life_ratio", 0) >= 1:
        reasons.append((58, "AGE_BEYOND_EXPECTED_LIFE"))
    elif features.get("age_to_expected_life_ratio", 0) >= 0.85:
        reasons.append((56, "AGE_NEAR_EXPECTED_LIFE"))
    if features.get("data_completeness_ratio", 1) < 0.75:
        reasons.append((54, "POOR_DATA_COMPLETENESS"))
    if not reasons:
        reasons.append((1, "LOW_RECENT_STRESS"))
    ordered = [code for _, code in sorted(reasons, key=lambda item: (-item[0], item[1]))]
    return tuple(ordered[: config.max_reason_codes])
