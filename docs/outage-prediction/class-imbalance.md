# Class Imbalance

Unplanned outage labels are rare in the synthetic profile.

Milestone 6 handles class imbalance through:

- positive class weighting in deterministic logistic regression;
- prevalence reporting for overall, train, validation, and test splits;
- rare-event metrics such as precision, recall, F1, balanced accuracy, ROC AUC, PR AUC, Brier score, and log loss;
- threshold reporting without temporal oversampling.

The implementation does not randomly oversample across time because that would weaken the chronological evaluation design.
