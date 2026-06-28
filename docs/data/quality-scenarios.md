# Controlled Quality Scenarios

Milestone 2 injects small, reproducible quality scenarios to support future validation work.

Implemented scenarios:

- absent smart-meter interval records to represent missing readings;
- delayed `ingested_at` timestamps;
- `ESTIMATED` quality codes;
- unusual but plausible voltage and load readings;
- high substation utilisation and temperature warning alarms;
- missing optional maintenance timestamps for scheduled or cancelled work;
- outage incidents with `unknown` cause categories;
- duplicate-like business situations without duplicate primary keys.

These scenarios are controlled by `target_anomaly_rate` and `target_missing_reading_rate`. They are deliberate synthetic data properties, not accidental generator defects.

The generator preserves unique primary keys and required foreign keys.

