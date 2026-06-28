# Data Flow

Milestone 1 establishes the intended flow without implementing data movement.

```mermaid
flowchart LR
    inputs["Smart meters, substations, weather, maintenance systems<br/>(planned synthetic sources)"]
    ingestion["Local ingestion interfaces<br/>(future milestone)"]
    validation["Validation and quality controls<br/>(future milestone)"]
    storage["Local data zones<br/>raw, interim, processed"]
    analytics["Forecasting, anomaly, asset health, reliability analytics<br/>(future milestones)"]
    reporting["Power BI-ready outputs and operational monitoring<br/>(future milestones)"]

    inputs --> ingestion --> validation --> storage --> analytics --> reporting
```

The matching Azure pattern is Event Hubs, stream processing, Data Lake Storage Gen2, Azure Data Explorer or Synapse, Azure Machine Learning, Azure Monitor, and Power BI.

