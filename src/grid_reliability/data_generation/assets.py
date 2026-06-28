"""Synthetic asset inventory generation."""

from __future__ import annotations

import random
from datetime import timedelta

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.models import Network, Record

MANUFACTURERS = ("Fictional Gridworks", "Northstar Synthetic Power", "Voltvale Systems")
STATUSES = ("active", "maintenance", "standby", "retired")
CRITICALITY = ("tier_1", "tier_2", "tier_3")


def _asset(
    *,
    asset_id: str,
    asset_type: str,
    asset_name: str,
    grid_region: str,
    substation_id: str,
    feeder_id: str,
    capacity: float,
    unit: str,
    commissioned_days_ago: int,
    rng: random.Random,
    config: SyntheticDataConfig,
) -> Record:
    commissioned = config.start_timestamp - timedelta(days=commissioned_days_ago)
    last_inspection = config.start_timestamp - timedelta(days=rng.randint(20, 360))
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "asset_name": asset_name,
        "grid_region": grid_region,
        "substation_id": substation_id,
        "feeder_id": feeder_id,
        "manufacturer": rng.choice(MANUFACTURERS),
        "model": f"SYN-{asset_type.upper().replace('_', '-')}-{rng.randint(100, 999)}",
        "commissioned_date": commissioned.date().isoformat(),
        "expected_life_years": rng.choice((20, 25, 30, 35, 40)),
        "rated_capacity": round(capacity, 3),
        "capacity_unit": unit,
        "criticality_tier": rng.choice(CRITICALITY),
        "operational_status": rng.choices(STATUSES, weights=(82, 8, 8, 2), k=1)[0],
        "last_inspection_date": last_inspection.date().isoformat(),
        "next_inspection_due": (last_inspection + timedelta(days=365)).date().isoformat(),
        "synthetic_location_code": (
            f"LOC-{grid_region.replace('GRID-', '')}-{rng.randint(1000, 9999)}"
        ),
        "schema_version": config.schema_version,
    }


def generate_assets(
    config: SyntheticDataConfig, network: Network, rng: random.Random
) -> list[Record]:
    records: list[Record] = []
    for substation in network.substations:
        records.append(
            _asset(
                asset_id=f"AST-{substation.substation_id}",
                asset_type="primary_substation",
                asset_name=f"Synthetic {substation.substation_id}",
                grid_region=substation.grid_region,
                substation_id=substation.substation_id,
                feeder_id="",
                capacity=substation.capacity_mva,
                unit="MVA",
                commissioned_days_ago=rng.randint(365, 9000),
                rng=rng,
                config=config,
            )
        )
    for feeder in network.feeders:
        records.append(
            _asset(
                asset_id=f"AST-SEC-{feeder.feeder_id}",
                asset_type="secondary_substation",
                asset_name=f"Synthetic secondary substation {feeder.feeder_id}",
                grid_region=feeder.grid_region,
                substation_id=feeder.substation_id,
                feeder_id=feeder.feeder_id,
                capacity=feeder.capacity_mva * 0.55,
                unit="MVA",
                commissioned_days_ago=rng.randint(180, 7000),
                rng=rng,
                config=config,
            )
        )
        for asset_type, suffix, unit, multiplier in (
            ("feeder", "FDR", "MVA", 1.0),
            ("transformer", "TX", "MVA", 0.75),
            ("circuit_breaker", "CB", "kA", 2.5),
            ("switchgear", "SWG", "kV", 11.0),
            ("protection_relay", "PR", "unit", 1.0),
        ):
            records.append(
                _asset(
                    asset_id=f"AST-{suffix}-{feeder.feeder_id}",
                    asset_type=asset_type,
                    asset_name=f"Synthetic {asset_type.replace('_', ' ')} {feeder.feeder_id}",
                    grid_region=feeder.grid_region,
                    substation_id=feeder.substation_id,
                    feeder_id=feeder.feeder_id,
                    capacity=feeder.capacity_mva * multiplier,
                    unit=unit,
                    commissioned_days_ago=rng.randint(180, 8000),
                    rng=rng,
                    config=config,
                )
            )
    for meter in network.meters:
        records.append(
            _asset(
                asset_id=f"AST-{meter.meter_id}",
                asset_type="smart_meter",
                asset_name=f"Synthetic meter {meter.meter_id}",
                grid_region=meter.grid_region,
                substation_id=meter.substation_id,
                feeder_id=meter.feeder_id,
                capacity=0.1,
                unit="MW",
                commissioned_days_ago=rng.randint(90, 4500),
                rng=rng,
                config=config,
            )
        )
    return records
