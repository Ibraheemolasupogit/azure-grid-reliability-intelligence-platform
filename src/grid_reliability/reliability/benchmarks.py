"""Internal synthetic reliability benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from grid_reliability.reliability.models import ReliabilityResult


@dataclass(frozen=True)
class BenchmarkRow:
    entity_type: str
    entity_id: str
    period_start: object
    metric_name: str
    benchmark_scope: str
    benchmark_method: str
    benchmark_value: float | None
    entity_value: float | None
    absolute_gap: float | None
    relative_gap: float | None
    percentile_rank: float | None
    performance_direction: str


def calculate_benchmarks(results: list[ReliabilityResult], method: str) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    metrics = ("saifi", "saidi_minutes", "asai", "reliability_score")
    for result in results:
        peers = [
            peer
            for peer in results
            if peer.entity.entity_type == result.entity.entity_type
            and peer.period_start == result.period_start
        ]
        for metric in metrics:
            values = [
                float(getattr(peer, metric)) for peer in peers if getattr(peer, metric) is not None
            ]
            value = getattr(result, metric)
            benchmark = median(values) if values else None
            rows.append(
                BenchmarkRow(
                    entity_type=result.entity.entity_type.value,
                    entity_id=result.entity.entity_id,
                    period_start=result.period_start,
                    metric_name=metric,
                    benchmark_scope="entity_type",
                    benchmark_method=method,
                    benchmark_value=benchmark,
                    entity_value=float(value) if value is not None else None,
                    absolute_gap=_gap(value, benchmark),
                    relative_gap=_relative_gap(value, benchmark),
                    percentile_rank=_percentile(value, values),
                    performance_direction=_direction(metric, value, benchmark),
                )
            )
    return rows


def _gap(value: object, benchmark: float | None) -> float | None:
    if not isinstance(value, int | float) or benchmark is None:
        return None
    return float(value) - benchmark


def _relative_gap(value: object, benchmark: float | None) -> float | None:
    if not isinstance(value, int | float) or benchmark is None or benchmark == 0:
        return None
    return (float(value) - benchmark) / benchmark * 100


def _percentile(value: object, values: list[float]) -> float | None:
    if not isinstance(value, int | float) or len(values) < 2:
        return None
    below_or_equal = sum(1 for item in values if item <= float(value))
    return below_or_equal / len(values)


def _direction(metric: str, value: object, benchmark: float | None) -> str:
    if not isinstance(value, int | float) or benchmark is None:
        return "UNAVAILABLE"
    if float(value) == benchmark:
        return "AT_BENCHMARK"
    higher_is_better = metric in {"asai", "reliability_score"}
    improved = float(value) > benchmark if higher_is_better else float(value) < benchmark
    return "BETTER_THAN_PEER_MEDIAN" if improved else "WORSE_THAN_PEER_MEDIAN"
