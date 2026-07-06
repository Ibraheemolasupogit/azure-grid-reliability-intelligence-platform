# ADR-001: Use Bicep For Azure IaC

Status: BLUEPRINT_COMPLETE

Context: Milestone 11 needs a single Azure-native IaC language.

Decision: Use Bicep only.

Alternatives: Terraform, ARM JSON, ad hoc scripts.

Consequences: Azure-native modules, no parallel Terraform state, future deployment can use Azure CLI or pipelines.

Security implications: Templates remain reviewable and static-testable.

Cost implications: No cost until deployed.
