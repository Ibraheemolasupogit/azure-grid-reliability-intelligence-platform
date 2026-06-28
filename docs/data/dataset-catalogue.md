# Dataset Catalogue

| Dataset | Format | Description | Key |
| --- | --- | --- | --- |
| `smart_meter_events.jsonl` | JSON Lines | Fictional smart meter interval readings | `event_id` |
| `substation_events.jsonl` | JSON Lines | Fictional substation and feeder telemetry | `event_id` |
| `weather_data.csv` | CSV | Fictional regional weather observations | `weather_timestamp`, `grid_region` |
| `asset_inventory.csv` | CSV | Fictional grid asset inventory | `asset_id` |
| `maintenance_logs.csv` | CSV | Fictional maintenance events | `maintenance_id` |
| `outage_history.csv` | CSV | Fictional outage incidents | `outage_id` |

Full runtime datasets are generated under `data/raw/` and ignored by Git. Small deterministic fixtures are committed under `tests/fixtures/synthetic_data/`.

Field definitions, units, allowed categorical values, keys, and quality expectations are machine-readable in `configs/data_contracts/`.

