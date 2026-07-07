# Limitations And Assumptions

## Data

- All datasets are synthetic.
- No real grid, customer, address, coordinate, asset, outage, maintenance, or operational data is included.
- Synthetic records are useful for engineering demonstration, not operational calibration.

## Analytics

- Forecasting and outage-risk outputs are local deterministic demonstrations.
- Asset-health scores are transparent condition indicators, not asset-failure probability models.
- Reliability KPIs use documented observed-meter denominators and are not certified regulatory submissions.
- Monitoring alerts are local review artifacts only.

## Assistant

- The assistant is retrieval-grounded over approved repository-local evidence.
- Responses are deterministic and citation-oriented.
- It cannot execute operations, dispatch crews, suppress alerts, call external APIs, or call Azure-hosted models.

## Azure

- Azure architecture is a blueprint only.
- Bicep templates and parameter files are for review and future planning.
- No Azure resources, identities, networking, data services, model endpoints, dashboards, or monitoring workspaces are deployed.

## Reporting

- Reporting outputs are Power BI-ready local files and design specifications.
- No `.pbix`, `.pbit`, Power BI workspace, Fabric workspace, gateway, scheduled refresh, app, or REST API call is created.

## Review Assumptions

- Reviewers can run the CI-sized local workflow on a Python 3.11 environment.
- Generated runtime artifacts should be cleaned before committing.
- Any real-world deployment would require security, privacy, operational, model-risk, and cloud-governance review.
