# Data Contracts

Milestone 2 adds YAML data contracts under `configs/data_contracts/`.

Each contract defines:

- dataset name and description;
- schema version;
- expected file format;
- fields, types, required flags, units, and categorical values;
- primary or natural key;
- foreign-key relationships where applicable;
- timestamp semantics;
- partitioning recommendation;
- synthetic-data classification;
- basic quality expectations.

The contracts are intentionally lightweight. They are loadable by `grid_reliability.data_generation.contracts`, but they are not a full validation engine. Full validation belongs to Milestone 3.

