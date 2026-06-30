"""Chronological splitting with a prediction-horizon purge."""

from __future__ import annotations

from datetime import timedelta

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.models import (
    FeatureRow,
    OutagePredictionError,
    SplitBoundaries,
    SplitRows,
)


def chronological_split(rows: list[FeatureRow], config: OutagePredictionConfig) -> SplitRows:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.labelled.panel.observation_timestamp,
            row.labelled.panel.entity.entity_id,
        ),
    )
    timestamps = sorted({row.labelled.panel.observation_timestamp for row in ordered})
    required = (
        config.validation_intervals + config.test_intervals + config.prediction_horizon_intervals
    )
    if len(timestamps) <= required:
        raise OutagePredictionError("Insufficient timestamps for chronological split and purge.")
    test_times = set(timestamps[-config.test_intervals :])
    validation_start_index = len(timestamps) - config.test_intervals - config.validation_intervals
    validation_times = set(
        timestamps[validation_start_index : validation_start_index + config.validation_intervals]
    )
    purge_delta = timedelta(
        minutes=config.observation_frequency_minutes * config.prediction_horizon_intervals
    )
    validation_start = min(validation_times)
    test_start = min(test_times)
    train = [
        row
        for row in ordered
        if row.labelled.panel.observation_timestamp < validation_start - purge_delta
    ]
    validation = [
        row
        for row in ordered
        if row.labelled.panel.observation_timestamp in validation_times
        and row.labelled.label_window_end <= test_start
    ]
    test = [row for row in ordered if row.labelled.panel.observation_timestamp in test_times]
    _validate_class_counts(train, config, "training")
    if not validation:
        raise OutagePredictionError("Validation split is empty.")
    if not test:
        raise OutagePredictionError("Test split is empty.")
    return SplitRows(
        train=train,
        validation=validation,
        test=test,
        boundaries=SplitBoundaries(
            train_start=min(row.labelled.panel.observation_timestamp for row in train),
            train_end=max(row.labelled.panel.observation_timestamp for row in train),
            validation_start=min(validation_times),
            validation_end=max(validation_times),
            test_start=min(test_times),
            test_end=max(test_times),
            purge_intervals=config.prediction_horizon_intervals,
        ),
    )


def split_name(row: FeatureRow, splits: SplitRows) -> str:
    if row in splits.train:
        return "train"
    if row in splits.validation:
        return "validation"
    if row in splits.test:
        return "test"
    return "unused"


def _validate_class_counts(
    rows: list[FeatureRow], config: OutagePredictionConfig, name: str
) -> None:
    positives = sum(row.labelled.label for row in rows)
    negatives = len(rows) - positives
    if positives < config.minimum_positive_examples:
        raise OutagePredictionError(f"{name} split has insufficient positive examples.")
    if negatives < config.minimum_negative_examples:
        raise OutagePredictionError(f"{name} split has insufficient negative examples.")
