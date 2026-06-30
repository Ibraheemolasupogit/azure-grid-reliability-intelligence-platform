"""Deterministic Markdown reports for reliability analytics."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.models import ReasonDescription, ReliabilityResult


def write_reports(
    report_root: Path,
    run_id: str,
    config: ReliabilityConfig,
    results: list[ReliabilityResult],
    system_summary: dict[str, object],
) -> dict[str, Path]:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "performance": run_root / "reliability_performance_report.md",
        "trends": run_root / "reliability_trend_report.md",
        "methodology": run_root / "reliability_methodology.md",
        "executive": run_root / "executive_reliability_summary.md",
    }
    paths["performance"].write_text(_performance(results, system_summary), encoding="utf-8")
    paths["trends"].write_text(_trend_report(), encoding="utf-8")
    paths["methodology"].write_text(_methodology(config), encoding="utf-8")
    paths["executive"].write_text(_executive(system_summary), encoding="utf-8")
    return paths


def _performance(results: list[ReliabilityResult], summary: dict[str, object]) -> str:
    lowest = sorted(
        [row for row in results if row.reliability_score is not None],
        key=lambda row: (float(row.reliability_score or 0), row.entity.entity_id),
    )[:10]
    lines = [
        "# Reliability Performance Report",
        "",
        "## System KPIs",
        "",
        f"- System SAIFI: `{summary.get('system_saifi')}` interruptions per customer",
        f"- System SAIDI: `{summary.get('system_saidi_minutes')}` minutes per customer",
        f"- System CAIDI: `{summary.get('system_caidi_minutes')}` minutes per interruption",
        f"- System ASAI: `{summary.get('system_asai')}`",
        "",
        "## Reliability-Band Distribution",
        "",
    ]
    bands = Counter(row.reliability_band.value for row in results)
    for band, count in sorted(bands.items()):
        lines.append(f"- `{band}`: {count}")
    lines.extend(["", "## Lowest Reliability Entities", ""])
    for row in lowest:
        lines.append(
            f"- `{row.entity.entity_type.value}` `{row.entity.entity_id}`: "
            f"score `{row.reliability_score}`, SAIFI `{row.saifi}`, SAIDI `{row.saidi_minutes}`"
        )
    lines.extend(
        [
            "",
            "Metrics are based on fictional synthetic data and are not regulatory submissions.",
        ]
    )
    return "\n".join(lines) + "\n"


def _trend_report() -> str:
    return (
        "# Reliability Trend Report\n\n"
        "Trend outputs compare each period with the previous period where available. "
        "Small synthetic samples do not support statistical significance claims.\n"
    )


def _methodology(config: ReliabilityConfig) -> str:
    lines = [
        "# Reliability Methodology",
        "",
        "## Formulas",
        "",
        "- `SAIFI = total customer interruptions / population denominator`.",
        "- `SAIDI = customer interruption minutes / population denominator`.",
        "- `CAIDI = customer interruption minutes / customer interruptions`.",
        "- `ASAI = 1 - availability interruption minutes / customer service minutes demanded`.",
        "- `ASUI = 1 - ASAI`.",
        "",
        "## Population",
        "",
        f"Population method: `{config.customer_population_method}`.",
        "",
        "## Score Weights",
        "",
    ]
    for name, weight in config.component_weights.items():
        lines.append(f"- `{name}`: {weight}")
    lines.extend(["", "## Reason Codes", ""])
    for code, description in ReasonDescription.items():
        lines.append(f"- `{code}`: {description}")
    lines.extend(
        [
            "",
            "CTAIDI and CAIFI are not calculated because distinct interrupted customer IDs "
            "are not present in the synthetic outage records.",
            "No Azure resources are deployed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _executive(summary: dict[str, object]) -> str:
    return (
        "# Executive Reliability Summary\n\n"
        f"- Entities assessed: `{summary.get('entities_assessed')}`\n"
        f"- Total outages: `{summary.get('total_outages')}`\n"
        f"- Unplanned outages: `{summary.get('total_unplanned_outages')}`\n"
        f"- System SAIFI: `{summary.get('system_saifi')}`\n"
        f"- System SAIDI minutes: `{summary.get('system_saidi_minutes')}`\n"
        f"- System CAIDI minutes: `{summary.get('system_caidi_minutes')}`\n"
        f"- System ASAI: `{summary.get('system_asai')}`\n"
        "- Outputs use fictional synthetic data and do not claim regulatory compliance, "
        "financial savings, or real-grid deployment.\n"
    )
