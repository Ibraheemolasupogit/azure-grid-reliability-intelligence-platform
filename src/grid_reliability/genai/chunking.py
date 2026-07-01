"""Deterministic evidence chunking."""

from __future__ import annotations

import hashlib

from grid_reliability.genai.config import AssistantConfig
from grid_reliability.genai.models import EvidenceChunk, NormalizedDocument


def chunk_documents(
    documents: tuple[NormalizedDocument, ...], config: AssistantConfig
) -> tuple[EvidenceChunk, ...]:
    chunks: list[EvidenceChunk] = []
    seen_hashes: set[str] = set()
    for document in documents:
        for index, content in enumerate(_split(document.content, config), start=1):
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            duplicate_key = f"{document.source_path}|{content_hash}"
            if duplicate_key in seen_hashes:
                continue
            seen_hashes.add(duplicate_key)
            chunks.append(_chunk(document, index, content, content_hash))
    return tuple(sorted(chunks, key=lambda item: item.chunk_id))


def _split(content: str, config: AssistantConfig) -> list[str]:
    if len(content) <= config.chunk_size_characters:
        return [content]
    chunks: list[str] = []
    step = config.chunk_size_characters - config.chunk_overlap_characters
    start = 0
    while start < len(content):
        end = min(len(content), start + config.chunk_size_characters)
        chunks.append(content[start:end].strip())
        if end == len(content):
            break
        start += step
    return [chunk for chunk in chunks if chunk]


def _chunk(
    document: NormalizedDocument, index: int, content: str, content_hash: str
) -> EvidenceChunk:
    chunk_id = (
        "CHK-"
        + hashlib.sha256(f"{document.document_id}|{index}|{content_hash}".encode())
        .hexdigest()[:12]
        .upper()
    )
    return EvidenceChunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        source_id=document.source_id,
        chunk_index=index,
        content=content,
        content_hash=content_hash,
        component_name=document.component_name,
        source_type=document.source_type,
        section_title=document.section_title,
        source_path=document.source_path,
        source_checksum=document.source_checksum,
        run_id=document.run_id,
        entity_type=document.entity_type,
        entity_id=document.entity_id,
        metric_names=document.metric_names,
        reason_codes=document.reason_codes,
        allowed_query_categories=document.allowed_query_categories,
        synthetic_data_flag=document.synthetic_data_flag,
    )
