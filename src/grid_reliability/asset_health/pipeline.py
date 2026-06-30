"""Asset-health analytics pipeline and CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from grid_reliability.asset_health.config import AssetHealthConfig, load_asset_health_config
from grid_reliability.asset_health.data import eligible_assets, load_inputs
from grid_reliability.asset_health.features import derive_features
from grid_reliability.asset_health.models import AssetHealthError, AssetHealthResult
from grid_reliability.asset_health.persistence import write_outputs
from grid_reliability.asset_health.reporting import write_reports
from grid_reliability.asset_health.scoring import assess_asset
from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.metadata import __version__
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file


@dataclass(frozen=True)
class AssetHealthPipelineResult:
    run_id: str
    score_path: Path
    metrics_path: Path
    manifest_path: Path
    report_paths: dict[str, Path]
    results: list[AssetHealthResult]
    metrics: dict[str, Any]


def build_run_id(config: AssetHealthConfig, provided: str | None = None) -> str:
    if provided:
        return provided
    if config.run_id_strategy == "deterministic":
        return "asset-health-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_asset_health(
    config: AssetHealthConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
) -> AssetHealthPipelineResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config, run_id)
    datasets, input_checksums, missing_optional = load_inputs(root / config.interim_root, config)
    assets, excluded_assets = eligible_assets(datasets["asset_inventory"], config)
    results = [
        assess_asset(asset, derive_features(asset, datasets, config), config) for asset in assets
    ]
    results = sorted(results, key=lambda result: result.asset.asset_id)
    metrics = _metrics(results, len(datasets["asset_inventory"]), excluded_assets)
    fleet_summary = _fleet_summary(results, metrics)
    output_root = root / config.output_root
    report_root = root / config.report_root
    manifest = _manifest(
        settings.project_name,
        effective_run_id,
        config,
        input_checksums,
        metrics,
        missing_optional,
    )
    output_paths = write_outputs(
        output_root, effective_run_id, results, fleet_summary, metrics, manifest
    )
    report_paths = write_reports(report_root, effective_run_id, results, config, metrics)
    return AssetHealthPipelineResult(
        run_id=effective_run_id,
        score_path=output_paths["asset_health_scores"],
        metrics_path=output_paths["metrics"],
        manifest_path=output_paths["manifest"],
        report_paths=report_paths,
        results=results,
        metrics=metrics,
    )


def _metrics(
    results: list[AssetHealthResult],
    discovered_assets: int,
    excluded_assets: int,
) -> dict[str, Any]:
    scores = [result.health_score for result in results]
    component_names = (
        "age_component_score",
        "inspection_component_score",
        "maintenance_component_score",
        "telemetry_stress_component_score",
        "alarm_component_score",
        "outage_component_score",
    )
    component_means = {
        name: round(mean(getattr(result.components, name) for result in results), 6)
        if results
        else None
        for name in component_names
    }
    reason_counts = Counter(code for result in results for code in result.reason_codes)
    return {
        "assets_discovered": discovered_assets,
        "eligible_assets": len(results),
        "excluded_assets": excluded_assets,
        "assets_scored": len(results),
        "insufficient_data_assets": sum(
            1 for result in results if result.features.insufficient_data_flag
        ),
        "counts_by_asset_type": dict(
            sorted(Counter(result.asset.asset_type for result in results).items())
        ),
        "counts_by_health_band": dict(
            sorted(Counter(result.health_band.value for result in results).items())
        ),
        "counts_by_priority": dict(
            sorted(Counter(result.maintenance_priority.value for result in results).items())
        ),
        "component_availability": {
            "maintenance": sum(1 for result in results if result.features.maintenance_count > 0),
            "telemetry": sum(
                1 for result in results if result.features.telemetry_observation_count > 0
            ),
            "outage": sum(
                1
                for result in results
                if result.features.direct_outage_count + result.features.contextual_outage_count > 0
            ),
        },
        "mean_component_scores": component_means,
        "overdue_inspection_count": sum(
            1 for result in results if result.features.inspection_overdue_flag
        ),
        "maintenance_evidence_coverage": _coverage(results, "maintenance_count"),
        "telemetry_evidence_coverage": _coverage(results, "telemetry_observation_count"),
        "outage_evidence_coverage": _outage_coverage(results),
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "score_distribution": {
            "mean": round(mean(scores), 6) if scores else None,
            "median": round(median(scores), 6) if scores else None,
            "minimum": min(scores) if scores else None,
            "maximum": max(scores) if scores else None,
        },
    }


def _fleet_summary(results: list[AssetHealthResult], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_eligible_assets": metrics["eligible_assets"],
        "assets_scored": metrics["assets_scored"],
        "insufficient_data_assets": metrics["insufficient_data_assets"],
        "counts_by_asset_type": metrics["counts_by_asset_type"],
        "counts_by_health_band": metrics["counts_by_health_band"],
        "counts_by_maintenance_priority": metrics["counts_by_priority"],
        "average_health_score": metrics["score_distribution"]["mean"],
        "median_health_score": metrics["score_distribution"]["median"],
        "overdue_inspection_count": metrics["overdue_inspection_count"],
        "recent_direct_outage_count": sum(
            1 for result in results if result.features.direct_outage_count > 0
        ),
        "telemetry_stress_indicator_count": sum(
            1 for result in results if result.features.high_utilisation_event_count > 0
        ),
        "synthetic_data_declaration": "Asset-health analytics use fictional synthetic data only.",
    }


def _manifest(
    project_name: str,
    run_id: str,
    config: AssetHealthConfig,
    input_checksums: dict[str, str],
    metrics: dict[str, Any],
    missing_optional: list[str],
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "run_id": run_id,
        "assessment_timestamp": config.assessment_timestamp.isoformat().replace("+00:00", "Z"),
        "component_version": __version__,
        "score_version": config.schema_version,
        "input_files": sorted(input_checksums),
        "input_checksums": input_checksums,
        "configuration_checksum": _config_checksum(config),
        "included_asset_types": config.included_asset_types,
        "lookback_windows": {
            "maintenance_days": config.lookback_days_maintenance,
            "telemetry_days": config.lookback_days_telemetry,
            "outage_days": config.lookback_days_outages,
        },
        "component_weights": config.component_weights,
        "thresholds": {
            "health_bands": config.health_band_thresholds,
            "priorities": config.priority_thresholds,
        },
        "asset_counts": {
            "eligible_assets": metrics["eligible_assets"],
            "assets_scored": metrics["assets_scored"],
            "insufficient_data_assets": metrics["insufficient_data_assets"],
        },
        "warning_counts": {"missing_optional_datasets": len(missing_optional)},
        "missing_optional_datasets": missing_optional,
        "repository_revision": _git_revision(),
        "synthetic_data_declaration": "All asset-health inputs are fictional synthetic data.",
        "limitations": [
            "Scores are transparent decision-support indicators, not engineering certification.",
            "No failure-probability model is trained.",
            "No Azure resources are deployed.",
        ],
    }


def _coverage(results: list[AssetHealthResult], field_name: str) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if getattr(result.features, field_name) > 0) / len(results)


def _outage_coverage(results: list[AssetHealthResult]) -> float:
    if not results:
        return 0.0
    return sum(
        1
        for result in results
        if result.features.direct_outage_count + result.features.contextual_outage_count > 0
    ) / len(results)


def _config_checksum(config: AssetHealthConfig) -> str | None:
    path = Path(
        "configs/asset_health_ci.yaml" if config.profile == "ci" else "configs/asset_health.yaml"
    )
    return sha256_file(path) if path.exists() else None


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local asset-health analytics.")
    parser.add_argument("--config", default="configs/asset_health.yaml")
    parser.add_argument("--interim-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--assessment-timestamp")
    parser.add_argument("--asset-id")
    parser.add_argument("--asset-type")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = resolve_project_root()
    try:
        config = load_asset_health_config(
            args.config,
            project_root=project_root,
            interim_root=args.interim_root,
            output_root=args.output_root,
            report_root=args.report_root,
            assessment_timestamp=args.assessment_timestamp,
            asset_id=args.asset_id,
            asset_type=args.asset_type,
        )
        result = run_asset_health(config, project_root=project_root, run_id=args.run_id)
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except AssetHealthError as exc:
        print(json.dumps({"run_status": "FAILED_ASSET_HEALTH_INPUT", "error": str(exc)}))
        return 3
    except Exception as exc:
        print(json.dumps({"run_status": "FAILED_ASSET_HEALTH_PROCESSING", "error": str(exc)}))
        return 1
    print(
        "Asset-health run "
        f"{result.run_id}: assets={len(result.results)}; "
        f"scores={result.score_path}; report={result.report_paths['asset_health_report']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
