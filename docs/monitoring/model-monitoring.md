# Model Monitoring

Forecast monitoring consumes forecast metrics and checks MAE, WAPE, and bias
against configured thresholds.

Outage-prediction monitoring consumes classification metrics and checks
precision, recall, Brier score, positive-example availability, and null metrics.
The pipeline does not retrain, retune thresholds, deploy endpoints, or replace
models.
