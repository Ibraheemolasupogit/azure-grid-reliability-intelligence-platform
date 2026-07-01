"""Deterministic local response provider."""

from __future__ import annotations

from grid_reliability.genai.models import (
    GenerationRequest,
    GenerationResult,
    GroundingStatus,
    ResponseStatus,
)


class DeterministicLocalProvider:
    """Template-based provider that uses only retrieved chunks."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.grounding.status == GroundingStatus.RESTRICTED_REQUEST:
            return _restricted_response(request)
        if request.grounding.status == GroundingStatus.INSUFFICIENT_EVIDENCE:
            return _insufficient_response(request)
        citations = tuple(citation.citation_id for citation in request.citations)
        findings = _findings(request)
        status = (
            ResponseStatus.GROUNDED
            if request.grounding.status == GroundingStatus.GROUNDED
            else ResponseStatus.PARTIALLY_GROUNDED
        )
        answer = (
            f"Using governed repository evidence for `{request.classification.query_category}`, "
            f"the assistant found {len(request.chunks)} relevant evidence chunk(s): "
            f"{', '.join(citations) if citations else 'no citations available'}."
        )
        return GenerationResult(
            response_status=status,
            answer=answer,
            key_findings=findings,
            limitations=(
                request.synthetic_data_disclaimer,
                "Findings support human review only and are not live grid status.",
            ),
            recommended_human_review=(
                "Review the cited local evidence before operational decisions."
            ),
            citation_ids=citations,
        )


def _findings(request: GenerationRequest) -> tuple[str, ...]:
    findings: list[str] = []
    for citation, chunk in zip(request.citations, request.chunks, strict=False):
        snippet = chunk.content.replace("\n", " ")[:220]
        findings.append(f"{snippet} [{citation.citation_id}]")
    return tuple(findings[:5])


def _restricted_response(request: GenerationRequest) -> GenerationResult:
    return GenerationResult(
        response_status=ResponseStatus.REFUSED,
        answer=(
            "I cannot provide or execute operational-control instructions. "
            "The repository evidence can only support human review of analytical findings."
        ),
        key_findings=(),
        limitations=(request.synthetic_data_disclaimer, "Restricted operational action refused."),
        recommended_human_review="Use authorised operational procedures outside this assistant.",
        citation_ids=(),
    )


def _insufficient_response(request: GenerationRequest) -> GenerationResult:
    return GenerationResult(
        response_status=ResponseStatus.INSUFFICIENT_EVIDENCE,
        answer="I do not have enough governed repository evidence to answer that question.",
        key_findings=(),
        limitations=(request.synthetic_data_disclaimer, "No unsupported claim was generated."),
        recommended_human_review=(
            "Generate or approve more local evidence before relying on an answer."
        ),
        citation_ids=(),
    )
