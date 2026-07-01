# Milestone Roadmap

## Milestone 1: Repository Foundation and Architecture Scaffold

Status: implemented in this repository state.

Scope: project structure, Python package foundation, configuration, documentation, diagrams, baseline tests, developer automation, and CI.

## Milestone 2: Governed Synthetic Energy Data Generation

Status: implemented.

Implemented deterministic fictional source datasets include `smart_meter_events.jsonl`, `substation_events.jsonl`, `weather_data.csv`, `asset_inventory.csv`, `maintenance_logs.csv`, and `outage_history.csv`.

## Milestone 3: Ingestion and Data Quality

Status: implemented.

Implemented local source discovery, manifest verification, CSV and JSON Lines readers, contract validation, relationship validation, duplicate handling, interim JSONL outputs, quarantine JSONL outputs, metrics, audit manifests, quality reports, CLI exit semantics, and a finite local event-oriented reader abstraction.

## Milestone 4: Electricity Demand Forecasting

Status: implemented.

Implemented local short-term forecasting over validated interim telemetry, leakage-safe features, chronological splits, baselines, deterministic autoregressive linear modelling, backtesting, model selection, forecast CSVs, metrics, manifests, model metadata, and reports.

Reliability KPI calculation remains out of scope for this milestone.

## Milestone 5: Asset Health Analytics

Status: implemented for asset-health analytics only.

Implemented validated interim-only asset-health scoring, default smart-meter exclusion, age and lifecycle features, inspection recency features, maintenance history features, operational telemetry stress features, outage-history evidence, bounded component scores, weighted health scores, health bands, reason codes, maintenance review priorities, manifests, metrics, CSV outputs, reports, tests, Makefile targets, and CI checks.

Failure prediction, outage prediction, reliability KPI calculation, anomaly detection, dashboards, optimisation, GenAI, Spark, and Azure deployment remain out of scope.

## Milestone 6: Outage Prediction

Status: implemented for outage prediction only.

Implemented validated interim-only outage-risk prediction, feeder/substation/primary-asset entity semantics, leakage-safe future unplanned-outage labels, historical operational/weather/smart-meter/asset/maintenance/prior-outage features, chronological splitting with purge, baselines, deterministic logistic regression, class weighting, rare-event metrics, raw-score calibration metadata, model selection, risk bands, reason codes, manifests, model metadata, reports, Makefile targets, and CI checks.

Reliability KPIs, separate asset-failure probability models, anomaly detection, dashboards, automated response, restoration optimisation, GenAI, Spark, and Azure deployment remain out of scope.

## Milestone 7: Grid Reliability Scoring and KPI Analytics

Status: implemented.

Implemented validated interim-only reliability analytics, observed-meter population denominators, planned and unplanned outage separation, SAIFI, SAIDI, CAIDI, ASAI, ASUI, operational outage measures, hierarchy aggregation, overlap-aware availability windows, trend outputs, internal peer benchmarks, composite reliability scores, reliability bands, reason codes, manifests, metrics, reports, Makefile targets, and CI checks.

Regulatory submissions, real operator benchmarking, financial-loss estimation, dashboards, optimisation, GenAI, Spark, and Azure deployment remain out of scope.

## Milestone 8: Operational Monitoring and Data/Model Observability

Status: implemented for local monitoring and observability only.

Implemented deterministic local component discovery, pipeline-health checks, freshness and volume checks, ingestion quality trends, schema drift records, distribution drift records, forecast monitoring, outage-prediction monitoring, asset-health and reliability analytical monitoring, alert-rule evaluation, alert suppression, metrics, manifests, CSV outputs, Markdown reports, Makefile targets, and CI checks.

Live Azure Monitor ingestion, Application Insights SDK connectivity, Log Analytics workspaces, external alert delivery, dashboards, automated retraining, automated remediation, GenAI, Spark, and Azure deployment remain out of scope.

## Milestone 9: Azure Deployment Guidance

Planned reference architecture, deployment guidance, security model, and Azure service configuration. No Azure deployment is included in Milestones 1 through 8.
