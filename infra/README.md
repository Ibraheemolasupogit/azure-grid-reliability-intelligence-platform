# Azure Blueprint Infrastructure

This folder contains **blueprint-only** Bicep templates for the Azure Grid
Reliability Intelligence Platform. The templates are intended for static
validation, architecture review, and future environment-specific deployment
planning.

No Azure deployment has been executed from this repository. The parameter files
use placeholder, subscription-independent values only.

Safe commands:

```bash
make verify-azure-blueprint
make validate-iac
```

Potential future commands such as `scripts/azure/what_if.sh` and
`scripts/azure/deploy.sh` require explicit arguments and Azure credentials. They
are not run by CI and must not be treated as evidence of deployed resources.
