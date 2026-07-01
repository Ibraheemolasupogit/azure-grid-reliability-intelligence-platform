# Monitoring Fixtures

Milestone 8 tests create most monitoring evidence in temporary directories so normal
runtime outputs are not committed. This folder documents the fixture intent:

- healthy, warning, failed, and unavailable component runs;
- freshness, volume, schema, and distribution checks;
- model and analytical monitoring records;
- deterministic local alert evaluation and suppression.

The repository should not commit generated `outputs/monitoring` or `reports/monitoring`
artifacts from normal execution.
