"""Synthetic regional weather generation."""

from __future__ import annotations

import math
import random
from datetime import datetime

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.models import Network, Record
from grid_reliability.data_generation.time import iso_timestamp, iter_timestamps


def temperature_for(timestamp: datetime, region_index: int) -> float:
    day_fraction = (timestamp.hour * 60 + timestamp.minute) / 1440
    daily = math.sin((day_fraction - 0.25) * math.tau) * 4.5
    seasonal = math.cos((timestamp.timetuple().tm_yday - 205) / 365 * math.tau) * 8.0 + 10.5
    return seasonal + daily + region_index * 0.35


def generate_weather(
    config: SyntheticDataConfig, network: Network, rng: random.Random
) -> list[Record]:
    records: list[Record] = []
    timestamps = iter_timestamps(
        config.start_timestamp, config.end_timestamp, config.weather_interval_minutes
    )
    for region_index, region in enumerate(network.regions):
        severe_slot = len(timestamps) // 2 if timestamps else -1
        for timestamp_index, timestamp in enumerate(timestamps):
            severe = timestamp_index == severe_slot and region_index % 2 == 0
            base_temp = temperature_for(timestamp, region_index) + rng.uniform(-1.5, 1.5)
            wind = rng.uniform(2.0, 7.0) + (6.0 if severe else 0.0)
            precipitation = max(0.0, rng.gauss(0.4, 0.9)) + (5.0 if severe else 0.0)
            condition = "storm" if severe else rng.choice(("clear", "cloud", "rain", "wind"))
            records.append(
                {
                    "weather_timestamp": iso_timestamp(timestamp),
                    "grid_region": region.region_id,
                    "temperature_c": round(base_temp, 2),
                    "feels_like_c": round(base_temp - max(0.0, wind - 5.0) * 0.35, 2),
                    "humidity_pct": round(min(98.0, max(35.0, 62 + precipitation * 4)), 2),
                    "wind_speed_mps": round(wind, 2),
                    "wind_gust_mps": round(wind + rng.uniform(1.5, 5.0), 2),
                    "precipitation_mm": round(precipitation, 2),
                    "pressure_hpa": round(rng.uniform(996.0, 1028.0) - precipitation * 1.5, 2),
                    "weather_condition": condition,
                    "severe_weather_flag": severe,
                    "data_source": "synthetic",
                    "schema_version": config.schema_version,
                }
            )
    return records


def weather_lookup(weather_records: list[Record]) -> dict[tuple[str, str], Record]:
    return {
        (str(record["grid_region"]), str(record["weather_timestamp"])): record
        for record in weather_records
    }
