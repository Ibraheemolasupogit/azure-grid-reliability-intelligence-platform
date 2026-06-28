# Quality Issue Codes

Milestone 3 issue codes are stable strings emitted in metrics, quarantine records, and reports.

| Code | Meaning |
| --- | --- |
| `REQUIRED_FIELD_MISSING` | A non-nullable contract field is missing or blank. |
| `UNEXPECTED_FIELD` | A record contains a field outside the active data contract. |
| `INVALID_DATA_TYPE` | A field cannot be parsed as its contract data type. |
| `INVALID_TIMESTAMP` | A timestamp field is not valid ISO-8601. |
| `INVALID_DATE` | A date field is not valid ISO-8601 date format. |
| `VALUE_OUT_OF_RANGE` | A numeric or temporal value is outside a plausible range. |
| `INVALID_CATEGORY` | A controlled field contains a value outside `allowed_values`. |
| `DUPLICATE_PRIMARY_KEY` | A duplicate primary key was observed in one dataset. |
| `DUPLICATE_NATURAL_KEY` | Reserved for explicit future natural-key checks. |
| `FOREIGN_KEY_NOT_FOUND` | A referenced asset, feeder, substation, meter, or region is unknown. |
| `HIERARCHY_MISMATCH` | Related hierarchy fields disagree across datasets. |
| `SCHEMA_VERSION_MISMATCH` | A record schema version differs from the contract version. |
| `MALFORMED_RECORD` | A source line or row could not be parsed as a record. |
| `EMPTY_FILE` | A required dataset file exists but contains no records. |
| `MANIFEST_MISSING` | The configured source manifest is required but absent. |
| `MANIFEST_MALFORMED` | The source manifest is invalid JSON or lacks required structure. |
| `MANIFEST_CHECKSUM_MISMATCH` | A file SHA-256 does not match the manifest entry. |
| `MANIFEST_COUNT_MISMATCH` | A parsed source record count does not match the manifest entry. |
| `MANIFEST_SIZE_MISMATCH` | A file size does not match the manifest entry. |
| `MANIFEST_DATASET_MISSING` | A required dataset is missing from the manifest. |
| `MANIFEST_DATASET_UNEXPECTED` | The manifest contains an unexpected dataset or filename. |
| `MANIFEST_DUPLICATE_ENTRY` | The manifest contains duplicate dataset or filename entries. |
| `FILE_MISSING` | A required source file is missing. |
| `FILE_UNEXPECTED` | A source directory contains a file outside the contract catalogue. |
| `UNSUPPORTED_FORMAT` | A dataset declares an unsupported source format. |
| `INCONSISTENT_CSV_ROW` | A CSV row has extra or missing columns. |
| `CHRONOLOGY_INVALID` | A start/end or lifecycle chronology is inconsistent or unusual. |
| `DERIVED_VALUE_MISMATCH` | A supplied derived value differs from recomputation. |
