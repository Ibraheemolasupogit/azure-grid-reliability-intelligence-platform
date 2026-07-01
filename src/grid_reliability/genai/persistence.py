"""Persistence for assistant outputs."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from grid_reliability.common.metadata import __version__
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.genai.models import (
    AssistantResponse,
    Citation,
    EvaluationResult,
    PromptAuditRecord,
    QueryClassification,
    RetrievalResult,
    to_jsonable,
)


def write_outputs(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    responses: tuple[AssistantResponse, ...],
    retrievals: tuple[RetrievalResult, ...],
    citations: tuple[Citation, ...],
    prompt_audits: tuple[PromptAuditRecord, ...],
    classifications: tuple[QueryClassification, ...],
    evaluations: tuple[EvaluationResult, ...],
    metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Path]:
    root = project_root / output_root
    run_root = root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "responses": root / "grid_operations_responses.jsonl",
        "retrieval_results": run_root / "retrieval_results.jsonl",
        "citations": run_root / "citations.json",
        "prompt_audit": run_root / "prompt_audit.jsonl",
        "safety_evaluations": run_root / "safety_evaluations.jsonl",
        "evaluation_results": run_root / "evaluation_results.csv",
        "metrics": run_root / "metrics.json",
        "manifest": run_root / "assistant_manifest.json",
    }
    _write_jsonl(paths["responses"], responses)
    _write_jsonl(paths["retrieval_results"], retrievals)
    _write_json(paths["citations"], {"citations": [to_jsonable(row) for row in citations]})
    _write_jsonl(paths["prompt_audit"], prompt_audits)
    _write_jsonl(paths["safety_evaluations"], classifications)
    _write_evaluation(paths["evaluation_results"], evaluations)
    _write_json(paths["metrics"], metrics)
    manifest_payload = {
        **manifest,
        "component_version": __version__,
        "repository_revision": _repo_revision(project_root),
        "output_files": {
            name: _relative(project_root, path) for name, path in sorted(paths.items())
        },
    }
    _write_json(paths["manifest"], manifest_payload)
    manifest_payload["output_checksums"] = {
        name: sha256_file(path) for name, path in sorted(paths.items()) if name != "manifest"
    }
    _write_json(paths["manifest"], manifest_payload)
    return paths


def _write_jsonl(path: Path, rows: tuple[Any, ...]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        for row in rows:
            temp.write(json.dumps(to_jsonable(row), sort_keys=True) + "\n")
    temp_path.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        json.dump(to_jsonable(payload), temp, indent=2, sort_keys=True)
        temp.write("\n")
    temp_path.replace(path)


def _write_evaluation(path: Path, rows: tuple[EvaluationResult, ...]) -> None:
    fieldnames = [
        "query_id",
        "expected_category",
        "observed_category",
        "expected_response_status",
        "observed_response_status",
        "category_match",
        "response_status_match",
        "citation_count",
        "minimum_citations",
        "citation_requirement_met",
        "must_refuse",
        "refused",
        "passed",
    ]
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item.query_id):
            writer.writerow({key: to_jsonable(getattr(row, key)) for key in fieldnames})
    temp_path.replace(path)


def manifest_payload(
    *,
    project_name: str,
    run_id: str,
    provider: str,
    configuration_checksum: str | None,
    source_checksums: dict[str, str],
    document_count: int,
    chunk_count: int,
    index_checksum: str,
    query_fixture_checksum: str | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project": project_name,
        "assistant_run_id": run_id,
        "provider": provider,
        "configuration_checksum": configuration_checksum,
        "source_files": sorted(source_checksums),
        "source_checksums": source_checksums,
        "document_count": document_count,
        "chunk_count": chunk_count,
        "index_checksum": index_checksum,
        "query_fixture_checksum": query_fixture_checksum,
        "query_counts": metrics.get("query_category_counts", {}),
        "response_status_counts": metrics.get("response_status_counts", {}),
        "citation_counts": metrics.get("citation_count", 0),
        "safety_rule_counts": metrics.get("safety_rule_counts", {}),
        "synthetic_data_declaration": (
            "Assistant uses fictional synthetic repository-local evidence."
        ),
        "limitations": [
            "No Azure AI Foundry, Azure AI Search, Azure OpenAI, or external model is called.",
            "Responses are deterministic templates and cannot execute operational actions.",
            "No hidden chain-of-thought is persisted.",
        ],
    }


def _repo_revision(project_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name
