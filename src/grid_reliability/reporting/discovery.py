"""Governed reporting source discovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

from grid_reliability.reporting.models import ReportingConfig, ReportingError, SourceFile

SOURCE_PATTERNS: dict[str, dict[str, str]] = {
    "forecasting": {
        "forecast": "outputs/forecasting/*/load_forecast.csv",
        "metrics": "outputs/forecasting/*/metrics.json",
        "manifest": "outputs/forecasting/*/forecast_manifest.json",
    },
    "asset_health": {
        "scores": "outputs/asset_health/*/asset_health_scores.csv",
        "components": "outputs/asset_health/*/asset_health_components.csv",
        "priorities": "outputs/asset_health/*/maintenance_priorities.csv",
        "manifest": "outputs/asset_health/*/asset_health_manifest.json",
    },
    "outage_prediction": {
        "predictions": "outputs/outage_prediction/*/outage_risk_predictions.csv",
        "manifest": "outputs/outage_prediction/*/outage_prediction_manifest.json",
    },
    "reliability": {
        "kpis": "outputs/reliability/*/reliability_kpis.csv",
        "reasons": "outputs/reliability/*/reliability_reasons.csv",
        "manifest": "outputs/reliability/*/reliability_manifest.json",
    },
    "monitoring": {
        "summary": "outputs/monitoring/monitoring_summary.csv",
        "alerts": "outputs/monitoring/alerts.csv",
        "manifest": "outputs/monitoring/*/monitoring_manifest.json",
    },
    "genai": {
        "responses": "outputs/genai/grid_operations_responses.jsonl",
        "manifest": "outputs/genai/*/assistant_manifest.json",
    },
    "interim": {
        "asset_inventory": "data/interim/asset_inventory.jsonl",
    },
}


def discover_reporting_sources(project_root: Path, config: ReportingConfig) -> list[SourceFile]:
    """Discover supported generated source files with stable ordering."""

    discovered: list[SourceFile] = []
    required_components = set(config.included_components)
    if not config.include_monitoring_outputs:
        required_components.discard("monitoring")
    if not config.include_assistant_outputs:
        required_components.discard("genai")

    for component in sorted(required_components | {"interim"}):
        patterns = SOURCE_PATTERNS.get(component, {})
        for kind, pattern in sorted(patterns.items()):
            paths = sorted(project_root.glob(pattern))
            if not paths and component != "interim":
                raise ReportingError(f"Missing required reporting source: {component}:{kind}")
            for path in paths:
                if path.is_symlink() or not path.is_file():
                    continue
                if not _under_allowed_root(path.resolve(), config.source_roots):
                    continue
                discovered.append(
                    SourceFile(
                        component_name=component,
                        source_run_id=_run_id(component, kind, path),
                        kind=kind,
                        path=path.resolve(),
                        checksum=_sha256(path),
                    )
                )

    _detect_duplicate_runs(discovered)
    return sorted(
        discovered, key=lambda source: (source.component_name, source.kind, str(source.path))
    )


def _under_allowed_root(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_id(component: str, kind: str, path: Path) -> str:
    if component == "monitoring" and kind in {"summary", "alerts"}:
        return "monitoring-shared"
    if component == "genai" and kind == "responses":
        return "assistant-shared"
    if component == "interim":
        return "interim-latest"
    return path.parent.name


def _detect_duplicate_runs(sources: list[SourceFile]) -> None:
    seen: set[tuple[str, str, str]] = set()
    duplicates: list[str] = []
    for source in sources:
        key = (source.component_name, source.kind, source.source_run_id)
        if key in seen:
            duplicates.append(":".join(key))
        seen.add(key)
    if duplicates:
        raise ReportingError(f"Duplicate reporting source run IDs detected: {sorted(duplicates)}")
