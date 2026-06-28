# Validation Framework

Validation is contract-driven. The YAML contracts define dataset names, formats, schema versions, primary keys, required fields, nullable fields, types, allowed categorical values, and foreign-key intent.

Implemented validation layers:

- field validation: required fields, nullability, types, timestamps, dates, booleans, integers, finite numbers, categories, schema versions, and plausible ranges;
- dataset validation: duplicate primary keys, chronology checks, coherent outage duration, utilisation checks, completed maintenance completion fields, and hierarchy shape checks;
- relationship validation: meter to feeder/substation/region, feeder to substation/region, maintenance to asset, outage to primary asset, outage to feeder/substation, and weather to known region.

Warnings indicate unusual but acceptable synthetic conditions. Errors make the affected record invalid and send it to quarantine. Manifest errors are classified separately from record quality errors.

Relationship validation uses `asset_inventory` as the reference dataset. Dependent records are finalised after reference lookups are available.
