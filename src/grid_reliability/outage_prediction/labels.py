"""Leakage-safe future outage labels."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.data import parse_timestamp
from grid_reliability.outage_prediction.models import EntityType, LabelledRow, PanelRow


def apply_labels(
    panel: list[PanelRow],
    outages: list[dict[str, Any]],
    config: OutagePredictionConfig,
) -> list[LabelledRow]:
    labelled: list[LabelledRow] = []
    horizon = timedelta(
        minutes=config.observation_frequency_minutes * config.prediction_horizon_intervals
    )
    eligible = [
        row
        for row in outages
        if row.get("outage_type") == "unplanned" and not bool(row.get("planned_flag"))
    ]
    for panel_row in panel:
        start = panel_row.observation_timestamp
        end = start + horizon
        matches = [
            outage
            for outage in eligible
            if _matches(panel_row, outage)
            and start < parse_timestamp(str(outage["outage_start"])) <= end
        ]
        matches.sort(
            key=lambda outage: (parse_timestamp(str(outage["outage_start"])), outage["outage_id"])
        )
        first = matches[0] if matches else None
        labelled.append(
            LabelledRow(
                panel=panel_row,
                label=1 if first else 0,
                label_window_start=start,
                label_window_end=end,
                label_source_outage_id=str(first["outage_id"]) if first else None,
                label_linkage=_linkage(panel_row, first) if first else "none",
            )
        )
    return labelled


def _matches(panel_row: PanelRow, outage: dict[str, Any]) -> bool:
    entity = panel_row.entity
    if entity.entity_type == EntityType.FEEDER:
        return outage.get("feeder_id") == entity.entity_id
    if entity.entity_type == EntityType.SUBSTATION:
        return outage.get("substation_id") == entity.entity_id
    return outage.get("primary_asset_id") == entity.entity_id


def _linkage(panel_row: PanelRow, outage: dict[str, Any] | None) -> str:
    if outage is None:
        return "none"
    if panel_row.entity.entity_type == EntityType.PRIMARY_ASSET:
        return "direct_asset"
    if outage.get("primary_asset_id") == panel_row.entity.entity_id:
        return "direct_asset"
    return panel_row.entity.entity_type.value
