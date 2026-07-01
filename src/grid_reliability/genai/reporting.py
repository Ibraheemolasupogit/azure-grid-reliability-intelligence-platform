"""Markdown reports for assistant runs."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.genai.models import AssistantResponse, EvaluationResult


def write_reports(
    *,
    project_root: Path,
    report_root: Path,
    run_id: str,
    responses: tuple[AssistantResponse, ...],
    evaluations: tuple[EvaluationResult, ...],
    metrics: dict[str, Any],
) -> dict[str, Path]:
    root = project_root / report_root / run_id
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "operations": root / "assistant_operations_report.md",
        "grounding": root / "grounding_and_citation_report.md",
        "safety": root / "safety_report.md",
        "methodology": root / "assistant_methodology.md",
        "executive": root / "executive_assistant_summary.md",
        "evaluation": root / "assistant_evaluation.md",
    }
    _write(paths["operations"], _operations(responses, metrics))
    _write(paths["grounding"], _grounding(responses, metrics))
    _write(paths["safety"], _safety(metrics))
    _write(paths["methodology"], _methodology())
    _write(paths["executive"], _executive(metrics))
    _write(paths["evaluation"], _evaluation(evaluations, metrics))
    return paths


def _operations(responses: tuple[AssistantResponse, ...], metrics: dict[str, Any]) -> list[str]:
    lines = ["# Assistant Operations Report", "", "## Responses", ""]
    for response in responses:
        lines.append(
            f"- `{response.query_id}`: `{response.response_status}` ({response.query_category})"
        )
    lines.extend(["", f"- Queries processed: {metrics.get('queries_processed', 0)}"])
    return lines


def _grounding(responses: tuple[AssistantResponse, ...], metrics: dict[str, Any]) -> list[str]:
    return [
        "# Grounding And Citation Report",
        "",
        f"- Average retrieval score: {metrics.get('average_retrieval_score', 0)}",
        f"- Average grounding coverage: {metrics.get('average_grounding_coverage', 0)}",
        f"- Citation coverage: {metrics.get('citation_coverage', 0)}",
        "",
        "| Query | Citations | Confidence |",
        "| --- | --- | ---: |",
        *[
            f"| {row.query_id} | {' '.join(row.citation_ids)} | "
            f"{row.response_confidence if row.response_confidence is not None else ''} |"
            for row in responses
        ],
    ]


def _safety(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "# Safety Report",
        "",
        "Restricted requests are refused and no action is executed.",
        "",
    ]
    for reason, count in metrics.get("safety_rule_counts", {}).items():
        lines.append(f"- `{reason}`: {count}")
    if not metrics.get("safety_rule_counts"):
        lines.append("- No restricted requests.")
    return lines


def _methodology() -> list[str]:
    return [
        "# Assistant Methodology",
        "",
        "The assistant discovers approved repository-local evidence, extracts text "
        "from Markdown, JSON, YAML, and CSV files, chunks text deterministically, "
        "builds a local lexical index, classifies queries with deterministic keyword "
        "rules, retrieves evidence, applies grounding and safety checks, and "
        "generates template-based responses with citations.",
        "",
        "No external model, Azure AI Foundry, Azure AI Search, Azure OpenAI, "
        "internet access, or operational action is used.",
    ]


def _executive(metrics: dict[str, Any]) -> list[str]:
    return [
        "# Executive Assistant Summary",
        "",
        f"- Queries processed: {metrics.get('queries_processed', 0)}",
        f"- Grounded responses: {metrics.get('grounded', 0)}",
        f"- Restricted requests: {metrics.get('restricted_requests', 0)}",
        f"- Zero-result queries: {metrics.get('zero_result_queries', 0)}",
        "",
        "All evidence is synthetic and repository-local.",
    ]


def _evaluation(evaluations: tuple[EvaluationResult, ...], metrics: dict[str, Any]) -> list[str]:
    lines = [
        "# Assistant Evaluation",
        "",
        f"- Evaluation queries: {metrics.get('evaluation_queries', 0)}",
        f"- Evaluation passed: {metrics.get('evaluation_passed', 0)}",
        "",
        "| Query | Passed | Category | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in evaluations:
        lines.append(
            f"| {row.query_id} | {row.passed} | {row.observed_category} | "
            f"{row.observed_response_status} |"
        )
    return lines


def _write(path: Path, lines: list[str]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write("\n".join(lines) + "\n")
    temp_path.replace(path)
