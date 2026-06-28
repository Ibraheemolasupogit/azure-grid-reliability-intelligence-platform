"""Quarantine persistence for invalid records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.ingestion.records import IngestionRecord
from grid_reliability.validation.models import ValidationIssue


@dataclass(frozen=True)
class QuarantineEntry:
    ingestion_record: IngestionRecord
    issues: list[ValidationIssue]
    schema_version: str | None


@dataclass(frozen=True)
class WrittenQuarantine:
    dataset_name: str
    filename: str
    record_count: int
    file_size_bytes: int
    sha256: str


def write_quarantine_dataset(
    *,
    quarantine_root: Path,
    run_id: str,
    dataset_name: str,
    entries: list[QuarantineEntry],
    quarantined_at: datetime,
) -> WrittenQuarantine | None:
    if not entries:
        return None
    run_root = quarantine_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / f"{dataset_name}.jsonl"
    with NamedTemporaryFile("w", encoding="utf-8", dir=run_root, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        for entry in entries:
            payload: dict[str, Any] = {
                "dataset_name": entry.ingestion_record.dataset_name,
                "source_file": entry.ingestion_record.source_file,
                "source_record_number": entry.ingestion_record.source_record_number,
                "ingestion_run_id": entry.ingestion_record.ingestion_run_id,
                "raw_record": entry.ingestion_record.raw_record,
                "validation_issues": [issue.to_dict() for issue in entry.issues],
                "quarantine_timestamp": quarantined_at.isoformat().replace("+00:00", "Z"),
                "schema_version": entry.schema_version,
            }
            temp_file.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    temp_path.replace(path)
    return WrittenQuarantine(
        dataset_name=dataset_name,
        filename=str(Path(run_id) / path.name),
        record_count=len(entries),
        file_size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )
