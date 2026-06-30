"""Chronological split and rolling-origin fold construction."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from grid_reliability.forecasting.config import ForecastingConfig
from grid_reliability.forecasting.models import FeatureRow, ForecastingError, SplitBoundaries


def chronological_split(
    rows: list[FeatureRow],
    config: ForecastingConfig,
) -> tuple[list[FeatureRow], list[FeatureRow], list[FeatureRow], SplitBoundaries]:
    timestamps = sorted({row.forecast_timestamp for row in rows})
    required = config.validation_intervals + config.test_intervals + 1
    if len(timestamps) < required:
        raise ForecastingError(
            f"Insufficient forecast timestamps for split: {len(timestamps)} available, "
            f"{required} required."
        )
    test_start_index = len(timestamps) - config.test_intervals
    validation_start_index = test_start_index - config.validation_intervals
    validation_timestamps = set(timestamps[validation_start_index:test_start_index])
    test_timestamps = set(timestamps[test_start_index:])
    train_rows: list[FeatureRow] = []
    validation_rows: list[FeatureRow] = []
    test_rows: list[FeatureRow] = []
    for row in rows:
        if row.forecast_timestamp in test_timestamps:
            test_rows.append(replace(row, data_split="test"))
        elif row.forecast_timestamp in validation_timestamps:
            validation_rows.append(replace(row, data_split="validation"))
        else:
            train_rows.append(replace(row, data_split="train"))
    if not train_rows or not validation_rows or not test_rows:
        raise ForecastingError(
            "Chronological split produced an empty train, validation, or test set."
        )
    boundaries = SplitBoundaries(
        training_start=_first_timestamp(train_rows),
        training_end=_last_timestamp(train_rows),
        validation_start=_first_timestamp(validation_rows),
        validation_end=_last_timestamp(validation_rows),
        test_start=_first_timestamp(test_rows),
        test_end=_last_timestamp(test_rows),
    )
    return train_rows, validation_rows, test_rows, boundaries


def rolling_origin_folds(
    train_rows: list[FeatureRow],
    validation_rows: list[FeatureRow],
    test_rows: list[FeatureRow],
    config: ForecastingConfig,
) -> list[tuple[int, list[FeatureRow], list[FeatureRow], datetime]]:
    all_rows = sorted([*train_rows, *validation_rows, *test_rows], key=_row_key)
    origins = sorted({row.forecast_origin for row in [*validation_rows, *test_rows]})
    selected_origins = origins[-config.backtest_folds :]
    folds: list[tuple[int, list[FeatureRow], list[FeatureRow], datetime]] = []
    for fold_number, cutoff in enumerate(selected_origins, start=1):
        fold_train = [row for row in all_rows if row.forecast_timestamp <= cutoff]
        fold_eval = [row for row in all_rows if row.forecast_origin == cutoff]
        if fold_train and fold_eval:
            folds.append((fold_number, fold_train, fold_eval, cutoff))
    return folds


def _row_key(row: FeatureRow) -> tuple[datetime, str, int]:
    return (row.forecast_timestamp, row.entity_id, row.forecast_horizon_intervals)


def _first_timestamp(rows: list[FeatureRow]) -> str | None:
    return (
        min(row.forecast_timestamp for row in rows).isoformat().replace("+00:00", "Z")
        if rows
        else None
    )


def _last_timestamp(rows: list[FeatureRow]) -> str | None:
    return (
        max(row.forecast_timestamp for row in rows).isoformat().replace("+00:00", "Z")
        if rows
        else None
    )
