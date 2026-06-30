# System Overview

This repository is a local-first grid reliability and energy operations intelligence platform mapped to Azure services.

The current implementation provides repository structure, shared Python foundation utilities, configuration, synthetic data generation, governed ingestion, forecasting, asset-health analytics, outage prediction, documentation, tests, and CI. It does not calculate reliability KPIs, deploy Azure resources, or build dashboards.

## Current Local Capabilities

- Python package scaffold under `src/grid_reliability`.
- Typed configuration loading from `configs/base.yaml` with local environment overrides.
- Path resolution for data and output directories.
- Logging initialisation for local tools and future pipeline components.
- Local synthetic outage-risk prediction with leakage-safe labels, chronological splits, baselines, deterministic logistic regression, metrics, manifests, metadata, and reports.
- Architecture and governance documentation for local-to-Azure mapping.

## Planned Platform Capabilities

Implemented milestones add synthetic meter, substation, weather, maintenance, and outage datasets; batch ingestion; data quality checks; forecasting; asset-health analytics; and outage prediction. Future milestones will add anomaly detection, reliability KPI calculation, reporting outputs, and GenAI-assisted incident analysis.

## Azure Subscription Boundary

The repository documents Azure mappings but does not deploy or authenticate against Azure. Live Event Hubs, Storage, Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, or Azure AI Foundry use would require a real Azure subscription and separate deployment work.
