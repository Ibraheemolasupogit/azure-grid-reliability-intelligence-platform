"""Synthetic maintenance log generation."""

from __future__ import annotations

import random
from datetime import date, timedelta

from grid_reliability.data_generation.config import SyntheticDataConfig
from grid_reliability.data_generation.identifiers import stable_id
from grid_reliability.data_generation.models import Record
from grid_reliability.data_generation.time import iso_timestamp

TYPES = ("preventive", "corrective", "inspection", "emergency", "condition-based")
STATUSES = ("completed", "scheduled", "deferred", "cancelled", "in-progress")


def _selection_probability(asset: Record, config: SyntheticDataConfig) -> float:
    commissioned = date.fromisoformat(str(asset["commissioned_date"]))
    age_years = max(0.0, (config.start_timestamp.date() - commissioned).days / 365.25)
    probability = 0.28 + min(0.28, age_years / 100)
    if asset["criticality_tier"] == "tier_1":
        probability += 0.16
    if asset["operational_status"] == "maintenance":
        probability += 0.18
    if asset["asset_type"] in {"transformer", "circuit_breaker", "secondary_substation"}:
        probability += 0.08
    return min(0.9, probability)


def generate_maintenance_logs(
    config: SyntheticDataConfig, assets: list[Record], rng: random.Random
) -> list[Record]:
    records: list[Record] = []
    selected_assets = [asset for asset in assets if asset["asset_type"] != "smart_meter"]
    for index, asset in enumerate(selected_assets):
        if rng.random() > _selection_probability(asset, config):
            continue
        total_minutes = int((config.end_timestamp - config.start_timestamp).total_seconds() // 60)
        scheduled_start = config.start_timestamp + timedelta(
            minutes=rng.randint(0, max(1, total_minutes))
        )
        status = rng.choice(STATUSES)
        duration = rng.choice((30, 60, 90, 120, 240, 360))
        actual_start = (
            None
            if status in {"scheduled", "cancelled"}
            else scheduled_start + timedelta(minutes=rng.choice((-15, 0, 30, 90)))
        )
        completed_at = (
            actual_start + timedelta(minutes=duration)
            if status == "completed" and actual_start
            else None
        )
        maintenance_type = rng.choice(TYPES)
        records.append(
            {
                "maintenance_id": stable_id("MNT", asset["asset_id"], index, config.random_seed),
                "asset_id": asset["asset_id"],
                "maintenance_type": maintenance_type,
                "scheduled_start": iso_timestamp(scheduled_start),
                "actual_start": iso_timestamp(actual_start) if actual_start else "",
                "completed_at": iso_timestamp(completed_at) if completed_at else "",
                "maintenance_status": status,
                "priority": rng.choice(("low", "medium", "high", "urgent")),
                "work_category": rng.choice(("inspection", "repair", "replacement", "testing")),
                "fault_code": ""
                if maintenance_type in {"preventive", "inspection"}
                else rng.choice(("F_SYN_01", "F_SYN_02", "F_SYN_03")),
                "technician_team": rng.choice(("TEAM-A", "TEAM-B", "TEAM-C")),
                "downtime_minutes": 0 if status in {"scheduled", "cancelled"} else duration,
                "parts_replaced": rng.choice(("none", "relay", "seal-kit", "breaker-module")),
                "maintenance_cost_gbp": round(rng.uniform(120, 8500), 2),
                "follow_up_required": rng.random() < 0.18,
                "notes_code": rng.choice(("NOTE_SYN_OK", "NOTE_SYN_MONITOR", "NOTE_SYN_REVISIT")),
                "schema_version": config.schema_version,
            }
        )
    return records
