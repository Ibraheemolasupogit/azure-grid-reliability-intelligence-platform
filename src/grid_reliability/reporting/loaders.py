"""Load governed reporting sources."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from grid_reliability.reporting.models import ReportingError, SourceData, SourceFile


def load_reporting_sources(sources: list[SourceFile]) -> SourceData:
    """Load CSV, JSON, and JSONL source records."""

    data = SourceData(files=sources)
    for source in sources:
        key = f"{source.component_name}.{source.kind}"
        suffix = source.path.suffix.lower()
        try:
            if suffix == ".csv":
                data.csv_tables[key] = _read_csv(source.path)
            elif suffix == ".json":
                data.json_docs[key] = _read_json(source.path)
            elif suffix == ".jsonl":
                data.jsonl_tables[key] = _read_jsonl(source.path)
            else:
                raise ReportingError(f"Unsupported reporting source extension: {source.path}")
        except (csv.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ReportingError(f"Malformed reporting source: {source.path}") from exc
    return data


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ReportingError(f"CSV source has no header: {path}")
        return [dict(row) for row in reader]


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReportingError(f"JSON source must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            value: Any = json.loads(line)
            if not isinstance(value, dict):
                raise ReportingError(f"JSONL record {line_number} is not an object: {path}")
            records.append(value)
    return records
