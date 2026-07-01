# Data Health

Data-health checks cover freshness, volume, and ingestion quality trends for
`smart_meter_events`, `substation_events`, `weather_data`, `asset_inventory`,
`maintenance_logs`, and `outage_history`.

Freshness uses event timestamps when present and a configured monitoring
timestamp. Volume compares observed record counts with configured minimum and
maximum ranges and, when configured, baseline counts. Quality trends consume
ingestion metrics and preserve warning/error distinctions.
