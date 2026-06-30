# Reliability Analytics Design

Milestone 7 calculates historical distribution-reliability analytics from validated interim data only. It reads `data/interim/outage_history.jsonl`, `asset_inventory.jsonl`, and supporting smart-meter evidence. It does not read raw data, outage-prediction outputs, dashboards, live systems, or Azure resources.

The implemented workflow is:

1. load validated interim data;
2. derive observed-meter population denominators;
3. classify planned and unplanned outages;
4. aggregate outages by period and entity;
5. calculate SAIFI, SAIDI, CAIDI, ASAI, ASUI, and operational event measures;
6. create trends and internal synthetic peer benchmarks;
7. calculate composite reliability scores;
8. assign reliability bands and reason codes;
9. write Power BI-ready CSV outputs, metrics, manifest, and Markdown reports.

Supported aggregation levels are `grid_region`, `substation`, and `feeder`. Higher-level KPIs are recalculated from numerator and denominator components; lower-level SAIDI or SAIFI values are not averaged.
