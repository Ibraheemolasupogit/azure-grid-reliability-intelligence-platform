# Health Score Methodology

The health score is a deterministic weighted average of component scores. The default weights are:

| Component | Weight |
| --- | ---: |
| Age | 0.18 |
| Inspection | 0.17 |
| Maintenance | 0.20 |
| Telemetry stress | 0.20 |
| Alarm | 0.10 |
| Outage | 0.15 |

Weights must be between `0` and `1` and sum to `1.0`.

Default health bands are:

| Band | Rule |
| --- | --- |
| `CRITICAL` | score `<= 35` |
| `DEGRADED` | score `> 35` and `<= 55` |
| `WATCH` | score `> 55` and `<= 75` |
| `HEALTHY` | score `> 75` |
| `INSUFFICIENT_DATA` | evidence completeness below the configured minimum |

Health score is independent of criticality tier. Criticality is used only when assigning review priority.

The model is rule-based and auditable. It is not trained to predict failures or outages.
