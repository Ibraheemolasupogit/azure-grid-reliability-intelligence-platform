# Reliability Data Governance

Reliability analytics use fictional synthetic data only.

Runtime outputs are ignored by Git and written under:

```text
outputs/reliability/<run_id>/
reports/reliability/<run_id>/
```

The manifest records input files and checksums, configuration checksum, KPI version, score version, aggregation levels, period frequency, population method, outage inclusion policy, component weights, band thresholds, output checksums, assumptions, limitations, and repository revision where available.

Local time-series calculations map conceptually to Azure Data Explorer, Synapse, or Microsoft Fabric. Outputs are Power BI-ready CSV files, but no dashboard exists. Metrics map conceptually to Azure Monitor, and lineage maps conceptually to Microsoft Purview. No Azure resources are deployed.
