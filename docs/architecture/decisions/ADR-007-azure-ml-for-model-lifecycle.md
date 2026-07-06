# ADR-007: Azure ML For Model Lifecycle

Status: BLUEPRINT_COMPLETE

Context: Forecasting and outage-risk pipelines need governed ML lifecycle mapping.

Decision: Use Azure Machine Learning for jobs, tracking, registry, and future batch endpoints.

Alternatives: Custom Functions-only ML execution.

Consequences: Better governance and model lineage.

Security implications: Separate training and inference identities.

Cost implications: Compute scale controls are required.
