"""Transparent component scoring and health classification."""

from __future__ import annotations

from grid_reliability.asset_health.config import AssetHealthConfig
from grid_reliability.asset_health.models import (
    AssetFeatures,
    AssetHealthResult,
    AssetRecord,
    ComponentScores,
    HealthBand,
    MaintenancePriority,
)


def component_scores(features: AssetFeatures, config: AssetHealthConfig) -> ComponentScores:
    missing: list[str] = []
    maintenance_missing = features.maintenance_count == 0
    telemetry_missing = features.telemetry_observation_count == 0
    outage_missing = features.direct_outage_count + features.contextual_outage_count == 0
    if maintenance_missing:
        missing.append("maintenance")
    if telemetry_missing:
        missing.extend(["telemetry_stress", "alarm"])
    if outage_missing:
        missing.append("outage")
    return ComponentScores(
        age_component_score=_age_score(features),
        inspection_component_score=_inspection_score(features),
        maintenance_component_score=(
            _missing_score(config) if maintenance_missing else _maintenance_score(features)
        ),
        telemetry_stress_component_score=(
            _missing_score(config) if telemetry_missing else _telemetry_score(features)
        ),
        alarm_component_score=_missing_score(config)
        if telemetry_missing
        else _alarm_score(features),
        outage_component_score=_missing_score(config)
        if outage_missing
        else _outage_score(features),
        missing_components=tuple(missing),
    )


def health_score(
    components: ComponentScores, config: AssetHealthConfig
) -> tuple[float, dict[str, float]]:
    values = {
        "age": components.age_component_score,
        "inspection": components.inspection_component_score,
        "maintenance": components.maintenance_component_score,
        "telemetry_stress": components.telemetry_stress_component_score,
        "alarm": components.alarm_component_score,
        "outage": components.outage_component_score,
    }
    contributions = {
        name: round(values[name] * config.component_weights[name], 6) for name in values
    }
    return round(_bounded(sum(contributions.values())), 6), contributions


def classify_health(score: float, insufficient_data: bool, config: AssetHealthConfig) -> HealthBand:
    if insufficient_data:
        return HealthBand.INSUFFICIENT_DATA
    thresholds = config.health_band_thresholds
    if score <= thresholds["critical_max"]:
        return HealthBand.CRITICAL
    if score <= thresholds["degraded_max"]:
        return HealthBand.DEGRADED
    if score <= thresholds["watch_max"]:
        return HealthBand.WATCH
    return HealthBand.HEALTHY


def reason_codes(
    asset: AssetRecord,
    features: AssetFeatures,
    components: ComponentScores,
    max_codes: int,
) -> tuple[str, ...]:
    codes: list[str] = []
    if features.beyond_expected_life_flag:
        codes.append("AGE_BEYOND_EXPECTED_LIFE")
    elif features.age_to_expected_life_ratio >= 0.85:
        codes.append("AGE_NEAR_EXPECTED_LIFE")
    if features.inspection_overdue_flag:
        codes.append("INSPECTION_OVERDUE")
    elif features.days_since_last_inspection <= 180:
        codes.append("GOOD_RECENT_INSPECTION")
    if features.deferred_maintenance_count:
        codes.append("MAINTENANCE_DEFERRED")
    if _share(features.corrective_maintenance_count, features.maintenance_count) >= 0.5:
        codes.append("HIGH_CORRECTIVE_MAINTENANCE_SHARE")
    if features.emergency_maintenance_count:
        codes.append("RECENT_EMERGENCY_MAINTENANCE")
    if features.follow_up_required_count:
        codes.append("FOLLOW_UP_WORK_OUTSTANDING")
    if features.telemetry_observation_count == 0:
        codes.append("INSUFFICIENT_TELEMETRY")
    elif (features.high_utilisation_share or 0) >= 0.25:
        codes.append("SUSTAINED_HIGH_UTILISATION")
    else:
        codes.append("LOW_OPERATIONAL_STRESS")
    if features.temperature_exceedance_count:
        codes.append("PEAK_TEMPERATURE_STRESS")
    if features.alarm_event_count >= 2:
        codes.append("REPEATED_OPERATIONAL_ALARMS")
    if features.direct_unplanned_outage_count:
        codes.append("RECENT_DIRECT_UNPLANNED_OUTAGE")
    if features.equipment_failure_outage_count:
        codes.append("EQUIPMENT_FAILURE_OUTAGE_HISTORY")
    if features.maintenance_count == 0:
        codes.append("INSUFFICIENT_MAINTENANCE_HISTORY")
    if asset.operational_status in {"maintenance", "retired"}:
        codes.append(f"STATUS_{asset.operational_status.upper()}")
    deduped = list(dict.fromkeys(codes))
    return tuple(deduped[:max_codes])


