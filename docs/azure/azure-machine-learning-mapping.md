# Azure Machine Learning Mapping

Forecasting and outage-risk pipelines map to Azure ML jobs, environments, data
assets, MLflow tracking, model registry patterns, batch endpoint architecture,
and monitoring. The blueprint includes a workspace, Key Vault, Application
Insights dependency, storage dependency, and a low-minimum AML compute cluster.

No model is registered, no endpoint is deployed, and no workspace is contacted.
Training and inference identities should remain separate in future deployment.
