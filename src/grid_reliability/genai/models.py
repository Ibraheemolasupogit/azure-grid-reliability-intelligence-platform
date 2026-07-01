"""Typed models for the local grid operations assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AssistantError(Exception):
    """Raised when assistant processing cannot continue."""


class QueryCategory(StrEnum):
    GRID_STATUS = "grid_status"
    FORECAST_SUMMARY = "forecast_summary"
    ASSET_HEALTH = "asset_health"
    MAINTENANCE_PRIORITY = "maintenance_priority"
    OUTAGE_RISK = "outage_risk"
    RELIABILITY_PERFORMANCE = "reliability_performance"
    MONITORING_ALERTS = "monitoring_alerts"
    INCIDENT_INVESTIGATION = "incident_investigation"
    EXECUTIVE_SUMMARY = "executive_summary"
    METHODOLOGY = "methodology"
    UNSUPPORTED = "unsupported"


class GroundingStatus(StrEnum):
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    RESTRICTED_REQUEST = "RESTRICTED_REQUEST"


class ResponseStatus(StrEnum):
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class SourceEntry:
    source_family: str
    component_name: str
    file_pattern: str
    content_type: str
    trust_level: str
    allowed_query_categories: tuple[str, ...]
    contains_model_output: bool
    contains_historical_observation: bool
    contains_recommendation: bool
    synthetic_data_flag: bool


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    source_family: str
    component_name: str
    source_path: str
    content_type: str
    source_checksum: str
    trust_level: str
    allowed_query_categories: tuple[str, ...]
    synthetic_data_flag: bool


@dataclass(frozen=True)
class NormalizedDocument:
    document_id: str
    source_id: str
    component_name: str
    source_type: str
    section_title: str
    content: str
    content_hash: str
    source_path: str
    source_checksum: str
    run_id: str | None
    assessment_start: str | None
    assessment_end: str | None
    entity_type: str | None
    entity_id: str | None
    metric_names: tuple[str, ...]
    reason_codes: tuple[str, ...]
    allowed_query_categories: tuple[str, ...]
    synthetic_data_flag: bool


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document_id: str
    source_id: str
    chunk_index: int
    content: str
    content_hash: str
    component_name: str
    source_type: str
    section_title: str
    source_path: str
    source_checksum: str
    run_id: str | None
    entity_type: str | None
    entity_id: str | None
    metric_names: tuple[str, ...]
    reason_codes: tuple[str, ...]
    allowed_query_categories: tuple[str, ...]
    synthetic_data_flag: bool


@dataclass(frozen=True)
class QueryInput:
    query_id: str
    query_text: str
    expected_category: str | None = None
    expected_source_components: tuple[str, ...] = ()
    expected_metric_names: tuple[str, ...] = ()
    expected_reason_codes: tuple[str, ...] = ()
    expected_response_status: str | None = None
    must_refuse: bool = False
    minimum_citations: int = 0


@dataclass(frozen=True)
class QueryClassification:
    query_id: str
    query_text: str
    query_category: str
    entities_detected: tuple[str, ...]
    components_requested: tuple[str, ...]
    time_scope: str
    restricted_action_detected: bool
    unsupported_current_status: bool
    confidence: float
    classification_reason: str
    safety_reason_code: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    query_id: str
    chunk_id: str
    document_id: str
    source_id: str
    source_path: str
    component_name: str
    score: float
    scoring_rationale: str
    rank: int


@dataclass(frozen=True)
class GroundingResult:
    status: GroundingStatus
    grounding_coverage: float
    citation_coverage: float
    source_diversity: float
    entity_match: float
    run_consistency: float
    response_confidence: float | None
    reason_code: str | None


@dataclass(frozen=True)
class Citation:
    citation_id: str
    source_id: str
    source_path: str
    section_title: str
    row_or_record_reference: str | None
    source_run_id: str | None
    content_hash: str
    claim_types: tuple[str, ...]


@dataclass(frozen=True)
class GenerationRequest:
    query: QueryInput
    classification: QueryClassification
    chunks: tuple[EvidenceChunk, ...]
    citations: tuple[Citation, ...]
    grounding: GroundingResult
    synthetic_data_disclaimer: str
    schema_version: str


@dataclass(frozen=True)
class GenerationResult:
    response_status: ResponseStatus
    answer: str
    key_findings: tuple[str, ...]
    limitations: tuple[str, ...]
    recommended_human_review: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class AssistantResponse:
    assistant_run_id: str
    query_id: str
    query_timestamp: datetime
    query_text: str
    query_category: str
    response_status: str
    answer: str
    key_findings: tuple[str, ...]
    limitations: tuple[str, ...]
    recommended_human_review: str
    citation_ids: tuple[str, ...]
    retrieval_score: float
    grounding_coverage: float
    citation_coverage: float
    response_confidence: float | None
    safety_reason_code: str | None
    synthetic_data_flag: bool
    schema_version: str


@dataclass(frozen=True)
class PromptAuditRecord:
    query_id: str
    provider: str
    query_category: str
    retrieved_chunk_ids: tuple[str, ...]
    prompt_hash: str
    context_character_count: int
    response_status: str
    safety_status: str


@dataclass(frozen=True)
class EvaluationResult:
    query_id: str
    expected_category: str | None
    observed_category: str
    expected_response_status: str | None
    observed_response_status: str
    category_match: bool
    response_status_match: bool
    citation_count: int
    minimum_citations: int
    citation_requirement_met: bool
    must_refuse: bool
    refused: bool
    passed: bool


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_jsonable(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True)
class AssistantRunResult:
    run_id: str
    documents: tuple[NormalizedDocument, ...]
    chunks: tuple[EvidenceChunk, ...]
    responses: tuple[AssistantResponse, ...]
    retrieval_results: tuple[RetrievalResult, ...]
    citations: tuple[Citation, ...]
    evaluations: tuple[EvaluationResult, ...]
    metrics: dict[str, Any] = field(default_factory=dict)
