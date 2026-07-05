# Reporting Data Governance

Reporting sources are restricted to governed local analytical outputs, manifests,
metrics, reports, and validated interim asset inventory. Raw and quarantined data
are not reporting sources.

The reporting layer records synthetic-data flags and limitations. It does not
contain real customers, addresses, coordinates, utility assets, credentials, or
external data sources.

Relationship validation checks primary-key uniqueness, foreign-key integrity,
unknown-member usage, fact grain uniqueness, and null critical fields.
