"""Atomic dataset writers and manifest creation."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.models import Record, WrittenDataset
from grid_reliability.data_generation.time import iso_timestamp


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_atomically(temp_path: Path, destination: Path) -> None:
    temp_path.replace(destination)


def write_jsonl(path: Path, records: Iterable[Record]) -> WrittenDataset:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        for record in records:
            temp_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
    _replace_atomically(temp_path, path)
    return WrittenDataset(path.name, path, count, path.stat().st_size, sha256_file(path))


def write_csv(path: Path, records: list[Record], fieldnames: list[str]) -> WrittenDataset:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as temp_file:
        temp_path = Path(temp_file.name)
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    _replace_atomically(temp_path, path)
    return WrittenDataset(path.name, path, len(records), path.stat().st_size, sha256_file(path))


def write_manifest(
    path: Path,
    *,
    config: SyntheticDataConfig,
    project_name: str,
    generator_version: str,
    generated_at: datetime,
    datasets: dict[str, WrittenDataset],
) -> Record:
    manifest: Record = {
        "project_name": project_name,
        "generator_version": generator_version,
        "generation_timestamp": iso_timestamp(generated_at),
        "random_seed": config.random_seed,
        "configuration_profile": config.profile,
        "schema_version": config.schema_version,
        "date_range": {
            "start_timestamp": iso_timestamp(config.start_timestamp),
            "end_timestamp": iso_timestamp(config.end_timestamp),
        },
        "synthetic_data_statement": "All generated records are fictional synthetic data.",
        "datasets": {
            name: {
                "filename": dataset.filename,
                "record_count": dataset.record_count,
                "file_size_bytes": dataset.file_size_bytes,
                "sha256": dataset.sha256,
            }
            for name, dataset in sorted(datasets.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(manifest, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
    _replace_atomically(temp_path, path)
    return manifest
