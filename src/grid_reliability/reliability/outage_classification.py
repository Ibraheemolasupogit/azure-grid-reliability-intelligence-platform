"""Outage filtering and classification."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.data import parse_timestamp
from grid_reliability.reliability.models import ClassifiedOutage, ReliabilityError


def classify_outages(
    rows: list[dict[str, Any]],
    config: ReliabilityConfig,
) -> tuple[list[ClassifiedOutage], int]:
    classified: list[ClassifiedOutage] = []
    excluded = 0
    for row in rows:
        outage_type = str(row["outage_type"])
        if outage_type == "planned" and not config.include_planned_outages:
            excluded += 1
            continue
        if outage_type == "unplanned" and not config.include_unplanned_outages:
            excluded += 1
            continue
        start = parse_timestamp(str(row["outage_start"]))
        restoration = parse_timestamp(str(row["restoration_time"]))
        duration = int(row["duration_minutes"])
        if restoration < start or duration < 0:
            raise ReliabilityError(f"Invalid outage duration for {row['outage_id']}.")
        expected_restoration = start + timedelta(minutes=duration)
        if expected_restoration != restoration:
            raise ReliabilityError(f"Outage duration mismatch for {row['outage_id']}.")
        if (
            duration < config.minimum_outage_duration_minutes
            or duration > config.maximum_outage_duration_minutes
        ):
            excluded += 1
            continue
        classified.append(
            ClassifiedOutage(
                outage_id=str(row["outage_id"]),
                outage_start=start,
                restoration_time=restoration,
                duration_minutes=duration,
                grid_region=str(row["grid_region"]),
                substation_id=str(row["substation_id"]),
                feeder_id=str(row["feeder_id"]),
                primary_asset_id=str(row["primary_asset_id"]),
                outage_type=outage_type,
                cause_category=str(row["cause_category"]),
                customers_interrupted=int(row["customers_interrupted"]),
                estimated_load_lost_mw=float(row["estimated_load_lost_mw"]),
                planned_flag=bool(row["planned_flag"]),
                severe_weather_related=bool(row["severe_weather_related"]),
                equipment_related=str(row["cause_category"]) == "equipment_failure",
                duration_class=_duration_class(duration, config),
                assessment_period_start=config.assessment_start,
                assessment_period_end=config.assessment_end,
            )
        )
    return sorted(classified, key=lambda item: (item.outage_start, item.outage_id)), excluded


def _duration_class(duration: int, config: ReliabilityConfig) -> str:
    if duration < config.sustained_interruption_threshold_minutes:
        return "MOMENTARY_OR_SHORT"
    if duration >= config.restoration_target_minutes:
        return "PROLONGED"
    return "SUSTAINED"
