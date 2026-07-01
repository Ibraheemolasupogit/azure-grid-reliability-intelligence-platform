"""Configuration loading for local monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import resolve_project_root

COMPONENTS = (
    "data_generation",
    "ingestion",
    "forecasting",
    "asset_health",
    "outage_prediction",
    "reliability",
)
DRIFT_METHODS = {"population_stability_index", "standardised_mean_difference"}
SCHEMA_POLICIES = {"warn", "fail_on_breaking"}
SEVERITIES = {"INFO", "WARNING", "HIGH", "CRITICAL"}


@dataclass(frozen=True)
class MonitoringConfig:
    source_roots: dict[str, Path]
    output_root: Path
    report_root: Path
    baseline_root: Path | None
    component_inclusion: tuple[str, ...]
    required_components: tuple[str, ...]
    freshness_thresholds: dict[str, int]
    minimum_expected_records: dict[str, int]
    maximum_expected_records: dict[str, int]
    quality_error_rate_threshold: float
    quality_warning_rate_threshold: float
    schema_drift_policy: str
    distribution_drift_method: str
    distribution_drift_threshold: float
    forecast_mae_threshold: float
    forecast_wape_threshold: float
    forecast_bias_threshold: float
    outage_precision_threshold: float
    outage_recall_threshold: float
    outage_brier_threshold: float
    asset_health_distribution_threshold: float
    reliability_distribution_threshold: float
    alert_severity_mapping: dict[str, str]
    alert_suppression_rules: dict[str, bool]
    minimum_sample_size: int
    comparison_window: int
    schema_version: str
    run_id_strategy: str
    monitoring_timestamp: datetime
    profile: str = "default"


def load_monitoring_config(
    config_path: Path | str,
    *,
    project_root: Path | None = None,
    source_root: str | None = None,
    baseline_root: str | None = None,
    output_root: str | None = None,
    report_root: str | None = None,
    monitoring_timestamp: str | None = None,
    component: str | None = None,
) -> MonitoringConfig:
    root = (project_root or resolve_project_root()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    raw = _read_yaml(path)
    if output_root is not None:
        raw["output_root"] = output_root
    if report_root is not None:
        raw["report_root"] = report_root
    if baseline_root is not None:
        raw["baseline_root"] = baseline_root
    if monitoring_timestamp is not None:
        raw["monitoring_timestamp"] = monitoring_timestamp
    if component is not None:
        raw["component_inclusion"] = [component]
    if source_root is not None:
        raw["source_roots"] = {name: source_root for name in COMPONENTS}

    components = _components(raw.get("component_inclusion", list(COMPONENTS)))
    required = _components(raw.get("required_components", []), allow_empty=True)
    source_roots = _source_roots(raw.get("source_roots", {}))
    config = MonitoringConfig(
        source_roots=source_roots,
        output_root=_safe_path(raw, "output_root", "outputs/monitoring"),
        report_root=_safe_path(raw, "report_root", "reports/monitoring"),
        baseline_root=_optional_path(raw.get("baseline_root")),
        component_inclusion=components,
        required_components=required,
        freshness_thresholds=_int_map(raw, "freshness_thresholds", 1440),
        minimum_expected_records=_int_map(raw, "minimum_expected_records", 0),
        maximum_expected_records=_int_map(raw, "maximum_expected_records", 1_000_000),
        quality_error_rate_threshold=_rate(raw, "quality_error_rate_threshold", 0.01),
        quality_warning_rate_threshold=_rate(raw, "quality_warning_rate_threshold", 0.1),
        schema_drift_policy=_choice(
            _string(raw, "schema_drift_policy", "warn"), SCHEMA_POLICIES, "schema_drift_policy"
        ),
        distribution_drift_method=_choice(
            _string(raw, "distribution_drift_method", "population_stability_index"),
            DRIFT_METHODS,
            "distribution_drift_method",
        ),
        distribution_drift_threshold=_non_negative_float(raw, "distribution_drift_threshold", 0.2),
        forecast_mae_threshold=_non_negative_float(raw, "forecast_mae_threshold", 500.0),
        forecast_wape_threshold=_non_negative_float(raw, "forecast_wape_threshold", 0.5),
        forecast_bias_threshold=_non_negative_float(raw, "forecast_bias_threshold", 200.0),
        outage_precision_threshold=_rate(raw, "outage_precision_threshold", 0.2),
        outage_recall_threshold=_rate(raw, "outage_recall_threshold", 0.2),
        outage_brier_threshold=_rate(raw, "outage_brier_threshold", 0.4),
        asset_health_distribution_threshold=_non_negative_float(
            raw, "asset_health_distribution_threshold", 15.0
        ),
        reliability_distribution_threshold=_non_negative_float(
            raw, "reliability_distribution_threshold", 15.0
        ),
        alert_severity_mapping=_severity_mapping(raw.get("alert_severity_mapping", {})),
        alert_suppression_rules=_suppression(raw.get("alert_suppression_rules", {})),
        minimum_sample_size=_positive_int(raw, "minimum_sample_size", 2),
        comparison_window=_positive_int(raw, "comparison_window", 1),
        schema_version=_string(raw, "schema_version", "8.0.0"),
        run_id_strategy=_choice(
            _string(raw, "run_id_strategy", "timestamp"),
            {"timestamp", "deterministic"},
            "run_id_strategy",
        ),
        monitoring_timestamp=_timestamp(raw.get("monitoring_timestamp", "2026-01-02T00:00:00Z")),
        profile=str(raw.get("profile", "default")),
    )
    _validate_paths(config)
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Monitoring config not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("Monitoring config must contain a mapping.")
    return raw


def _components(value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ConfigurationError("component list must be a list.")
    components = tuple(str(item) for item in value)
    unknown = sorted(set(components) - set(COMPONENTS))
    if unknown:
        raise ConfigurationError(f"Unknown monitoring component: {unknown[0]}.")
    return tuple(sorted(dict.fromkeys(components), key=COMPONENTS.index))


def _source_roots(value: Any) -> dict[str, Path]:
    defaults = {
        "data_generation": "data/raw",
        "ingestion": "reports/ingestion",
        "forecasting": "outputs/forecasting",
        "asset_health": "outputs/asset_health",
        "outage_prediction": "outputs/outage_prediction",
        "reliability": "outputs/reliability",
    }
    if not isinstance(value, dict):
        raise ConfigurationError("source_roots must be a mapping.")
    return {
        name: _path_value(value.get(name, default), f"source_roots.{name}")
        for name, default in defaults.items()
    }


def _safe_path(raw: dict[str, Any], key: str, default: str) -> Path:
    return _path_value(raw.get(key, default), key)


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return _path_value(value, "baseline_root")


def _path_value(value: Any, key: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{key} must be a safe relative path.")
    return path


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ConfigurationError("monitoring_timestamp must be an ISO-8601 string.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise ConfigurationError("monitoring_timestamp must be an ISO-8601 string.") from exc


def _int_map(raw: dict[str, Any], key: str, default: int) -> dict[str, int]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a mapping.")
    output = {str(name): default for name in value if str(name)}
    output.update(
        {str(name): _non_negative_int(item, f"{key}.{name}") for name, item in value.items()}
    )
    return dict(sorted(output.items()))


def _severity_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ConfigurationError("alert_severity_mapping must be a mapping.")
    mapping = {str(key): str(item) for key, item in value.items()}
    invalid = sorted(set(mapping.values()) - SEVERITIES)
    if invalid:
        raise ConfigurationError(f"Invalid alert severity: {invalid[0]}.")
    return dict(sorted(mapping.items()))


def _suppression(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise ConfigurationError("alert_suppression_rules must be a mapping.")
    return {str(key): bool(item) for key, item in sorted(value.items())}


def _string(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{key} must be a non-empty string.")
    return value


def _choice(value: str, choices: set[str], key: str) -> str:
    if value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(sorted(choices))}.")
    return value


def _rate(raw: dict[str, Any], key: str, default: float) -> float:
    value = _non_negative_float(raw, key, default)
    if value > 1:
        raise ConfigurationError(f"{key} must be between 0 and 1.")
    return value


def _positive_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    parsed = _non_negative_int(value, key)
    if parsed <= 0:
        raise ConfigurationError(f"{key} must be greater than zero.")
    return parsed


def _non_negative_int(value: Any, key: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ConfigurationError(f"{key} must be a non-negative integer.")
    return value


def _non_negative_float(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if not isinstance(value, (int, float)) or value < 0:
        raise ConfigurationError(f"{key} must be a non-negative number.")
    return float(value)


def _validate_paths(config: MonitoringConfig) -> None:
    roots = [config.output_root, config.report_root]
    if config.baseline_root:
        roots.append(config.baseline_root)
    for source in config.source_roots.values():
        if source in {config.output_root, config.report_root}:
            raise ConfigurationError("source roots must not collide with monitoring outputs.")
    if config.output_root == config.report_root:
        raise ConfigurationError("output_root and report_root must be distinct.")
