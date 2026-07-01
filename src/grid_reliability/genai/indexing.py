"""Deterministic lexical indexing and scoring."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter

from grid_reliability.genai.models import EvidenceChunk, QueryClassification

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_\-]*")


class LexicalIndex:
    def __init__(self, chunks: tuple[EvidenceChunk, ...]) -> None:
        self.chunks = tuple(sorted(chunks, key=lambda item: item.chunk_id))
        self.tokens = {chunk.chunk_id: Counter(tokenize(chunk.content)) for chunk in self.chunks}
        self.document_frequency = _document_frequency(self.tokens)
        self.checksum = _index_checksum(self.chunks)

    def search(
        self,
        query_text: str,
        classification: QueryClassification,
        *,
        top_k: int,
        minimum_score: float,
    ) -> list[tuple[EvidenceChunk, float, str]]:
        query_tokens = Counter(tokenize(query_text))
        scored: list[tuple[EvidenceChunk, float, str]] = []
        for chunk in self.chunks:
            if classification.query_category not in chunk.allowed_query_categories:
                continue
            score, rationale = self._score(chunk, query_tokens, classification)
            if score >= minimum_score:
                scored.append((chunk, round(score, 6), rationale))
        scored.sort(key=lambda item: (-item[1], item[0].source_path, item[0].chunk_id))
        return scored[:top_k]

    def _score(
        self,
        chunk: EvidenceChunk,
        query_tokens: Counter[str],
        classification: QueryClassification,
    ) -> tuple[float, str]:
        chunk_tokens = self.tokens[chunk.chunk_id]
        if not query_tokens or not chunk_tokens:
            return 0.0, "no lexical terms"
        lexical = 0.0
        for token, count in query_tokens.items():
            if token in chunk_tokens:
                idf = math.log((1 + len(self.chunks)) / (1 + self.document_frequency[token])) + 1
                lexical += min(count, chunk_tokens[token]) * idf
        normaliser = max(1.0, sum(query_tokens.values()))
        score = lexical / normaliser
        boosts: list[str] = []
        if chunk.component_name in classification.components_requested:
            score += 1.0
            boosts.append("component")
        if chunk.entity_id and chunk.entity_id in classification.entities_detected:
            score += 1.0
            boosts.append("entity")
        if classification.query_category in chunk.allowed_query_categories:
            score += 0.3
            boosts.append("category")
        metric_overlap = set(chunk.metric_names) & set(query_tokens)
        if metric_overlap:
            score += 0.5
            boosts.append("metric")
        return score, "+".join(boosts) or "lexical"


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _document_frequency(tokens: dict[str, Counter[str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for chunk_tokens in tokens.values():
        for token in chunk_tokens:
            counts[token] += 1
    return counts


def _index_checksum(chunks: tuple[EvidenceChunk, ...]) -> str:
    payload = [
        {"chunk_id": chunk.chunk_id, "content_hash": chunk.content_hash}
        for chunk in sorted(chunks, key=lambda item: item.chunk_id)
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
