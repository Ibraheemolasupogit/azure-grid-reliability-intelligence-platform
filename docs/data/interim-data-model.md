# Interim Data Model

Milestone 3 writes all valid normalised datasets as JSON Lines under:

```text
data/interim/<dataset>.jsonl
```

The interim representation uses:

- contract field ordering;
- parsed numeric and boolean values;
- timestamps normalised to UTC ISO-8601 with `Z`;
- nulls for optional blank values;
- schema version from the contract;
- deterministic JSON serialisation;
- `_ingestion` metadata containing dataset name, source file, source record number, ingestion run ID, and ingestion timestamp.

The interim layer does not add analytical features, forecasts, reliability KPIs, risk scores, or model targets.
