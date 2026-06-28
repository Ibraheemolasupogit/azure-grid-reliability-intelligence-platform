"""Synthetic substation and feeder telemetry generation."""

from __future__ import annotations

import random
from datetime import timedelta

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.identifiers import stable_id
from grid_reliability.data_generation.models import Network, Record
from grid_reliability.data_generation.time import iso_timestamp, iter_timestamps
from grid_reliability.data_generation.weather import temperature_for


def generate_substation_events(
    config: SyntheticDataConfig, network: Network, rng: random.Random
) -> list[Record]:
    records: list[Record] = []
    timestamps = iter_timestamps(
        config.start_timestamp, config.end_timestamp, config.substation_interval_minutes
    )
    region_index = {region.region_id: index for index, region in enumerate(network.regions)}
    for feeder in network.feeders:
        substation = next(
            item for item in network.substations if item.substation_id == feeder.substation_id
        )
        for timestamp in timestamps:
            anomaly = rng.random() < config.target_anomaly_rate
            hour_factor = 0.68 + (0.22 if 7 <= timestamp.hour <= 21 else 0.0)
            weekday_factor = 1.05 if timestamp.weekday() < 5 else 0.92
            ambient = temperature_for(timestamp, region_index[feeder.grid_region]) + rng.uniform(
                -1.0, 1.0
            )
            load_mw = feeder.capacity_mva * hour_factor * weekday_factor * rng.uniform(0.72, 1.08)
            if anomaly:
                load_mw *= 1.22
            utilisation = min(135.0, load_mw / feeder.capacity_mva * 100)
            transformer_temp = ambient + 24 + utilisation * 0.35 + rng.uniform(-2, 2)
            alarm = (
                "TEMP_WARN" if transformer_temp > 75 else "HIGH_LOAD" if utilisation > 95 else ""
            )
            status = "warning" if alarm else "normal"
            if anomaly and utilisation > 105:
                status = "constrained"
            records.append(
                {
                    "event_id": stable_id("SSE", feeder.feeder_id, iso_timestamp(timestamp)),
                    "event_timestamp": iso_timestamp(timestamp),
                    "ingested_at": iso_timestamp(
                        timestamp + timedelta(minutes=rng.choice((0, 5, 10)))
                    ),
                    "substation_id": substation.substation_id,
                    "feeder_id": feeder.feeder_id,
                    "grid_region": feeder.grid_region,
                    "load_mw": round(load_mw, 4),
                    "capacity_mva": round(feeder.capacity_mva, 3),
                    "utilisation_pct": round(utilisation, 2),
                    "voltage_kv": round(substation.voltage_kv * rng.uniform(0.985, 1.015), 3),
                    "frequency_hz": round(rng.gauss(50.0, 0.02), 3),
                    "transformer_temperature_c": round(transformer_temp, 2),
                    "oil_temperature_c": round(transformer_temp - rng.uniform(4.0, 8.5), 2),
                    "ambient_temperature_c": round(ambient, 2),
                    "breaker_status": "closed",
                    "alarm_code": alarm,
                    "operational_status": status,
                    "quality_code": "ESTIMATED" if anomaly else "GOOD",
                    "schema_version": config.schema_version,
                }
            )
    return records
