# Environment Strategy

The blueprint supports `dev`, `test`, and `prod` through separate Bicep parameter
files. Environments may use separate subscriptions or resource groups depending
on organisational policy.

Development permits controlled public network access for selected resources in
the placeholder parameters. Test and production disable public network access
where supported. Production uses longer retention, stronger criticality tags,
private networking by default, resource-lock recommendations, and formal
approval gates.

No parameter file contains tenant IDs, subscription IDs, object IDs, credentials,
real IP ranges, or deployed resource IDs.
