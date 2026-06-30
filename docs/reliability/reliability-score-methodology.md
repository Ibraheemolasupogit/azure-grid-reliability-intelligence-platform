# Reliability Score Methodology

The composite reliability score uses the convention `0 = weakest reliability` and `100 = strongest reliability`.

Default component weights:

| Component | Weight |
| --- | ---: |
| Interruption frequency | 0.25 |
| Interruption duration | 0.25 |
| Restoration | 0.15 |
| Availability | 0.20 |
| Severe-weather resilience | 0.05 |
| Equipment outage | 0.05 |
| Data completeness | 0.05 |

Frequency, duration, restoration, severe-weather, and equipment components use bounded inverse scaling. Availability uses `ASAI * 100`. Data completeness uses observed-meter denominator completeness.

Default reliability bands:

| Band | Rule |
| --- | --- |
| `WEAK` | score `<= 50` |
| `WATCH` | score `> 50` and `<= 70` |
| `STABLE` | score `> 70` and `<= 85` |
| `STRONG` | score `> 85` |
| `INSUFFICIENT_DATA` | denominator below configured minimum |

The score is decision support only and does not replace raw KPI values.
