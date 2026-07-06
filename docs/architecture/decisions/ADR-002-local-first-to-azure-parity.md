# ADR-002: Preserve Local-First To Azure Parity

Status: BLUEPRINT_COMPLETE

Context: The platform is implemented locally through Milestone 10.

Decision: Map each local component to Azure services without changing local logic.

Alternatives: Rewrite components for cloud-only execution.

Consequences: Clear migration path and testable local behavior.

Security implications: Local controls become explicit Azure controls.

Cost implications: Avoids premature cloud spend.
