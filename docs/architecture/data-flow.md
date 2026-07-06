# Data Flow

Milestones 3 through 11 implement local governed movement from raw synthetic source files into interim and quarantine zones, then forecasting, asset-health analytics, outage prediction, reliability KPI analytics, operational monitoring, retrieval-grounded assistant responses, Power BI-ready reporting outputs, and a deployment-free Azure reference blueprint over governed runtime evidence.

```mermaid
flowchart LR
    inputs["Synthetic source files<br/>data/raw"]
    manifest["Manifest and checksum verification"]
    ingestion["CSV and JSONL readers"]
    validation["Contract, dataset, duplicate, and relationship validation"]
    interim["Valid interim JSONL<br/>data/interim"]
    quarantine["Invalid quarantine JSONL<br/>data/quarantine/run_id"]
    reports["Metrics and audit reports<br/>reports/ingestion"]
    forecasting["Local demand forecasting<br/>outputs/forecasting"]
    assethealth["Local asset-health analytics<br/>outputs/asset_health"]
    outage["Local outage prediction<br/>outputs/outage_prediction"]
    reliability["Local reliability analytics<br/>outputs/reliability"]
    analytics["Anomaly analytics<br/>(future milestones)"]
    monitoring["Local operational monitoring<br/>outputs/monitoring"]
    assistant["Local grid operations assistant<br/>outputs/genai"]
    reporting["Power BI-ready outputs and reports<br/>(local artifacts)"]
    azure["Azure Bicep blueprint<br/>infra/bicep"]

    inputs --> manifest --> ingestion --> validation
    validation --> interim --> forecasting --> analytics --> monitoring --> assistant --> reporting --> azure
    interim --> assethealth --> monitoring
    interim --> outage --> monitoring
    interim --> reliability --> monitoring
    validation --> quarantine --> reports
    interim --> reports
    forecasting --> reports
    assethealth --> reports
    outage --> reports
    reliability --> reports
    monitoring --> reports
    assistant --> reports
    reporting --> reports
    azure --> reports
```

The matching Azure pattern is Event Hubs, Azure Functions or Stream Analytics, Data Lake Storage Gen2 raw/quarantine/silver zones, Azure Monitor or Application Insights, Microsoft Purview, Azure Data Explorer or Synapse, Azure Machine Learning, and Power BI. These are mappings only; no Azure resources are deployed.
