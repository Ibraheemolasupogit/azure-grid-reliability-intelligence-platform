"""Parsed ingestion record models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceDataset:
    dataset_name: str
    filename: str
    path: Path
    file_format: str
    contract: dict[str, Any]


@dataclass(frozen=True)
class IngestionRecord:
    dataset_name: str
    source_file: str
    source_record_number: int
    ingestion_run_id: str
    ingested_at: datetime
    raw_record: Any
    parsed_record: dict[str, Any] | None
    parse_issues: list[Any] = field(default_factory=list)

    @property
    def record_key(self) -> str | None:
        if not self.parsed_record:
            return None
        for key in ("event_id", "asset_id", "maintenance_id", "outage_id"):
            if key in self.parsed_record:
                return str(self.parsed_record[key])
        if "weather_timestamp" in self.parsed_record and "grid_region" in self.parsed_record:
            return f"{self.parsed_record['weather_timestamp']}|{self.parsed_record['grid_region']}"
        return None
