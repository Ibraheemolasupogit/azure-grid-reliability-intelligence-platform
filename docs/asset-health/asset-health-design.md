# Asset Health Design

Milestone 5 implements local, transparent asset-health analytics over validated interim data only. It consumes `data/interim/*.jsonl`; it does not read raw source files and does not use ingestion metadata as scoring evidence.

The workflow assesses eligible network assets from `asset_inventory.jsonl`, derives evidence from maintenance logs, substation events, and outage history, then writes auditable scores, component evidence, reason codes, priorities, metrics, manifests, and Markdown reports.

Eligible asset types are:

- `primary_substation`
- `secondary_substation`
- `transformer`
- `circuit_breaker`
- `feeder`
- `switchgear`
- `protection_relay`

`smart_meter` assets are excluded by default because this milestone scores network asset condition, not customer meter health.

The score convention is `0` for poorest condition and `100` for strongest condition. Condition score, criticality, operational risk evidence, and maintenance priority are kept as separate outputs.

This milestone does not implement failure prediction, outage prediction, reliability KPIs, maintenance optimisation, dashboards, GenAI, Azure SDK calls, Azure resource deployment, Spark, or production certification.
