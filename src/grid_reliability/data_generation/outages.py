"""Synthetic outage history generation."""

from __future__ import annotations

import random
from datetime import timedelta

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.identifiers import stable_id
from grid_reliability.data_generation.models import Network, Record
from grid_reliability.data_generation.time import iso_timestamp

CAUSES = (
    "equipment_failure",
    "severe_weather",
    "vegetation",
    "third-party_damage",
    "protection_operation",
    "overload",
    "planned_maintenance",
    "unknown",
)


def generate_outage_history(
    config: SyntheticDataConfig,
    network: Network,
    assets: list[Record],
    rng: random.Random,
) -> list[Record]:
    records: list[Record] = []
    feeder_assets = [
        asset
        for asset in assets
        if asset["asset_type"] in {"feeder", "transformer", "circuit_breaker"}
    ]
    minutes_total = max(
        1, int((config.end_timestamp - config.start_timestamp).total_seconds() // 60)
    )
    outage_count = max(2, len(network.feeders) // 2)
    for index in range(outage_count):
        feeder = rng.choice(network.feeders)
        candidate_assets = [
            asset for asset in feeder_assets if asset["feeder_id"] == feeder.feeder_id
        ]
        asset = rng.choice(candidate_assets)
        start = config.start_timestamp + timedelta(minutes=rng.randint(0, minutes_total - 1))
        duration = rng.choice((30, 45, 60, 90, 120, 180, 240))
        cause = rng.choice(CAUSES)
        planned = cause == "planned_maintenance"
        records.append(
            {
                "outage_id": stable_id("OUT", feeder.feeder_id, index, config.random_seed),
                "outage_start": iso_timestamp(start),
                "restoration_time": iso_timestamp(start + timedelta(minutes=duration)),
                "duration_minutes": duration,
                "grid_region": feeder.grid_region,
                "substation_id": feeder.substation_id,
                "feeder_id": feeder.feeder_id,
                "primary_asset_id": asset["asset_id"],
                "outage_type": "planned" if planned else "unplanned",
                "cause_category": cause,
                "customers_interrupted": rng.randint(12, max(24, config.meters_per_feeder * 35)),
                "estimated_load_lost_mw": round(rng.uniform(0.05, feeder.capacity_mva * 0.7), 3),
                "planned_flag": planned,
                "severe_weather_related": cause == "severe_weather",
                "protection_operated": cause
                in {"protection_operation", "overload", "equipment_failure"},
                "restoration_method": rng.choice(
                    (
                        "remote_switching",
                        "field_repair",
                        "planned_switching",
                        "auto_reclose",
                    )
                ),
                "incident_severity": rng.choice(("low", "medium", "high")),
                "data_quality_flag": "UNKNOWN_CAUSE" if cause == "unknown" else "GOOD",
                "schema_version": config.schema_version,
            }
        )
    return records
