# Milestone 6: Outage Prediction

Milestone 6 adds local unplanned-outage risk prediction over validated interim synthetic data.

Run the default profile after generation and ingestion:

```bash
python3 -m grid_reliability.outage_prediction.pipeline --config configs/outage_prediction.yaml
```

Run the CI profile end to end:

```bash
python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml
python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml
python3 -m grid_reliability.outage_prediction.pipeline --config configs/outage_prediction_ci.yaml
```

Implemented scope:

- validated interim-only loading;
- feeder, substation, and primary-asset entity semantics;
- leakage-safe future unplanned-outage labels;
- historical operational, weather, smart-meter, asset, maintenance, and prior-outage features;
- chronological train/validation/test splitting with horizon purge;
- prevalence, recent-outage, and operational-warning baselines;
- deterministic logistic regression with positive class weighting;
- rare-event metrics, raw-score calibration metadata, model selection, risk bands, reason codes, manifests, metadata, and reports.

Out of scope:

- reliability KPIs;
- asset-failure probability models separate from outage risk;
- anomaly detection;
- automated response or restoration optimisation;
- GenAI;
- dashboards;
- Azure authentication, SDK resource creation, endpoints, Terraform, Bicep, or Spark.
