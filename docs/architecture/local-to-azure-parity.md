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
- Tests and static quality checks.

## What Is Planned Locally

- Local analytical tables and ML training workflows.
- Local metrics, reporting extracts, and investigation workflows.

## What Requires Azure

- Event Hubs namespaces and event streams.
- Data Lake Storage Gen2 accounts and containers.
- Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, and Azure AI Foundry resources.
- Identity, networking, RBAC, private endpoints, and production-grade observability.

Local simulations demonstrate architecture and delivery patterns, not live Azure deployment.
