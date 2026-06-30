# KPI Definitions

`SAIFI = total customer interruptions / population denominator`

Unit: interruptions per customer.

`SAIDI = sum(customers_interrupted * outage_duration_minutes) / population denominator`

Unit: minutes per customer.

`CAIDI = customer interruption minutes / customer interruptions`

Unit: minutes per interruption. When customer interruptions are zero, CAIDI is `null`.

`ASAI = 1 - availability interruption minutes / customer service minutes demanded`

`ASUI = 1 - ASAI`

ASAI is bounded between zero and one. Customer service minutes demanded are `population_denominator * assessment_period_minutes`.

CTAIDI and CAIFI are not calculated because the synthetic outage records do not identify distinct interrupted customers. The outputs retain these fields as `null` and document the reason.
