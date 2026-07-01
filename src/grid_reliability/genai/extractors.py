"""Extraction and normalisation for approved assistant sources."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.genai.models import AssistantError, NormalizedDocument, SourceDocument

METRIC_PATTERN = re.compile(
    r"\b([a-zA-Z][a-zA-Z0-9_]*(?:_minutes|_score|_rate|_count|_mae|_wape)?)\b"
)
REASON_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){1,}\b")


def extract_documents(
    project_root: Path, sources: tuple[SourceDocument, ...]
) -> tuple[NormalizedDocument, ...]:
    documents: list[NormalizedDocument] = []
    for source in sources:
        path = project_root / source.source_path
        try:
            documents.extend(_extract_source(path, source))
        except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError, csv.Error) as exc:
            raise AssistantError(f"Malformed assistant source: {source.source_path}") from exc
    return tuple(sorted(documents, key=lambda item: (item.source_path, item.section_title)))


def _extract_source(path: Path, source: SourceDocument) -> list[NormalizedDocument]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        sections = _markdown_sections(path.read_text(encoding="utf-8"))
    elif suffix == ".json":
        sections = _json_sections(json.loads(path.read_text(encoding="utf-8")))
    elif suffix in {".yaml", ".yml"}:
        sections = _json_sections(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    elif suffix == ".csv":
        sections = _csv_sections(path)
    elif suffix == ".jsonl":
        sections = _jsonl_sections(path)
    else:
        sections = []
    output: list[NormalizedDocument] = []
    for index, (section, content, metadata) in enumerate(sections):
        clean = _normalise_content(content)
        if not clean:
            continue
        output.append(_document(source, section, clean, metadata, index))
    return output


def _markdown_sections(text: str) -> list[tuple[str, str, dict[str, str]]]:
    sections: list[tuple[str, str, dict[str, str]]] = []
    current_title = "Document"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines), {}))
            current_title = line.strip("# ").strip() or "Section"
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines), {}))
    return sections


def _json_sections(payload: Any) -> list[tuple[str, str, dict[str, str]]]:
    if not isinstance(payload, dict):
        payload = {"value": payload}
    lines = _flatten_mapping(payload)
    return [("JSON summary", "\n".join(lines), _metadata(payload))]


def _csv_sections(path: Path) -> list[tuple[str, str, dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    sections: list[tuple[str, str, dict[str, str]]] = []
    for index, row in enumerate(rows[:50], start=1):
        content = "; ".join(
            f"{key}={value if value != '' else 'null'}" for key, value in row.items()
        )
        sections.append((f"CSV row {index}", content, _metadata(row)))
    if not rows:
        sections.append(("CSV empty", "No rows available.", {}))
    return sections


def _jsonl_sections(path: Path) -> list[tuple[str, str, dict[str, str]]]:
    sections: list[tuple[str, str, dict[str, str]]] = []
    with path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file, start=1):
            if index > 50:
                break
            payload = json.loads(line)
            sections.append(
                (f"JSONL record {index}", "\n".join(_flatten_mapping(payload)), _metadata(payload))
            )
    return sections


def _document(
    source: SourceDocument,
    section_title: str,
    content: str,
    metadata: dict[str, str],
    index: int,
) -> NormalizedDocument:
    content_hash = _hash(content)
    document_id = "DOC-" + _hash(f"{source.source_id}|{index}|{section_title}")[:12].upper()
    metric_names = tuple(sorted(set(_metric_names(content))))
    reason_codes = tuple(sorted(set(REASON_PATTERN.findall(content))))
    return NormalizedDocument(
        document_id=document_id,
        source_id=source.source_id,
        component_name=source.component_name,
        source_type=source.content_type,
        section_title=section_title,
        content=content,
        content_hash=content_hash,
        source_path=source.source_path,
        source_checksum=source.source_checksum,
        run_id=metadata.get("run_id"),
        assessment_start=metadata.get("assessment_start"),
        assessment_end=metadata.get("assessment_end"),
        entity_type=metadata.get("entity_type"),
        entity_id=metadata.get("entity_id"),
        metric_names=metric_names,
        reason_codes=reason_codes,
        allowed_query_categories=source.allowed_query_categories,
        synthetic_data_flag=source.synthetic_data_flag,
    )


def _flatten_mapping(payload: Any, prefix: str = "") -> list[str]:
    if isinstance(payload, dict):
        lines: list[str] = []
        for key in sorted(payload):
            nested = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten_mapping(payload[key], nested))
        return lines
    if isinstance(payload, list):
        return [f"{prefix}={json.dumps(payload[:20], sort_keys=True)}"]
    return [f"{prefix}={payload if payload is not None else 'null'}"]


def _metadata(payload: dict[str, Any]) -> dict[str, str]:
    keys = {
        "run_id",
        "forecast_run_id",
        "asset_health_run_id",
        "outage_prediction_run_id",
        "reliability_run_id",
        "monitoring_run_id",
        "assessment_start",
        "assessment_end",
        "entity_type",
        "entity_id",
        "asset_id",
        "feeder_id",
    }
    metadata: dict[str, str] = {}
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            if key.endswith("run_id") or key == "run_id":
                metadata["run_id"] = str(value)
            elif key in {"asset_id", "feeder_id"}:
                metadata["entity_id"] = str(value)
            else:
                metadata[key] = str(value)
    return metadata


def _metric_names(content: str) -> list[str]:
    names = []
    for name in METRIC_PATTERN.findall(content.lower()):
        if name in {"the", "and", "with", "from", "this", "that", "null", "true", "false"}:
            continue
        if "_" in name or name in {"saifi", "saidi", "caidi", "asai", "wape", "mae", "bias"}:
            names.append(name)
    return names


def _normalise_content(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.splitlines() if line.strip()).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
