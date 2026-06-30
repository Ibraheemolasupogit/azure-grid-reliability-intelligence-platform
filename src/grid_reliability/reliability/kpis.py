"""Reliability KPI formulas and helper calculations."""

from __future__ import annotations

from datetime import datetime
from statistics import median

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.models import ClassifiedOutage


def reliability_kpis(
    outages: list[ClassifiedOutage],
    population: int,
    period_minutes: float,
    config: ReliabilityConfig,
) -> dict[str, float | int | None]:
    sustained = [
        outage
        for outage in outages
        if outage.duration_minutes >= config.sustained_interruption_threshold_minutes
    ]
    customer_interruptions = sum(outage.customers_interrupted for outage in sustained)
    customer_minutes = sum(
        outage.customers_interrupted * outage.duration_minutes for outage in sustained
    )
    durations = [float(outage.duration_minutes) for outage in sustained]
    outage_count = len(outages)
    mean_duration = sum(durations) / len(durations) if durations else None
    merged_minutes, overlap_count = merged_outage_minutes(sustained)
    asai_denominator = population * period_minutes
    availability_minutes = min(customer_minutes, population * merged_minutes)
    saifi = customer_interruptions / population if population > 0 else None
    saidi = customer_minutes / population if population > 0 else None
    caidi = customer_minutes / customer_interruptions if customer_interruptions else None
    asai = (
        max(0.0, min(1.0, 1 - availability_minutes / asai_denominator))
        if asai_denominator > 0
        else None
    )
    within_target = [
        outage
        for outage in sustained
        if outage.duration_minutes <= config.restoration_target_minutes
    ]
    return {
        "outage_count": outage_count,
        "planned_outage_count": sum(1 for outage in outages if outage.outage_type == "planned"),
        "unplanned_outage_count": sum(1 for outage in outages if outage.outage_type == "unplanned"),
        "severe_weather_outage_count": sum(
            1 for outage in outages if outage.severe_weather_related
        ),
        "equipment_failure_outage_count": sum(1 for outage in outages if outage.equipment_related),
        "customer_interruptions": customer_interruptions,
        "customer_interruption_minutes": float(customer_minutes),
        "total_outage_duration_minutes": float(sum(durations)),
        "mean_outage_duration_minutes": mean_duration,
        "median_outage_duration_minutes": float(median(durations)) if durations else None,
        "maximum_outage_duration_minutes": max(durations) if durations else None,
        "estimated_load_lost_mw_total": sum(outage.estimated_load_lost_mw for outage in outages),
        "restoration_within_target_rate": len(within_target) / len(sustained)
        if sustained
        else None,
        "merged_outage_minutes": merged_minutes,
        "overlap_count": overlap_count,
        "saifi": saifi,
        "saidi_minutes": saidi,
        "caidi_minutes": caidi,
        "asai": asai,
        "asui": 1 - asai if asai is not None else None,
        "ctaidi_minutes": None,
        "caifi": None,
    }


def merged_outage_minutes(outages: list[ClassifiedOutage]) -> tuple[float, int]:
    windows = sorted((outage.outage_start, outage.restoration_time) for outage in outages)
    if not windows:
        return 0.0, 0
    merged: list[tuple[datetime, datetime]] = []
    overlaps = 0
    for start, end in windows:
        if not merged or start >= merged[-1][1]:
            merged.append((start, end))
            continue
        overlaps += 1
        if end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end)
    minutes = sum((end - start).total_seconds() / 60 for start, end in merged)
    return minutes, overlaps
