"""Time-range helpers for synthetic datasets."""

from __future__ import annotations

from datetime import datetime, timedelta


def iter_timestamps(start: datetime, end: datetime, interval_minutes: int) -> list[datetime]:
    """Return timestamps from start up to but not including end."""
    timestamps: list[datetime] = []
    current = start
    step = timedelta(minutes=interval_minutes)
    while current < end:
        timestamps.append(current)
        current += step
    return timestamps


def iso_timestamp(value: datetime) -> str:
    """Return second-precision ISO timestamps for deterministic files."""
    return value.replace(microsecond=0).isoformat()
