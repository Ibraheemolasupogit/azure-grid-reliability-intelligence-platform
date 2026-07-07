# Interview Talking Points

## 60-Second Explanation

This is a local-first Azure-mapped grid reliability platform. It uses synthetic grid telemetry to demonstrate the full path from governed ingestion to validated interim data, forecasting, asset health, outage risk, reliability KPIs, monitoring, grounded assistant responses, and Power BI-ready outputs. The Azure side is documented as a blueprint with Bicep and architecture guidance only; no cloud resources or dashboards are deployed.

## 2-Minute Explanation

The project is built around evidence flow. Synthetic sources represent smart meters, substations, weather, assets, maintenance, and outages. Ingestion validates manifests, schemas, quality rules, relationships, and record counts before writing validated interim data. Analytics then consume only that governed layer.

Forecasting, asset health, outage prediction, and reliability analytics each produce outputs, metrics, manifests, and reports. Monitoring reviews those artifacts for pipeline, data, model, and analytical health. The assistant retrieves from approved repository evidence and produces grounded, cited, deterministic responses. Reporting turns governed outputs into Power BI-ready tables, relationships, DAX text, and page specifications.

The Azure blueprint maps those local patterns to services such as Event Hubs, ADLS Gen2, Azure Data Explorer, Azure Machine Learning, Azure AI Foundry, Azure AI Search, Azure Monitor, Purview, Power BI, and Fabric. It is deliberately not deployed.

## 5-Minute Technical Walkthrough

1. Start with [README.md](../../README.md) and [docs/portfolio/reviewer-guide.md](reviewer-guide.md).
2. Show synthetic data contracts in [configs/data_contracts](../../configs/data_contracts) and design notes in [docs/data](../data/README.md).
3. Explain ingestion and the validated interim boundary in [src/grid_reliability/ingestion](../../src/grid_reliability/ingestion) and [docs/data/interim-data-model.md](../data/interim-data-model.md).
4. Walk through analytics modules under [src/grid_reliability](../../src/grid_reliability): forecasting, asset health, outage prediction, reliability, monitoring, GenAI, and reporting.
5. Show quality gates in [Makefile](../../Makefile), [tests/unit](../../tests/unit), and [.github/workflows](../../.github/workflows).
6. Close with [docs/azure/reference-architecture.md](../azure/reference-architecture.md), [infra/README.md](../../infra/README.md), and [docs/security/threat-model.md](../security/threat-model.md).

## Architecture Explanation

The design separates source data, validated interim data, analytical outputs, monitoring evidence, assistant evidence, and reporting outputs. That separation keeps quality controls visible and makes it clear which artifacts are source-like, validated, analytical, or presentation-ready.

## Data Engineering Explanation

The ingestion layer checks manifests, file integrity, schemas, data quality, relationships, and run status. It writes valid records to `data/interim/`, quarantines invalid records, and emits metrics and audit reports. Generated runtime data is ignored by Git.

## ML Explanation

The forecasting and classification workflows are deterministic local demonstrations over synthetic data. They use chronological splits, leakage controls, metrics, model metadata, reports, and explicit limitations. They are not calibrated for live grid operations.

## Security And Governance Explanation

The project uses synthetic data, documented data classification, no checked-in secrets, local-only execution, human review boundaries, and a STRIDE threat model. The Azure blueprint favours managed identity, private networking, least privilege, monitoring, and Purview governance patterns.

## Azure Architecture Explanation

Azure is represented as a target blueprint only. Bicep modules, parameter files, diagrams, ADRs, and mapping docs describe a plausible cloud architecture, but CI does not authenticate to Azure, run what-if, create resources, or deploy services.

## Power BI And Reporting Explanation

The reporting layer creates Power BI-ready local artifacts: dimensions, facts, bridge tables, relationships, KPI catalogue, DAX text, page specifications, wireframes, and executive Markdown reports. It does not create a `.pbix` file or deploy a Power BI/Fabric workspace.

## Likely Questions

**Is this deployed to production?**  
No. It is a local-first portfolio implementation with a blueprint-only Azure target architecture.

**Is the data real?**  
No. All data is synthetic and fictional.

**What is the strongest engineering signal?**  
The consistent evidence chain: deterministic data, validation, metrics, manifests, reports, tests, CI, documentation, and explicit limitations.

**How did you avoid leakage in outage prediction?**  
Labels use future unplanned outage windows after the observation timestamp, with chronological splitting and documented leakage controls.

**What would be next before a real deployment?**  
Cloud identity/RBAC design review, data protection impact assessment, network design, operational runbooks, real data contracts, model validation, Power BI workspace governance, and staged Azure deployment approvals.
