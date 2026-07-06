# Data Platform

The data platform maps local raw, quarantine, interim, processed, analytics,
model-artifacts, monitoring, assistant-index, and reporting paths to ADLS Gen2
containers with hierarchical namespace enabled.

Event Hubs represents future telemetry ingress but the local generator does not
send live events. Azure Data Explorer represents time-series query serving with
documented retention and cache policies. Synapse or Fabric remains a serving
mapping for curated analytics, not a deployed workspace in this milestone.

Storage uses secure transfer, TLS 1.2, no anonymous access, soft delete, and
public access disabled for production parameters.
