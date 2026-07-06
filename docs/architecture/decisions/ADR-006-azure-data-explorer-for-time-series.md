# ADR-006: Azure Data Explorer For Time Series

Status: BLUEPRINT_COMPLETE

Context: Grid telemetry and reliability events are time-series heavy.

Decision: Use Azure Data Explorer as the time-series analytics target.

Alternatives: Synapse-only serving, Fabric-only serving.

Consequences: KQL-oriented analytical serving for operations data.

Security implications: Private access and RBAC required.

Cost implications: Cluster capacity is a significant driver.
