# Reporting Architecture

Milestone 10 adds a deterministic local reporting layer that consolidates governed
outputs from forecasting, asset health, outage prediction, reliability,
monitoring, and the Grid Operations Assistant.

```text
governed analytical outputs
-> reporting source discovery
-> key and schema standardisation
-> dimension construction
-> fact-table construction
-> relationship validation
-> KPI and semantic definitions
-> Power BI-ready CSV exports
-> dashboard specifications and executive reports
```

The layer writes local CSV datasets under `outputs/reporting/<run_id>/` and
Markdown reports under `reports/reporting/<run_id>/`. It does not create a
`.pbix`, `.pbit`, Power BI workspace, Fabric workspace, gateway, scheduled
refresh, or Azure resource.
