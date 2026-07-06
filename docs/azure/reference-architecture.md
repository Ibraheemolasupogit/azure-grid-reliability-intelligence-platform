# Azure Reference Architecture

Status: `BLUEPRINT_ONLY`.

Milestone 11 maps the local platform to a secure Azure architecture without
deploying resources. The target flow is Event Hubs ingestion, validation and
stream processing, ADLS Gen2 data zones, Azure Data Explorer for time-series
analytics, Azure Machine Learning for jobs and model lifecycle, Azure AI Foundry
and Azure AI Search for governed assistant patterns, Azure Monitor for
observability, Microsoft Purview for catalogue and lineage, and Power BI/Fabric
for reporting.

Every service in the blueprint has a documented platform purpose. No Azure
subscription, credential, resource ID, endpoint, model deployment, workspace, or
Power BI artifact is created.
