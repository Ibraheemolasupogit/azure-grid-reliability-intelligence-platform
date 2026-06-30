# Evaluation and Thresholds

Models are evaluated on chronological splits. Rows are never shuffled.

Implemented baselines:

- constant prevalence baseline;
- recent-outage heuristic;
- operational-warning heuristic.

Implemented candidate model:

- deterministic logistic regression with fixed iteration count, L2 penalty, standardisation based on training rows, and positive class weighting.

Model selection uses validation metrics only. If validation data is too small for the configured metric, the prevalence baseline can remain selected. The test split is preserved for final evaluation and does not tune the threshold.

The CI profile uses raw risk scores because the validation slice is too small for reliable calibration. Reports explicitly state this limitation.
