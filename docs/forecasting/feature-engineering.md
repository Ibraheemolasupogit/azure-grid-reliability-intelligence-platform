# Forecasting Feature Engineering

Features are built only from values available at the forecast origin.

Implemented feature families:

- calendar: hour, day of week, weekend flag, month, day of year, cyclical hour, cyclical weekday;
- autoregressive: latest observed target and configured lag intervals;
- rolling: mean, standard deviation, minimum, and maximum over windows ending at the forecast origin;
- weather: observed temperature, humidity, wind speed, precipitation, and severe-weather flag at the forecast origin;
- context: contributing record count, coverage ratio, and imputation indicator.

Weather features are an evaluation simplification: local runs assume observed weather at the forecast origin is available. A production forecast would require weather forecasts.

Missing interval policies are `drop`, `fail`, and `forward_fill_with_limit`. Forward-filled points retain an imputation indicator. The default configuration does not treat absent data as measured zero.
