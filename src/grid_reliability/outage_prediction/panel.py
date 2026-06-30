"""Entity-time panel construction."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.data import parse_timestamp
from grid_reliability.outage_prediction.models import (
    Entity,
    EntityType,
    OutagePredictionError,
    PanelRow,
)


def build_panel(
    datasets: dict[str, list[dict[str, Any]]],
    config: OutagePredictionConfig,
) -> list[PanelRow]:
    entities = _entities(datasets["asset_inventory"], config)
    timestamps = sorted(
        {parse_timestamp(str(row["event_timestamp"])) for row in datasets["substation_events"]}
    )
    if not timestamps:
        raise OutagePredictionError("No observation timestamps available for panel construction.")
    final_allowed = max(timestamps) - timedelta(
        minutes=config.observation_frequency_minutes * config.prediction_horizon_intervals
    )
    telemetry_keys = {
        (str(row["feeder_id"]), parse_timestamp(str(row["event_timestamp"])))
        for row in datasets["substation_events"]
    }
    rows: list[PanelRow] = []
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        for timestamp in timestamps:
            if timestamp > final_allowed:
                continue
            key = (entity.entity_id, timestamp.isoformat())
            if key in seen:
                raise OutagePredictionError("Duplicate entity-time panel row generated.")
            seen.add(key)
            history_start = timestamp - timedelta(
                minutes=config.observation_frequency_minutes
                * (config.feature_lookback_intervals - 1)
            )
            expected = config.feature_lookback_intervals
            available = sum(
                1
                for item in timestamps
                if history_start <= item <= timestamp
                and (
                    (entity.feeder_id, item) in telemetry_keys
                    if entity.feeder_id
                    else any(
                        row.get("substation_id") == entity.substation_id
                        and parse_timestamp(str(row["event_timestamp"])) == item
                        for row in datasets["substation_events"]
                    )
                )
            )
            if available < config.minimum_history_intervals:
                continue
            rows.append(
                PanelRow(
                    entity=entity,
                    observation_timestamp=timestamp,
                    available_history_intervals=available,
                    expected_history_intervals=expected,
                    data_completeness_ratio=round(available / expected, 6),
                    missing_interval_count=max(0, expected - available),
                )
            )
    return sorted(rows, key=lambda row: (row.observation_timestamp, row.entity.entity_id))


def _entities(records: list[dict[str, Any]], config: OutagePredictionConfig) -> list[Entity]:
    entities: dict[str, Entity] = {}
    for record in records:
        asset_type = str(record["asset_type"])
        feeder_id = record.get("feeder_id")
        if config.entity_type == EntityType.FEEDER and asset_type == "feeder" and feeder_id:
            entity_id = str(feeder_id)
            entities[entity_id] = Entity(
                entity_type=EntityType.FEEDER,
                entity_id=entity_id,
                grid_region=str(record["grid_region"]),
                substation_id=str(record["substation_id"]),
                feeder_id=entity_id,
            )
        elif config.entity_type == EntityType.SUBSTATION and asset_type == "primary_substation":
            entity_id = str(record["substation_id"])
            entities[entity_id] = Entity(
                entity_type=EntityType.SUBSTATION,
                entity_id=entity_id,
                grid_region=str(record["grid_region"]),
                substation_id=entity_id,
            )
        elif config.entity_type == EntityType.PRIMARY_ASSET and asset_type != "smart_meter":
            entity_id = str(record["asset_id"])
            entities[entity_id] = Entity(
                entity_type=EntityType.PRIMARY_ASSET,
                entity_id=entity_id,
                grid_region=str(record["grid_region"]),
                substation_id=str(record["substation_id"]),
                feeder_id=str(feeder_id) if feeder_id else None,
                primary_asset_id=entity_id,
            )
    if config.entity_id:
        entities = {key: value for key, value in entities.items() if key == config.entity_id}
    if not entities:
        raise OutagePredictionError("No valid prediction entities found.")
    return [entities[key] for key in sorted(entities)]
