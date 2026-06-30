"""Composite reliability scoring and reason codes."""

from __future__ import annotations

from typing import Any

from grid_reliability.reliability.config import ReliabilityConfig
from grid_reliability.reliability.models import (
    ClassifiedOutage,
    PopulationRecord,
    ReliabilityBand,
)


def reliability_score(
    kpis: dict[str, Any],
    population: PopulationRecord,
    config: ReliabilityConfig,
    outages: list[ClassifiedOutage],
) -> tuple[float | None, dict[str, float], dict[str, float], ReliabilityBand, tuple[str, ...]]:
    if population.estimated_customer_population < config.minimum_population:
        return None, {}, {}, ReliabilityBand.INSUFFICIENT_DATA, ("INSUFFICIENT_POPULATION_DATA",)
    components = {
        "interruption_frequency": _inverse(kpis.get("saifi"), 5.0),
        "interruption_duration": _inverse(kpis.get("saidi_minutes"), 720.0),
        "restoration": _inverse(kpis.get("mean_outage_duration_minutes"), 240.0),
        "availability": _availability(kpis.get("asai")),
        "severe_weather_resilience": _inverse(kpis.get("severe_weather_outage_count"), 3.0),
        "equipment_outage": _inverse(kpis.get("equipment_failure_outage_count"), 3.0),
        "data_completeness": population.population_completeness_ratio * 100,
    }
    contributions = {
        name: round(components[name] * weight, 6)
        for name, weight in config.component_weights.items()
    }
    score = round(sum(contributions.values()), config.kpi_precision)
    band = _band(score, config)
    return score, components, contributions, band, _reasons(kpis, population, config, outages)


def _inverse(value: object, weak_at: float) -> float:
    if not isinstance(value, int | float):
        return 100.0
    return round(max(0.0, min(100.0, 100.0 * (1.0 - float(value) / weak_at))), 6)


def _availability(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.0
    return round(max(0.0, min(100.0, float(value) * 100)), 6)


def _band(score: float, config: ReliabilityConfig) -> ReliabilityBand:
    thresholds = config.reliability_band_thresholds
    if score <= thresholds["weak_max"]:
        return ReliabilityBand.WEAK
    if score <= thresholds["watch_max"]:
        return ReliabilityBand.WATCH
    if score <= thresholds["stable_max"]:
        return ReliabilityBand.STABLE
    return ReliabilityBand.STRONG


def _reasons(
    kpis: dict[str, Any],
    population: PopulationRecord,
    config: ReliabilityConfig,
    outages: list[ClassifiedOutage],
) -> tuple[str, ...]:
    reasons: list[tuple[int, str]] = []
    if population.population_completeness_ratio < config.minimum_data_completeness:
        reasons.append((100, "LOW_DATA_COMPLETENESS"))
    if population.estimated_customer_population < config.minimum_population:
        reasons.append((99, "INSUFFICIENT_POPULATION_DATA"))
    if float(kpis.get("saifi") or 0) >= 1:
        reasons.append((90, "HIGH_INTERRUPTION_FREQUENCY"))
    if float(kpis.get("saidi_minutes") or 0) >= 120:
        reasons.append((88, "HIGH_INTERRUPTION_DURATION"))
    if float(kpis.get("mean_outage_duration_minutes") or 0) > config.restoration_target_minutes:
        reasons.append((86, "LONG_RESTORATION_TIME"))
    if kpis.get("asai") is not None and float(kpis["asai"]) < 0.99:
        reasons.append((84, "LOW_SERVICE_AVAILABILITY"))
    if int(kpis.get("unplanned_outage_count") or 0) > 1:
        reasons.append((82, "REPEATED_UNPLANNED_OUTAGES"))
    if int(kpis.get("severe_weather_outage_count") or 0) > 0:
        reasons.append((80, "SEVERE_WEATHER_OUTAGE_EXPOSURE"))
    if int(kpis.get("equipment_failure_outage_count") or 0) > 0:
        reasons.append((78, "EQUIPMENT_FAILURE_OUTAGE_CONCENTRATION"))
    if int(kpis.get("customer_interruptions") or 0) > population.estimated_customer_population:
        reasons.append((76, "HIGH_CUSTOMER_INTERRUPTION_VOLUME"))
    if any(outage.duration_class == "PROLONGED" for outage in outages):
        reasons.append((74, "PROLONGED_OUTAGE_EVENT"))
    if int(kpis.get("planned_outage_count") or 0) > 0:
        reasons.append((72, "PLANNED_OUTAGE_CONCENTRATION"))
    if int(kpis.get("outage_count") or 0) == 0:
        reasons.append((10, "INSUFFICIENT_OUTAGE_HISTORY"))
    if int(kpis.get("unplanned_outage_count") or 0) == 0:
        reasons.append((8, "NO_UNPLANNED_OUTAGES"))
    if kpis.get("asai") is not None and float(kpis["asai"]) >= 0.999:
        reasons.append((6, "STRONG_SERVICE_AVAILABILITY"))
    ordered = [code for _, code in sorted(reasons, key=lambda item: (-item[0], item[1]))]
    return tuple(ordered[: config.max_reason_codes])
