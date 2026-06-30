"""Feature derivation and evidence linkage for asset health."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from grid_reliability.asset_health.config import AssetHealthConfig
from grid_reliability.asset_health.data import parse_timestamp
from grid_reliability.asset_health.models import AssetFeatures, AssetRecord


def derive_features(
    asset: AssetRecord,
    datasets: dict[str, list[dict[str, Any]]],
    config: AssetHealthConfig,
) -> AssetFeatures:
    maintenance = _maintenance_for(asset, datasets.get("maintenance_logs", []), config)
    telemetry = _telemetry_for(asset, datasets.get("substation_events", []), config)
    outages = _outages_for(asset, datasets.get("outage_history", []), config)
    assessment_date = config.assessment_timestamp.date()
    age_years = max(0.0, (assessment_date - asset.commissioned_date).days / 365.25)
    remaining = asset.expected_life_years - age_years
    ratio = age_years / asset.expected_life_years if asset.expected_life_years else 999.0
    days_since_inspection = max(0, (assessment_date - asset.last_inspection_date).days)
    days_until_next = (asset.next_inspection_due - assessment_date).days
    overdue_days = max(0, -days_until_next)
    available = 2
    if maintenance["maintenance_count"] > 0:
        available += 1
    if telemetry["telemetry_observation_count"] > 0:
        available += 1
    if outages["direct_outage_count"] + outages["contextual_outage_count"] > 0:
        available += 1
    completeness = available / 5
    return AssetFeatures(
        asset_age_years=round(age_years, 4),
        expected_life_years=asset.expected_life_years,
        age_to_expected_life_ratio=round(ratio, 6),
        remaining_expected_life_years=round(remaining, 4),
        beyond_expected_life_flag=remaining < 0,
        days_since_last_inspection=days_since_inspection,
        days_until_next_inspection=days_until_next,
        inspection_overdue_days=overdue_days,
        inspection_overdue_flag=overdue_days > 0,
        expected_evidence_sources=5,
        available_evidence_sources=available,
        data_completeness_ratio=round(completeness, 6),
        insufficient_data_flag=completeness < config.minimum_data_completeness,
        **maintenance,
        **telemetry,
        **outages,
    )


def _maintenance_for(
    asset: AssetRecord,
    records: list[dict[str, Any]],
    config: AssetHealthConfig,
) -> dict[str, Any]:
    cutoff = config.assessment_timestamp - timedelta(days=config.lookback_days_maintenance)
    linked = [
        record
        for record in records
        if record.get("asset_id") == asset.asset_id
        and cutoff <= _maintenance_time(record) <= config.assessment_timestamp
    ]
    completed_dates = [
        parse_timestamp(str(record["completed_at"]))
        for record in linked
        if record.get("completed_at") and record.get("maintenance_status") == "completed"
    ]
    last_completed = max(completed_dates) if completed_dates else None
    days_since = (
        (config.assessment_timestamp.date() - last_completed.date()).days
        if last_completed is not None
        else None
    )
    return {
        "maintenance_count": len(linked),
        "preventive_maintenance_count": _count(linked, "maintenance_type", "preventive"),
        "corrective_maintenance_count": _count(linked, "maintenance_type", "corrective"),
        "emergency_maintenance_count": _count(linked, "maintenance_type", "emergency"),
        "deferred_maintenance_count": _count(linked, "maintenance_status", "deferred"),
        "cancelled_maintenance_count": _count(linked, "maintenance_status", "cancelled"),
        "days_since_last_completed_maintenance": days_since,
        "maintenance_overdue_flag": bool(days_since is None or days_since > 365),
        "total_recent_downtime_minutes": sum(int(record["downtime_minutes"]) for record in linked),
        "recent_maintenance_cost_gbp": round(
            sum(float(record["maintenance_cost_gbp"]) for record in linked), 2
        ),
        "follow_up_required_count": sum(
            1 for record in linked if bool(record["follow_up_required"])
        ),
    }


def _telemetry_for(
    asset: AssetRecord,
    records: list[dict[str, Any]],
    config: AssetHealthConfig,
) -> dict[str, Any]:
    cutoff = config.assessment_timestamp - timedelta(days=config.lookback_days_telemetry)
    linked = [
        record
        for record in records
        if _telemetry_matches(asset, record)
        and cutoff <= parse_timestamp(record["event_timestamp"]) <= config.assessment_timestamp
    ]
    utilisations = [float(record["utilisation_pct"]) for record in linked]
    temperatures = [float(record["transformer_temperature_c"]) for record in linked]
    alarm_count = sum(1 for record in linked if record.get("alarm_code"))
    offline_or_constrained = sum(
        1 for record in linked if record.get("operational_status") in {"offline", "constrained"}
    )
    high_count = sum(1 for value in utilisations if value >= 90)
    temp_count = sum(1 for value in temperatures if value >= 75)
    return {
        "telemetry_observation_count": len(linked),
        "mean_utilisation_pct": round(mean(utilisations), 6) if utilisations else None,
        "maximum_utilisation_pct": max(utilisations) if utilisations else None,
        "high_utilisation_event_count": high_count,
        "high_utilisation_share": high_count / len(linked) if linked else None,
        "mean_transformer_temperature_c": round(mean(temperatures), 6) if temperatures else None,
        "maximum_transformer_temperature_c": max(temperatures) if temperatures else None,
        "temperature_exceedance_count": temp_count,
        "temperature_exceedance_share": temp_count / len(linked) if linked else None,
        "alarm_event_count": alarm_count,
        "offline_or_constrained_count": offline_or_constrained,
    }


def _outages_for(
    asset: AssetRecord,
    records: list[dict[str, Any]],
    config: AssetHealthConfig,
) -> dict[str, Any]:
    cutoff = config.assessment_timestamp - timedelta(days=config.lookback_days_outages)
    linked = [
        record
        for record in records
        if _outage_matches(asset, record)
        and cutoff <= parse_timestamp(record["outage_start"]) <= config.assessment_timestamp
    ]
    direct = [record for record in linked if record.get("primary_asset_id") == asset.asset_id]
    contextual = [record for record in linked if record.get("primary_asset_id") != asset.asset_id]
    direct_dates = [parse_timestamp(record["outage_start"]) for record in direct]
    last_direct = max(direct_dates) if direct_dates else None
    return {
        "direct_outage_count": len(direct),
        "contextual_outage_count": len(contextual),
        "direct_unplanned_outage_count": _count(direct, "outage_type", "unplanned"),
        "total_outage_duration_minutes": sum(int(record["duration_minutes"]) for record in linked),
        "maximum_outage_duration_minutes": max(
            [int(record["duration_minutes"]) for record in linked],
            default=0,
        ),
        "customers_interrupted_total": sum(
            int(record["customers_interrupted"]) for record in linked
        ),
        "severe_weather_outage_count": sum(
            1 for record in linked if bool(record["severe_weather_related"])
        ),
        "equipment_failure_outage_count": _count(linked, "cause_category", "equipment_failure"),
        "days_since_last_direct_outage": (
            (config.assessment_timestamp.date() - last_direct.date()).days if last_direct else None
        ),
    }


def _maintenance_time(record: dict[str, Any]) -> datetime:
    for key in ("completed_at", "actual_start", "scheduled_start"):
        if record.get(key):
            return parse_timestamp(record[key])
    return parse_timestamp(record["scheduled_start"])


def _telemetry_matches(asset: AssetRecord, record: dict[str, Any]) -> bool:
    if asset.asset_type == "primary_substation":
        return record.get("substation_id") == asset.substation_id
    if asset.feeder_id:
        return record.get("feeder_id") == asset.feeder_id
    return record.get("substation_id") == asset.substation_id


def _outage_matches(asset: AssetRecord, record: dict[str, Any]) -> bool:
    if record.get("primary_asset_id") == asset.asset_id:
        return True
    if asset.feeder_id and record.get("feeder_id") == asset.feeder_id:
        return True
    return record.get("substation_id") == asset.substation_id


def _count(records: list[dict[str, Any]], key: str, value: str) -> int:
    return sum(1 for record in records if record.get(key) == value)
