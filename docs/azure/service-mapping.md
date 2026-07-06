# Azure Service Mapping

| Local capability | Azure service | Purpose | Deployment status |
| --- | --- | --- | --- |
| Synthetic/event ingestion | Azure Event Hubs | Event ingress boundary for telemetry | BLUEPRINT_ONLY |
| Raw/interim/processed zones | ADLS Gen2 | Governed data lake zones | BLUEPRINT_ONLY |
| Validation and batch processing | Azure Functions, Azure ML jobs, Data Factory patterns | Orchestration options | BLUEPRINT_ONLY |
| Time-series analytics | Azure Data Explorer | Query operational telemetry and reliability signals | BLUEPRINT_ONLY |
| Analytical serving | Synapse or Fabric mapping | Serving layer for curated analytics | BLUEPRINT_ONLY |
| Forecasting/outage ML lifecycle | Azure Machine Learning | Jobs, environments, tracking, registry mapping | BLUEPRINT_ONLY |
| Assistant provider seam | Azure AI Foundry | Future governed GenAI provider | BLUEPRINT_ONLY |
| Assistant retrieval | Azure AI Search | Search index for governed chunks and citations | BLUEPRINT_ONLY |
| Secrets | Azure Key Vault | Managed secret and key reference boundary | BLUEPRINT_ONLY |
| Identity | Entra ID and managed identities | Least-privilege runtime identity | BLUEPRINT_ONLY |
| Monitoring | Azure Monitor, Log Analytics, Application Insights | Logs, metrics, diagnostics, workbooks | BLUEPRINT_ONLY |
| Governance | Microsoft Purview | Catalogue, lineage, ownership, classification | BLUEPRINT_ONLY |
| Reporting | Power BI and Fabric mapping | Semantic model and dashboard deployment target | BLUEPRINT_ONLY |
