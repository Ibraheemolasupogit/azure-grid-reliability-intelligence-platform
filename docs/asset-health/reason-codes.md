# Reason Codes

Reason codes explain the main drivers behind health scores and priorities.

| Code | Meaning |
| --- | --- |
| `AGE_NEAR_EXPECTED_LIFE` | asset age is near configured expected life |
| `AGE_BEYOND_EXPECTED_LIFE` | asset age exceeds configured expected life |
| `INSPECTION_OVERDUE` | inspection due date has passed |
| `MAINTENANCE_DEFERRED` | deferred maintenance appears in the lookback window |
| `HIGH_CORRECTIVE_MAINTENANCE_SHARE` | recent maintenance is largely corrective |
| `RECENT_EMERGENCY_MAINTENANCE` | emergency maintenance appears in the lookback window |
| `SUSTAINED_HIGH_UTILISATION` | telemetry shows repeated high utilisation |
| `PEAK_TEMPERATURE_STRESS` | telemetry shows high transformer temperature |
| `REPEATED_OPERATIONAL_ALARMS` | telemetry contains repeated alarm events |
| `RECENT_DIRECT_UNPLANNED_OUTAGE` | asset is directly linked to recent unplanned outage evidence |
| `EQUIPMENT_FAILURE_OUTAGE_HISTORY` | related outage evidence has equipment-failure cause |
| `FOLLOW_UP_WORK_OUTSTANDING` | maintenance follow-up is required |
| `INSUFFICIENT_TELEMETRY` | telemetry evidence is missing |
| `INSUFFICIENT_MAINTENANCE_HISTORY` | maintenance evidence is missing |
| `GOOD_RECENT_INSPECTION` | inspection evidence is recent and not overdue |
| `LOW_OPERATIONAL_STRESS` | telemetry stress evidence is low |

Reason order is deterministic so repeated runs with the same inputs produce stable explanation ordering.
