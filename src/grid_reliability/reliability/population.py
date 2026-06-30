"""Observed-meter population denominators."""

from __future__ import annotations

from typing import Any

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.models import (
    AggregationLevel,
    PopulationRecord,
    ReliabilityEntity,
)


def build_population(
    datasets: dict[str, list[dict[str, Any]]],
    config: ReliabilityConfig,
) -> list[PopulationRecord]:
    entities = _entities(datasets["asset_inventory"], config)
    meter_rows = datasets.get("smart_meter_events", [])
    meters_by_feeder: dict[str, set[str]] = {}
    meters_by_substation: dict[str, set[str]] = {}
    meters_by_region: dict[str, set[str]] = {}
    for row in meter_rows:
        meter_id = str(row["meter_id"])
        feeder_id = str(row["feeder_id"])
        substation_id = str(row["substation_id"])
        region = str(row["grid_region"])
        meters_by_feeder.setdefault(feeder_id, set()).add(meter_id)
        meters_by_substation.setdefault(substation_id, set()).add(meter_id)
        meters_by_region.setdefault(region, set()).add(meter_id)
    records: list[PopulationRecord] = []
    for entity in entities:
        if entity.entity_type == AggregationLevel.FEEDER:
            meters = meters_by_feeder.get(entity.entity_id, set())
        elif entity.entity_type == AggregationLevel.SUBSTATION:
            meters = meters_by_substation.get(entity.entity_id, set())
        else:
            meters = meters_by_region.get(entity.entity_id, set())
        population = len(meters)
        records.append(
            PopulationRecord(
                entity=entity,
                observed_meter_count=population,
                estimated_customer_population=population,
                population_method=config.customer_population_method,
                population_completeness_ratio=1.0
                if population >= config.minimum_population
                else 0.0,
            )
        )
    return sorted(records, key=lambda item: (item.entity.entity_type.value, item.entity.entity_id))


def _entities(
    inventory: list[dict[str, Any]],
    config: ReliabilityConfig,
) -> list[ReliabilityEntity]:
    entities: dict[tuple[AggregationLevel, str], ReliabilityEntity] = {}
    for row in inventory:
        region = str(row["grid_region"])
        substation_id = str(row["substation_id"])
        feeder = str(row.get("feeder_id") or "")
        if AggregationLevel.GRID_REGION in config.aggregation_levels:
            entities[(AggregationLevel.GRID_REGION, region)] = ReliabilityEntity(
                AggregationLevel.GRID_REGION,
                region,
                region,
            )
        if AggregationLevel.SUBSTATION in config.aggregation_levels:
            entities[(AggregationLevel.SUBSTATION, substation_id)] = ReliabilityEntity(
                AggregationLevel.SUBSTATION,
                substation_id,
                region,
                substation_id,
            )
        if AggregationLevel.FEEDER in config.aggregation_levels and row["asset_type"] == "feeder":
            entities[(AggregationLevel.FEEDER, feeder)] = ReliabilityEntity(
                AggregationLevel.FEEDER,
                feeder,
                region,
                substation_id,
                feeder,
            )
    selected = list(entities.values())
    if config.entity_id:
        selected = [entity for entity in selected if entity.entity_id == config.entity_id]
    return selected
