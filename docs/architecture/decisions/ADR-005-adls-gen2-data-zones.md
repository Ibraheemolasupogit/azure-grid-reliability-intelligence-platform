# ADR-005: ADLS Gen2 Data Zones

Status: BLUEPRINT_COMPLETE

Context: Local folders use raw, quarantine, interim, processed, analytics, monitoring, assistant, and reporting zones.

Decision: Map these to ADLS Gen2 containers with hierarchical namespace.

Alternatives: Flat blob storage or per-component accounts.

Consequences: Consistent lineage and access boundaries.

Security implications: Container-level RBAC and diagnostics.

Cost implications: Storage lifecycle policies become important.
