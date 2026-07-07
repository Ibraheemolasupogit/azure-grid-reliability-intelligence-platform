# Architecture Walkthrough

The platform follows a local evidence flow that mirrors a cloud-ready architecture without requiring cloud deployment.

## 1. Synthetic Source Layer

Synthetic sources are generated under `data/raw/` from configuration in [configs/synthetic_data.yaml](../../configs/synthetic_data.yaml) or the CI profile in [configs/synthetic_data_ci.yaml](../../configs/synthetic_data_ci.yaml). The generated records are fictional and ignored by Git.

## 2. Governed Ingestion

Ingestion verifies manifests, sizes, hashes, record counts, schemas, field rules, relationship rules, duplicates, and quality thresholds. Valid records are written to `data/interim/`; invalid records are quarantined. This creates the validated interim data boundary.

## 3. Analytical Capabilities

Forecasting, asset-health analytics, outage prediction, and reliability KPIs read from validated interim data. Each component writes outputs, metrics, manifests, and reports so reviewers can inspect both results and evidence.

## 4. Monitoring And Assistant Evidence

Monitoring reads runtime manifests and metrics to produce local health checks and alert evaluations. The assistant reads approved repository-local evidence, retrieves relevant chunks, applies safety checks, and produces deterministic cited responses for decision support.

## 5. Reporting Layer

Reporting converts governed outputs into Power BI-ready dimensions, facts, bridge tables, relationships, DAX text, KPI catalogue entries, dashboard page specifications, wireframes, and executive summaries. These artifacts are local files only.

## 6. Azure Blueprint

The Azure blueprint maps local components to Azure services and deployment concerns:

- Event Hubs for event ingestion.
- ADLS Gen2 for raw, interim, processed, and reporting zones.
- Azure Data Explorer for time-series analytics.
- Azure Machine Learning for model lifecycle patterns.
- Azure AI Foundry and Azure AI Search for future RAG patterns.
- Azure Monitor, Log Analytics, and Application Insights for observability.
- Microsoft Purview for governance.
- Power BI and Fabric for governed consumption.

The blueprint is supported by Bicep modules, parameter files, validation scripts, diagrams, ADRs, security controls, threat modelling, and operational guidance. It remains not deployed.
