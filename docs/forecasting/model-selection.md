# Forecast Model Selection

Every run evaluates the persistence baseline. Optional baselines and candidates include moving average, seasonal naive where the seasonal lag is supported, and a deterministic autoregressive linear model.

The selected model is the eligible model with the best configured validation metric. Ties are broken deterministically by model name. Failed or unsupported model attempts are recorded rather than silently ignored.

If a baseline performs best, the baseline is selected. Milestone 4 does not manipulate metrics to prefer the more complex model.

The current implementation uses transparent standard-library code for the autoregressive linear model to keep dependency impact small and CI fast.
