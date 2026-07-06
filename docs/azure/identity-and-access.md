# Identity And Access

The blueprint prefers managed identity over secrets. It separates deployment
identity from runtime identities and defines user-assigned identities for
ingestion, analytics, ML training, ML inference, assistant retrieval, and
monitoring.

Role assignments are disabled by default through `enableRoleAssignments` for
static validation. Future deployment should use least-privilege built-in roles at
resource-group or resource scope, avoid `Owner`, avoid wildcard custom roles, and
document any privileged deployment role separately.

No secret values are embedded in Bicep or application settings.
