# Measure Catalogue

These DAX definitions reference the local CSV semantic model. Ratio measures use
`DIVIDE` or numerator/denominator recalculation and are not deployed.

| Measure | Format | Description |
| --- | --- | --- |
| System SAIFI | 0.000 | Recalculated interruptions divided by population denominator. |
| System SAIDI | 0.0 | Recalculated interruption minutes divided by population denominator. |
| System CAIDI | 0.0 | Recalculated minutes divided by customer interruptions. |
| Forecast MAE | #,##0.00 | Row-level absolute forecast error average. |
| Grounded Response Rate | 0.0% | Grounded assistant responses divided by all responses. |
