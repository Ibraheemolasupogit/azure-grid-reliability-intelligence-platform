"""Past-only outage prediction feature engineering."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, pstdev
from typing import Any

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.data import parse_optional_timestamp, parse_timestamp
from grid_reliability.outage_prediction.models import EntityType, FeatureRow, LabelledRow


def build_feature_rows(
    rows: list[LabelledRow],
    datasets: dict[str, list[dict[str, Any]]],
    config: OutagePredictionConfig,
) -> list[FeatureRow]:
    inventory = {str(row["asset_id"]): row for row in datasets["asset_inventory"]}
    by_feeder_assets = _assets_by_key(datasets["asset_inventory"], "feeder_id")
    by_substation_assets = _assets_by_key(datasets["asset_inventory"], "substation_id")
    feature_rows: list[FeatureRow] = []
    for row in rows:
        cutoff = row.panel.observation_timestamp
        lookback_start = cutoff - timedelta(
            minutes=config.observation_frequency_minutes * (config.feature_lookback_intervals - 1)
        )
        features: dict[str, float] = {
            "available_history_intervals": float(row.panel.available_history_intervals),
            "missing_interval_count": float(row.panel.missing_interval_count),
            "data_completeness_ratio": row.panel.data_completeness_ratio,
        }
        if config.include_substation_features:
            features.update(
                _telemetry_features(row, datasets["substation_events"], lookback_start, cutoff)
            )
        if config.include_weather_features:
            features.update(
                _weather_features(row, datasets["weather_data"], lookback_start, cutoff)
            )
        if config.include_smart_meter_features:
            features.update(
                _meter_features(row, datasets["smart_meter_events"], lookback_start, cutoff)
            )
        if config.include_maintenance_features:
            assets = _entity_assets(row, inventory, by_feeder_assets, by_substation_assets)
            features.update(
                _maintenance_features(assets, datasets["maintenance_logs"], lookback_start, cutoff)
            )
            features.update(
                _asset_features(assets, cutoff.date()) if config.include_asset_features else {}
            )
        features.update(
            _prior_outage_features(row, datasets["outage_history"], lookback_start, cutoff)
        )
        categorical = {
            "entity_type": row.panel.entity.entity_type.value,
            "grid_region": row.panel.entity.grid_region,
        }
        feature_rows.append(
            FeatureRow(
                labelled=row, features=_normalise(features), categorical_features=categorical
            )
        )
    return feature_rows


def feature_names(rows: list[FeatureRow]) -> list[str]:
    names = sorted({name for row in rows for name in row.features})
    return names


def feature_matrix(rows: list[FeatureRow], names: list[str]) -> list[list[float]]:
    return [[row.features.get(name, 0.0) for name in names] for row in rows]


def labels(rows: list[FeatureRow]) -> list[int]:
    return [row.labelled.label for row in rows]


def _telemetry_features(
    labelled: LabelledRow,
    records: list[dict[str, Any]],
    start: Any,
    cutoff: Any,
) -> dict[str, float]:
    linked = [
        row
        for row in records
        if _event_matches(labelled, row)
        and start <= parse_timestamp(str(row["event_timestamp"])) <= cutoff
    ]
    loads = [float(row["load_mw"]) for row in linked]
    utilisations = [float(row["utilisation_pct"]) for row in linked]
    temperatures = [float(row["transformer_temperature_c"]) for row in linked]
    frequencies = [float(row["frequency_hz"]) for row in linked]
    voltages = [float(row["voltage_kv"]) for row in linked]
    return {
        "telemetry_observation_count": float(len(linked)),
        "mean_load_mw": _mean(loads),
        "maximum_load_mw": max(loads, default=0.0),
        "load_standard_deviation": pstdev(loads) if len(loads) > 1 else 0.0,
        "mean_utilisation_pct": _mean(utilisations),
        "maximum_utilisation_pct": max(utilisations, default=0.0),
        "high_utilisation_count": float(sum(1 for value in utilisations if value >= 80)),
        "high_utilisation_share": _share(utilisations, 80),
        "mean_transformer_temperature_c": _mean(temperatures),
        "maximum_transformer_temperature_c": max(temperatures, default=0.0),
        "temperature_warning_count": float(sum(1 for value in temperatures if value >= 75)),
        "alarm_count": float(sum(1 for row in linked if row.get("alarm_code"))),
        "breaker_open_count": 0.0,
        "offline_count": float(
            sum(1 for row in linked if row.get("operational_status") == "offline")
        ),
        "constrained_count": float(
            sum(1 for row in linked if row.get("operational_status") == "constrained")
        ),
        "frequency_deviation_count": float(
            sum(1 for value in frequencies if abs(value - 50.0) >= 0.05)
        ),
        "voltage_deviation_count": float(
            sum(1 for value in voltages if value < 32.0 or value > 34.0)
        ),
    }


def _weather_features(
    labelled: LabelledRow,
    records: list[dict[str, Any]],
    start: Any,
    cutoff: Any,
) -> dict[str, float]:
    linked = [
        row
        for row in records
        if row.get("grid_region") == labelled.panel.entity.grid_region
        and start <= parse_timestamp(str(row["weather_timestamp"])) <= cutoff
    ]
    latest = max(linked, key=lambda row: parse_timestamp(str(row["weather_timestamp"])), default={})
    gusts = [float(row["wind_gust_mps"]) for row in linked]
    precipitation = [float(row["precipitation_mm"]) for row in linked]
    return {
        "temperature_c": float(latest.get("temperature_c", 0.0)),
        "humidity_pct": float(latest.get("humidity_pct", 0.0)),
        "wind_speed_mps": float(latest.get("wind_speed_mps", 0.0)),
        "wind_gust_mps": float(latest.get("wind_gust_mps", 0.0)),
        "precipitation_mm": float(latest.get("precipitation_mm", 0.0)),
        "pressure_hpa": float(latest.get("pressure_hpa", 0.0)),
        "severe_weather_flag": 1.0 if latest.get("severe_weather_flag") else 0.0,
        "recent_severe_weather_count": float(
            sum(1 for row in linked if row.get("severe_weather_flag"))
        ),
        "recent_precipitation_total": sum(precipitation),
        "recent_maximum_wind_gust": max(gusts, default=0.0),
    }


def _meter_features(
    labelled: LabelledRow,
    records: list[dict[str, Any]],
    start: Any,
    cutoff: Any,
) -> dict[str, float]:
    linked = [
        row
        for row in records
        if _event_matches(labelled, row)
        and start <= parse_timestamp(str(row["event_timestamp"])) <= cutoff
    ]
    energy = [float(row["active_energy_kwh"]) for row in linked]
    meters = {str(row["meter_id"]) for row in linked}
    estimated = sum(1 for row in linked if row.get("quality_code") == "ESTIMATED")
    voltage_issues = sum(
        1 for row in linked if float(row["voltage_v"]) < 216 or float(row["voltage_v"]) > 253
    )
    return {
        "aggregate_energy_kwh": sum(energy),
        "energy_change_rate": (energy[-1] - energy[0]) if len(energy) > 1 else 0.0,
        "meter_count": float(len(meters)),
        "meter_coverage_ratio": min(1.0, len(linked) / max(1, len(meters) * 2)),
        "estimated_reading_share": estimated / len(linked) if linked else 0.0,
        "missing_reading_share": 0.0 if linked else 1.0,
        "voltage_quality_issue_count": float(voltage_issues),
    }


def _maintenance_features(
    assets: list[dict[str, Any]],
    records: list[dict[str, Any]],
    start: Any,
    cutoff: Any,
) -> dict[str, float]:
    asset_ids = {str(asset["asset_id"]) for asset in assets}
    linked = [
        row
        for row in records
        if row.get("asset_id") in asset_ids
        and _maintenance_time(row) is not None
        and start <= _maintenance_time(row) <= cutoff
    ]
    completed = [
        _maintenance_time(row)
        for row in linked
        if row.get("maintenance_status") == "completed" and _maintenance_time(row) is not None
    ]
    last_completed = max(completed) if completed else None
    days_since = (cutoff.date() - last_completed.date()).days if last_completed else 999.0
    return {
        "days_since_last_completed_maintenance": float(days_since),
        "recent_corrective_maintenance_count": float(
            _count(linked, "maintenance_type", "corrective")
        ),
        "recent_emergency_maintenance_count": float(
            _count(linked, "maintenance_type", "emergency")
        ),
        "deferred_maintenance_count": float(_count(linked, "maintenance_status", "deferred")),
        "follow_up_required_count": float(
            sum(1 for row in linked if row.get("follow_up_required"))
        ),
        "recent_downtime_minutes": float(sum(int(row["downtime_minutes"]) for row in linked)),
    }


def _asset_features(assets: list[dict[str, Any]], observation_date: date) -> dict[str, float]:
    ages: list[float] = []
    ratios: list[float] = []
    overdue = 0
    criticality = 0.0
    statuses = 0.0
    for asset in assets:
        commissioned = date.fromisoformat(str(asset["commissioned_date"]))
        age = max(0.0, (observation_date - commissioned).days / 365.25)
        expected = max(1.0, float(asset["expected_life_years"]))
        ages.append(age)
        ratios.append(age / expected)
        overdue += date.fromisoformat(str(asset["next_inspection_due"])) < observation_date
        criticality = max(
            criticality,
            {"tier_1": 3.0, "tier_2": 2.0, "tier_3": 1.0}.get(str(asset["criticality_tier"]), 0.0),
        )
        statuses = max(
            statuses,
            {"active": 0.0, "standby": 1.0, "maintenance": 2.0, "retired": 3.0}.get(
                str(asset["operational_status"]), 0.0
            ),
        )
    return {
        "asset_age_years": _mean(ages),
        "age_to_expected_life_ratio": _mean(ratios),
        "criticality_tier_score": criticality,
        "operational_status_score": statuses,
        "inspection_overdue_flag": 1.0 if overdue else 0.0,
    }


def _prior_outage_features(
    labelled: LabelledRow,
    records: list[dict[str, Any]],
    start: Any,
    cutoff: Any,
) -> dict[str, float]:
    linked = [
        row
        for row in records
        if row.get("outage_type") == "unplanned"
        and _outage_matches(labelled, row)
        and start <= parse_timestamp(str(row["outage_start"])) < cutoff
        and parse_timestamp(str(row["restoration_time"])) <= cutoff
    ]
    starts = [parse_timestamp(str(row["outage_start"])) for row in linked]
    last = max(starts) if starts else None
    days_since = (cutoff.date() - last.date()).days if last else 999.0
    return {
        "prior_unplanned_outage_count": float(len(linked)),
        "days_since_previous_unplanned_outage": float(days_since),
        "prior_equipment_failure_outage_count": float(
            _count(linked, "cause_category", "equipment_failure")
        ),
        "prior_severe_weather_outage_count": float(
            sum(1 for row in linked if row.get("severe_weather_related"))
        ),
        "historical_outage_duration_minutes": float(
            sum(int(row["duration_minutes"]) for row in linked)
        ),
    }


def _event_matches(labelled: LabelledRow, record: dict[str, Any]) -> bool:
    entity = labelled.panel.entity
    if entity.entity_type == EntityType.FEEDER:
        return record.get("feeder_id") == entity.entity_id
    if entity.entity_type == EntityType.SUBSTATION:
        return record.get("substation_id") == entity.entity_id
    return bool(entity.feeder_id and record.get("feeder_id") == entity.feeder_id)


def _outage_matches(labelled: LabelledRow, record: dict[str, Any]) -> bool:
    entity = labelled.panel.entity
    if entity.entity_type == EntityType.FEEDER:
        return record.get("feeder_id") == entity.entity_id
    if entity.entity_type == EntityType.SUBSTATION:
        return record.get("substation_id") == entity.entity_id
    return record.get("primary_asset_id") == entity.entity_id


def _entity_assets(
    row: LabelledRow,
    inventory: dict[str, dict[str, Any]],
    by_feeder: dict[str, list[dict[str, Any]]],
    by_substation: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    entity = row.panel.entity
    if entity.entity_type == EntityType.PRIMARY_ASSET and entity.primary_asset_id:
        return [inventory[entity.primary_asset_id]]
    if entity.entity_type == EntityType.FEEDER and entity.feeder_id:
        return by_feeder.get(entity.feeder_id, [])
    return by_substation.get(entity.substation_id, [])


def _assets_by_key(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        value = record.get(key)
        if value:
            grouped.setdefault(str(value), []).append(record)
    return grouped


def _maintenance_time(row: dict[str, Any]) -> Any:
    return (
        parse_optional_timestamp(row.get("completed_at"))
        or parse_optional_timestamp(row.get("actual_start"))
        or parse_optional_timestamp(row.get("scheduled_start"))
    )


def _normalise(features: dict[str, float]) -> dict[str, float]:
    return {name: round(float(value), 6) for name, value in features.items()}


def _mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _share(values: list[float], threshold: float) -> float:
    return sum(1 for value in values if value >= threshold) / len(values) if values else 0.0


def _count(records: list[dict[str, Any]], key: str, value: str) -> int:
    return sum(1 for record in records if record.get(key) == value)
