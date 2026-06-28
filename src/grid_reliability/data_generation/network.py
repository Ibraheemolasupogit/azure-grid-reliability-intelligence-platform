"""Fictional UK-style network topology generation."""

from __future__ import annotations

import random

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.models import Feeder, Meter, Network, Region, Substation

REGION_IDS = ("GRID-NORTH", "GRID-SOUTH", "GRID-EAST", "GRID-WEST", "GRID-CENTRAL")
CUSTOMER_SEGMENTS = ("residential", "commercial", "industrial", "public-service")


def build_network(config: SyntheticDataConfig, rng: random.Random) -> Network:
    """Build a coherent fictional region/substation/feeder/meter hierarchy."""
    if config.number_of_regions > len(REGION_IDS):
        raise ConfigurationError(f"number_of_regions cannot exceed {len(REGION_IDS)}.")

    regions = tuple(
        Region(region_id=region_id) for region_id in REGION_IDS[: config.number_of_regions]
    )
    substations: list[Substation] = []
    feeders: list[Feeder] = []
    meters: list[Meter] = []

    for region in regions:
        region_slug = region.region_id.replace("GRID-", "")
        for sub_index in range(1, config.substations_per_region + 1):
            capacity = float(rng.choice((24, 32, 40, 48, 64)))
            substation_id = f"SUB-{region_slug}-{sub_index:03d}"
            substations.append(
                Substation(
                    substation_id=substation_id,
                    grid_region=region.region_id,
                    capacity_mva=capacity,
                    voltage_kv=float(rng.choice((11, 33))),
                )
            )
            for feeder_index in range(1, config.feeders_per_substation + 1):
                feeder_id = f"FDR-{region_slug}-{sub_index:03d}-{feeder_index:02d}"
                feeder_capacity = round(capacity / config.feeders_per_substation * 0.92, 3)
                feeders.append(
                    Feeder(
                        feeder_id=feeder_id,
                        substation_id=substation_id,
                        grid_region=region.region_id,
                        capacity_mva=feeder_capacity,
                    )
                )
                for meter_index in range(1, config.meters_per_feeder + 1):
                    segment = CUSTOMER_SEGMENTS[(meter_index + feeder_index + sub_index) % 4]
                    meters.append(
                        Meter(
                            meter_id=(
                                f"MTR-{region_slug}-{sub_index:03d}-"
                                f"{feeder_index:02d}-{meter_index:04d}"
                            ),
                            feeder_id=feeder_id,
                            substation_id=substation_id,
                            grid_region=region.region_id,
                            customer_segment=segment,
                        )
                    )

    return Network(
        regions=regions,
        substations=tuple(substations),
        feeders=tuple(feeders),
        meters=tuple(meters),
    )
