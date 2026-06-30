"""Period-over-period reliability trends."""

from __future__ import annotations

from dataclasses import dataclass

from grid_reliability.reliability.models import ReliabilityResult


@dataclass(frozen=True)
class TrendRow:
    entity_type: str
    entity_id: str
    period_start: object
    metric_name: str
    current_value: float | None
    previous_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    direction: str


def calculate_trends(results: list[ReliabilityResult]) -> list[TrendRow]:
    grouped: dict[tuple[str, str], list[ReliabilityResult]] = {}
    for result in results:
        grouped.setdefault((result.entity.entity_type.value, result.entity.entity_id), []).append(
            result
        )
    trends: list[TrendRow] = []
    for (entity_type, entity_id), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: row.period_start)
        previous: ReliabilityResult | None = None
        for row in ordered:
            for metric_name in ("saifi", "saidi_minutes", "caidi_minutes", "asai"):
                current = getattr(row, metric_name)
                prior = getattr(previous, metric_name) if previous else None
                trends.append(
                    TrendRow(
                        entity_type,
                        entity_id,
                        row.period_start,
                        metric_name,
                        current,
                        prior,
                        _absolute(current, prior),
                        _percentage(current, prior),
                        _direction(metric_name, current, prior),
                    )
                )
            previous = row
    return trends


def _absolute(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def _percentage(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100


def _direction(metric_name: str, current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "NO_PRIOR_PERIOD"
    if current == previous:
        return "UNCHANGED"
    lower_is_better = metric_name != "asai"
    improved = current < previous if lower_is_better else current > previous
    return "IMPROVED" if improved else "DETERIORATED"
