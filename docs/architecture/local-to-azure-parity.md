# Local-to-Azure Parity

The platform is designed to demonstrate engineering patterns locally before cloud deployment.

## What Runs Locally Now

- Configuration loading.
- Environment validation.
- Path resolution.
- Logging setup.
- Deterministic synthetic data generation.
- Manifest verification.
- CSV and JSON Lines ingestion.
- Contract, duplicate, dataset, and relationship validation.
- Interim JSONL and quarantine JSONL persistence.
- Ingestion metrics, audit manifests, and Markdown quality reports.
- Local short-term forecasting over validated interim telemetry.
- Forecast CSVs, model comparison metrics, model metadata, manifests, and Markdown model reports.
- Local transparent asset-health analytics over validated interim data.
- Asset-health CSVs, component evidence, reason codes, priorities, manifests, metrics, and Markdown reports.
- Local synthetic outage-risk prediction over validated interim data.
- Outage-risk CSVs, metrics, model metadata, manifests, risk bands, reason codes, and Markdown reports.
- Tests and static quality checks.

## What Is Planned Locally

- Local analytical tables beyond forecasting, asset health, and outage prediction.
- Local metrics, reporting extracts, and investigation workflows.

## What Requires Azure

- Event Hubs namespaces and event streams.
- Data Lake Storage Gen2 accounts and containers.
- Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, and Azure AI Foundry resources.
- Online model endpoints, model registry deployment, and production retraining orchestration.
- Identity, networking, RBAC, private endpoints, and production-grade observability.

Local simulations demonstrate architecture and delivery patterns, not live Azure deployment.
