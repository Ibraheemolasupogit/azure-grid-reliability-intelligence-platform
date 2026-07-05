"""Deterministic reporting summaries and semantic documentation outputs."""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

from grid_reliability.reporting.models import ReportingConfig, ReportingTables, ValidationResult


def write_reporting_reports(
    project_root: Path,
    config: ReportingConfig,
    tables: ReportingTables,
    validation: ValidationResult,
) -> dict[str, Path]:
    """Write executive and operational reporting summaries."""

    root = project_root / config.report_root / config.run_id
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "executive": root / "executive_grid_reliability_brief.md",
        "operations": root / "grid_operations_dashboard_summary.md",
        "asset": root / "asset_management_summary.md",
        "reliability": root / "reliability_performance_summary.md",
        "governance": root / "data_and_model_governance_summary.md",
        "validation": root / "reporting_model_validation.md",
    }
    counts = {
        table_name: len(rows)
        for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items()
    }
    _write(
        paths["executive"],
        "# Executive Grid Reliability Brief\n\n"
        "This deterministic local brief consolidates synthetic forecasting, asset-health, "
        "outage-risk, reliability, monitoring, and assistant evidence into Power BI-ready "
        "reporting outputs.\n\n"
        f"- Reliability KPI rows: `{counts.get('fact_reliability_kpi', 0)}`\n"
        f"- Forecast rows: `{counts.get('fact_demand_forecast', 0)}`\n"
        f"- Asset-health rows: `{counts.get('fact_asset_health', 0)}`\n"
        f"- Outage-risk rows: `{counts.get('fact_outage_risk', 0)}`\n"
        f"- Monitoring alerts: `{counts.get('fact_monitoring_alert', 0)}`\n"
        f"- Assistant responses: `{counts.get('fact_assistant_response', 0)}`\n\n"
        "No savings, live grid state, Power BI deployment, Fabric workspace, or Azure "
        "resource deployment is claimed.\n",
    )
    _write(
        paths["operations"],
        "# Grid Operations Dashboard Summary\n\n"
        "The operations page set should combine demand forecast context, elevated outage-risk "
        "entities, reliability weakness indicators, and monitoring alerts requiring human review.\n\n"
        f"- Demand forecast facts: `{counts.get('fact_demand_forecast', 0)}`\n"
        f"- Outage-risk facts: `{counts.get('fact_outage_risk', 0)}`\n"
        f"- Monitoring check facts: `{counts.get('fact_monitoring_check', 0)}`\n",
    )
    _write(
        paths["asset"],
        "# Asset Management Summary\n\n"
        "Asset management reporting uses the existing transparent asset-health scores and "
        "maintenance review priorities without introducing new formulas.\n\n"
        f"- Asset dimension rows: `{counts.get('dim_asset', 0)}`\n"
        f"- Maintenance priority facts: `{counts.get('fact_maintenance_priority', 0)}`\n"
        f"- Asset reason bridge rows: `{counts.get('bridge_asset_reason', 0)}`\n",
    )
    _write(
        paths["reliability"],
        "# Reliability Performance Summary\n\n"
        "SAIFI, SAIDI, CAIDI, and ASAI are surfaced from the reliability component and must be "
        "recalculated from numerator and denominator fields for aggregate contexts.\n\n"
        f"- Reliability facts: `{counts.get('fact_reliability_kpi', 0)}`\n"
        "- Population denominator: observed synthetic smart-meter count.\n"
        "- CTAIDI and CAIFI remain unsupported by the source data.\n",
    )
    _write(
        paths["governance"],
        "# Data And Model Governance Summary\n\n"
        "Governance reporting combines pipeline statuses, data freshness, drift checks, model "
        "health signals, local alert records, and assistant grounding metrics.\n\n"
        f"- Component-run dimension rows: `{counts.get('dim_component_run', 0)}`\n"
        f"- Monitoring alert rows: `{counts.get('fact_monitoring_alert', 0)}`\n"
        f"- Assistant response rows: `{counts.get('fact_assistant_response', 0)}`\n",
    )
    _write(
        paths["validation"],
        "# Reporting Model Validation\n\n"
        f"- Duplicate keys: `{validation.duplicate_key_count}`\n"
        f"- Orphan foreign keys: `{validation.orphan_foreign_key_count}`\n"
        f"- Unknown-member references: `{validation.unknown_member_count}`\n"
        f"- Null critical fields: `{validation.null_critical_field_count}`\n"
        f"- Validation failures: `{len(validation.failures)}`\n\n"
        "All relationship definitions use many-to-one, single-direction filtering semantics.\n",
    )
    return paths


