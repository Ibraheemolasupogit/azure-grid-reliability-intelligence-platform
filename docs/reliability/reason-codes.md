# Reliability Reason Codes

Reason codes are deterministic metric explanations, not causal claims.

| Code | Meaning |
| --- | --- |
| `HIGH_INTERRUPTION_FREQUENCY` | SAIFI is elevated |
| `HIGH_INTERRUPTION_DURATION` | SAIDI is elevated |
| `LONG_RESTORATION_TIME` | mean restoration exceeds target |
| `LOW_SERVICE_AVAILABILITY` | ASAI is below strong-service threshold |
| `REPEATED_UNPLANNED_OUTAGES` | more than one unplanned outage |
| `SEVERE_WEATHER_OUTAGE_EXPOSURE` | severe-weather outage evidence |
| `EQUIPMENT_FAILURE_OUTAGE_CONCENTRATION` | equipment-failure outage evidence |
| `HIGH_CUSTOMER_INTERRUPTION_VOLUME` | interruptions exceed population denominator |
| `PROLONGED_OUTAGE_EVENT` | prolonged outage event |
| `PLANNED_OUTAGE_CONCENTRATION` | planned outage evidence |
| `IMPROVING_SAIDI_TREND` | SAIDI improved versus prior period |
| `IMPROVING_SAIFI_TREND` | SAIFI improved versus prior period |
| `STRONG_SERVICE_AVAILABILITY` | ASAI is close to one |
| `NO_UNPLANNED_OUTAGES` | no unplanned outages |
| `INSUFFICIENT_POPULATION_DATA` | denominator unavailable or below minimum |
| `INSUFFICIENT_OUTAGE_HISTORY` | no outage events available |
| `LOW_DATA_COMPLETENESS` | population evidence incomplete |
