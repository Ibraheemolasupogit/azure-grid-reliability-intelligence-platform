from __future__ import annotations

import json
from pathlib import Path

import pytest

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.genai.chunking import chunk_documents
from grid_reliability.genai.config import load_assistant_config
from grid_reliability.genai.discovery import discover_sources
from grid_reliability.genai.extractors import extract_documents
from grid_reliability.genai.indexing import LexicalIndex
from grid_reliability.genai.models import QueryInput
from grid_reliability.genai.pipeline import main, run_assistant
from grid_reliability.genai.query_classifier import classify_query
from grid_reliability.genai.safety import safety_status


def test_assistant_config_validation(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_assistant_config(config_path, project_root=tmp_path)
    assert config.provider == "deterministic_local"
    assert config.retrieval_method == "lexical_bm25"

    bad_provider = config_path.read_text(encoding="utf-8").replace(
        "deterministic_local", "network_model"
    )
    bad_path = tmp_path / "bad-provider.yaml"
    bad_path.write_text(bad_provider, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="provider"):
        load_assistant_config(bad_path, project_root=tmp_path)

    bad_overlap = config_path.read_text(encoding="utf-8").replace(
        "chunk_overlap_characters: 10", "chunk_overlap_characters: 600"
    )
    bad_overlap_path = tmp_path / "bad-overlap.yaml"
    bad_overlap_path.write_text(bad_overlap, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="smaller"):
        load_assistant_config(bad_overlap_path, project_root=tmp_path)

    unsafe = config_path.read_text(encoding="utf-8").replace(
        "output_root: outputs/genai", "output_root: ../outside"
    )
    unsafe_path = tmp_path / "unsafe.yaml"
    unsafe_path.write_text(unsafe, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_assistant_config(unsafe_path, project_root=tmp_path)


def test_source_discovery_extraction_chunking_and_retrieval(tmp_path: Path) -> None:
    config = load_assistant_config(_write_config(tmp_path), project_root=tmp_path)
    _write_base_config(tmp_path)
    _write_sources(tmp_path)
    sources = discover_sources(tmp_path, config)
    assert {source.component_name for source in sources} >= {"forecasting", "monitoring"}
    assert all(not source.source_path.startswith("data/raw") for source in sources)

    documents = extract_documents(tmp_path, sources)
    chunks = chunk_documents(documents, config)
    assert documents
    assert chunks
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)

    classification = classify_query(
        QueryInput("Q1", "Summarise the latest demand forecast and MAE.")
    )
    index = LexicalIndex(chunks)
    results = index.search(
        "Summarise the latest demand forecast and MAE.",
        classification,
        top_k=3,
        minimum_score=0.01,
    )
    assert results
    assert results[0][0].component_name == "forecasting"


def test_classification_and_safety() -> None:
    forecast = classify_query(QueryInput("Q1", "Summarise the latest demand forecast."))
    assert forecast.query_category == "forecast_summary"
    assert safety_status(forecast) == (True, None)

    restricted = classify_query(QueryInput("Q2", "Open this breaker now."))
    allowed, reason = safety_status(restricted)
    assert not allowed
    assert reason == "RESTRICTED_OPERATIONAL_CONTROL"

    alert_suppression = classify_query(
        QueryInput("Q4", "Suppress this safety alert automatically.")
    )
    allowed, reason = safety_status(alert_suppression)
    assert not allowed
    assert reason == "RESTRICTED_ALERT_SUPPRESSION"

    live = classify_query(QueryInput("Q3", "What is the current live status of the real grid?"))
    allowed, reason = safety_status(live)
    assert not allowed
    assert reason == "UNSUPPORTED_REAL_WORLD_STATUS"


def test_run_assistant_outputs_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_base_config(tmp_path)
    _write_sources(tmp_path)
    config_path = _write_config(tmp_path)
    query_path = _write_queries(tmp_path)
    config = load_assistant_config(config_path, project_root=tmp_path)

    result, outputs = run_assistant(
        config,
        project_root=tmp_path,
        config_path=config_path,
        query_file=query_path,
    )
    assert result.run_id == "assistant-ci"
    assert len(result.responses) == 3
    assert any(response.response_status == "REFUSED" for response in result.responses)
    assert outputs.output_paths["responses"].exists()
    assert outputs.output_paths["manifest"].exists()
    assert outputs.report_paths["safety"].exists()

    first = outputs.output_paths["responses"].read_text(encoding="utf-8")
    result2, outputs2 = run_assistant(
        config,
        project_root=tmp_path,
        config_path=config_path,
        query_file=query_path,
    )
    assert result2.run_id == result.run_id
    assert outputs2.output_paths["responses"].read_text(encoding="utf-8") == first

    monkeypatch.chdir(tmp_path)
    assert main(["--config", str(config_path), "--query", "Summarise monitoring alerts."]) == 0
    with pytest.raises(SystemExit) as exc:
        main(["--config", str(tmp_path / "missing.yaml")])
    assert exc.value.code == 2


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "genai.yaml"
    path.write_text(
        """
profile: ci
source_roots:
  - reports
  - outputs
  - docs
  - configs/data_contracts
approved_components:
  - forecasting
  - monitoring
  - reliability
  - documentation
  - contracts
approved_file_patterns:
  - "*.md"
  - "*.json"
  - "*.csv"
  - "*.yaml"
excluded_file_patterns:
  - "data/raw/*"
  - "outputs/genai/*"
  - "reports/genai/*"
index_root: outputs/genai/index
output_root: outputs/genai
report_root: reports/genai
provider: deterministic_local
retrieval_method: lexical_bm25
top_k: 4
minimum_relevance_score: 0.01
maximum_context_chunks: 3
maximum_context_characters: 3000
chunk_size_characters: 500
chunk_overlap_characters: 10
citation_required: true
minimum_grounding_coverage: 0.2
allowed_query_categories:
  - forecast_summary
  - monitoring_alerts
  - reliability_performance
  - methodology
restricted_action_patterns:
  - open breaker
safety_refusal_mode: refuse_and_redirect
synthetic_data_disclaimer: "Synthetic local evidence only."
schema_version: 9.0.0
run_id_strategy: deterministic
query_timestamp: "2026-01-02T00:00:00Z"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_base_config(tmp_path: Path) -> None:
    base = tmp_path / "configs/base.yaml"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(
        """
project:
  name: azure-grid-reliability-intelligence-platform
runtime:
  environment: local
  timezone: UTC
  random_seed: 42
paths:
  data_root: data
  output_root: outputs
  raw_data: data/raw
  interim_data: data/interim
  processed_data: data/processed
  reports: reports
logging:
  level: INFO
  json: false
pipeline_components:
  planned: []
azure_service_mapping: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_sources(tmp_path: Path) -> None:
    forecast = tmp_path / "outputs/forecasting/forecast-ci"
    forecast.mkdir(parents=True, exist_ok=True)
    (forecast / "metrics.json").write_text(
        json.dumps(
            {
                "forecast_run_id": "forecast-ci",
                "selected_model": "persistence",
                "selected_model_test_mae": 8.5,
                "metrics": [{"metric_name": "mae", "value": 8.5}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monitoring = tmp_path / "outputs/monitoring"
    monitoring.mkdir(parents=True, exist_ok=True)
    (monitoring / "alerts.csv").write_text(
        "component_name,metric_name,severity,reason_code\n"
        "monitoring,wape,WARNING,FORECAST_WAPE_HIGH\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs/reliability"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "kpi-definitions.md").write_text(
        "# KPI Definitions\n\nSAIFI and SAIDI are reliability metrics for synthetic data.\n",
        encoding="utf-8",
    )
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "secret.csv").write_text("do,not,index\n", encoding="utf-8")


def _write_queries(tmp_path: Path) -> Path:
    path = tmp_path / "questions.jsonl"
    rows = [
        {
            "query_id": "Q1",
            "query_text": "Summarise the latest demand forecast.",
            "expected_category": "forecast_summary",
            "expected_response_status": "GROUNDED",
            "minimum_citations": 1,
        },
        {
            "query_id": "Q2",
            "query_text": "Which monitoring alerts require human attention?",
            "expected_category": "monitoring_alerts",
            "expected_response_status": "GROUNDED",
            "minimum_citations": 1,
        },
        {
            "query_id": "Q3",
            "query_text": "Open this breaker.",
            "expected_response_status": "REFUSED",
            "must_refuse": True,
        },
    ]
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path
