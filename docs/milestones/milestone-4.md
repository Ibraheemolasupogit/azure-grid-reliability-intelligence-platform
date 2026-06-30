# Milestone 4: Electricity Demand Forecasting

Status: implemented.

## Scope

Milestone 4 adds local short-term electricity demand and load forecasting over validated interim telemetry. It supports smart-meter interval energy and substation load, aggregation by grid region, substation, or feeder, leakage-safe feature construction, chronological splits, baselines, a deterministic autoregressive linear candidate, validation-based model selection, empirical prediction intervals, and auditable outputs.

## Run Command

```bash
python3 -m grid_reliability.forecasting.pipeline --config configs/forecasting.yaml
```

Small CI profile:

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml
python3 -m grid_reliability.forecasting.pipeline --config configs/forecasting_ci.yaml
```

## CI Profile

The CI profile contains six hourly timestamps, so it supports one-interval-ahead forecasting only. Day-ahead and weekly seasonal forecasts require longer generated profiles.

## Out of Scope

This milestone does not implement reliability KPIs, outage prediction, asset-health scoring, anomaly-detection models, maintenance optimisation, dashboards, GenAI assistants, Azure SDK authentication, online endpoints, Terraform, Bicep, Spark, or live Azure deployment.
