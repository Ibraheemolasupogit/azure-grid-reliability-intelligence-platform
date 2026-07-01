"""Local GenAI grid operations assistant pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.genai.chunking import chunk_documents
from grid_reliability.genai.citations import build_citations
from grid_reliability.genai.config import AssistantConfig, load_assistant_config
from grid_reliability.genai.deterministic_provider import DeterministicLocalProvider
from grid_reliability.genai.discovery import discover_sources
from grid_reliability.genai.evaluation import (
    evaluate_responses,
    evaluation_metrics,
    load_queries,
)
from grid_reliability.genai.extractors import extract_documents
from grid_reliability.genai.grounding import evaluate_grounding
from grid_reliability.genai.indexing import LexicalIndex
from grid_reliability.genai.models import (
    AssistantError,
    AssistantResponse,
    AssistantRunResult,
    Citation,
    EvidenceChunk,
    GenerationRequest,
    GroundingStatus,
    PromptAuditRecord,
    QueryClassification,
    QueryInput,
    ResponseStatus,
    RetrievalResult,
    utc_timestamp,
)
from grid_reliability.genai.persistence import manifest_payload, write_outputs
from grid_reliability.genai.query_classifier import classify_query, query_id
from grid_reliability.genai.reporting import write_reports
from grid_reliability.genai.safety import safety_status


@dataclass(frozen=True)
class PipelineOutputs:
    output_paths: dict[str, Path]
    report_paths: dict[str, Path]


def build_run_id(config: AssistantConfig, provided: str | None = None) -> str:
    if provided:
        return provided
    if config.run_id_strategy == "deterministic":
        return "assistant-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_assistant(
    config: AssistantConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
    config_path: Path | None = None,
    query_text: str | None = None,
    query_file: Path | None = None,
    entity_id: str | None = None,
) -> tuple[AssistantRunResult, PipelineOutputs]:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config, run_id)
    sources = discover_sources(root, config)
    documents = extract_documents(root, sources)
    chunks = chunk_documents(documents, config)
    index = LexicalIndex(chunks)
    queries = _queries(
        root, config, query_text=query_text, query_file=query_file, entity_id=entity_id
    )
    provider = DeterministicLocalProvider()

    responses: list[AssistantResponse] = []
    all_retrievals: list[RetrievalResult] = []
    all_citations: list[Citation] = []
    audits: list[PromptAuditRecord] = []
    classifications: dict[str, QueryClassification] = {}
    timestamp = utc_timestamp(config.query_timestamp)
    for query in queries:
        classification = classify_query(query)
        classifications[query.query_id] = classification
        safety_allowed, safety_reason = safety_status(classification)
        scored = index.search(
            query.query_text,
            classification,
            top_k=config.top_k,
            minimum_score=config.minimum_relevance_score,
        )
        selected_chunks = tuple(chunk for chunk, _, _ in scored[: config.maximum_context_chunks])
        selected_chunks = _bounded_context(selected_chunks, config.maximum_context_characters)
        retrievals = tuple(
            RetrievalResult(
                query_id=query.query_id,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_id=chunk.source_id,
                source_path=chunk.source_path,
                component_name=chunk.component_name,
                score=score,
                scoring_rationale=rationale,
                rank=rank,
            )
            for rank, (chunk, score, rationale) in enumerate(scored[: config.top_k], start=1)
        )
        grounding = evaluate_grounding(
            config,
            classification,
            selected_chunks,
            retrievals,
            safety_allowed=safety_allowed,
            safety_reason_code=safety_reason,
        )
        citations = (
            build_citations(selected_chunks)
            if grounding.status
            not in {
                GroundingStatus.RESTRICTED_REQUEST,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
            }
            else ()
        )
        request = GenerationRequest(
            query=query,
            classification=classification,
            chunks=selected_chunks,
            citations=citations,
            grounding=grounding,
            synthetic_data_disclaimer=config.synthetic_data_disclaimer,
            schema_version=config.schema_version,
        )
        generation = provider.generate(request)
        response = _response(
            effective_run_id,
            timestamp,
            query,
            classification,
            generation,
            retrievals,
            grounding,
            safety_reason,
            config,
        )
        responses.append(response)
        all_retrievals.extend(retrievals)
        all_citations.extend(citations)
        audits.append(_audit(config, classification, selected_chunks, grounding, response))

    evaluations = evaluate_responses(queries, classifications, tuple(responses))
    metrics = _metrics(
        tuple(responses),
        tuple(all_retrievals),
        tuple(all_citations),
        classifications,
        evaluations,
    )
    metrics.update(evaluation_metrics(evaluations))
    source_checksums = {source.source_path: source.source_checksum for source in sources}
    query_fixture_checksum = _query_fixture_checksum(root, config, query_file)
    manifest = manifest_payload(
        project_name=settings.project_name,
        run_id=effective_run_id,
        provider=config.provider,
        configuration_checksum=sha256_file(config_path)
        if config_path and config_path.exists()
        else None,
        source_checksums=source_checksums,
        document_count=len(documents),
        chunk_count=len(chunks),
        index_checksum=index.checksum,
        query_fixture_checksum=query_fixture_checksum,
        metrics=metrics,
    )
    output_paths = write_outputs(
        project_root=root,
        output_root=config.output_root,
        run_id=effective_run_id,
        responses=tuple(responses),
        retrievals=tuple(all_retrievals),
        citations=tuple(all_citations),
        prompt_audits=tuple(audits),
        classifications=tuple(classifications.values()),
        evaluations=evaluations,
        metrics=metrics,
        manifest=manifest,
    )
    report_paths = write_reports(
        project_root=root,
        report_root=config.report_root,
        run_id=effective_run_id,
        responses=tuple(responses),
        evaluations=evaluations,
        metrics=metrics,
    )
    result = AssistantRunResult(
        run_id=effective_run_id,
        documents=documents,
        chunks=chunks,
        responses=tuple(responses),
        retrieval_results=tuple(all_retrievals),
        citations=tuple(all_citations),
        evaluations=evaluations,
        metrics=metrics,
    )
    return result, PipelineOutputs(output_paths, report_paths)


def _queries(
    root: Path,
    config: AssistantConfig,
    *,
    query_text: str | None,
    query_file: Path | None,
    entity_id: str | None,
) -> tuple[QueryInput, ...]:
    if query_text:
        text = f"{query_text} {entity_id}" if entity_id else query_text
        return (QueryInput(query_id=query_id(text), query_text=text),)
    path = query_file or config.query_file
    if path is None:
        return (
            QueryInput(
                query_id="QRY-DEFAULT",
                query_text="Summarise the latest platform monitoring alerts.",
            ),
        )
    if not path.is_absolute():
        path = root / path
    return load_queries(path)


def _bounded_context(
    chunks: tuple[EvidenceChunk, ...], max_chars: int
) -> tuple[EvidenceChunk, ...]:
    selected: list[EvidenceChunk] = []
    total = 0
    for chunk in chunks:
        if total + len(chunk.content) > max_chars and selected:
            break
        selected.append(chunk)
        total += len(chunk.content)
    return tuple(selected)


def _response(
    run_id: str,
    timestamp: datetime,
    query: QueryInput,
    classification: QueryClassification,
    generation: Any,
    retrievals: tuple[RetrievalResult, ...],
    grounding: Any,
    safety_reason: str | None,
    config: AssistantConfig,
) -> AssistantResponse:
    retrieval_score = mean([row.score for row in retrievals]) if retrievals else 0.0
    reason = safety_reason or grounding.reason_code
    return AssistantResponse(
        assistant_run_id=run_id,
        query_id=query.query_id,
        query_timestamp=timestamp,
        query_text=query.query_text,
        query_category=classification.query_category,
        response_status=generation.response_status.value,
        answer=generation.answer,
        key_findings=generation.key_findings,
        limitations=generation.limitations,
        recommended_human_review=generation.recommended_human_review,
        citation_ids=generation.citation_ids,
        retrieval_score=round(retrieval_score, 6),
        grounding_coverage=grounding.grounding_coverage,
        citation_coverage=grounding.citation_coverage,
        response_confidence=grounding.response_confidence,
        safety_reason_code=reason,
        synthetic_data_flag=bool(config.synthetic_data_disclaimer),
        schema_version=config.schema_version,
    )


def _audit(
    config: AssistantConfig,
    classification: QueryClassification,
    chunks: tuple[Any, ...],
    grounding: Any,
    response: AssistantResponse,
) -> PromptAuditRecord:
    context = "\n".join(chunk.content for chunk in chunks)
    prompt_hash = hashlib.sha256(
        f"{classification.query_text}|{classification.query_category}|{context}".encode()
    ).hexdigest()
    return PromptAuditRecord(
        query_id=classification.query_id,
        provider=config.provider,
        query_category=classification.query_category,
        retrieved_chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
        prompt_hash=prompt_hash,
        context_character_count=len(context),
        response_status=response.response_status,
        safety_status=grounding.status.value,
    )


def _metrics(
    responses: tuple[AssistantResponse, ...],
    retrievals: tuple[RetrievalResult, ...],
    citations: tuple[Any, ...],
    classifications: dict[str, QueryClassification],
    evaluations: tuple[Any, ...],
) -> dict[str, Any]:
    response_counts = Counter(response.response_status for response in responses)
    category_counts = Counter(response.query_category for response in responses)
    safety_counts = Counter(
        response.safety_reason_code for response in responses if response.safety_reason_code
    )
    return {
        "queries_processed": len(responses),
        "grounded": response_counts.get(ResponseStatus.GROUNDED.value, 0),
        "partially_grounded": response_counts.get(ResponseStatus.PARTIALLY_GROUNDED.value, 0),
        "insufficient_evidence": response_counts.get(ResponseStatus.INSUFFICIENT_EVIDENCE.value, 0),
        "restricted_requests": response_counts.get(ResponseStatus.REFUSED.value, 0),
        "zero_result_queries": sum(1 for response in responses if response.retrieval_score == 0),
        "average_retrieval_score": round(
            mean([row.retrieval_score for row in responses]) if responses else 0.0, 6
        ),
        "average_grounding_coverage": round(
            mean([row.grounding_coverage for row in responses]) if responses else 0.0, 6
        ),
        "citation_coverage": round(
            mean([row.citation_coverage for row in responses]) if responses else 0.0, 6
        ),
        "source_family_usage": dict(
            sorted(Counter(row.component_name for row in retrievals).items())
        ),
        "query_category_counts": dict(sorted(category_counts.items())),
        "response_status_counts": dict(sorted(response_counts.items())),
        "safety_rule_counts": dict(
            sorted((str(key), value) for key, value in safety_counts.items())
        ),
        "citation_count": len(citations),
        "classification_count": len(classifications),
        "evaluation_count": len(evaluations),
    }


def _query_fixture_checksum(
    root: Path, config: AssistantConfig, query_file: Path | None
) -> str | None:
    path = query_file or config.query_file
    if path is None:
        return None
    if not path.is_absolute():
        path = root / path
    return sha256_file(path) if path.exists() else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local grid operations assistant.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--index-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--query")
    parser.add_argument("--query-file")
    parser.add_argument("--category")
    parser.add_argument("--entity-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = resolve_project_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    try:
        config = load_assistant_config(
            config_path,
            project_root=root,
            source_root=args.source_root,
            index_root=args.index_root,
            output_root=args.output_root,
            report_root=args.report_root,
            category=args.category,
        )
        query_file = Path(args.query_file) if args.query_file else None
        result, outputs = run_assistant(
            config,
            project_root=root,
            run_id=args.run_id,
            config_path=config_path,
            query_text=args.query,
            query_file=query_file,
            entity_id=args.entity_id,
        )
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except AssistantError as exc:
        print(json.dumps({"run_status": "FAILED_ASSISTANT_SOURCE", "error": str(exc)}))
        return 3
    except Exception as exc:
        print(json.dumps({"run_status": "FAILED_ASSISTANT_PROCESSING", "error": str(exc)}))
        return 1
    print(
        f"Assistant run {result.run_id}: queries={len(result.responses)}; "
        f"documents={len(result.documents)}; chunks={len(result.chunks)}; "
        f"responses={outputs.output_paths['responses']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
