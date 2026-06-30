"""Entity and period aggregation for reliability analytics."""

from __future__ import annotations

from datetime import datetime, timedelta

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.kpis import reliability_kpis
from grid_reliability.reliability.models import (
    AggregationLevel,
    ClassifiedOutage,
    PopulationRecord,
    ReliabilityResult,
)
from grid_reliability.reliability.scoring import reliability_score


def calculate_results(
    populations: list[PopulationRecord],
    outages: list[ClassifiedOutage],
    config: ReliabilityConfig,
    run_id: str,
) -> list[ReliabilityResult]:
    periods = assessment_periods(config)
    results: list[ReliabilityResult] = []
    for period_start, period_end in periods:
        period_minutes = (period_end - period_start).total_seconds() / 60
        period_outages = [
            outage for outage in outages if period_start <= outage.outage_start < period_end
        ]
        for population in populations:
            entity_outages = [outage for outage in period_outages if _matches(population, outage)]
            kpis = reliability_kpis(
                entity_outages,
                population.estimated_customer_population,
                period_minutes,
                config,
            )
            score, components, contributions, band, reasons = reliability_score(
                kpis,
                population,
                config,
                entity_outages,
            )
            results.append(
                ReliabilityResult(
                    run_id=run_id,
                    assessment_start=config.assessment_start,
                    assessment_end=config.assessment_end,
                    period_start=period_start,
                    period_end=period_end,
                    period_frequency=config.period_frequency.value,
                    entity=population.entity,
                    population_denominator=population.estimated_customer_population,
                    population_method=population.population_method,
                    outage_count=int(kpis["outage_count"] or 0),
                    planned_outage_count=int(kpis["planned_outage_count"] or 0),
                    unplanned_outage_count=int(kpis["unplanned_outage_count"] or 0),
                    severe_weather_outage_count=int(kpis["severe_weather_outage_count"] or 0),
                    equipment_failure_outage_count=int(kpis["equipment_failure_outage_count"] or 0),
                    customer_interruptions=int(kpis["customer_interruptions"] or 0),
                    customer_interruption_minutes=float(kpis["customer_interruption_minutes"] or 0),
                    total_outage_duration_minutes=float(kpis["total_outage_duration_minutes"] or 0),
                    mean_outage_duration_minutes=_float_or_none(
                        kpis["mean_outage_duration_minutes"]
                    ),
                    median_outage_duration_minutes=_float_or_none(
                        kpis["median_outage_duration_minutes"]
                    ),
                    maximum_outage_duration_minutes=_float_or_none(
                        kpis["maximum_outage_duration_minutes"]
                    ),
                    estimated_load_lost_mw_total=float(kpis["estimated_load_lost_mw_total"] or 0),
                    restoration_within_target_rate=_float_or_none(
                        kpis["restoration_within_target_rate"]
                    ),
                    merged_outage_minutes=float(kpis["merged_outage_minutes"] or 0),
                    overlap_count=int(kpis["overlap_count"] or 0),
                    saifi=_float_or_none(kpis["saifi"]),
                    saidi_minutes=_float_or_none(kpis["saidi_minutes"]),
                    caidi_minutes=_float_or_none(kpis["caidi_minutes"]),
                    asai=_float_or_none(kpis["asai"]),
                    asui=_float_or_none(kpis["asui"]),
                    ctaidi_minutes=None,
                    caifi=None,
                    reliability_score=score,
                    reliability_band=band,
                    component_scores=components,
                    component_contributions=contributions,
                    reason_codes=reasons,
                    data_completeness_ratio=population.population_completeness_ratio,
                    schema_version=config.schema_version,
                )
            )
    return sorted(
        results,
        key=lambda row: (
            row.period_start,
            row.entity.entity_type.value,
            row.entity.entity_id,
        ),
    )


def assessment_periods(config: ReliabilityConfig) -> list[tuple[datetime, datetime]]:
    if config.period_frequency == "full":
        return [(config.assessment_start, config.assessment_end)]
    step = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=31),
    }[config.period_frequency.value]
    periods: list[tuple[datetime, datetime]] = []
    start = config.assessment_start
    while start < config.assessment_end:
        end = min(start + step, config.assessment_end)
        periods.append((start, end))
        start = end
    return periods


def _matches(population: PopulationRecord, outage: ClassifiedOutage) -> bool:
    entity = population.entity
    if entity.entity_type == AggregationLevel.FEEDER:
        return outage.feeder_id == entity.entity_id
    if entity.entity_type == AggregationLevel.SUBSTATION:
        return outage.substation_id == entity.entity_id
    return outage.grid_region == entity.entity_id


def _float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
