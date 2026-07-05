# Power BI Deployment Mapping

Local artifacts map conceptually to Microsoft services:

- CSV dimensions, facts, and bridges: Power BI semantic model or Fabric Lakehouse tables.
- KPI catalogue and DAX text: Power BI measures and model documentation.
- Reporting manifests and checksums: Microsoft Purview lineage metadata.
- Monitoring and validation outputs: Azure Monitor, Log Analytics, and Power BI refresh monitoring concepts.
- Analytical component outputs: Azure Synapse Analytics or Azure Data Explorer serving layers.

No workspace, dataset, semantic model, gateway, scheduled refresh, app, API
call, authentication, or Azure/Fabric infrastructure is created.
