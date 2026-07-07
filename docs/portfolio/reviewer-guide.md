# Reviewer Guide

## Where To Start

1. Read [README.md](../../README.md).
2. Review [docs/milestones/roadmap.md](../milestones/roadmap.md).
3. Open [docs/portfolio/project-overview.md](project-overview.md).
4. Inspect [docs/portfolio/skills-mapping.md](skills-mapping.md) for evidence by skill area.

## What To Run

```bash
make quality
make verify-azure-blueprint
python3 scripts/verify_repository_polish.py
```

For a deterministic local demo path:

```bash
make generate-data-ci
make ingest-data-ci
make forecast-data-ci
make assess-asset-health-ci
make predict-outages-ci
make calculate-reliability-ci
make monitor-platform-ci
make run-assistant-ci
make build-reporting-model-ci
make verify-azure-blueprint
```

## What To Inspect

- Source modules under [src/grid_reliability](../../src/grid_reliability).
- Configuration under [configs](../../configs).
- Tests under [tests/unit](../../tests/unit).
- Architecture docs under [docs/architecture](../architecture/README.md).
- Azure blueprint docs under [docs/azure](../azure/README.md) and [infra](../../infra/README.md).
- Reporting specifications under [dashboard](../../dashboard/README.md).

## How To Understand Each Milestone

The milestone docs in [docs/milestones](../milestones) describe scope, implemented evidence, and explicit non-goals. The roadmap shows all 12 milestones as complete.

## What Not To Expect

- No real grid or customer data.
- No Azure login, deployment, resource creation, or what-if execution in CI.
- No deployed Power BI or Fabric workspace.
- No live operational alerting, crew dispatch, equipment control, or external model calls.
- No claim that synthetic model outputs are calibrated for live operations.

## Verify Cloud Deployment Is Not Claimed

Check [infra/README.md](../../infra/README.md), [docs/azure/reference-architecture.md](../azure/reference-architecture.md), [docs/reporting/power-bi-deployment-mapping.md](../reporting/power-bi-deployment-mapping.md), and [.github/workflows/iac.yml](../../.github/workflows/iac.yml). They describe a blueprint-only posture and CI avoids Azure authentication and deployment commands.
