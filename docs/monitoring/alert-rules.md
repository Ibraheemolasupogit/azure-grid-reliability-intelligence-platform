# Alert Rules

Monitoring alert records are local, deterministic, and template-based. Supported
severities are `INFO`, `WARNING`, `HIGH`, and `CRITICAL`.

Suppression is deterministic and auditable. The CI profile suppresses INFO
alerts, repeated alerts for the same run, and insufficient-sample alerts. Alert
records are retained with suppression reason; no email, SMS, Teams, PagerDuty,
webhook, or live delivery is implemented.
