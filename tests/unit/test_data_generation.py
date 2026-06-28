from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grid_reliability.common import ConfigurationError
from grid_reliability.data_generation.config import load_generation_config
from grid_reliability.data_generation.contracts import load_contracts
from grid_reliability.data_generation.network import build_network
from grid_reliability.data_generation.pipeline import (
    CSV_FIELDS,
    build_dataset_bundle,
    generate_datasets,
    main,
)
from grid_reliability.data_generation.writers import sha256_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ci_config():
    return load_generation_config("configs/synthetic_data_ci.yaml", project_root=PROJECT_ROOT)


def test_valid_generation_config_loads(ci_config) -> None:
    assert ci_config.random_seed == 20260201
    assert ci_config.number_of_regions == 2
    assert ci_config.start_timestamp < ci_config.end_timestamp
    assert ci_config.output_root == Path("data/raw")


def test_invalid_time_range_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
random_seed: 1
start_timestamp: "2026-01-02T00:00:00"
end_timestamp: "2026-01-01T00:00:00"
timezone: Europe/London
meter_interval_minutes: 60
substation_interval_minutes: 60
number_of_regions: 1
substations_per_region: 1
feeders_per_substation: 1
meters_per_feeder: 1
weather_interval_minutes: 60
target_anomaly_rate: 0.1
target_missing_reading_rate: 0.1
output_root: data/raw
schema_version: "2.0.0"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="start_timestamp must be before"):
        load_generation_config(config_path)


def test_invalid_interval_rate_and_entity_count_raise(tmp_path: Path) -> None:
    base = (PROJECT_ROOT / "configs/synthetic_data_ci.yaml").read_text(encoding="utf-8")

    interval_path = tmp_path / "bad_interval.yaml"
    interval_path.write_text(
        base.replace("meter_interval_minutes: 60", "meter_interval_minutes: 7"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="meter_interval_minutes"):
        load_generation_config(interval_path)

    rate_path = tmp_path / "bad_rate.yaml"
    rate_path.write_text(
        base.replace("target_anomaly_rate: 0.08", "target_anomaly_rate: 1.5"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="target_anomaly_rate"):
        load_generation_config(rate_path)

    count_path = tmp_path / "bad_count.yaml"
    count_path.write_text(
        base.replace("meters_per_feeder: 3", "meters_per_feeder: 0"), encoding="utf-8"
    )
    with pytest.raises(ConfigurationError, match="meters_per_feeder"):
        load_generation_config(count_path)


def test_network_topology_has_unique_stable_ids(ci_config) -> None:
    import random

    first = build_network(ci_config, random.Random(ci_config.random_seed))
    second = build_network(ci_config, random.Random(ci_config.random_seed))

    assert first == second
    assert len({region.region_id for region in first.regions}) == len(first.regions)
    assert len({sub.substation_id for sub in first.substations}) == len(first.substations)
    assert len({feeder.feeder_id for feeder in first.feeders}) == len(first.feeders)
    assert len({meter.meter_id for meter in first.meters}) == len(first.meters)
    assert {meter.feeder_id for meter in first.meters} <= {
        feeder.feeder_id for feeder in first.feeders
    }


def test_generated_datasets_have_schema_and_integrity(ci_config) -> None:
    bundle = build_dataset_bundle(ci_config)
    assets = bundle.asset_inventory
    feeders = {row["feeder_id"] for row in assets if row["feeder_id"]}
    substations = {row["substation_id"] for row in assets}
    asset_ids = {row["asset_id"] for row in assets}
    regions = {row["grid_region"] for row in bundle.weather_data}

    assert bundle.smart_meter_events
    assert bundle.substation_events
    assert bundle.weather_data
    assert assets
    assert bundle.maintenance_logs
    assert bundle.outage_history

    smart_event = bundle.smart_meter_events[0]
    smart_contract = load_contracts(PROJECT_ROOT / "configs/data_contracts")["smart_meter_events"]
    expected_smart_fields = {field["name"] for field in smart_contract["fields"]}
    assert expected_smart_fields == set(smart_event)
    assert smart_event["schema_version"] == ci_config.schema_version
    assert smart_event["customer_segment"] in {
        "residential",
        "commercial",
        "industrial",
        "public-service",
    }
    assert 180 <= smart_event["voltage_v"] <= 260
    assert smart_event["feeder_id"] in feeders
    assert smart_event["substation_id"] in substations
    datetime.fromisoformat(smart_event["event_timestamp"])

    assert {row["grid_region"] for row in bundle.substation_events} <= regions
    assert {row["asset_id"] for row in bundle.maintenance_logs} <= asset_ids
    assert {row["primary_asset_id"] for row in bundle.outage_history} <= asset_ids
    assert {row["feeder_id"] for row in bundle.outage_history} <= feeders

    for outage in bundle.outage_history:
        start = datetime.fromisoformat(outage["outage_start"])
        restored = datetime.fromisoformat(outage["restoration_time"])
        assert restored - start == timedelta(minutes=int(outage["duration_minutes"]))


def test_deterministic_seed_handling(ci_config) -> None:
    first = build_dataset_bundle(ci_config)
    second = build_dataset_bundle(ci_config)
    different = build_dataset_bundle(replace(ci_config, random_seed=ci_config.random_seed + 1))

    assert first.smart_meter_events == second.smart_meter_events
    assert first.asset_inventory == second.asset_inventory
    assert first.smart_meter_events != different.smart_meter_events


def test_contracts_load() -> None:
    contracts = load_contracts(PROJECT_ROOT / "configs/data_contracts")

    assert set(contracts) == {
        "asset_inventory",
        "maintenance_logs",
        "outage_history",
        "smart_meter_events",
        "substation_events",
        "weather_data",
    }
    assert contracts["outage_history"]["classification"] == "synthetic"


def test_writers_manifest_and_file_formats(tmp_path: Path, ci_config) -> None:
    config = replace(ci_config, output_root=Path("generated/raw"))
    result = generate_datasets(config, project_root=tmp_path)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert (
        manifest["synthetic_data_statement"]
        == "All generated records are fictional synthetic data."
    )
    assert set(manifest["datasets"]) == {
        "asset_inventory",
        "maintenance_logs",
        "outage_history",
        "smart_meter_events",
        "substation_events",
        "weather_data",
    }

    for dataset_name, dataset in result.datasets.items():
        assert dataset.path.exists()
        assert manifest["datasets"][dataset_name]["record_count"] == dataset.record_count
        assert manifest["datasets"][dataset_name]["sha256"] == sha256_file(dataset.path)

    with result.datasets["smart_meter_events"].path.open("r", encoding="utf-8") as jsonl_file:
        assert all(json.loads(line)["event_id"] for line in jsonl_file)

    with result.datasets["weather_data"].path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames == CSV_FIELDS["weather_data"]


def test_cli_succeeds_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_root = "data/raw"
    exit_code = main(
        [
            "--config",
            str(PROJECT_ROOT / "configs/synthetic_data_ci.yaml"),
            "--output-root",
            output_root,
            "--seed",
            "123",
            "--profile",
            "test",
        ]
    )

    assert exit_code == 0
    assert "Synthetic data generated" in capsys.readouterr().out

    with pytest.raises(SystemExit):
        main(["--config", str(tmp_path / "missing.yaml")])
