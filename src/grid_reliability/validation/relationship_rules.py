"""Cross-dataset relationship validation using asset inventory as reference data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from grid_reliability.validation.models import Severity, ValidationIssue
from grid_reliability.validation.quality_codes import IssueCode


@dataclass(frozen=True)
class ReferenceIndex:
    asset_ids: set[str]
    meter_to_feeder: dict[str, str]
    meter_to_substation: dict[str, str]
    meter_to_region: dict[str, str]
    feeder_to_substation: dict[str, str]
    feeder_to_region: dict[str, str]
    substation_to_region: dict[str, str]
    regions: set[str]


def build_reference_index(asset_records: list[dict[str, Any]]) -> ReferenceIndex:
    asset_ids: set[str] = set()
    meter_to_feeder: dict[str, str] = {}
    meter_to_substation: dict[str, str] = {}
    meter_to_region: dict[str, str] = {}
    feeder_to_substation: dict[str, str] = {}
    feeder_to_region: dict[str, str] = {}
    substation_to_region: dict[str, str] = {}
    regions: set[str] = set()

    for record in asset_records:
        asset_id = str(record.get("asset_id", ""))
        asset_type = record.get("asset_type")
        feeder_id = str(record.get("feeder_id") or "")
        substation_id = str(record.get("substation_id") or "")
        region = str(record.get("grid_region") or "")
        if asset_id:
            asset_ids.add(asset_id)
        if region:
            regions.add(region)
        if asset_type == "primary_substation" and substation_id:
            substation_to_region[substation_id] = region
        if asset_type == "feeder" and feeder_id:
            feeder_to_substation[feeder_id] = substation_id
            feeder_to_region[feeder_id] = region
        if asset_type == "smart_meter" and asset_id.startswith("AST-"):
            meter_id = asset_id.removeprefix("AST-")
            meter_to_feeder[meter_id] = feeder_id
            meter_to_substation[meter_id] = substation_id
            meter_to_region[meter_id] = region

    return ReferenceIndex(
        asset_ids,
        meter_to_feeder,
        meter_to_substation,
        meter_to_region,
        feeder_to_substation,
        feeder_to_region,
        substation_to_region,
        regions,
    )


def validate_relationships(
    datasets: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[int, list[ValidationIssue]]]:
    refs = build_reference_index(datasets.get("asset_inventory", []))
    results: dict[str, dict[int, list[ValidationIssue]]] = defaultdict(lambda: defaultdict(list))
    for dataset_name, records in datasets.items():
        for index, record in enumerate(records):
            if dataset_name == "smart_meter_events":
                _check_meter(record, index, results[dataset_name], refs)
                _check_feeder_substation_region(record, index, results[dataset_name], refs)
            elif dataset_name == "substation_events":
                _check_feeder_substation_region(record, index, results[dataset_name], refs)
            elif dataset_name == "weather_data":
                _check_region(record, index, results[dataset_name], refs)
            elif dataset_name == "maintenance_logs":
                _check_asset(record, "asset_id", index, results[dataset_name], refs)
            elif dataset_name == "outage_history":
                _check_asset(record, "primary_asset_id", index, results[dataset_name], refs)
                _check_feeder_substation_region(record, index, results[dataset_name], refs)
    return {dataset: dict(indexes) for dataset, indexes in results.items()}


def _record_key(record: dict[str, Any]) -> str | None:
    for key in ("event_id", "asset_id", "maintenance_id", "outage_id"):
        value = record.get(key)
        if value:
            return str(value)
    if record.get("weather_timestamp") and record.get("grid_region"):
        return f"{record['weather_timestamp']}|{record['grid_region']}"
    return None


def _issue(
    dataset_name: str,
    code: IssueCode,
    message: str,
    *,
    field_name: str,
    record: dict[str, Any],
    observed_value: Any,
    expected_rule: str,
) -> ValidationIssue:
    return ValidationIssue(
        code,
        Severity.ERROR,
        dataset_name,
        message,
        field_name=field_name,
        record_key=_record_key(record),
        observed_value=observed_value,
        expected_rule=expected_rule,
    )


def _check_meter(
    record: dict[str, Any],
    index: int,
    issues: dict[int, list[ValidationIssue]],
    refs: ReferenceIndex,
) -> None:
    meter_id = str(record.get("meter_id") or "")
    if meter_id not in refs.meter_to_feeder:
        issues[index].append(
            _issue(
                "smart_meter_events",
                IssueCode.FOREIGN_KEY_NOT_FOUND,
                "meter_id is not present in asset_inventory smart_meter assets.",
                field_name="meter_id",
                record=record,
                observed_value=meter_id,
                expected_rule="known smart_meter asset",
            )
        )
        return
    comparisons = {
        "feeder_id": refs.meter_to_feeder[meter_id],
        "substation_id": refs.meter_to_substation[meter_id],
        "grid_region": refs.meter_to_region[meter_id],
    }
    for field_name, expected in comparisons.items():
        if record.get(field_name) != expected:
            issues[index].append(
                _issue(
                    "smart_meter_events",
                    IssueCode.HIERARCHY_MISMATCH,
                    f"{field_name} does not match the meter hierarchy.",
                    field_name=field_name,
                    record=record,
                    observed_value=record.get(field_name),
                    expected_rule=expected,
                )
            )


def _check_feeder_substation_region(
    record: dict[str, Any],
    index: int,
    issues: dict[int, list[ValidationIssue]],
    refs: ReferenceIndex,
) -> None:
    dataset_name = str(record["_ingestion"]["dataset_name"])
    feeder_id = str(record.get("feeder_id") or "")
    substation_id = str(record.get("substation_id") or "")
    region = str(record.get("grid_region") or "")
    if feeder_id not in refs.feeder_to_substation:
        issues[index].append(
            _issue(
                dataset_name,
                IssueCode.FOREIGN_KEY_NOT_FOUND,
                "feeder_id is not present in asset_inventory feeder assets.",
                field_name="feeder_id",
                record=record,
                observed_value=feeder_id,
                expected_rule="known feeder asset",
            )
        )
        return
    if refs.feeder_to_substation[feeder_id] != substation_id:
        issues[index].append(
            _issue(
                dataset_name,
                IssueCode.HIERARCHY_MISMATCH,
                "feeder_id does not belong to substation_id.",
                field_name="substation_id",
                record=record,
                observed_value=substation_id,
                expected_rule=refs.feeder_to_substation[feeder_id],
            )
        )
    if refs.feeder_to_region[feeder_id] != region:
        issues[index].append(
            _issue(
                dataset_name,
                IssueCode.HIERARCHY_MISMATCH,
                "feeder_id does not belong to grid_region.",
                field_name="grid_region",
                record=record,
                observed_value=region,
                expected_rule=refs.feeder_to_region[feeder_id],
            )
        )


def _check_region(
    record: dict[str, Any],
    index: int,
    issues: dict[int, list[ValidationIssue]],
    refs: ReferenceIndex,
) -> None:
    region = str(record.get("grid_region") or "")
    if region not in refs.regions:
        issues[index].append(
            _issue(
                "weather_data",
                IssueCode.FOREIGN_KEY_NOT_FOUND,
                "grid_region is not present in asset_inventory.",
                field_name="grid_region",
                record=record,
                observed_value=region,
                expected_rule="known grid_region",
            )
        )


def _check_asset(
    record: dict[str, Any],
    field_name: str,
    index: int,
    issues: dict[int, list[ValidationIssue]],
    refs: ReferenceIndex,
) -> None:
    dataset_name = str(record["_ingestion"]["dataset_name"])
    asset_id = str(record.get(field_name) or "")
    if asset_id not in refs.asset_ids:
        issues[index].append(
            _issue(
                dataset_name,
                IssueCode.FOREIGN_KEY_NOT_FOUND,
                f"{field_name} is not present in asset_inventory.",
                field_name=field_name,
                record=record,
                observed_value=asset_id,
                expected_rule="known asset_id",
            )
        )
