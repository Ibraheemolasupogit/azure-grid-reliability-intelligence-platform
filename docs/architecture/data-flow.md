# Data Flow

Milestone 3 implements local governed movement from raw synthetic source files into interim and quarantine zones.

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
    analytics["Anomaly, asset health, reliability analytics<br/>(future milestones)"]
    reporting["Power BI-ready outputs and operational monitoring<br/>(future milestones)"]

    inputs --> manifest --> ingestion --> validation
    validation --> interim --> forecasting --> analytics --> reporting
    validation --> quarantine --> reports
    interim --> reports
    forecasting --> reports
```

The matching Azure pattern is Event Hubs, Azure Functions or Stream Analytics, Data Lake Storage Gen2 raw/quarantine/silver zones, Azure Monitor or Application Insights, Microsoft Purview, Azure Data Explorer or Synapse, Azure Machine Learning, and Power BI. These are mappings only; no Azure resources are deployed.
