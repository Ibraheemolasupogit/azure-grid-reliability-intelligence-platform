# Outage Prediction Fixtures

Milestone 6 tests build small temporary prediction datasets from the committed synthetic-data generator and ingestion pipeline. Runtime outputs are written to pytest temporary directories and are not committed.

The tests cover future unplanned outage labels, planned-outage exclusion, horizon boundaries, leakage controls, split purging, metrics, reason codes, persistence, and CLI failure behaviour.
