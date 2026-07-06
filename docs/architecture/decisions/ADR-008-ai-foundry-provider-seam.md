# ADR-008: AI Foundry Provider Seam

Status: BLUEPRINT_COMPLETE

Context: The local assistant is provider-neutral and deterministic.

Decision: Map the provider seam to Azure AI Foundry and retrieval to Azure AI Search.

Alternatives: Hard-code Azure OpenAI or external orchestration frameworks.

Consequences: Local safety, citations, and grounding controls remain portable.

Security implications: Prompt telemetry and retrieval sources require governance.

Cost implications: Model and search usage must be budgeted before deployment.
