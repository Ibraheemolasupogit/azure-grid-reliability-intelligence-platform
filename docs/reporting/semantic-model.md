# Semantic Model

The semantic model uses a star-schema-style design with explicit surrogate keys,
natural IDs, and many-to-one single-direction relationships.

Core dimensions include date, time, grid region, substation, feeder, asset,
model, component run, alert reason, and metric. Core facts include demand
forecast, asset health, outage risk, reliability KPIs, monitoring checks,
monitoring alerts, assistant responses, and maintenance priorities.

Surrogate keys are deterministic SHA-256 prefixes derived from natural business
identifiers. Unknown members use `SK_UNKNOWN`. Business IDs from source systems
are preserved and never replaced.
