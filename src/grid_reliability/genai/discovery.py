"""Approved source discovery for the assistant."""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.genai.config import AssistantConfig
from grid_reliability.genai.models import SourceDocument, SourceEntry
from grid_reliability.genai.source_registry import source_registry


def discover_sources(project_root: Path, config: AssistantConfig) -> tuple[SourceDocument, ...]:
    entries = [
        entry for entry in source_registry() if entry.component_name in config.approved_components
    ]
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for entry in entries:
        root = project_root / entry.source_family
        if not root.exists():
            continue
        for path in sorted(root.rglob(entry.file_pattern)):
            if not path.is_file() or path.is_symlink() or _excluded(project_root, path, config):
                continue
            if not _approved_pattern(path, config):
                continue
            relative = _relative(project_root, path)
            source_id = _source_id(relative)
            if source_id in seen:
                continue
            seen.add(source_id)
            documents.append(_source_document(entry, relative, source_id, sha256_file(path)))
    return tuple(sorted(documents, key=lambda item: (item.component_name, item.source_path)))


def _source_document(
    entry: SourceEntry, relative: str, source_id: str, checksum: str
) -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        source_family=entry.source_family,
        component_name=entry.component_name,
        source_path=relative,
        content_type=entry.content_type,
        source_checksum=checksum,
        trust_level=entry.trust_level,
        allowed_query_categories=entry.allowed_query_categories,
        synthetic_data_flag=entry.synthetic_data_flag,
    )


def _approved_pattern(path: Path, config: AssistantConfig) -> bool:
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in config.approved_file_patterns)


def _excluded(project_root: Path, path: Path, config: AssistantConfig) -> bool:
    relative = _relative(project_root, path)
    excluded_fragments = (
        "data/raw/",
        "data/quarantine/",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "outputs/genai/",
        "reports/genai/",
        ".env",
    )
    if any(fragment in relative for fragment in excluded_fragments):
        return True
    return any(fnmatch.fnmatch(relative, pattern) for pattern in config.excluded_file_patterns)


def _source_id(relative_path: str) -> str:
    return "SRC-" + hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12].upper()


def _relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name
