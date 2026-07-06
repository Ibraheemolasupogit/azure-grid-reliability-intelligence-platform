# Naming And Tagging

Naming inputs:

```text
organisation_prefix + workload_name + environment + region_code + instance
```

Names are deterministic and lower-case. Storage and Key Vault names remove
hyphens and are truncated for service constraints. Globally unique names are
placeholders and must be reviewed before deployment.

Required tags include `application`, `environment`, `owner`, `cost_center`,
`data_classification`, `criticality`, `managed_by`, `repository`, and
`deployment_stage`.
