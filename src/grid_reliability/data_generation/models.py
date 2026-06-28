"""Typed records and topology models for synthetic grid data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

Record: TypeAlias = dict[str, Any]


@dataclass(frozen=True)
class Region:
    region_id: str


@dataclass(frozen=True)
class Substation:
    substation_id: str
    grid_region: str
    capacity_mva: float
    voltage_kv: float


@dataclass(frozen=True)
class Feeder:
    feeder_id: str
    substation_id: str
    grid_region: str
    capacity_mva: float


@dataclass(frozen=True)
class Meter:
    meter_id: str
    feeder_id: str
    substation_id: str
    grid_region: str
    customer_segment: str


@dataclass(frozen=True)
class Network:
    regions: tuple[Region, ...]
    substations: tuple[Substation, ...]
    feeders: tuple[Feeder, ...]
    meters: tuple[Meter, ...]


@dataclass(frozen=True)
class DatasetBundle:
    smart_meter_events: list[Record]
    substation_events: list[Record]
    weather_data: list[Record]
    asset_inventory: list[Record]
    maintenance_logs: list[Record]
    outage_history: list[Record]


@dataclass(frozen=True)
class WrittenDataset:
    filename: str
    path: Path
    record_count: int
    file_size_bytes: int
    sha256: str


@dataclass(frozen=True)
class GenerationResult:
    output_root: Path
    datasets: dict[str, WrittenDataset]
    manifest_path: Path
    manifest: Record
    generated_at: datetime
