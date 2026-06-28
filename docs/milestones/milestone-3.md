# Milestone 3: Governed Ingestion and Data Validation

Status: implemented.

## Scope

Milestone 3 adds local ingestion and validation for the six Milestone 2 synthetic datasets. It verifies source manifests, parses CSV and JSON Lines, validates contracts and relationships, writes valid records to `data/interim/`, quarantines invalid records under `data/quarantine/<run_id>/`, and emits ingestion metrics and audit reports.

## Run Command

```bash
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion.yaml
```

Small CI profile:

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml
```

## Run Statuses

- `PASSED`
- `PASSED_WITH_WARNINGS`
- `FAILED_QUALITY_THRESHOLD`
- `FAILED_MANIFEST`
- `FAILED_CONFIGURATION`
- `FAILED_PROCESSING`

The CLI exits non-zero for failed statuses.

## Out of Scope

This milestone does not implement forecasting, reliability KPI calculation, model training, anomaly detection models, outage prediction models, dashboards, GenAI assistants, Azure SDK authentication, live Event Hubs connectivity, Terraform, Bicep, Spark processing, or Azure resource deployment.

Azure services are architectural mappings only.
