# Condition Components

Asset health is built from six transparent component scores, each bounded from `0` to `100`.

| Component | Evidence | Direction |
| --- | --- | --- |
| Age | commissioned date and expected life | declines as age approaches or exceeds expected life |
| Inspection | last inspection and next due date | declines when inspections are overdue |
| Maintenance | maintenance type, status, downtime, follow-up | declines with corrective, emergency, deferred, or follow-up work |
| Telemetry stress | utilisation, transformer temperature, constrained/offline states | declines with sustained operating stress |
| Alarm | recent telemetry alarm events | declines with repeated alarms |
| Outage | direct and contextual outage history | declines with direct unplanned and equipment-failure outage evidence |

Missing maintenance, telemetry, or outage evidence is handled by the configured `missing_data_policy`. The default `neutral` policy uses a neutral component value and records the missing component in the component output.

The component table includes the derived feature values, component scores, and weighted component contributions for review.
