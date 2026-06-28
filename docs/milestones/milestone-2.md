# Milestone 2: Governed Synthetic Energy Data Generation

Status: implemented.

## Scope

Milestone 2 adds deterministic generation for six fictional source datasets:

- smart meter readings;
- substation and feeder telemetry;
- weather observations;
- asset inventory;
- maintenance logs;
- outage history.

## Out of Scope

This milestone does not implement ingestion, Event Hubs consumers, stream processing, forecasting, outage prediction, asset-health scoring, anomaly detection, reliability KPI calculation, dashboards, GenAI assistants, Azure deployment, Terraform, Bicep, or model training.

## Run Command

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data.yaml
```

## Privacy and Security

All generated records are fictional. They must not be mixed with real customer, asset, location, outage, maintenance, or operational data.

