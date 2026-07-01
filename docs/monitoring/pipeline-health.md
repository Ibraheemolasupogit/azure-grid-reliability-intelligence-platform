# Pipeline Health

Pipeline-health checks classify component runs as `HEALTHY`,
`HEALTHY_WITH_WARNINGS`, `DEGRADED`, `FAILED`, or `NOT_AVAILABLE`.

Rules inspect run status, metrics availability, manifest availability, output
availability, output checksums, required component presence, malformed JSON, and
duplicate run IDs. Warning-only ingestion runs remain healthy with warnings.
