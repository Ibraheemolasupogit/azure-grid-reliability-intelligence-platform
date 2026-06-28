"""Synthetic data generation pipeline and CLI."""

from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.metadata import __version__
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.assets import generate_assets
from grid_reliability.data_generation.config import SyntheticDataConfig, load_generation_config
from grid_reliability.data_generation.maintenance import generate_maintenance_logs
from grid_reliability.data_generation.meters import generate_smart_meter_events
from grid_reliability.data_generation.models import DatasetBundle, GenerationResult
from grid_reliability.data_generation.network import build_network
from grid_reliability.data_generation.outages import generate_outage_history
from grid_reliability.data_generation.substations import generate_substation_events
from grid_reliability.data_generation.weather import generate_weather
from grid_reliability.data_generation.writers import write_csv, write_jsonl, write_manifest

JSONL_DATASETS = {
    "smart_meter_events": "smart_meter_events.jsonl",
    "substation_events": "substation_events.jsonl",
}

CSV_FIELDS = {
    "weather_data": [
        "weather_timestamp",
        "grid_region",
        "temperature_c",
        "feels_like_c",
        "humidity_pct",
        "wind_speed_mps",
        "wind_gust_mps",
        "precipitation_mm",
        "pressure_hpa",
        "weather_condition",
        "severe_weather_flag",
        "data_source",
        "schema_version",
    ],
    "asset_inventory": [
        "asset_id",
        "asset_type",
        "asset_name",
        "grid_region",
        "substation_id",
        "feeder_id",
        "manufacturer",
        "model",
        "commissioned_date",
        "expected_life_years",
        "rated_capacity",
        "capacity_unit",
        "criticality_tier",
        "operational_status",
        "last_inspection_date",
        "next_inspection_due",
        "synthetic_location_code",
        "schema_version",
    ],
    "maintenance_logs": [
        "maintenance_id",
        "asset_id",
        "maintenance_type",
        "scheduled_start",
        "actual_start",
        "completed_at",
        "maintenance_status",
        "priority",
        "work_category",
        "fault_code",
        "technician_team",
        "downtime_minutes",
        "parts_replaced",
        "maintenance_cost_gbp",
        "follow_up_required",
        "notes_code",
        "schema_version",
    ],
    "outage_history": [
        "outage_id",
        "outage_start",
        "restoration_time",
        "duration_minutes",
        "grid_region",
        "substation_id",
        "feeder_id",
        "primary_asset_id",
        "outage_type",
        "cause_category",
        "customers_interrupted",
        "estimated_load_lost_mw",
        "planned_flag",
        "severe_weather_related",
        "protection_operated",
        "restoration_method",
        "incident_severity",
        "data_quality_flag",
        "schema_version",
    ],
}

CSV_DATASETS = {
    "weather_data": "weather_data.csv",
    "asset_inventory": "asset_inventory.csv",
    "maintenance_logs": "maintenance_logs.csv",
    "outage_history": "outage_history.csv",
}


def build_dataset_bundle(config: SyntheticDataConfig) -> DatasetBundle:
    rng = random.Random(config.random_seed)
    network = build_network(config, rng)
    weather = generate_weather(config, network, rng)
    assets = generate_assets(config, network, rng)
    return DatasetBundle(
        smart_meter_events=generate_smart_meter_events(config, network, rng),
        substation_events=generate_substation_events(config, network, rng),
        weather_data=weather,
        asset_inventory=assets,
        maintenance_logs=generate_maintenance_logs(config, assets, rng),
        outage_history=generate_outage_history(config, network, assets, rng),
    )


def generate_datasets(
    config: SyntheticDataConfig,
    *,
    project_root: Path | None = None,
    project_name: str = "azure-grid-reliability-intelligence-platform",
) -> GenerationResult:
    root = (project_root or resolve_project_root()).resolve()
    output_root = root / config.output_root
    bundle = build_dataset_bundle(config)
    datasets = {
        "smart_meter_events": write_jsonl(
            output_root / JSONL_DATASETS["smart_meter_events"], bundle.smart_meter_events
        ),
        "substation_events": write_jsonl(
            output_root / JSONL_DATASETS["substation_events"], bundle.substation_events
        ),
        "weather_data": write_csv(
            output_root / CSV_DATASETS["weather_data"],
            bundle.weather_data,
            CSV_FIELDS["weather_data"],
        ),
        "asset_inventory": write_csv(
            output_root / CSV_DATASETS["asset_inventory"],
            bundle.asset_inventory,
            CSV_FIELDS["asset_inventory"],
        ),
        "maintenance_logs": write_csv(
            output_root / CSV_DATASETS["maintenance_logs"],
            bundle.maintenance_logs,
            CSV_FIELDS["maintenance_logs"],
        ),
        "outage_history": write_csv(
            output_root / CSV_DATASETS["outage_history"],
            bundle.outage_history,
            CSV_FIELDS["outage_history"],
        ),
    }
    generated_at = datetime.now(tz=ZoneInfo(config.timezone))
    manifest = write_manifest(
        output_root / "_manifest.json",
        config=config,
        project_name=project_name,
        generator_version=__version__,
        generated_at=generated_at,
        datasets=datasets,
    )
    return GenerationResult(
        output_root, datasets, output_root / "_manifest.json", manifest, generated_at
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate fictional synthetic grid reliability data."
    )
    parser.add_argument("--config", default="configs/synthetic_data.yaml")
    parser.add_argument("--output-root")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--profile")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = resolve_project_root()
    try:
        settings = load_settings(project_root=project_root)
        config = load_generation_config(
            args.config,
            project_root=project_root,
            output_root=args.output_root,
            seed=args.seed,
            start=args.start,
            end=args.end,
            profile=args.profile,
        )
        result = generate_datasets(
            config, project_root=project_root, project_name=settings.project_name
        )
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2

    print(f"Synthetic data generated in {result.output_root}")
    for name, dataset in sorted(result.datasets.items()):
        print(f"- {name}: {dataset.record_count} records -> {dataset.filename}")
    print(f"- manifest: {result.manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
