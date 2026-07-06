# ADR-004: Private Networking For Production

Status: BLUEPRINT_COMPLETE

Context: Critical-infrastructure analytics should reduce public exposure.

Decision: Production disables public network access where supported and uses private endpoint design.

Alternatives: Public endpoints with firewall rules only.

Consequences: DNS, routing, and Power BI connectivity require planning.

Security implications: Smaller exposure surface.

Cost implications: Private networking adds operational overhead.
