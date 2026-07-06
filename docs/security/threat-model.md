# Threat Model

Method: STRIDE. Status: `BLUEPRINT_ONLY`.

| asset | threat | attack path | impact | existing local control | Azure control | residual risk | validation evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Telemetry ingress | Event spoofing | Untrusted producer sends synthetic-like events | False analytics | Manifest validation | Event Hubs auth, managed identity | Producer onboarding risk | Bicep/eventing review |
| Data lake | Telemetry tampering | Modify raw or interim files | Corrupted outputs | Checksums and contracts | ADLS RBAC, soft delete, diagnostics | Privileged insider | Storage module review |
| Manifests | Manifest tampering | Replace checksums or counts | False lineage | SHA-256 checks | Immutable logging and Purview lineage | Admin compromise | Manifest lineage docs |
| ML data | Data poisoning | Insert biased examples | Bad forecasts or risk scores | Validation and leakage controls | AML data assets, approvals | Sophisticated poisoning | ML mapping |
| Model artifacts | Artifact substitution | Replace registered model | Wrong predictions | Local metadata checksums | AML registry, identity separation | Registry admin risk | AML mapping |
| Assistant sources | Prompt injection | Malicious document text | Unsafe response | Grounding and refusal rules | AI Foundry safety, Search source filters | Novel prompt attacks | AI mapping |
| Retrieval index | Retrieval poisoning | Poison chunks or metadata | Bad citations | Source registry and checksums | Search index lineage and RBAC | Governance gaps | AI mapping |
| Citations | Citation manipulation | Alter citation metadata | False evidence | Citation persistence | Source checksum preservation | Admin compromise | Assistant docs |
| RBAC | Privilege escalation | Excessive assignments | Data/control-plane misuse | No local secrets | Least privilege, no Owner | Deployment role misuse | Static tests |
| Secrets | Secret exposure | Hard-coded credentials | Compromise | No credentials in repo | Key Vault and managed identity | Operator mishandling | Secret scan/static tests |
| Network | Public endpoint exposure | Internet-accessible services | Unauthorized access | Local only | Private networking | Misconfigured exception | Parameter tests |
| Logs | Log tampering | Delete evidence | Loss of auditability | Local files | Log Analytics retention | Workspace admin risk | Monitoring docs |
| Reports | Dashboard leakage | Overbroad sharing | Data disclosure | Synthetic data | Power BI RLS/workspaces | Misconfigured sharing | Power BI mapping |
| Availability | Denial of service | Excess load or quota exhaustion | Delayed operations | Batch local runs | Scale controls and budgets | Regional outage | DR docs |
| Supply chain | Dependency compromise | Malicious package/action | Code execution | Pinned tooling patterns | CI review, no deployment in CI | Upstream compromise | CI workflow |

This document avoids exploitation instructions and focuses on defensive controls.
