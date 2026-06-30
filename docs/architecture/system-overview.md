# System Overview

This repository is the Milestone 1 foundation for a local-first grid reliability and energy operations intelligence platform mapped to Azure services.

The current implementation provides repository structure, shared Python foundation utilities, configuration, documentation, tests, and CI. It does not yet generate telemetry, run ingestion pipelines, train models, calculate reliability metrics, deploy Azure resources, or build dashboards.

## Current Local Capabilities

- Python package scaffold under `src/grid_reliability`.
- Typed configuration loading from `configs/base.yaml` with local environment overrides.
- Path resolution for data and output directories.
- Logging initialisation for local tools and future pipeline components.
- Architecture and governance documentation for later milestones.

## Planned Platform Capabilities

Implemented milestones add synthetic meter, substation, weather, maintenance, and outage datasets; batch ingestion; data quality checks; forecasting; and asset-health analytics. Future milestones will add anomaly detection, reliability KPI calculation, reporting outputs, and GenAI-assisted incident analysis.

## Azure Subscription Boundary

The repository documents Azure mappings but does not deploy or authenticate against Azure. Live Event Hubs, Storage, Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, or Azure AI Foundry use would require a real Azure subscription and separate deployment work.
