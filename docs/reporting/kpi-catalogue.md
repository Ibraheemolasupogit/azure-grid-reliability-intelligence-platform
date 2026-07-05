# KPI Catalogue

The reporting pipeline writes `kpi_catalogue.csv` with business definitions,
technical definitions, source columns, aggregation methods, units, format
strings, directionality, audience, and limitations.

Ratio KPIs such as SAIFI, SAIDI, CAIDI, WAPE, and grounded-response rate must be
recalculated from numerator and denominator fields in the selected context. They
must not be averaged across lower-level entities. Additive counts such as
unplanned outages and alert counts can be summed when hierarchy levels are not
mixed.
