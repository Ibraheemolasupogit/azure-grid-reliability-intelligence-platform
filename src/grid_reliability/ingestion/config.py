"""Configuration loading for local governed ingestion."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root

SUPPORTED_WRITE_FORMATS = {"jsonl"}
SUPPORTED_RUN_ID_STRATEGIES = {"timestamp", "deterministic"}


@dataclass(frozen=True)
class IngestionConfig:
    source_root: Path
    interim_root: Path
    quarantine_root: Path
    report_root: Path
    contract_root: Path
    manifest_filename: str
    verify_manifest_checksums: bool
    require_manifest: bool
    fail_on_missing_dataset: bool
    fail_on_contract_error: bool
    maximum_error_rate: float
    batch_size: int
    timezone: str
    normalised_timestamp_format: str
    run_id_strategy: str
    write_format: str
    profile: str = "default"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Ingestion config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Ingestion config must contain a mapping.")
    return raw


def _safe_relative_path(raw: dict[str, Any], key: str, default: str) -> Path:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{key} must be a positive integer.")
    return value


def _bool(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{key} must be true or false.")
    return value


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
        raise ConfigurationError(f"{key} must be between 0 and 1.")
    return float(value)


def _timezone(raw: dict[str, Any]) -> str:
    value = raw.get("timezone", "UTC")
    if not isinstance(value, str) or not value:
        raise ConfigurationError("timezone must be a non-empty IANA timezone string.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"Unsupported timezone: {value}") from exc
    return value


def _choice(raw: dict[str, Any], key: str, default: str, choices: set[str]) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or value not in choices:
        supported = ", ".join(sorted(choices))
        raise ConfigurationError(f"{key} must be one of: {supported}.")
    return value


def _validate_no_overlap(project_root: Path, config: IngestionConfig) -> None:
    resolved = {
        "source_root": (project_root / config.source_root).resolve(),
        "interim_root": (project_root / config.interim_root).resolve(),
        "quarantine_root": (project_root / config.quarantine_root).resolve(),
    }
    pairs = (
        ("source_root", "interim_root"),
        ("source_root", "quarantine_root"),
        ("interim_root", "quarantine_root"),
    )
    for left_name, right_name in pairs:
        left = resolved[left_name]
        right = resolved[right_name]
        if left == right or left in right.parents or right in left.parents:
            raise ConfigurationError(f"{left_name} and {right_name} must not overlap.")


def load_ingestion_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    source_root: str | None = None,
    interim_root: str | None = None,
    quarantine_root: str | None = None,
    report_root: str | None = None,
    strict: bool | None = None,
) -> IngestionConfig:
    """Load and validate local ingestion configuration."""
    root = (project_root or resolve_project_root()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    raw = _read_yaml(path)
    if source_root is not None:
        raw["source_root"] = source_root
    if interim_root is not None:
        raw["interim_root"] = interim_root
    if quarantine_root is not None:
        raw["quarantine_root"] = quarantine_root
    if report_root is not None:
        raw["report_root"] = report_root
    if strict is not None:
        raw["require_manifest"] = strict
        raw["verify_manifest_checksums"] = strict
        raw["fail_on_contract_error"] = strict

    config = IngestionConfig(
        source_root=_safe_relative_path(raw, "source_root", "data/raw"),
        interim_root=_safe_relative_path(raw, "interim_root", "data/interim"),
        quarantine_root=_safe_relative_path(raw, "quarantine_root", "data/quarantine"),
        report_root=_safe_relative_path(raw, "report_root", "reports/ingestion"),
        contract_root=_safe_relative_path(raw, "contract_root", "configs/data_contracts"),
        manifest_filename=str(raw.get("manifest_filename", "_manifest.json")),
        verify_manifest_checksums=_bool(raw, "verify_manifest_checksums", True),
        require_manifest=_bool(raw, "require_manifest", True),
        fail_on_missing_dataset=_bool(raw, "fail_on_missing_dataset", True),
        fail_on_contract_error=_bool(raw, "fail_on_contract_error", True),
        maximum_error_rate=_rate(raw, "maximum_error_rate", 0.0),
        batch_size=_positive_int(raw, "batch_size", 500),
        timezone=_timezone(raw),
        normalised_timestamp_format=str(raw.get("normalised_timestamp_format", "iso8601_utc")),
        run_id_strategy=_choice(raw, "run_id_strategy", "timestamp", SUPPORTED_RUN_ID_STRATEGIES),
        write_format=_choice(raw, "write_format", "jsonl", SUPPORTED_WRITE_FORMATS),
        profile=str(raw.get("profile", "default")),
    )
    if not config.manifest_filename or "/" in config.manifest_filename:
        raise ConfigurationError("manifest_filename must be a filename, not a path.")
    if config.normalised_timestamp_format != "iso8601_utc":
        raise ConfigurationError("normalised_timestamp_format must be iso8601_utc.")
    if not (root / config.contract_root).exists():
        raise ConfigurationError(f"contract_root does not exist: {config.contract_root}")
    _validate_no_overlap(root, config)
    return replace(config)
