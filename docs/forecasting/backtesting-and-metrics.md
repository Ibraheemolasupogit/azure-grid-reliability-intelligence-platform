# Backtesting And Metrics

Milestone 4 uses chronological splits. Rows are sorted by forecast timestamp and divided into training, validation, and test periods without shuffling.

Model selection uses validation metrics. Test metrics are preserved for final evaluation.

Rolling-origin backtesting uses an expanding-window pattern over configured forecast origins:

1. train on rows available up to the cutoff;
2. forecast the next configured horizon from that cutoff;
3. advance to the next cutoff.

Metrics:

- MAE;
- RMSE;
- MAPE, omitted where all actuals are zero;
- sMAPE;
- WAPE, omitted where the sum of actuals is zero;
- bias / mean forecast error;
- empirical interval coverage.

Metrics are emitted by model, entity, horizon, aggregation level, and split. Weighted overall summaries are used for model selection.
