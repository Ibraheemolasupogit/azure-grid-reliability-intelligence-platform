# Refresh And Lineage

Local refresh order:

```text
synthetic generation
-> ingestion and validation
-> interim data
-> forecasting, asset health, outage prediction, reliability
-> monitoring
-> assistant
-> reporting model
```

The reporting manifest records source files, checksums, source runs,
configuration checksum, output checksums, row counts, relationships, KPI
catalogue checksum, DAX checksum, repository revision, and limitations.

Conceptually, the CSV outputs could be imported into Power BI or Fabric, with
lineage mapped to Microsoft Purview and source observability mapped to Azure
Monitor. This repository does not configure cloud refresh.
