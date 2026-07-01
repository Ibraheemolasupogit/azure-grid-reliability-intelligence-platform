"""Grounding and confidence checks."""

from __future__ import annotations

from statistics import mean

from grid_reliability.genai.config import AssistantConfig
from grid_reliability.genai.models import (
    EvidenceChunk,
    GroundingResult,
    GroundingStatus,
    QueryClassification,
    RetrievalResult,
)


def evaluate_grounding(
    config: AssistantConfig,
    classification: QueryClassification,
    chunks: tuple[EvidenceChunk, ...],
    retrievals: tuple[RetrievalResult, ...],
    *,
    safety_allowed: bool,
    safety_reason_code: str | None,
) -> GroundingResult:
    if not safety_allowed:
        return GroundingResult(
            GroundingStatus.RESTRICTED_REQUEST,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            None,
            safety_reason_code,
        )
    if not chunks or not retrievals:
        return GroundingResult(
            GroundingStatus.INSUFFICIENT_EVIDENCE,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            "INSUFFICIENT_GROUNDED_EVIDENCE",
        )
    average_score = mean(row.score for row in retrievals)
    grounding_coverage = min(1.0, len(chunks) / max(1, config.maximum_context_chunks))
    citation_coverage = 1.0 if config.citation_required else 0.0
    source_diversity = min(1.0, len({chunk.source_id for chunk in chunks}) / 3)
    entity_match = _entity_match(classification, chunks)
    run_consistency = _run_consistency(chunks)
    confidence = min(
        1.0,
        (min(1.0, average_score / 3) + grounding_coverage + citation_coverage + run_consistency)
        / 4,
    )
    if grounding_coverage >= config.minimum_grounding_coverage and confidence >= 0.45:
        status = GroundingStatus.GROUNDED
        reason = None
    else:
        status = GroundingStatus.PARTIALLY_GROUNDED
        reason = "INSUFFICIENT_GROUNDED_EVIDENCE"
    return GroundingResult(
        status,
        round(grounding_coverage, 6),
        citation_coverage,
        round(source_diversity, 6),
        entity_match,
        run_consistency,
        round(confidence, 6),
        reason,
    )


def _entity_match(classification: QueryClassification, chunks: tuple[EvidenceChunk, ...]) -> float:
    if not classification.entities_detected:
        return 1.0
    chunk_entities = {chunk.entity_id for chunk in chunks if chunk.entity_id}
    return 1.0 if set(classification.entities_detected) & chunk_entities else 0.0


def _run_consistency(chunks: tuple[EvidenceChunk, ...]) -> float:
    run_ids = {chunk.run_id for chunk in chunks if chunk.run_id}
    if len(run_ids) <= 1:
        return 1.0
    return 0.75
