# Demo Script

This deterministic path uses CI-sized data and local-only execution.

## 1. Quality

```bash
make quality
```

Expected result: Ruff, format check, mypy, pytest, and coverage pass.

## 2. Generate Synthetic Data

```bash
make generate-data-ci
```

Expected result: synthetic source files and `_manifest.json` appear under `data/raw/`.

## 3. Ingest And Validate

```bash
make ingest-data-ci
```

Expected result: validated interim JSONL files appear under `data/interim/`; ingestion reports appear under `reports/ingestion/local-ci/`.

## 4. Run Analytics

```bash
make forecast-data-ci
make assess-asset-health-ci
make predict-outages-ci
make calculate-reliability-ci
```

Expected result: analytical outputs and reports appear under `outputs/` and `reports/` for forecasting, asset health, outage prediction, and reliability.

## 5. Run Monitoring

```bash
make monitor-platform-ci
```

Expected result: pipeline, data, model, analytical, and alert evaluation outputs appear under `outputs/monitoring/` and `reports/monitoring/monitoring-ci/`.

## 6. Run Assistant

```bash
make run-assistant-ci
```

Expected result: deterministic grounded responses, citations, retrieval records, safety evaluations, metrics, and reports appear under `outputs/genai/` and `reports/genai/assistant-ci/`.

## 7. Build Reporting Model

```bash
make build-reporting-model-ci
```

Expected result: Power BI-ready dimensions, facts, bridge tables, relationships, KPI catalogue, DAX text, dashboard specs, and executive reporting summaries appear under `outputs/reporting/`, `reports/reporting/`, and `dashboard/`.

## 8. Verify Azure Blueprint

```bash
make verify-azure-blueprint
make validate-iac
```

Expected result: static blueprint checks pass. `validate-iac` skips Azure CLI Bicep build/lint when Azure CLI is unavailable.

## 9. Clean Runtime Artifacts

```bash
make clean-data clean-interim clean-quarantine clean-ingestion-reports
make clean-forecasting clean-model-artifacts clean-forecast-reports
make clean-asset-health clean-asset-health-reports
make clean-outage-prediction clean-outage-models clean-outage-reports
make clean-reliability clean-reliability-reports
make clean-monitoring clean-monitoring-reports
make clean-assistant clean-assistant-reports
make clean-reporting clean-reporting-reports clean
```

Expected result: generated runtime paths are removed while `.gitkeep` placeholders remain.
