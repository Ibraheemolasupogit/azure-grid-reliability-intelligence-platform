# 04 Asset Health

Purpose: answer the audience's highest-priority reporting questions using local semantic tables.

Target audience: `asset_management`.

Filters: assessment date, grid region, substation, feeder, asset type, criticality tier, health band, maintenance priority, risk band, reliability band, monitoring severity, component, and run ID.

Headline KPIs: selected KPI catalogue measures relevant to this page.

Visuals: KPI cards, trend chart, bar chart, matrix, detail table, and tooltip detail where relevant.

Drill-through behaviour: asset detail, feeder detail, substation detail, monitoring alert detail, and model run detail use natural IDs plus surrogate keys.

Tooltips: expose source run ID, schema version, data completeness, and primary reason code.

Conditional formatting: severity, health band, risk band, reliability band, and response status.

Data sources: local CSV dimensions, facts, bridges, relationships, and KPI catalogue under `outputs/reporting/<run_id>/`.

Limitations: design specification only; no Power BI workspace, semantic model, gateway, scheduled refresh, app, or deployment exists.
