# Schema And Distribution Drift

Schema drift compares machine-readable contracts under `configs/data_contracts`
with an optional baseline root. Field additions, removals, type changes,
requiredness changes, and schema-version changes are emitted as records. No
contract is modified automatically.

Distribution drift uses transparent deterministic checks. Numeric fields use
absolute mean shift, while categorical fields use total variation distance.
Missing baselines and insufficient samples remain explicit `NOT_AVAILABLE`
records.
