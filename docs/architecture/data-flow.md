# Data Flow

Milestones 3 through 8 implement local governed movement from raw synthetic source files into interim and quarantine zones, then forecasting, asset-health analytics, outage prediction, reliability KPI analytics, and operational monitoring over validated runtime evidence.

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
    reporting["Power BI-ready outputs and reports<br/>(local artifacts)"]

    inputs --> manifest --> ingestion --> validation
    validation --> interim --> forecasting --> analytics --> monitoring --> reporting
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
```

The matching Azure pattern is Event Hubs, Azure Functions or Stream Analytics, Data Lake Storage Gen2 raw/quarantine/silver zones, Azure Monitor or Application Insights, Microsoft Purview, Azure Data Explorer or Synapse, Azure Machine Learning, and Power BI. These are mappings only; no Azure resources are deployed.