def maintenance_priority(
    asset: AssetRecord,
    health_band: HealthBand,
    features: AssetFeatures,
    config: AssetHealthConfig,
) -> tuple[MaintenancePriority, tuple[str, ...]]:
    reasons: list[str] = []
    criticality_score = config.criticality_mapping.get(asset.criticality_tier, 1)
    if health_band == HealthBand.INSUFFICIENT_DATA:
        return MaintenancePriority.DATA_REVIEW_REQUIRED, ("INSUFFICIENT_DATA",)
    if health_band == HealthBand.CRITICAL and criticality_score >= 3:
        return MaintenancePriority.P1_IMMEDIATE_REVIEW, ("CRITICAL_HEALTH_HIGH_CRITICALITY",)
    if health_band == HealthBand.CRITICAL:
        return MaintenancePriority.P2_HIGH, ("CRITICAL_HEALTH",)
    if health_band == HealthBand.DEGRADED and criticality_score >= 3:
        return MaintenancePriority.P2_HIGH, ("DEGRADED_HEALTH_HIGH_CRITICALITY",)
    if features.inspection_overdue_flag:
        reasons.append("INSPECTION_OVERDUE")
    if features.deferred_maintenance_count:
        reasons.append("MAINTENANCE_DEFERRED")
    if features.direct_unplanned_outage_count:
        reasons.append("RECENT_DIRECT_UNPLANNED_OUTAGE")
    if asset.operational_status in {"maintenance", "retired"}:
        reasons.append(f"STATUS_{asset.operational_status.upper()}")
    if reasons and (health_band == HealthBand.WATCH or criticality_score >= 2):
        return MaintenancePriority.P2_HIGH, tuple(reasons)
    if health_band in {HealthBand.DEGRADED, HealthBand.WATCH} or reasons:
        return MaintenancePriority.P3_MEDIUM, tuple(reasons or [health_band.value])
    return MaintenancePriority.P4_ROUTINE, ("ROUTINE_REVIEW",)


def assess_asset(
    asset: AssetRecord,
    features: AssetFeatures,
    config: AssetHealthConfig,
) -> AssetHealthResult:
    components = component_scores(features, config)
    score, contributions = health_score(components, config)
    band = classify_health(score, features.insufficient_data_flag, config)
    priority, priority_reasons = maintenance_priority(asset, band, features, config)
    return AssetHealthResult(
        asset=asset,
        assessment_timestamp=config.assessment_timestamp,
        features=features,
        components=components,
        health_score=score,
        health_band=band,
        maintenance_priority=priority,
        reason_codes=reason_codes(asset, features, components, config.max_reason_codes),
        priority_reason_codes=priority_reasons,
        component_contributions=contributions,
        schema_version=config.schema_version,
    )


def _age_score(features: AssetFeatures) -> float:
    ratio = features.age_to_expected_life_ratio
    if ratio <= 0.5:
        return _bounded(100 - ratio * 20)
    if ratio <= 1.0:
        return _bounded(90 - (ratio - 0.5) / 0.5 * 60)
    return _bounded(30 - min(1.0, ratio - 1.0) * 30)


def _inspection_score(features: AssetFeatures) -> float:
    if features.inspection_overdue_days > 0:
        return _bounded(70 - min(365, features.inspection_overdue_days) / 365 * 70)
    if features.days_until_next_inspection >= 180:
        return 100.0
    return _bounded(80 + max(0, features.days_until_next_inspection) / 180 * 20)


def _maintenance_score(features: AssetFeatures) -> float:
    corrective_share = _share(features.corrective_maintenance_count, features.maintenance_count)
    emergency_share = _share(features.emergency_maintenance_count, features.maintenance_count)
    penalty = (
        corrective_share * 25
        + emergency_share * 30
        + min(3, features.deferred_maintenance_count) * 12
        + min(3, features.follow_up_required_count) * 8
        + min(1.0, features.total_recent_downtime_minutes / 720) * 20
    )
    return _bounded(100 - penalty)


def _telemetry_score(features: AssetFeatures) -> float:
    mean_util = features.mean_utilisation_pct or 0
    max_util = features.maximum_utilisation_pct or 0
    high_share = features.high_utilisation_share or 0
    temp_share = features.temperature_exceedance_share or 0
    penalty = (
        max(0.0, mean_util - 75) * 0.8
        + max(0.0, max_util - 95) * 0.6
        + high_share * 25
        + temp_share * 25
        + min(5, features.offline_or_constrained_count) * 8
    )
    return _bounded(100 - penalty)


def _alarm_score(features: AssetFeatures) -> float:
    return _bounded(100 - min(8, features.alarm_event_count) * 12)


def _outage_score(features: AssetFeatures) -> float:
    penalty = (
        features.direct_unplanned_outage_count * 25
        + features.equipment_failure_outage_count * 15
        + min(1.0, features.total_outage_duration_minutes / 720) * 20
        + min(4, features.contextual_outage_count) * 4
    )
    return _bounded(100 - penalty)


def _missing_score(config: AssetHealthConfig) -> float:
    return 50.0 if config.missing_data_policy == "neutral" else 40.0


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 6)


def _share(count: int, total: int) -> float:
    return count / total if total else 0.0
