"""Citation construction for retrieved evidence."""

from __future__ import annotations

from grid_reliability.genai.models import Citation, EvidenceChunk


def build_citations(chunks: tuple[EvidenceChunk, ...]) -> tuple[Citation, ...]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for chunk in chunks:
        key = f"{chunk.source_id}|{chunk.section_title}|{chunk.content_hash}"
        if key in seen:
            continue
        seen.add(key)
        citation_id = f"SRC-{len(citations) + 1:03d}"
        citations.append(
            Citation(
                citation_id=citation_id,
                source_id=chunk.source_id,
                source_path=chunk.source_path,
                section_title=chunk.section_title,
                row_or_record_reference=chunk.section_title
                if "row" in chunk.section_title.lower()
                else None,
                source_run_id=chunk.run_id,
                content_hash=chunk.content_hash,
                claim_types=_claim_types(chunk),
            )
        )
    return tuple(citations)


def _claim_types(chunk: EvidenceChunk) -> tuple[str, ...]:
    claims = ["repository_evidence"]
    if chunk.metric_names:
        claims.append("metric")
    if chunk.reason_codes:
        claims.append("reason_code")
    if chunk.component_name in {"forecasting", "outage_prediction"}:
        claims.append("model_output")
    return tuple(claims)
