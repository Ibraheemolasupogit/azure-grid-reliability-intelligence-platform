# Azure Service Mapping

| Platform capability | Local-first implementation | Azure target |
| --- | --- | --- |
| Meter ingestion | JSONL/event simulator and Python consumers | Azure Event Hubs |
| Raw storage | Local filesystem partitioning | Azure Data Lake Storage Gen2 |
| Stream processing | Python event-processing pipeline | Azure Stream Analytics or Azure Functions |
| Analytical warehouse | Local analytical tables | Azure Synapse Analytics |
| Time-series analytics | Local Python/columnar analysis | Azure Data Explorer |
| ML lifecycle | Local reproducible training pipelines | Azure Machine Learning |
| GenAI operations assistant | Provider-neutral local interface | Azure AI Foundry |
| Monitoring | Structured logs and local metrics | Azure Monitor/Application Insights |
| Reporting | CSV/Parquet analytical outputs | Microsoft Power BI |
| Governance | Local metadata and documentation | Microsoft Purview |

These mappings are architectural targets. Milestone 1 does not provision Azure resources, validate Azure connectivity, or demonstrate live cloud operation.