def ensure_dashboard_assets(project_root: Path, config: ReportingConfig) -> dict[str, Path]:
    """Write local DAX definitions, page specifications, and wireframes."""

    dax_root = project_root / "dashboard/dax"
    pages_root = project_root / "dashboard/page-specifications"
    wireframes_root = project_root / "dashboard/wireframes"
    dax_root.mkdir(parents=True, exist_ok=True)
    pages_root.mkdir(parents=True, exist_ok=True)
    wireframes_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "measures": dax_root / "measures.dax",
        "catalogue": dax_root / "measure-catalogue.md",
        "visuals": project_root / "dashboard/visual-specifications.md",
    }
    _write(paths["measures"], _dax_definitions())
    _write(paths["catalogue"], _measure_catalogue())
    _write(paths["visuals"], _visual_specs(config.dashboard_pages))
    for page in config.dashboard_pages:
        _write(pages_root / f"{page}.md", _page_spec(page))
        _write(wireframes_root / f"{page}.md", _wireframe(page))
    return paths


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _dax_definitions() -> str:
    return """-- Local definitions only; not deployed to Power BI.
Total Unplanned Outages = SUM('fact_reliability_kpi'[unplanned_outage_count])
Average Health Score = AVERAGE('fact_asset_health'[health_score])
Critical Asset Count = CALCULATE(DISTINCTCOUNT('dim_asset'[asset_key]), 'fact_asset_health'[health_band] = "CRITICAL")
High Outage Risk Count = CALCULATE(COUNTROWS('fact_outage_risk'), 'fact_outage_risk'[risk_band] IN {"HIGH", "CRITICAL"})
System SAIFI = DIVIDE(SUM('fact_reliability_kpi'[customer_interruptions]), SUM('fact_reliability_kpi'[population_denominator]))
System SAIDI = DIVIDE(SUM('fact_reliability_kpi'[customer_interruption_minutes]), SUM('fact_reliability_kpi'[population_denominator]))
System CAIDI = DIVIDE(SUM('fact_reliability_kpi'[customer_interruption_minutes]), SUM('fact_reliability_kpi'[customer_interruptions]))
System ASAI = 1 - AVERAGE('fact_reliability_kpi'[asui])
Active Warning Alerts = CALCULATE(COUNTROWS('fact_monitoring_alert'), 'fact_monitoring_alert'[severity] = "WARNING", 'fact_monitoring_alert'[suppressed] = "False")
Active Critical Alerts = CALCULATE(COUNTROWS('fact_monitoring_alert'), 'fact_monitoring_alert'[severity] = "CRITICAL", 'fact_monitoring_alert'[suppressed] = "False")
Forecast MAE = AVERAGEX('fact_demand_forecast', ABS('fact_demand_forecast'[actual_value] - 'fact_demand_forecast'[predicted_value]))
Forecast Bias = AVERAGEX('fact_demand_forecast', 'fact_demand_forecast'[predicted_value] - 'fact_demand_forecast'[actual_value])
Grounded Response Rate = DIVIDE(CALCULATE(COUNTROWS('fact_assistant_response'), 'fact_assistant_response'[response_status] = "GROUNDED"), COUNTROWS('fact_assistant_response'))
Citation Coverage = AVERAGE('fact_assistant_response'[citation_coverage])
"""


def _measure_catalogue() -> str:
    return """# Measure Catalogue

These DAX definitions reference the local CSV semantic model. Ratio measures use
`DIVIDE` or numerator/denominator recalculation and are not deployed.

| Measure | Format | Description |
| --- | --- | --- |
| System SAIFI | 0.000 | Recalculated interruptions divided by population denominator. |
| System SAIDI | 0.0 | Recalculated interruption minutes divided by population denominator. |
| System CAIDI | 0.0 | Recalculated minutes divided by customer interruptions. |
| Forecast MAE | #,##0.00 | Row-level absolute forecast error average. |
| Grounded Response Rate | 0.0% | Grounded assistant responses divided by all responses. |
"""


def _visual_specs(pages: tuple[str, ...]) -> str:
    lines = [
        "# Visual Specifications",
        "",
        "These are design specifications only, not deployed visuals.",
        "",
    ]
    for page in pages:
        lines.extend(
            [
                f"## {page}",
                "",
                "| Visual title | Type | Fields | Interaction | Business question |",
                "| --- | --- | --- | --- | --- |",
                "| Headline KPI band | KPI card | KPI catalogue measures | Cross-filter page | What needs attention? |",
                "| Trend or distribution | Line/bar chart | Date, entity, selected measure | Drill-through enabled | How is performance changing? |",
                "| Detail table | Table | Natural IDs, score/status, reason code | Tooltip detail | Which records explain the KPI? |",
                "",
            ]
        )
    lines.append(
        "Colour should communicate severity conceptually and remain accessible; no hard-coded Power BI theme is deployed.\n"
    )
    return "\n".join(lines)


def _page_spec(page: str) -> str:
    title = page.replace("_", " ").title()
    return f"""# {title}

Purpose: answer the audience's highest-priority reporting questions using local semantic tables.

Target audience: `{_audience(page)}`.

Filters: assessment date, grid region, substation, feeder, asset type, criticality tier, health band, maintenance priority, risk band, reliability band, monitoring severity, component, and run ID.

Headline KPIs: selected KPI catalogue measures relevant to this page.

Visuals: KPI cards, trend chart, bar chart, matrix, detail table, and tooltip detail where relevant.

Drill-through behaviour: asset detail, feeder detail, substation detail, monitoring alert detail, and model run detail use natural IDs plus surrogate keys.

Tooltips: expose source run ID, schema version, data completeness, and primary reason code.

Conditional formatting: severity, health band, risk band, reliability band, and response status.

Data sources: local CSV dimensions, facts, bridges, relationships, and KPI catalogue under `outputs/reporting/<run_id>/`.

Limitations: design specification only; no Power BI workspace, semantic model, gateway, scheduled refresh, app, or deployment exists.
"""


def _wireframe(page: str) -> str:
    title = page.replace("_", " ").title()
    return f"""# {title} Wireframe

```text
+----------------------------------------------------------+
| {title[:56]:<56} |
+--------------+--------------+--------------+------------+
| KPI 1        | KPI 2        | KPI 3        | KPI 4      |
+--------------+--------------+--------------+------------+
| Trend / distribution visual                             |
+-----------------------------+----------------------------+
| Entity ranking              | Detail or decomposition    |
+-----------------------------+----------------------------+
| Source lineage, limitations, and human-review notes      |
+----------------------------------------------------------+
```
"""


def _audience(page: str) -> str:
    if "asset" in page:
        return "asset_management"
    if "reliability" in page:
        return "reliability_engineering"
    if "monitoring" in page or "governance" in page:
        return "data_and_model_governance"
    if "executive" in page:
        return "executive_leadership"
    return "grid_operations"
