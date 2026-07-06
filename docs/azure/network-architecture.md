# Network Architecture

The blueprint defines a virtual network with `integration`, `private_endpoints`,
`machine_learning`, `application`, and `management` subnets. CIDR blocks are
parameterised placeholders and must be checked against enterprise address plans.

Production disables public network access where supported and prefers private
endpoints plus private DNS. Development can enable controlled public access by
parameter for validation environments only.

Power BI connectivity, Azure AI Foundry, Azure AI Search, Azure Machine
Learning, Storage, Key Vault, and Azure Monitor private access require
environment-specific DNS and routing design before deployment. No blanket inbound
internet rule is included.
