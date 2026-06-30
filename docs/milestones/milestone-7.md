# Milestone 7: Grid Reliability Scoring and KPI Analytics

Milestone 7 adds local formula-driven reliability KPI analytics over validated historical outage and network data.

Run the default profile after generation and ingestion:

```bash
python3 -m grid_reliability.reliability.pipeline --config configs/reliability.yaml
```

Run the CI profile end to end:

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml
python3 -m grid_reliability.reliability.pipeline --config configs/reliability_ci.yaml
```

Implemented scope:

- observed-meter population denominators;
- planned and unplanned outage separation;
- SAIFI, SAIDI, CAIDI, ASAI, ASUI, and event-level operational measures;
- grid-region, substation, and feeder aggregation;
- overlap-aware availability windows;
- trend and internal peer benchmark outputs;
- composite reliability score, reliability bands, reason codes, metrics, manifests, and reports.

Out of scope:

- new prediction models;
- anomaly detection;
- optimisation;
- automated control;
- GenAI;
- Power BI project files;
- Azure authentication or deployment;
- regulatory submissions;
- financial-loss estimation.
