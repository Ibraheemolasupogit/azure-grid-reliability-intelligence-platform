# Project Overview

The Grid Reliability Intelligence Platform is a local-first portfolio project for energy and critical infrastructure analytics. It demonstrates how synthetic smart meter, substation, weather, asset, maintenance, and outage data can be turned into governed evidence for decision support.

The project matters because grid reliability work depends on many imperfect signals. A useful platform must show where data came from, how it was validated, how models were trained, what evidence supports each output, and where human review remains required.

Target users include data engineers, analytics engineers, ML engineers, reliability analysts, asset managers, operations leaders, security reviewers, and Azure solution architects.

The critical-infrastructure context is intentionally cautious. Outputs support review and prioritisation, but they do not control grid equipment, dispatch crews, suppress alerts, certify regulatory reporting, or replace operator judgement.

The local implementation covers synthetic data generation, governed ingestion, validated interim data, demand forecasting, asset-health scoring, outage-risk classification, reliability KPIs, monitoring, grounded assistant responses, and Power BI-ready semantic outputs.

The Azure mapping is a blueprint only. Documentation and Bicep templates describe how the local patterns could map to Event Hubs, ADLS Gen2, Azure Data Explorer, Azure Machine Learning, Azure AI Foundry, Azure AI Search, Azure Monitor, Microsoft Purview, Power BI, and Microsoft Fabric. No Azure resources are deployed.

## Major Capabilities

- Synthetic source data with deterministic CI profiles.
- Manifest, checksum, contract, relationship, and quality validation.
- Validated interim data used as the governed analytical boundary.
- Short-term demand forecasting with local model metadata and reports.
- Transparent asset-health scoring with component evidence and reason codes.
- Leakage-safe outage-risk prediction over synthetic future labels.
- Reliability KPI analytics with documented denominator assumptions.
- Local monitoring for pipeline health, data health, model health, drift, and alerts.
- Retrieval-grounded assistant responses over repository-local evidence.
- Power BI-ready dimensions, facts, bridge tables, DAX text, KPI catalogue, and page specifications.
- Blueprint-only Azure architecture, security controls, threat model, ADRs, and IaC validation.
