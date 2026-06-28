"""Persistence for normalised interim datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.data_generation.writers import sha256_file


@dataclass(frozen=True)
class WrittenOutput:
    dataset_name: str
    filename: str
    record_count: int
    file_size_bytes: int
    sha256: str


def _replace_atomically(temp_path: Path, destination: Path) -> None:
    temp_path.replace(destination)


def write_interim_dataset(
    *,
    interim_root: Path,
    dataset_name: str,
    records: list[dict[str, Any]],
) -> WrittenOutput:
    interim_root.mkdir(parents=True, exist_ok=True)
    path = interim_root / f"{dataset_name}.jsonl"
    with NamedTemporaryFile("w", encoding="utf-8", dir=interim_root, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        for record in records:
            temp_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    _replace_atomically(temp_path, path)
    return WrittenOutput(
        dataset_name=dataset_name,
        filename=path.name,
        record_count=len(records),
        file_size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )
