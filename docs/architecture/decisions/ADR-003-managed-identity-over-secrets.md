# ADR-003: Managed Identity Over Secrets

Status: BLUEPRINT_COMPLETE

Context: Secrets in code or app settings increase operational risk.

Decision: Prefer managed identities and Key Vault references.

Alternatives: Connection strings, shared keys, service-principal secrets.

Consequences: RBAC and identity lifecycle become central design concerns.

Security implications: Reduced credential exposure.

Cost implications: Minimal direct cost.
