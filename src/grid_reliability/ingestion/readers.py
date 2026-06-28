"""Bounded CSV and JSON Lines readers for local ingestion."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

from grid_reliability.ingestion.records import IngestionRecord, SourceDataset
from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


def read_dataset(
    dataset: SourceDataset,
    *,
    ingestion_run_id: str,
    ingested_at: datetime,
) -> Iterator[IngestionRecord]:
    if dataset.file_format == "csv":
        yield from read_csv_records(
            dataset, ingestion_run_id=ingestion_run_id, ingested_at=ingested_at
        )
        return
    if dataset.file_format == "jsonl":
        yield from read_jsonl_records(
            dataset, ingestion_run_id=ingestion_run_id, ingested_at=ingested_at
        )
        return
    yield IngestionRecord(
        dataset.dataset_name,
        dataset.filename,
        0,
        ingestion_run_id,
        ingested_at,
        None,
        None,
        [
            ValidationIssue(
                IssueCode.UNSUPPORTED_FORMAT,
                Severity.ERROR,
                dataset.dataset_name,
                f"Unsupported format: {dataset.file_format}",
            )
        ],
    )


def read_jsonl_records(
    dataset: SourceDataset,
    *,
    ingestion_run_id: str,
    ingested_at: datetime,
) -> Iterator[IngestionRecord]:
    seen_any = False
    try:
        with dataset.path.open("r", encoding="utf-8") as file_obj:
            for line_number, line in enumerate(file_obj, start=1):
                if not line.strip():
                    continue
                seen_any = True
                raw = line.rstrip("\n")
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield IngestionRecord(
                        dataset.dataset_name,
                        dataset.filename,
                        line_number,
                        ingestion_run_id,
                        ingested_at,
                        raw,
                        None,
                        [
                            ValidationIssue(
                                IssueCode.MALFORMED_RECORD,
                                Severity.ERROR,
                                dataset.dataset_name,
                                f"Malformed JSON Lines record: {exc.msg}",
                                record_number=line_number,
                                observed_value=exc.msg,
                                expected_rule="valid JSON object per line",
                            )
                        ],
                    )
                    continue
                if not isinstance(parsed, dict):
                    issues = [
                        ValidationIssue(
                            IssueCode.MALFORMED_RECORD,
                            Severity.ERROR,
                            dataset.dataset_name,
                            "JSON Lines record must be an object.",
                            record_number=line_number,
                            observed_value=type(parsed).__name__,
                            expected_rule="JSON object",
                        )
                    ]
                    parsed_record: dict[str, Any] | None = None
                else:
                    issues = []
                    parsed_record = parsed
                yield IngestionRecord(
                    dataset.dataset_name,
                    dataset.filename,
                    line_number,
                    ingestion_run_id,
                    ingested_at,
                    raw,
                    parsed_record,
                    issues,
                )
    except UnicodeDecodeError as exc:
        yield IngestionRecord(
            dataset.dataset_name,
            dataset.filename,
            0,
            ingestion_run_id,
            ingested_at,
            None,
            None,
            [
                ValidationIssue(
                    IssueCode.MALFORMED_RECORD,
                    Severity.ERROR,
                    dataset.dataset_name,
                    "Source file is not valid UTF-8.",
                    observed_value=str(exc),
                    expected_rule="UTF-8",
                )
            ],
        )
    if not seen_any:
        yield IngestionRecord(
            dataset.dataset_name,
            dataset.filename,
            0,
            ingestion_run_id,
            ingested_at,
            None,
            None,
            [
                ValidationIssue(
                    IssueCode.EMPTY_FILE,
                    Severity.ERROR,
                    dataset.dataset_name,
                    "Source file contains no records.",
                )
            ],
        )


def read_csv_records(
    dataset: SourceDataset,
    *,
    ingestion_run_id: str,
    ingested_at: datetime,
) -> Iterator[IngestionRecord]:
    expected_fields = [str(field["name"]) for field in dataset.contract["fields"]]
    seen_any = False
    try:
        with dataset.path.open("r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            if reader.fieldnames != expected_fields:
                yield IngestionRecord(
                    dataset.dataset_name,
                    dataset.filename,
                    1,
                    ingestion_run_id,
                    ingested_at,
                    {"fieldnames": reader.fieldnames},
                    None,
                    [
                        ValidationIssue(
                            IssueCode.INCONSISTENT_CSV_ROW,
                            Severity.ERROR,
                            dataset.dataset_name,
                            "CSV header does not match the contract field order.",
                            record_number=1,
                            observed_value=reader.fieldnames,
                            expected_rule=",".join(expected_fields),
                        )
                    ],
                )
                return
            for row_number, row in enumerate(reader, start=2):
                seen_any = True
                issues: list[ValidationIssue] = []
                if None in row:
                    issues.append(
                        ValidationIssue(
                            IssueCode.INCONSISTENT_CSV_ROW,
                            Severity.ERROR,
                            dataset.dataset_name,
                            "CSV row contains extra columns.",
                            record_number=row_number,
                            observed_value=row[None],
                            expected_rule="contract column count",
                        )
                    )
                    row.pop(None, None)
                if set(row) != set(expected_fields):
                    issues.append(
                        ValidationIssue(
                            IssueCode.INCONSISTENT_CSV_ROW,
                            Severity.ERROR,
                            dataset.dataset_name,
                            "CSV row columns do not match the contract.",
                            record_number=row_number,
                            observed_value=sorted(row),
                            expected_rule="contract fields",
                        )
                    )
                yield IngestionRecord(
                    dataset.dataset_name,
                    dataset.filename,
                    row_number,
                    ingestion_run_id,
                    ingested_at,
                    dict(row),
                    dict(row),
                    issues,
                )
    except UnicodeDecodeError as exc:
        yield IngestionRecord(
            dataset.dataset_name,
            dataset.filename,
            0,
            ingestion_run_id,
            ingested_at,
            None,
            None,
            [
                ValidationIssue(
                    IssueCode.MALFORMED_RECORD,
                    Severity.ERROR,
                    dataset.dataset_name,
                    "Source file is not valid UTF-8.",
                    observed_value=str(exc),
                    expected_rule="UTF-8",
                )
            ],
        )
    if not seen_any:
        yield IngestionRecord(
            dataset.dataset_name,
            dataset.filename,
            0,
            ingestion_run_id,
            ingested_at,
            None,
            None,
            [
                ValidationIssue(
                    IssueCode.EMPTY_FILE,
                    Severity.ERROR,
                    dataset.dataset_name,
                    "Source file contains no records.",
                )
            ],
        )


def iter_micro_batches(
    records: Iterable[IngestionRecord], batch_size: int
) -> Iterator[list[IngestionRecord]]:
    """Yield finite bounded micro-batches from local records."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    batch: list[IngestionRecord] = []
    for record in records:
        batch.append(record)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


class JsonlEventReader:
    """Finite local JSONL event reader mirroring a future Event Hubs consumer boundary."""

    def __init__(
        self, dataset: SourceDataset, *, ingestion_run_id: str, ingested_at: datetime
    ) -> None:
        if dataset.file_format != "jsonl":
            raise ValueError("JsonlEventReader only supports jsonl datasets.")
        self._dataset = dataset
        self._ingestion_run_id = ingestion_run_id
        self._ingested_at = ingested_at

    def events(self) -> Iterator[IngestionRecord]:
        yield from read_jsonl_records(
            self._dataset,
            ingestion_run_id=self._ingestion_run_id,
            ingested_at=self._ingested_at,
        )

    def micro_batches(self, batch_size: int) -> Iterator[list[IngestionRecord]]:
        yield from iter_micro_batches(self.events(), batch_size)
