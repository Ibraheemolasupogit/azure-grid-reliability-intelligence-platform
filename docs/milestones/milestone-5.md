# Milestone 5: Asset Health Analytics

Milestone 5 adds local, transparent asset-health analytics over validated interim data. It assesses eligible network assets, calculates component condition scores, produces health bands, explains results with reason codes, and assigns rule-based maintenance review priorities.

Run the default profile after generating and ingesting data:

```bash
python3 -m grid_reliability.asset_health.pipeline --config configs/asset_health.yaml
```

Run the small CI profile end to end:

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml
python3 -m grid_reliability.asset_health.pipeline --config configs/asset_health_ci.yaml
```

The CI profile writes outputs under `outputs/asset_health/asset-health-ci/` and reports under `reports/asset_health/asset-health-ci/`.

Implemented scope:

- validated interim-only input loading;
- default exclusion of smart meters;
- deterministic feature derivation for age, inspection, maintenance, telemetry stress, alarms, and outage evidence;
- bounded component scores and weighted health scores;
- explicit health bands and insufficient-data handling;
- deterministic reason codes and review priorities;
- manifests, metrics, fleet summaries, CSV outputs, Markdown reports, tests, Makefile targets, and CI checks.

Out of scope:

- failure prediction;
- outage prediction;
- reliability KPIs such as SAIDI, SAIFI, CAIDI, or availability;
- maintenance optimisation;
- dashboards;
- GenAI;
- Azure SDK calls or Azure deployment;
- Spark processing;
- production engineering certification.
