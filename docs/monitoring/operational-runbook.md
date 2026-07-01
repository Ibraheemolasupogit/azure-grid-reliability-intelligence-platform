# Operational Runbook

Run the full local monitoring demonstration:

```bash
make monitoring-demo
```

Run monitoring against existing local artifacts:

```bash
python3 -m grid_reliability.monitoring.pipeline --config configs/monitoring.yaml
```

Review `outputs/monitoring/monitoring_summary.csv`,
`outputs/monitoring/alerts.csv`, and the Markdown reports under
`reports/monitoring/<run_id>/`. Triggered alerts indicate human review only.
They do not create incidents, deliver notifications, retrain models, or perform
remediation.
