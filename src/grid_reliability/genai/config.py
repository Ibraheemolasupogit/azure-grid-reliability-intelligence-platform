"""Configuration loading for the local assistant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.genai.models import QueryCategory

PROVIDERS = {"deterministic_local", "azure_ai_foundry"}
RETRIEVAL_METHODS = {"lexical_bm25"}
CATEGORIES = {category.value for category in QueryCategory if category != QueryCategory.UNSUPPORTED}


@dataclass(frozen=True)
class AssistantConfig:
    source_roots: tuple[Path, ...]
    approved_components: tuple[str, ...]
    approved_file_patterns: tuple[str, ...]
    excluded_file_patterns: tuple[str, ...]
    index_root: Path
    output_root: Path
    report_root: Path
    provider: str
    retrieval_method: str
    top_k: int
    minimum_relevance_score: float
    maximum_context_chunks: int
    maximum_context_characters: int
    chunk_size_characters: int
    chunk_overlap_characters: int
    citation_required: bool
    minimum_grounding_coverage: float
    allowed_query_categories: tuple[str, ...]
    restricted_action_patterns: tuple[str, ...]
    safety_refusal_mode: str
    synthetic_data_disclaimer: str
    schema_version: str
    run_id_strategy: str
    query_file: Path | None
    query_timestamp: str
    profile: str


def load_assistant_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    source_root: str | None = None,
    index_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    category: str | None = None,
) -> AssistantConfig:
    root = (project_root or resolve_project_root()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    raw = _read_yaml(path)
    if source_root is not None:
        raw["source_roots"] = [source_root]
    if index_root is not None:
        raw["index_root"] = index_root
    if output_root is not None:
        raw["output_root"] = output_root
    if report_root is not None:
        raw["report_root"] = report_root
    if category is not None:
        raw["allowed_query_categories"] = [category]

    config = AssistantConfig(
        source_roots=_path_tuple(
            raw, "source_roots", ["reports", "outputs", "docs", "configs/data_contracts"]
        ),
        approved_components=_string_tuple(
            raw,
            "approved_components",
            [
                "ingestion",
                "forecasting",
                "asset_health",
                "outage_prediction",
                "reliability",
                "monitoring",
                "documentation",
                "contracts",
            ],
        ),
        approved_file_patterns=_string_tuple(
            raw, "approved_file_patterns", ["*.md", "*.json", "*.csv", "*.yaml", "*.yml"]
        ),
        excluded_file_patterns=_string_tuple(
            raw,
            "excluded_file_patterns",
            [
                "data/raw/*",
                "data/quarantine/*",
                ".env*",
                "**/__pycache__/*",
                "outputs/genai/*",
                "reports/genai/*",
            ],
        ),
        index_root=_safe_path(raw, "index_root", "outputs/genai/index"),
        output_root=_safe_path(raw, "output_root", "outputs/genai"),
        report_root=_safe_path(raw, "report_root", "reports/genai"),
        provider=_choice(_string(raw, "provider", "deterministic_local"), PROVIDERS, "provider"),
        retrieval_method=_choice(
            _string(raw, "retrieval_method", "lexical_bm25"),
            RETRIEVAL_METHODS,
            "retrieval_method",
        ),
        top_k=_positive_int(raw, "top_k", 5),
        minimum_relevance_score=_rate(raw, "minimum_relevance_score", 0.05),
        maximum_context_chunks=_positive_int(raw, "maximum_context_chunks", 5),
        maximum_context_characters=_positive_int(raw, "maximum_context_characters", 6000),
        chunk_size_characters=_positive_int(raw, "chunk_size_characters", 1200),
        chunk_overlap_characters=_non_negative_int(raw, "chunk_overlap_characters", 120),
        citation_required=_bool(raw, "citation_required", True),
        minimum_grounding_coverage=_rate(raw, "minimum_grounding_coverage", 0.35),
        allowed_query_categories=_categories(raw),
        restricted_action_patterns=_string_tuple(
            raw,
            "restricted_action_patterns",
            [
                "open breaker",
                "switch feeder",
                "override protection",
                "suppress alert",
                "dispatch crew",
            ],
        ),
        safety_refusal_mode=_choice(
            _string(raw, "safety_refusal_mode", "refuse_and_redirect"),
            {"refuse_and_redirect"},
            "safety_refusal_mode",
        ),
        synthetic_data_disclaimer=_string(
            raw,
            "synthetic_data_disclaimer",
            "All evidence is fictional synthetic repository-local data.",
        ),
        schema_version=_string(raw, "schema_version", "9.0.0"),
        run_id_strategy=_choice(
            _string(raw, "run_id_strategy", "timestamp"),
            {"timestamp", "deterministic"},
            "run_id_strategy",
        ),
        query_file=_optional_path(raw.get("query_file")),
        query_timestamp=_string(raw, "query_timestamp", "2026-01-02T00:00:00Z"),
        profile=str(raw.get("profile", "default")),
    )
    _validate(config)
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Assistant config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Assistant config must contain a mapping.")
    return raw


def _path_tuple(raw: dict[str, Any], key: str, default: list[str]) -> tuple[Path, ...]:
    return tuple(_path_value(value, key) for value in _list(raw.get(key, default), key))


def _string_tuple(raw: dict[str, Any], key: str, default: list[str]) -> tuple[str, ...]:
    return tuple(str(value) for value in _list(raw.get(key, default), key))


def _list(value: Any, key: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{key} must be a non-empty list.")
    return value


def _safe_path(raw: dict[str, Any], key: str, default: str) -> Path:
    return _path_value(raw.get(key, default), key)


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return _path_value(value, "query_file")


def _path_value(value: Any, key: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _string(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty string.")
    return value


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _non_negative_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value < 0:
        raise ConfigurationError(f"{key} must be a non-negative integer.")
    return value


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, (int, float)) or value < 0 or value > 1:
        raise ConfigurationError(f"{key} must be between zero and one.")
    return float(value)


def _bool(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{key} must be true or false.")
    return value


def _categories(raw: dict[str, Any]) -> tuple[str, ...]:
    categories = tuple(
        str(value)
        for value in _list(
            raw.get("allowed_query_categories", sorted(CATEGORIES)), "allowed_query_categories"
        )
    )
    unknown = sorted(set(categories) - CATEGORIES)
    if unknown:
        raise ConfigurationError(f"Unknown query category: {unknown[0]}.")
    return categories


def _validate(config: AssistantConfig) -> None:
    if config.chunk_overlap_characters >= config.chunk_size_characters:
        raise ConfigurationError(
            "chunk_overlap_characters must be smaller than chunk_size_characters."
        )
    if config.output_root in config.source_roots or config.report_root in config.source_roots:
        raise ConfigurationError("source_roots must not overlap assistant outputs.")
    if config.index_root == config.output_root or config.index_root == config.report_root:
        raise ConfigurationError("index_root must be separate from output and report roots.")
