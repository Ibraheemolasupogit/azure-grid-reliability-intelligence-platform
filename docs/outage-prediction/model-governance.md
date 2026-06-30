# Outage Prediction Model Governance

Runtime outputs are written to:

```text
outputs/outage_prediction/<run_id>/outage_risk_predictions.csv
outputs/outage_prediction/<run_id>/metrics.json
outputs/outage_prediction/<run_id>/model_comparison.csv
outputs/outage_prediction/<run_id>/threshold_analysis.csv
outputs/outage_prediction/<run_id>/confusion_matrix.csv
outputs/outage_prediction/<run_id>/outage_prediction_manifest.json
outputs/models/outage_prediction/<run_id>/model_metadata.json
outputs/models/outage_prediction/<run_id>/feature_schema.json
outputs/models/outage_prediction/<run_id>/preprocessing_metadata.json
reports/outage_prediction/<run_id>/outage_prediction_evaluation.md
reports/outage_prediction/<run_id>/outage_risk_report.md
reports/outage_prediction/<run_id>/model_card.md
reports/outage_prediction/<run_id>/executive_outage_risk_summary.md
```

The manifest records input checksums, configuration checksum, label definition, entity grain, lookback, horizon, split boundaries, purge interval, candidate models, selected model, threshold, output checksums, row counts, failed models, repository revision where available, and synthetic-data limitations.

Local training maps conceptually to Azure Machine Learning. Time-series feature preparation maps conceptually to Azure Data Explorer, Synapse, or Fabric. Logs and metrics map conceptually to Azure Monitor. Lineage maps conceptually to Microsoft Purview. CSV outputs are Power BI-ready. No dashboard or Azure deployment exists.
