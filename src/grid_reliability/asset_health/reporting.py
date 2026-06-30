"""Deterministic Markdown reports for asset-health runs."""

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import cast

from grid_reliability.asset_health.config import AssetHealthConfig
from grid_reliability.asset_health.models import AssetHealthResult, ReasonDescription


def write_reports(
    report_root: Path,
    run_id: str,
    results: list[AssetHealthResult],
    config: AssetHealthConfig,
    metrics: dict[str, object],
) -> dict[str, Path]:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "asset_health_report": run_root / "asset_health_report.md",
        "maintenance_priority_report": run_root / "maintenance_priority_report.md",
        "asset_health_methodology": run_root / "asset_health_methodology.md",
        "executive_asset_health_summary": run_root / "executive_asset_health_summary.md",
    }
    paths["asset_health_report"].write_text(_health_report(results, metrics), encoding="utf-8")
    paths["maintenance_priority_report"].write_text(_priority_report(results), encoding="utf-8")
    paths["asset_health_methodology"].write_text(_methodology_report(config), encoding="utf-8")
    paths["executive_asset_health_summary"].write_text(
        _executive_summary(results, metrics), encoding="utf-8"
    )
    return paths


def _health_report(results: list[AssetHealthResult], metrics: dict[str, object]) -> str:
    lowest = sorted(results, key=lambda result: (result.health_score, result.asset.asset_id))[:5]
    band_counts = cast(dict[str, int], metrics["counts_by_health_band"])
    lines = [
        "# Asset Health Report",
        "",
        "## Assessment Scope",
        "",
        f"- Eligible assets: {metrics['eligible_assets']}",
        f"- Assets scored: {metrics['assets_scored']}",
        f"- Insufficient-data assets: {metrics['insufficient_data_assets']}",
        "",
        "## Health-Band Distribution",
        "",
    ]
    for band, count in band_counts.items():
        lines.append(f"- `{band}`: {count}")
    lines.extend(["", "## Lowest-Health Assets", ""])
    for result in lowest:
        lines.append(
            f"- `{result.asset.asset_id}` `{result.asset.asset_type}`: "
            f"{result.health_score:.2f} `{result.health_band.value}` "
            f"({', '.join(result.reason_codes)})"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Scores use fictional synthetic data only.",
            "- Health bands are decision-support categories, not engineering certification.",
            "- No failure-probability model or reliability KPI is calculated.",
        ]
    )
    return "\n".join(lines) + "\n"


def _priority_report(results: list[AssetHealthResult]) -> str:
    priority_assets = [
        result for result in results if result.maintenance_priority.value != "P4_ROUTINE"
    ]
    lines = [
        "# Maintenance Priority Report",
        "",
        "Recommendations are rule-based review priorities, not schedules or "
        "workforce optimisation.",
        "",
        "## Priority Assets",
        "",
    ]
    for result in priority_assets[:20]:
        lines.append(
            f"- `{result.asset.asset_id}`: `{result.maintenance_priority.value}` "
            f"health `{result.health_band.value}`, reasons "
            f"`{', '.join(result.priority_reason_codes)}`"
        )
    if not priority_assets:
        lines.append("- No non-routine review priorities.")
    lines.extend(
        [
            "",
            "Qualified engineering review is required before operational action.",
        ]
    )
    return "\n".join(lines) + "\n"


def _methodology_report(config: AssetHealthConfig) -> str:
    lines = [
        "# Asset Health Methodology",
        "",
        "## Score Direction",
        "",
        "`0` is poorest health and `100` is strongest health.",
        "",
        "## Component Weights",
        "",
    ]
    for name, weight in config.component_weights.items():
        lines.append(f"- `{name}`: {weight}")
    lines.extend(
        [
            "",
            "## Component Formulas",
            "",
            "- Age declines as age approaches and exceeds expected life.",
            "- Inspection declines as inspection due dates become overdue.",
            "- Maintenance penalises corrective/emergency/deferred work, follow-up, and downtime.",
            "- Telemetry stress penalises high utilisation, temperature stress, "
            "and constrained states.",
            "- Alarm score penalises recent telemetry alarms.",
            "- Outage score penalises direct unplanned and equipment-failure outage involvement.",
            "",
            "## Reason Codes",
            "",
        ]
    )
    for code, description in ReasonDescription.items():
        lines.append(f"- `{code}`: {description}")
    lines.extend(
        [
            "",
            "## Azure Mapping",
            "",
            "- Local feature derivation maps conceptually to Azure Data Explorer, "
            "Synapse, or Fabric.",
            "- Local score execution maps conceptually to Azure Machine Learning batch jobs.",
            "- Local lineage maps conceptually to Microsoft Purview.",
            "- No Azure resources are deployed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _executive_summary(results: list[AssetHealthResult], metrics: dict[str, object]) -> str:
    scores = [result.health_score for result in results]
    average = mean(scores) if scores else 0.0
    return (
        "# Executive Asset Health Summary\n\n"
        f"- Eligible assets assessed: `{metrics['eligible_assets']}`\n"
        f"- Average health score: `{average:.2f}`\n"
        f"- Critical/degraded assets: `{_critical_or_degraded(results)}`\n"
        f"- Non-routine review priorities: `{_non_routine(results)}`\n"
        "- Outputs are based on fictional synthetic data and do not represent a "
        "real utility fleet.\n"
        "- No business savings, certified condition assessment, or Azure deployment is claimed.\n"
    )


def _critical_or_degraded(results: list[AssetHealthResult]) -> int:
    return sum(1 for result in results if result.health_band.value in {"CRITICAL", "DEGRADED"})


def _non_routine(results: list[AssetHealthResult]) -> int:
    return sum(1 for result in results if result.maintenance_priority.value != "P4_ROUTINE")
