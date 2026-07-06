# System Overview

This repository is a local-first grid reliability and energy operations intelligence platform mapped to Azure services.

The current implementation provides repository structure, shared Python foundation utilities, configuration, synthetic data generation, governed ingestion, forecasting, asset-health analytics, outage prediction, reliability KPI analytics, operational monitoring, a grounded local assistant, Power BI-ready reporting outputs, documentation, tests, CI, and a deployment-free Azure Bicep blueprint. It does not deploy Azure resources or build deployed dashboards.

## Current Local Capabilities

- Python package scaffold under `src/grid_reliability`.
- Typed configuration loading from `configs/base.yaml` with local environment overrides.
- Path resolution for data and output directories.
- Logging initialisation for local tools and future pipeline components.
- Local synthetic outage-risk prediction with leakage-safe labels, chronological splits, baselines, deterministic logistic regression, metrics, manifests, metadata, and reports.
- Local reliability KPI analytics with SAIFI, SAIDI, CAIDI, ASAI, ASUI, trends, internal benchmarks, composite scores, manifests, metrics, and reports.
- Local monitoring, grounded assistant responses, and Power BI-ready reporting semantic outputs.
- Blueprint-only Azure reference architecture, modular Bicep templates, safe validation scripts, ADRs, threat model, and diagrams.
- Architecture and governance documentation for local-to-Azure mapping.

## Planned Platform Capabilities

Implemented milestones add synthetic meter, substation, weather, maintenance, and outage datasets; batch ingestion; data quality checks; forecasting; asset-health analytics; outage prediction; reliability KPI analytics; monitoring; GenAI-assisted local incident analysis; reporting outputs; and Azure blueprint documentation. Future work may add anomaly-detection models and real deployment.

## Azure Subscription Boundary

The repository documents Azure mappings and Bicep templates but does not deploy or authenticate against Azure. Live Event Hubs, Storage, Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, Azure AI Search, or Azure AI Foundry use would require a real Azure subscription, approvals, credentials, and separate deployment work.
