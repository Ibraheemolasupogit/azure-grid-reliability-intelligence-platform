# Asset Health Model Governance

Milestone 5 is a deterministic rules engine, not a predictive machine-learning model.

Runtime outputs are written to:

```text
outputs/asset_health/<run_id>/asset_health_scores.csv
outputs/asset_health/<run_id>/asset_health_components.csv
outputs/asset_health/<run_id>/asset_health_reasons.csv
outputs/asset_health/<run_id>/maintenance_priorities.csv
outputs/asset_health/<run_id>/fleet_summary.json
outputs/asset_health/<run_id>/metrics.json
outputs/asset_health/<run_id>/asset_health_manifest.json
reports/asset_health/<run_id>/asset_health_report.md
reports/asset_health/<run_id>/maintenance_priority_report.md
reports/asset_health/<run_id>/asset_health_methodology.md
reports/asset_health/<run_id>/executive_asset_health_summary.md
```

The manifest records input files, input checksums, configuration checksum, thresholds, weights, assessment timestamp, run ID, code revision where available, output files, output checksums, and synthetic-data declarations.

The local implementation maps conceptually to Azure Data Lake Storage Gen2, Azure Data Explorer or Synapse, Azure Machine Learning batch jobs, Microsoft Purview lineage, and Power BI-ready reporting outputs. No Azure services are called or provisioned by this milestone.
