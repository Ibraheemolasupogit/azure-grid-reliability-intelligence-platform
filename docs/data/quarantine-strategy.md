# Quarantine Strategy

Invalid records are written to:

```text
data/quarantine/<run_id>/<dataset>.jsonl
```

Each quarantine entry includes dataset name, source filename, source row or line number, ingestion run ID, original raw record where serialisable, validation issues, quarantine timestamp, and schema version. Absolute machine paths and credentials are not written.

Quarantined records are never written to interim outputs. Duplicate primary keys are not silently discarded; all records sharing the duplicated key receive issue context.

Runtime quarantine files are ignored by Git. The committed invalid fixtures under `tests/fixtures/invalid_ingestion/` are deliberately small examples for tests and review.
