# Fact And Dimension Catalogue

## Dimensions

- `dim_date`: calendar attributes for reporting dates.
- `dim_time`: hourly time members and dayparts.
- `dim_grid_region`: synthetic grid regions.
- `dim_substation`: substation hierarchy members.
- `dim_feeder`: feeder hierarchy members.
- `dim_asset`: governed synthetic asset inventory.
- `dim_model`: forecasting and outage-risk model identities.
- `dim_component_run`: source component run lineage.
- `dim_alert_reason`: alert and analytical reason codes.
- `dim_metric`: monitoring metric definitions.

## Facts

- `fact_demand_forecast`: forecast row grain by entity, timestamp, and model.
- `fact_asset_health`: one row per asset assessment.
- `fact_outage_risk`: one row per entity, observation timestamp, and model.
- `fact_reliability_kpi`: one row per entity and reporting period.
- `fact_monitoring_check`: one row per monitoring check.
- `fact_monitoring_alert`: one row per local alert record.
- `fact_assistant_response`: one row per assistant query response.
- `fact_maintenance_priority`: one row per asset review priority.

Bridge tables are limited to many-to-many reason and citation relationships.
