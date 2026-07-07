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
- Local reliability KPI analytics over validated outage and network data.
- Reliability KPI CSVs, trends, benchmarks, scores, manifests, metrics, and Markdown reports.
- Local operational monitoring over runtime manifests, metrics, datasets, contracts, model outputs, and analytical scores.
- Monitoring CSVs, alert evaluations, metrics, manifests, and Markdown reports.
- Local retrieval-grounded grid operations assistant over approved repository evidence.
- Assistant responses, citations, retrieval records, prompt-audit metadata, safety records, evaluation outputs, metrics, manifests, and reports.
- Local Power BI-ready reporting dimensions, facts, bridge tables, relationships, KPI catalogue, DAX text definitions, dashboard specifications, wireframes, metrics, manifests, and executive reports.
- Deployment-free Azure Bicep blueprint, placeholder parameters, architecture diagrams, ADRs, threat model, and static validation tests.
- Tests and static quality checks.

## What Is Planned Locally

- Local analytical tables beyond forecasting, asset health, outage prediction, and reliability KPIs.
- Future live deployment execution and environment-specific integration.

## What Requires Azure

- Event Hubs namespaces and event streams.
- Data Lake Storage Gen2 accounts and containers.
- Synapse, Azure Data Explorer, Azure Machine Learning, Azure Monitor, Power BI, Purview, and Azure AI Foundry resources.
- Azure Monitor ingestion, Application Insights SDK connectivity, Log Analytics workspaces, and alert action groups.
- Azure AI Foundry, Azure OpenAI, Azure AI Search, and external model hosting.
- Online model endpoints, model registry deployment, and production retraining orchestration.
- Identity, networking, RBAC, private endpoints, and production-oriented observability.

Local simulations demonstrate architecture and delivery patterns, not Azure deployment. Milestone 8 monitoring outputs map conceptually to Azure Monitor, Application Insights, Log Analytics, Azure Machine Learning monitoring, Microsoft Purview, and Power BI. Milestone 9 assistant outputs map conceptually to Azure AI Foundry, Azure AI Search, Azure Monitor/Application Insights, and Microsoft Purview. Milestone 10 reporting outputs map conceptually to Power BI semantic models, Microsoft Fabric, Azure Synapse Analytics, Azure Data Explorer, Microsoft Purview, and Azure Monitor. Milestone 11 represents these targets in Bicep and Azure documentation. They remain blueprint-only files.
