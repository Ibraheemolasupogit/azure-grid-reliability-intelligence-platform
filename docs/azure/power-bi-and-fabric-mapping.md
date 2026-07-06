# Power BI And Fabric Mapping

Milestone 10 dimensions, facts, bridges, KPI catalogue, and DAX definitions map
to a Power BI semantic model or Fabric Lakehouse/Warehouse model.

Recommended pattern: Import mode for smaller governed reporting exports,
DirectQuery only for curated enterprise-scale serving layers. Incremental
refresh should follow source run and date keys. RLS can use synthetic grid region
or operational role mappings after identity integration.

No `.pbix`, workspace, semantic model, deployment pipeline, gateway, REST API
call, workspace ID, tenant configuration, or Fabric capacity is created.
