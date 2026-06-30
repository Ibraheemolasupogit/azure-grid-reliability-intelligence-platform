# Reason Codes

Reason codes are deterministic rule-based explanations derived from observed feature values. They are not causal explanations.

| Code | Meaning |
| --- | --- |
| `RECENT_UNPLANNED_OUTAGE` | prior unplanned outage inside the lookback window |
| `REPEATED_OPERATIONAL_ALARMS` | repeated recent telemetry alarms |
| `SUSTAINED_HIGH_UTILISATION` | high recent utilisation |
| `PEAK_TEMPERATURE_STRESS` | high transformer temperature |
| `RECENT_OFFLINE_STATE` | recent offline operational state |
| `RECENT_CONSTRAINED_STATE` | recent constrained operational state |
| `SEVERE_WEATHER_EXPOSURE` | recent or current severe weather |
| `HIGH_WIND_EXPOSURE` | high recent wind gust |
| `HEAVY_PRECIPITATION_EXPOSURE` | heavy recent precipitation |
| `INSPECTION_OVERDUE` | inspection due date has passed |
| `RECENT_CORRECTIVE_MAINTENANCE` | corrective maintenance in lookback |
| `RECENT_EMERGENCY_MAINTENANCE` | emergency maintenance in lookback |
| `DEFERRED_MAINTENANCE` | deferred maintenance in lookback |
| `FOLLOW_UP_WORK_OUTSTANDING` | maintenance follow-up required |
| `AGE_NEAR_EXPECTED_LIFE` | asset age near expected life |
| `AGE_BEYOND_EXPECTED_LIFE` | asset age exceeds expected life |
| `POOR_DATA_COMPLETENESS` | incomplete historical evidence |
| `LOW_RECENT_STRESS` | no elevated rule-based drivers detected |
