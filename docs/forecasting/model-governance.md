# Forecasting Model Governance

Forecasting runs write:

```text
outputs/forecasting/<run_id>/load_forecast.csv
outputs/forecasting/<run_id>/metrics.json
outputs/forecasting/<run_id>/model_comparison.csv
outputs/forecasting/<run_id>/forecast_manifest.json
outputs/models/forecasting/<run_id>/model_metadata.json
reports/forecasting/<run_id>/forecast_evaluation.md
reports/forecasting/<run_id>/model_card.md
reports/forecasting/<run_id>/executive_load_forecast_summary.md
```

Metadata includes target definitions, feature list, split boundaries, model parameters, validation and test metrics, input checksums, package versions, and limitations.

Local training maps conceptually to Azure Machine Learning jobs. Local metadata maps conceptually to MLflow or Azure ML tracking. Local model metadata maps conceptually to an Azure ML registry entry. Forecast CSV outputs are Power BI-ready, but Milestone 4 does not create dashboards, endpoints, registries, or Azure resources.

Artifacts are generated runtime files and remain ignored by Git.
