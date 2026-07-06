# Azure Security Control Matrix

| control_id | control_name | risk | azure_service | implementation | environment | validation_method | deployment_status | limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AZ-001 | Encryption at rest | Data disclosure | Storage, ADX, AML, Key Vault | Platform encryption, optional CMK design | all | Bicep review | BLUEPRINT_ONLY | CMK not provisioned |
| AZ-002 | TLS in transit | Interception | all | TLS 1.2 minimum where supported | all | Static tests | BLUEPRINT_ONLY | Service-specific policy review required |
| AZ-003 | Managed identity | Secret exposure | Entra ID | System/user-assigned identities | all | Bicep review | BLUEPRINT_ONLY | RBAC disabled by default |
| AZ-004 | Private networking | Public endpoint exposure | Storage, AML, Search, Monitor | Public network disabled for test/prod | test/prod | Parameter tests | BLUEPRINT_ONLY | Private endpoints need environment IDs |
| AZ-005 | Diagnostic logging | Log gaps | Azure Monitor | Log Analytics and App Insights | all | Bicep review | BLUEPRINT_ONLY | Per-resource diagnostics require deployed IDs |
| AZ-006 | Least privilege | Privilege escalation | RBAC | No Owner role, no wildcard custom roles | all | Static tests | BLUEPRINT_ONLY | Final assignments environment-specific |
| AZ-007 | Soft delete | Accidental deletion | Storage, Key Vault | Delete retention and purge protection | all | Static tests | BLUEPRINT_ONLY | Recovery runbooks future |
| AZ-008 | Resource locks | Accidental production deletion | Azure Resource Manager | Production recommendation | prod | Checklist | BLUEPRINT_ONLY | Not provisioned in blueprint |
| AZ-009 | Defender recommendations | Configuration drift | Defender for Cloud | Review recommendation process | prod | Operational review | BLUEPRINT_ONLY | No policy assignment deployed |
| AZ-010 | Secret rotation | Credential aging | Key Vault | Managed identity preferred; rotation responsibility documented | all | Security review | BLUEPRINT_ONLY | No secrets are created |
