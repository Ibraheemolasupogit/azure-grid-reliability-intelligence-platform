"""Deterministic assistant evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from grid_reliability.genai.models import (
    AssistantResponse,
    EvaluationResult,
    QueryClassification,
    QueryInput,
)


def load_queries(path: Path) -> tuple[QueryInput, ...]:
    queries: list[QueryInput] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            queries.append(
                QueryInput(
                    query_id=str(payload["query_id"]),
                    query_text=str(payload["query_text"]),
                    expected_category=payload.get("expected_category"),
                    expected_source_components=tuple(payload.get("expected_source_components", [])),
                    expected_metric_names=tuple(payload.get("expected_metric_names", [])),
                    expected_reason_codes=tuple(payload.get("expected_reason_codes", [])),
                    expected_response_status=payload.get("expected_response_status"),
                    must_refuse=bool(payload.get("must_refuse", False)),
                    minimum_citations=int(payload.get("minimum_citations", 0)),
                )
            )
    return tuple(queries)


def evaluate_responses(
    queries: tuple[QueryInput, ...],
    classifications: dict[str, QueryClassification],
    responses: tuple[AssistantResponse, ...],
) -> tuple[EvaluationResult, ...]:
    response_by_query = {response.query_id: response for response in responses}
    results: list[EvaluationResult] = []
    for query in queries:
        classification = classifications[query.query_id]
        response = response_by_query[query.query_id]
        category_match = (
            query.expected_category is None
            or classification.query_category == query.expected_category
        )
        status_match = (
            query.expected_response_status is None
            or response.response_status == query.expected_response_status
        )
        citation_count = len(response.citation_ids)
        citation_met = citation_count >= query.minimum_citations
        refused = response.response_status == "REFUSED"
        passed = (
            category_match and status_match and citation_met and (not query.must_refuse or refused)
        )
        results.append(
            EvaluationResult(
                query_id=query.query_id,
                expected_category=query.expected_category,
                observed_category=classification.query_category,
                expected_response_status=query.expected_response_status,
                observed_response_status=response.response_status,
                category_match=category_match,
                response_status_match=status_match,
                citation_count=citation_count,
                minimum_citations=query.minimum_citations,
                citation_requirement_met=citation_met,
                must_refuse=query.must_refuse,
                refused=refused,
                passed=passed,
            )
        )
    return tuple(results)


def evaluation_metrics(results: tuple[EvaluationResult, ...]) -> dict[str, float | int]:
    total = len(results) or 1
    return {
        "evaluation_queries": len(results),
        "evaluation_passed": sum(1 for row in results if row.passed),
        "category_accuracy": sum(1 for row in results if row.category_match) / total,
        "response_status_accuracy": sum(1 for row in results if row.response_status_match) / total,
        "citation_requirement_rate": sum(1 for row in results if row.citation_requirement_met)
        / total,
        "restricted_request_detection_rate": sum(
            1 for row in results if not row.must_refuse or row.refused
        )
        / total,
    }
