"""Synthetic smart meter event generation."""

from __future__ import annotations

import random
from datetime import timedelta

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.identifiers import stable_id
from grid_reliability.data_generation.models import Network, Record
from grid_reliability.data_generation.time import iso_timestamp, iter_timestamps
from grid_reliability.data_generation.weather import temperature_for

SEGMENT_BASE_KW = {
    "residential": 1.4,
    "commercial": 5.2,
    "industrial": 16.0,
    "public-service": 3.6,
}


def _load_multiplier(hour: int, weekday: int, segment: str) -> float:
    evening = 1.25 if 17 <= hour <= 21 else 1.0
    business = 1.35 if segment in {"commercial", "public-service"} and 8 <= hour <= 17 else 1.0
    industrial = (
        1.18
        if segment == "industrial" and weekday < 5
        else 0.88
        if segment == "industrial"
        else 1.0
    )
    weekend = 0.9 if weekday >= 5 and segment in {"commercial", "public-service"} else 1.0
    return evening * business * industrial * weekend


def generate_smart_meter_events(
    config: SyntheticDataConfig, network: Network, rng: random.Random
) -> list[Record]:
    records: list[Record] = []
    timestamps = iter_timestamps(
        config.start_timestamp, config.end_timestamp, config.meter_interval_minutes
    )
    region_index = {region.region_id: index for index, region in enumerate(network.regions)}
    for meter in network.meters:
        for timestamp_index, timestamp in enumerate(timestamps):
            missing = rng.random() < config.target_missing_reading_rate
            if missing:
                continue
            anomaly = rng.random() < config.target_anomaly_rate
            temp = temperature_for(timestamp, region_index[meter.grid_region])
            weather_factor = 1 + max(0.0, 15 - temp) * 0.018 + max(0.0, temp - 22) * 0.015
            kw = SEGMENT_BASE_KW[meter.customer_segment] * _load_multiplier(
                timestamp.hour, timestamp.weekday(), meter.customer_segment
            )
            kw *= weather_factor * rng.uniform(0.82, 1.18)
            if anomaly:
                kw *= rng.choice((0.18, 2.2))
            energy = kw * config.meter_interval_minutes / 60
            delayed_minutes = rng.choice((0, 0, 0, 15, 30)) if anomaly else rng.choice((0, 0, 5))
            voltage = rng.gauss(230.0, 4.2) + (-18.0 if anomaly and timestamp_index % 2 == 0 else 0)
            power_factor = min(0.99, max(0.78, rng.gauss(0.94, 0.025)))
            current = kw * 1000 / max(voltage * power_factor, 1)
            quality_code = "ESTIMATED" if anomaly else "GOOD"
            records.append(
                {
                    "event_id": stable_id("SME", meter.meter_id, iso_timestamp(timestamp)),
                    "event_timestamp": iso_timestamp(timestamp),
                    "ingested_at": iso_timestamp(timestamp + timedelta(minutes=delayed_minutes)),
                    "meter_id": meter.meter_id,
                    "feeder_id": meter.feeder_id,
                    "substation_id": meter.substation_id,
                    "grid_region": meter.grid_region,
                    "customer_segment": meter.customer_segment,
                    "reading_interval_minutes": config.meter_interval_minutes,
                    "active_energy_kwh": round(max(0.0, energy), 4),
                    "reactive_energy_kvarh": round(max(0.0, energy * (1 - power_factor)), 4),
                    "voltage_v": round(voltage, 2),
                    "current_a": round(current, 3),
                    "power_factor": round(power_factor, 3),
                    "frequency_hz": round(rng.gauss(50.0, 0.025), 3),
                    "meter_status": "suspect" if anomaly else "active",
                    "quality_code": quality_code,
                    "schema_version": config.schema_version,
                }
            )
    return records
