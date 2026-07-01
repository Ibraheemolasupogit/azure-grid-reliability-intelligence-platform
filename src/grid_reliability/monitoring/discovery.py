"""Discovery and normalisation of monitoring source artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grid_reliability.monitoring.config import MonitoringConfig
from grid_reliability.monitoring.models import ComponentRun, MonitoringError, parse_timestamp

RUN_FILES = {
    "ingestion": ("metrics.json", "ingestion_manifest.json"),
    "forecasting": ("metrics.json", "forecast_manifest.json"),
    "asset_health": ("metrics.json", "asset_health_manifest.json"),
    "outage_prediction": ("metrics.json", "outage_prediction_manifest.json"),
    "reliability": ("metrics.json", "reliability_manifest.json"),
}


def discover_component_runs(project_root: Path, config: MonitoringConfig) -> list[ComponentRun]:
    """Discover configured component runs in stable order."""
    records: list[ComponentRun] = []
    for component in config.component_inclusion:
        if component == "data_generation":
            records.append(_discover_data_generation(project_root, config))
            continue
        records.extend(_discover_run_directories(project_root, config, component))
    return sorted(records, key=lambda row: (row.component_name, row.run_id, row.metrics_path or ""))


def duplicate_run_ids(records: list[ComponentRun]) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for record in records:
        key = (record.component_name, record.run_id)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def _discover_data_generation(project_root: Path, config: MonitoringConfig) -> ComponentRun:
    source_root = project_root / config.source_roots["data_generation"]
    manifest_path = source_root / "_manifest.json"
    manifest, malformed = _read_json(manifest_path)
    run_id = str(manifest.get("run_id") or manifest.get("generation_run_id") or "raw-local")
    dataset_counts = manifest.get("datasets", {})
    output_count = None
    if isinstance(dataset_counts, dict):
        output_count = sum(_record_count(item) for item in dataset_counts.values())
    return ComponentRun(
        component_name="data_generation",
        run_id=run_id,
        run_status="PASSED" if manifest_path.exists() and not malformed else "NOT_AVAILABLE",
        run_timestamp=parse_timestamp(manifest.get("generated_at")),
        assessment_start=None,
        assessment_end=None,
        input_record_count=None,
        output_record_count=output_count,
        invalid_record_count=None,
        warning_count=None,
        error_count=None,
        primary_metric_name="generated_records",
        primary_metric_value=float(output_count) if output_count is not None else None,
        manifest_path=_relative(project_root, manifest_path) if manifest_path.exists() else None,
        metrics_path=None,
        schema_version=_optional_string(manifest.get("schema_version")),
        synthetic_data_flag=True,
        metrics={},
        manifest=manifest,
        source_paths=(_relative(project_root, manifest_path),) if manifest_path.exists() else (),
        malformed=malformed,
    )


def _discover_run_directories(
    project_root: Path, config: MonitoringConfig, component: str
) -> list[ComponentRun]:
    source_root = project_root / config.source_roots[component]
    metrics_name, manifest_name = RUN_FILES[component]
    if not source_root.exists():
        return [
            _missing_record(
                project_root=project_root,
                component=component,
                source_root=source_root,
                required=component in config.required_components,
            )
        ]
    records: list[ComponentRun] = []
    for run_root in sorted(path for path in source_root.iterdir() if path.is_dir()):
        if run_root.is_symlink():
            continue
        metrics_path = run_root / metrics_name
        manifest_path = run_root / manifest_name
        metrics, metrics_malformed = _read_json(metrics_path)
        manifest, manifest_malformed = _read_json(manifest_path)
        records.append(
            _normalise_run(
                project_root,
                component,
                run_root.name,
                metrics_path,
                manifest_path,
                metrics,
                manifest,
                metrics_malformed or manifest_malformed,
            )
        )
    if not records:
        records.append(
            _missing_record(
                project_root=project_root,
                component=component,
                source_root=source_root,
                required=component in config.required_components,
            )
        )
    return records


def _normalise_run(
    project_root: Path,
    component: str,
    fallback_run_id: str,
    metrics_path: Path,
    manifest_path: Path,
    metrics: dict[str, Any],
    manifest: dict[str, Any],
    malformed: bool,
) -> ComponentRun:
    run_id = _run_id(component, metrics, manifest, fallback_run_id)
    status = _run_status(component, metrics, manifest, malformed)
    primary_name, primary_value = _primary_metric(component, metrics)
    output_count = _output_count(component, metrics, manifest)
    invalid = _nested_int(metrics, ("totals", "invalid_records")) or _optional_int(
        metrics.get("invalid_records")
    )
    warnings = _nested_int(metrics, ("totals", "warning_records")) or _optional_int(
        metrics.get("warning_count")
    )
    errors = _nested_int(metrics, ("totals", "error_records")) or _optional_int(
        metrics.get("error_count")
    )
    source_paths = tuple(
        _relative(project_root, path)
        for path in (metrics_path, manifest_path)
        if path.exists() and not path.is_symlink()
    )
    return ComponentRun(
        component_name=component,
        run_id=run_id,
        run_status=status,
        run_timestamp=_run_timestamp(metrics, manifest),
        assessment_start=parse_timestamp(
            manifest.get("assessment_start") or metrics.get("assessment_start")
        ),
        assessment_end=parse_timestamp(
            manifest.get("assessment_end") or metrics.get("assessment_end")
        ),
        input_record_count=_input_count(component, metrics, manifest),
        output_record_count=output_count,
        invalid_record_count=invalid,
        warning_count=warnings,
        error_count=errors,
        primary_metric_name=primary_name,
        primary_metric_value=primary_value,
        manifest_path=_relative(project_root, manifest_path) if manifest_path.exists() else None,
        metrics_path=_relative(project_root, metrics_path) if metrics_path.exists() else None,
        schema_version=_optional_string(
            metrics.get("schema_version") or manifest.get("schema_version")
        ),
        synthetic_data_flag="synthetic" in json.dumps({**metrics, **manifest}).lower(),
        metrics=metrics,
        manifest=manifest,
        source_paths=source_paths,
        malformed=malformed,
    )


def _missing_record(
    *, project_root: Path, component: str, source_root: Path, required: bool
) -> ComponentRun:
    return ComponentRun(
        component_name=component,
        run_id="missing-required" if required else "not-available",
        run_status="FAILED" if required else "NOT_AVAILABLE",
        run_timestamp=None,
        assessment_start=None,
        assessment_end=None,
        input_record_count=None,
        output_record_count=None,
        invalid_record_count=None,
        warning_count=None,
        error_count=None,
        primary_metric_name=None,
        primary_metric_value=None,
        manifest_path=None,
        metrics_path=None,
        schema_version=None,
        synthetic_data_flag=False,
        metrics={"source_root": _relative(project_root, source_root)},
        manifest={},
        source_paths=(),
    )


def _read_json(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists() or path.is_symlink():
        return {}, False
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        return {}, True
    if not isinstance(payload, dict):
        raise MonitoringError(f"JSON source must contain an object: {path}")
    return payload, False


def _run_id(
    component: str, metrics: dict[str, Any], manifest: dict[str, Any], fallback: str
) -> str:
    keys = {
        "ingestion": "ingestion_run_id",
        "forecasting": "forecast_run_id",
        "asset_health": "run_id",
        "outage_prediction": "run_id",
        "reliability": "run_id",
    }
    return str(metrics.get(keys[component]) or manifest.get(keys[component]) or fallback)


def _run_status(
    component: str, metrics: dict[str, Any], manifest: dict[str, Any], malformed: bool
) -> str:
    if malformed:
        return "FAILED_MALFORMED_JSON"
    if not metrics and not manifest:
        return "NOT_AVAILABLE"
    if component == "ingestion":
        return str(metrics.get("run_status") or manifest.get("run_status") or "PASSED")
    failed = manifest.get("failed_model_attempts") or metrics.get("failed_models")
    if failed:
        return "PASSED_WITH_WARNINGS"
    return "PASSED"


def _run_timestamp(metrics: dict[str, Any], manifest: dict[str, Any]) -> Any:
    for key in ("generated_at", "assessment_timestamp", "monitoring_timestamp"):
        parsed = parse_timestamp(metrics.get(key) or manifest.get(key))
        if parsed is not None:
            return parsed
    return None


def _primary_metric(component: str, metrics: dict[str, Any]) -> tuple[str | None, float | None]:
    if component == "forecasting":
        return "selected_model_test_mae", _optional_float(metrics.get("selected_model_test_mae"))
    if component == "asset_health":
        distribution = metrics.get("score_distribution", {})
        if isinstance(distribution, dict):
            return "mean_health_score", _optional_float(distribution.get("mean"))
    if component == "outage_prediction":
        return "selected_threshold", _optional_float(metrics.get("selected_threshold"))
    if component == "reliability":
        return "population_coverage", _optional_float(metrics.get("population_coverage"))
    if component == "ingestion":
        total = metrics.get("totals", {})
        if isinstance(total, dict):
            return "error_rate", _optional_float(total.get("error_rate"))
    return None, None


def _input_count(component: str, metrics: dict[str, Any], manifest: dict[str, Any]) -> int | None:
    if component == "ingestion":
        return _nested_int(metrics, ("totals", "source_records_discovered"))
    if component == "forecasting":
        return sum(
            value
            for value in (
                _optional_int(metrics.get("training_row_count")),
                _optional_int(metrics.get("validation_row_count")),
                _optional_int(metrics.get("test_row_count")),
            )
            if value is not None
        )
    row_counts = manifest.get("row_counts")
    if isinstance(row_counts, dict):
        return _optional_int(next(iter(row_counts.values()), None))
    return None


def _output_count(component: str, metrics: dict[str, Any], manifest: dict[str, Any]) -> int | None:
    if component == "forecasting":
        return _optional_int(manifest.get("forecast_row_count"))
    if component == "asset_health":
        return _optional_int(metrics.get("assets_scored"))
    if component == "outage_prediction":
        rows = manifest.get("row_counts", {})
        return _optional_int(rows.get("prediction_rows")) if isinstance(rows, dict) else None
    if component == "reliability":
        return _optional_int(metrics.get("entities_assessed"))
    if component == "ingestion":
        return _nested_int(metrics, ("totals", "valid_records"))
    return None


def _record_count(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("record_count", "records", "row_count"):
            parsed = _optional_int(value.get(key))
            if parsed is not None:
                return parsed
    return 0


def _nested_int(payload: dict[str, Any], path: tuple[str, ...]) -> int | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _optional_int(current)


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _optional_string(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name
