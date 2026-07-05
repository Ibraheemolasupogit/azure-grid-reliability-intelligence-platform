"""Build Power BI-ready dimensions, facts, bridges, and semantic metadata."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, time, timedelta

from grid_reliability.reporting.models import (
    RelationshipDefinition,
    ReportingConfig,
    ReportingTables,
    SourceData,
    ValidationResult,
)

UNKNOWN = "UNKNOWN"
UNKNOWN_KEY = "SK_UNKNOWN"


def stable_key(prefix: str, *parts: object) -> str:
    """Create a deterministic surrogate key without Python hash randomisation."""

    text = "|".join(str(part) if part not in (None, "") else UNKNOWN for part in parts)
    if text == UNKNOWN:
        return UNKNOWN_KEY
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16].upper()}"


def build_reporting_tables(data: SourceData, config: ReportingConfig) -> ReportingTables:
    """Build all requested reporting semantic tables."""

    context = _Context(data)
    dimensions = {
        "dim_date": _dim_date(config),
        "dim_time": _dim_time(),
        "dim_grid_region": context.dim_regions(),
        "dim_substation": context.dim_substations(),
        "dim_feeder": context.dim_feeders(),
        "dim_asset": context.dim_assets(),
        "dim_model": context.dim_models(),
        "dim_component_run": context.dim_runs(),
        "dim_alert_reason": context.dim_alert_reasons(),
        "dim_metric": context.dim_metrics(),
    }
    facts = {
        "fact_demand_forecast": context.fact_demand_forecast(),
        "fact_asset_health": context.fact_asset_health(),
        "fact_outage_risk": context.fact_outage_risk(),
        "fact_reliability_kpi": context.fact_reliability_kpi(),
        "fact_monitoring_check": context.fact_monitoring_check(),
        "fact_monitoring_alert": context.fact_monitoring_alert(),
        "fact_assistant_response": context.fact_assistant_response(),
        "fact_maintenance_priority": context.fact_maintenance_priority(),
    }
    bridges = {
        "bridge_asset_reason": context.bridge_asset_reason(),
        "bridge_entity_reason": context.bridge_entity_reason(),
        "bridge_response_citation": context.bridge_response_citation(),
    }
    return ReportingTables(
        dimensions=dimensions,
        facts=facts,
        bridges=bridges,
        relationships=_relationships(),
        kpis=kpi_catalogue(),
    )


def validate_reporting_tables(tables: ReportingTables) -> ValidationResult:
    """Validate uniqueness and many-to-one foreign-key integrity."""

    failures: list[str] = []
    duplicate_count = 0
    orphan_count = 0
    unknown_count = 0
    null_critical = 0

    for table_name, rows in {**tables.dimensions, **tables.facts, **tables.bridges}.items():
        key_columns = [
            column
            for column in (rows[0].keys() if rows else ())
            if column.endswith("_id") or column.endswith("_key")
        ]
        primary = _primary_key(table_name, rows)
        if primary:
            values = [str(row.get(primary, "")) for row in rows]
            duplicates = len(values) - len(set(values))
            duplicate_count += duplicates
            if duplicates:
                failures.append(f"{table_name}.{primary} contains {duplicates} duplicate key(s).")
        for column in key_columns:
            unknown_count += sum(1 for row in rows if row.get(column) == UNKNOWN_KEY)
        for row in rows:
            for field in _critical_fields(table_name):
                if row.get(field) in (None, ""):
                    null_critical += 1

    dim_index = {
        table_name: {str(row.get(_primary_key(table_name, rows), "")) for row in rows}
        for table_name, rows in tables.dimensions.items()
    }
    for relationship in tables.relationships:
        fact_rows = tables.facts.get(relationship.from_table, [])
        valid_keys = dim_index.get(relationship.to_table, set())
        for row in fact_rows:
            value = str(row.get(relationship.from_column, ""))
            if value and value != UNKNOWN_KEY and value not in valid_keys:
                orphan_count += 1
        if relationship.cardinality != "many-to-one":
            failures.append(
                f"{relationship.from_table}->{relationship.to_table} is not many-to-one."
            )
        if relationship.cross_filter_direction != "single":
            failures.append(
                f"{relationship.from_table}->{relationship.to_table} is not single direction."
            )

    if orphan_count:
        failures.append(f"Detected {orphan_count} orphan foreign key value(s).")
    return ValidationResult(
        duplicate_count, orphan_count, unknown_count, null_critical, tuple(failures)
    )


class _Context:
    def __init__(self, data: SourceData) -> None:
        self.data = data
        self.assets = data.jsonl_tables.get("interim.asset_inventory", [])
        self.forecasts = data.csv_tables.get("forecasting.forecast", [])
        self.health = data.csv_tables.get("asset_health.scores", [])
        self.health_components = {
            row.get("asset_id", ""): row
            for row in data.csv_tables.get("asset_health.components", [])
        }
        self.priorities = data.csv_tables.get("asset_health.priorities", [])
        self.outage = data.csv_tables.get("outage_prediction.predictions", [])
        self.reliability = data.csv_tables.get("reliability.kpis", [])
        self.reliability_reasons = data.csv_tables.get("reliability.reasons", [])
        self.monitoring = data.csv_tables.get("monitoring.summary", [])
        self.alerts = data.csv_tables.get("monitoring.alerts", [])
        self.responses = data.jsonl_tables.get("genai.responses", [])

    def dim_regions(self) -> list[dict[str, object]]:
        values = _sorted_unique(
            [str(row.get("grid_region", "")) for row in self.assets]
            + [
                row.get("grid_region", "")
                for row in self.forecasts + self.health + self.outage + self.reliability
            ]
        )
        return [_unknown_row("region_key", "grid_region")] + [
            {
                "region_key": stable_key("REG", value),
                "grid_region": value,
                "region_name": value.replace("GRID-", "Synthetic "),
                "synthetic_data_flag": True,
            }
            for value in values
        ]

    def dim_substations(self) -> list[dict[str, object]]:
        members: dict[str, dict[str, object]] = {}
        for row in self.assets:
            substation_id = str(row.get("substation_id") or "")
            if substation_id:
                members[substation_id] = {
                    "substation_key": stable_key("SUB", substation_id),
                    "substation_id": substation_id,
                    "grid_region": row.get("grid_region", UNKNOWN),
                    "region_key": stable_key("REG", row.get("grid_region")),
                    "asset_id": row.get("asset_id", ""),
                    "operational_status": row.get("operational_status", UNKNOWN),
                    "criticality_tier": row.get("criticality_tier", UNKNOWN),
                }
        return [
            _unknown_row("substation_key", "substation_id"),
            *_sorted_rows(members.values(), "substation_id"),
        ]

    def dim_feeders(self) -> list[dict[str, object]]:
        members: dict[str, dict[str, object]] = {}
        for row in self.assets:
            feeder_id = str(row.get("feeder_id") or "")
            if feeder_id:
                members[feeder_id] = {
                    "feeder_key": stable_key("FDR", feeder_id),
                    "feeder_id": feeder_id,
                    "substation_id": row.get("substation_id", UNKNOWN),
                    "substation_key": stable_key("SUB", row.get("substation_id")),
                    "grid_region": row.get("grid_region", UNKNOWN),
                    "region_key": stable_key("REG", row.get("grid_region")),
                    "rated_capacity": row.get("rated_capacity", ""),
                    "operational_status": row.get("operational_status", UNKNOWN),
                }
        return [
            _unknown_row("feeder_key", "feeder_id"),
            *_sorted_rows(members.values(), "feeder_id"),
        ]

    def dim_assets(self) -> list[dict[str, object]]:
        rows = []
        for row in sorted(self.assets, key=lambda item: str(item.get("asset_id", ""))):
            rows.append(
                {
                    "asset_key": stable_key("AST", row.get("asset_id")),
                    "asset_id": row.get("asset_id", UNKNOWN),
                    "asset_name": row.get("asset_name", ""),
                    "asset_type": row.get("asset_type", UNKNOWN),
                    "grid_region": row.get("grid_region", UNKNOWN),
                    "region_key": stable_key("REG", row.get("grid_region")),
                    "substation_id": row.get("substation_id", UNKNOWN),
                    "substation_key": stable_key("SUB", row.get("substation_id")),
                    "feeder_id": row.get("feeder_id") or UNKNOWN,
                    "feeder_key": stable_key("FDR", row.get("feeder_id")),
                    "manufacturer": row.get("manufacturer", ""),
                    "model": row.get("model", ""),
                    "commissioned_date": row.get("commissioned_date", ""),
                    "expected_life_years": row.get("expected_life_years", ""),
                    "criticality_tier": row.get("criticality_tier", UNKNOWN),
                    "operational_status": row.get("operational_status", UNKNOWN),
                    "synthetic_data_flag": True,
                }
            )
        return [_unknown_row("asset_key", "asset_id"), *rows]

    def dim_models(self) -> list[dict[str, object]]:
        members: dict[str, dict[str, object]] = {}
        for row in self.forecasts:
            key = ("forecasting", row.get("model_name", UNKNOWN), row.get("target_name", UNKNOWN))
            members["|".join(key)] = _model_row(
                "forecasting",
                row.get("model_name"),
                row.get("target_name"),
                row.get("target_unit"),
                row.get("entity_type"),
            )
        for row in self.outage:
            key = ("outage_prediction", row.get("model_name", UNKNOWN), "outage_flag")
            members["|".join(key)] = _model_row(
                "outage_prediction",
                row.get("model_name"),
                "outage_flag",
                "flag",
                row.get("entity_type"),
            )
        return [
            _unknown_row("model_key", "model_name"),
            *_sorted_rows(members.values(), "model_key"),
        ]

    def dim_runs(self) -> list[dict[str, object]]:
        manifests = {
            "forecasting": self.data.json_docs.get("forecasting.manifest", {}),
            "asset_health": self.data.json_docs.get("asset_health.manifest", {}),
            "outage_prediction": self.data.json_docs.get("outage_prediction.manifest", {}),
            "reliability": self.data.json_docs.get("reliability.manifest", {}),
            "monitoring": self.data.json_docs.get("monitoring.manifest", {}),
            "genai": self.data.json_docs.get("genai.manifest", {}),
        }
        rows = []
        for component, manifest in manifests.items():
            if not manifest:
                continue
            source_run_id = _manifest_run_id(component, manifest)
            rows.append(
                {
                    "run_key": stable_key("RUN", component, source_run_id),
                    "component_name": component,
                    "source_run_id": source_run_id,
                    "run_status": "PASSED",
                    "run_timestamp": manifest.get("assessment_timestamp")
                    or manifest.get("monitoring_timestamp")
                    or manifest.get("query_timestamp")
                    or "",
                    "assessment_start": manifest.get("assessment_start", ""),
                    "assessment_end": manifest.get("assessment_end", ""),
                    "schema_version": _schema_version(component),
                }
            )
        return _sorted_rows(rows, "component_name")

    def dim_alert_reasons(self) -> list[dict[str, object]]:
        values = _sorted_unique(
            [row.get("reason_code", "") for row in self.alerts]
            + [
                row.get("primary_reason_code", "")
                for row in self.health + self.outage + self.reliability
            ]
        )
        return [_unknown_row("reason_key", "reason_code")] + [
            {
                "reason_key": stable_key("RSN", value),
                "reason_code": value,
                "reason_family": _reason_family(value),
                "synthetic_data_flag": True,
            }
            for value in values
        ]

    def dim_metrics(self) -> list[dict[str, object]]:
        values = _sorted_unique(
            [row.get("metric_name", "") for row in self.monitoring + self.alerts]
        )
        return [_unknown_row("metric_key", "metric_name")] + [
            {
                "metric_key": stable_key("MET", value),
                "metric_name": value,
                "metric_group": _metric_group(value),
                "synthetic_data_flag": True,
            }
            for value in values
        ]

    def fact_demand_forecast(self) -> list[dict[str, object]]:
        rows = []
        for source in self.forecasts:
            timestamp = source.get("forecast_timestamp", "")
            rows.append(
                {
                    "forecast_fact_id": stable_key(
                        "FF",
                        source.get("forecast_run_id"),
                        source.get("entity_id"),
                        timestamp,
                        source.get("model_name"),
                    ),
                    "run_key": stable_key("RUN", "forecasting", source.get("forecast_run_id")),
                    "model_key": stable_key(
                        "MDL", "forecasting", source.get("model_name"), source.get("target_name")
                    ),
                    "date_key": _date_key(timestamp),
                    "time_key": _time_key(timestamp),
                    "region_key": stable_key("REG", source.get("grid_region")),
                    "substation_key": stable_key(
                        "SUB",
                        source.get("entity_id")
                        if source.get("entity_type") == "substation"
                        else "",
                    ),
                    "feeder_key": stable_key(
                        "FDR",
                        source.get("entity_id") if source.get("entity_type") == "feeder" else "",
                    ),
                    "forecast_origin": source.get("forecast_origin", ""),
                    "forecast_timestamp": timestamp,
                    "forecast_horizon_intervals": source.get("forecast_horizon_intervals", ""),
                    "target_name": source.get("target_name", ""),
                    "target_unit": source.get("target_unit", ""),
                    "predicted_value": source.get("predicted_value", ""),
                    "prediction_lower": source.get("prediction_lower", ""),
                    "prediction_upper": source.get("prediction_upper", ""),
                    "actual_value": source.get("actual_value", ""),
                    "data_split": source.get("data_split", ""),
                }
            )
        return _sorted_rows(rows, "forecast_fact_id")

    def fact_asset_health(self) -> list[dict[str, object]]:
        rows = []
        for source in self.health:
            asset_id = source.get("asset_id", "")
            components = self.health_components.get(asset_id, {})
            rows.append(
                {
                    "asset_health_fact_id": stable_key(
                        "AHF", source.get("asset_health_run_id"), asset_id
                    ),
                    "run_key": stable_key("RUN", "asset_health", source.get("asset_health_run_id")),
                    "asset_key": stable_key("AST", asset_id),
                    "date_key": _date_key(source.get("assessment_timestamp", "")),
                    "assessment_timestamp": source.get("assessment_timestamp", ""),
                    "health_score": source.get("health_score", ""),
                    "health_band": source.get("health_band", ""),
                    "maintenance_priority": source.get("maintenance_priority", ""),
                    "data_completeness_ratio": source.get("data_completeness_ratio", ""),
                    "age_component_score": source.get(
                        "age_component_score", components.get("age_component_score", "")
                    ),
                    "inspection_component_score": source.get(
                        "inspection_component_score",
                        components.get("inspection_component_score", ""),
                    ),
                    "maintenance_component_score": source.get(
                        "maintenance_component_score",
                        components.get("maintenance_component_score", ""),
                    ),
                    "telemetry_stress_component_score": source.get(
                        "telemetry_stress_component_score",
                        components.get("telemetry_stress_component_score", ""),
                    ),
                    "alarm_component_score": source.get(
                        "alarm_component_score", components.get("alarm_component_score", "")
                    ),
                    "outage_component_score": source.get(
                        "outage_component_score", components.get("outage_component_score", "")
                    ),
                    "primary_reason_code": source.get("primary_reason_code", ""),
                }
            )
        return _sorted_rows(rows, "asset_health_fact_id")

    def fact_outage_risk(self) -> list[dict[str, object]]:
        rows = []
        for source in self.outage:
            timestamp = source.get("observation_timestamp", "")
            rows.append(
                {
                    "outage_risk_fact_id": stable_key(
                        "ORF",
                        source.get("outage_prediction_run_id"),
                        source.get("entity_id"),
                        timestamp,
                        source.get("model_name"),
                    ),
                    "run_key": stable_key(
                        "RUN", "outage_prediction", source.get("outage_prediction_run_id")
                    ),
                    "model_key": stable_key(
                        "MDL", "outage_prediction", source.get("model_name"), "outage_flag"
                    ),
                    "date_key": _date_key(timestamp),
                    "time_key": _time_key(timestamp),
                    "region_key": stable_key("REG", source.get("grid_region")),
                    "substation_key": stable_key("SUB", source.get("substation_id")),
                    "feeder_key": stable_key("FDR", source.get("feeder_id")),
                    **{
                        name: source.get(name, "")
                        for name in (
                            "observation_timestamp",
                            "prediction_window_start",
                            "prediction_window_end",
                            "risk_score",
                            "risk_band",
                            "predicted_outage_flag",
                            "actual_outage_flag",
                            "classification_threshold",
                            "data_split",
                            "data_completeness_ratio",
                            "primary_reason_code",
                        )
                    },
                }
            )
        return _sorted_rows(rows, "outage_risk_fact_id")

    def fact_reliability_kpi(self) -> list[dict[str, object]]:
        rows = []
        for source in self.reliability:
            entity_key = stable_key(
                source.get("entity_type", "ENT").upper()[:3], source.get("entity_id")
            )
            rows.append(
                {
                    "reliability_fact_id": stable_key(
                        "RKF",
                        source.get("reliability_run_id"),
                        source.get("entity_type"),
                        source.get("entity_id"),
                        source.get("period_start"),
                    ),
                    "run_key": stable_key("RUN", "reliability", source.get("reliability_run_id")),
                    "date_key": _date_key(source.get("period_start", "")),
                    "entity_type": source.get("entity_type", ""),
                    "entity_key": entity_key,
                    "region_key": stable_key("REG", source.get("grid_region")),
                    "substation_key": stable_key("SUB", source.get("substation_id")),
                    "feeder_key": stable_key("FDR", source.get("feeder_id")),
                    **{
                        name: source.get(name, "")
                        for name in (
                            "period_start",
                            "period_end",
                            "population_denominator",
                            "outage_count",
                            "planned_outage_count",
                            "unplanned_outage_count",
                            "customer_interruptions",
                            "customer_interruption_minutes",
                            "saifi",
                            "saidi_minutes",
                            "caidi_minutes",
                            "asai",
                            "asui",
                            "reliability_score",
                            "reliability_band",
                            "data_completeness_ratio",
                            "primary_reason_code",
                        )
                    },
                }
            )
        return _sorted_rows(rows, "reliability_fact_id")

    def fact_monitoring_check(self) -> list[dict[str, object]]:
        return [
            {
                "monitoring_check_fact_id": stable_key(
                    "MCF",
                    row.get("monitoring_run_id"),
                    row.get("component_name"),
                    row.get("scope_type"),
                    row.get("scope_id"),
                    row.get("metric_name"),
                ),
                "run_key": stable_key("RUN", "monitoring", row.get("monitoring_run_id")),
                **{
                    name: row.get(name, "")
                    for name in (
                        "component_name",
                        "source_run_id",
                        "scope_type",
                        "scope_id",
                        "monitor_type",
                        "metric_name",
                        "metric_value",
                        "metric_unit",
                        "baseline_value",
                        "threshold",
                        "status",
                        "severity",
                        "reason_code",
                        "sample_size",
                    )
                },
            }
            for row in sorted(
                self.monitoring,
                key=lambda item: (
                    item.get("component_name", ""),
                    item.get("metric_name", ""),
                    item.get("scope_id", ""),
                ),
            )
        ]

    def fact_monitoring_alert(self) -> list[dict[str, object]]:
        return [
            {
                "monitoring_alert_fact_id": stable_key("MAF", row.get("alert_id")),
                "run_key": stable_key("RUN", "monitoring", row.get("monitoring_run_id")),
                "alert_key": stable_key("ALT", row.get("alert_id")),
                **{
                    name: row.get(name, "")
                    for name in (
                        "component_name",
                        "scope_type",
                        "scope_id",
                        "metric_name",
                        "observed_value",
                        "threshold",
                        "severity",
                        "alert_status",
                        "suppressed",
                        "suppression_reason",
                        "reason_code",
                    )
                },
            }
            for row in sorted(self.alerts, key=lambda item: item.get("alert_id", ""))
        ]

    def fact_assistant_response(self) -> list[dict[str, object]]:
        rows = []
        for source in self.responses:
            citation_ids = source.get("citation_ids", [])
            rows.append(
                {
                    "assistant_response_fact_id": stable_key(
                        "ARF", source.get("assistant_run_id"), source.get("query_id")
                    ),
                    "run_key": stable_key("RUN", "genai", source.get("assistant_run_id")),
                    "query_key": stable_key("QRY", source.get("query_id")),
                    "query_category": source.get("query_category", ""),
                    "response_status": source.get("response_status", ""),
                    "retrieval_score": source.get("retrieval_score", ""),
                    "grounding_coverage": source.get("grounding_coverage", ""),
                    "citation_coverage": source.get("citation_coverage", ""),
                    "response_confidence": source.get("response_confidence", ""),
                    "safety_reason_code": source.get("safety_reason_code") or "",
                    "citation_count": len(citation_ids) if isinstance(citation_ids, list) else 0,
                }
            )
        return _sorted_rows(rows, "assistant_response_fact_id")

    def fact_maintenance_priority(self) -> list[dict[str, object]]:
        return [
            {
                "maintenance_priority_fact_id": stable_key(
                    "MPF", row.get("asset_health_run_id"), row.get("asset_id")
                ),
                "run_key": stable_key("RUN", "asset_health", row.get("asset_health_run_id")),
                "asset_key": stable_key("AST", row.get("asset_id")),
                "priority": row.get("priority", ""),
                "health_band": row.get("health_band", ""),
                "criticality_tier": row.get("criticality_tier", ""),
                "primary_reason": row.get("primary_reason", ""),
                "review_recommended": row.get("review_recommended", ""),
            }
            for row in sorted(self.priorities, key=lambda item: item.get("asset_id", ""))
        ]

    def bridge_asset_reason(self) -> list[dict[str, object]]:
        rows = []
        for source in self.health:
            for rank, reason in enumerate(str(source.get("reason_codes", "")).split("|"), start=1):
                if reason:
                    rows.append(
                        {
                            "bridge_asset_reason_id": stable_key(
                                "BAR",
                                source.get("asset_health_run_id"),
                                source.get("asset_id"),
                                reason,
                            ),
                            "asset_health_fact_id": stable_key(
                                "AHF", source.get("asset_health_run_id"), source.get("asset_id")
                            ),
                            "asset_key": stable_key("AST", source.get("asset_id")),
                            "reason_key": stable_key("RSN", reason),
                            "reason_code": reason,
                            "reason_rank": rank,
                        }
                    )
        return _sorted_rows(rows, "bridge_asset_reason_id")

    def bridge_entity_reason(self) -> list[dict[str, object]]:
        rows = []
        for source in self.reliability_reasons:
            rows.append(
                {
                    "bridge_entity_reason_id": stable_key(
                        "BER",
                        source.get("reliability_run_id"),
                        source.get("entity_type"),
                        source.get("entity_id"),
                        source.get("period_start"),
                        source.get("reason_code"),
                    ),
                    "reliability_fact_id": stable_key(
                        "RKF",
                        source.get("reliability_run_id"),
                        source.get("entity_type"),
                        source.get("entity_id"),
                        source.get("period_start"),
                    ),
                    "entity_type": source.get("entity_type", ""),
                    "entity_id": source.get("entity_id", ""),
                    "reason_key": stable_key("RSN", source.get("reason_code")),
                    "reason_code": source.get("reason_code", ""),
                    "reason_rank": source.get("reason_rank", ""),
                }
            )
        return _sorted_rows(rows, "bridge_entity_reason_id")

    def bridge_response_citation(self) -> list[dict[str, object]]:
        rows = []
        for source in self.responses:
            citation_ids = source.get("citation_ids", [])
            if isinstance(citation_ids, list):
                for citation in citation_ids:
                    rows.append(
                        {
                            "bridge_response_citation_id": stable_key(
                                "BRC",
                                source.get("assistant_run_id"),
                                source.get("query_id"),
                                citation,
                            ),
                            "assistant_response_fact_id": stable_key(
                                "ARF", source.get("assistant_run_id"), source.get("query_id")
                            ),
                            "query_key": stable_key("QRY", source.get("query_id")),
                            "citation_id": citation,
                        }
                    )
        return _sorted_rows(rows, "bridge_response_citation_id")


def _dim_date(config: ReportingConfig) -> list[dict[str, object]]:
    start = date.fromisoformat(config.date_dimension_start)
    end = date.fromisoformat(config.date_dimension_end)
    rows = []
    current = start
    while current <= end:
        rows.append(
            {
                "date_key": current.strftime("%Y%m%d"),
                "date": current.isoformat(),
                "day": current.day,
                "day_name": current.strftime("%A"),
                "day_of_week": current.isoweekday(),
                "week_number": int(current.strftime("%V")),
                "month": current.month,
                "month_name": current.strftime("%B"),
                "quarter": (current.month - 1) // 3 + 1,
                "year": current.year,
                "is_weekend": current.isoweekday() >= 6,
            }
        )
        current += timedelta(days=1)
    return rows


def _dim_time() -> list[dict[str, object]]:
    rows = []
    for hour in range(24):
        current = time(hour=hour)
        rows.append(
            {
                "time_key": f"{hour:02d}00",
                "time": current.strftime("%H:%M"),
                "hour": hour,
                "minute": 0,
                "interval_label": f"{hour:02d}:00-{hour:02d}:59",
                "daypart": _daypart(hour),
            }
        )
    return rows


def _relationships() -> list[RelationshipDefinition]:
    specs = [
        ("fact_demand_forecast", "run_key", "dim_component_run", "run_key"),
        ("fact_demand_forecast", "model_key", "dim_model", "model_key"),
        ("fact_demand_forecast", "date_key", "dim_date", "date_key"),
        ("fact_demand_forecast", "time_key", "dim_time", "time_key"),
        ("fact_asset_health", "run_key", "dim_component_run", "run_key"),
        ("fact_asset_health", "asset_key", "dim_asset", "asset_key"),
        ("fact_asset_health", "date_key", "dim_date", "date_key"),
        ("fact_outage_risk", "run_key", "dim_component_run", "run_key"),
        ("fact_outage_risk", "model_key", "dim_model", "model_key"),
        ("fact_reliability_kpi", "run_key", "dim_component_run", "run_key"),
        ("fact_monitoring_check", "run_key", "dim_component_run", "run_key"),
        ("fact_monitoring_alert", "run_key", "dim_component_run", "run_key"),
        ("fact_assistant_response", "run_key", "dim_component_run", "run_key"),
        ("fact_maintenance_priority", "asset_key", "dim_asset", "asset_key"),
    ]
    return [
        RelationshipDefinition(
            from_table=from_table,
            from_column=from_column,
            to_table=to_table,
            to_column=to_column,
            cardinality="many-to-one",
            cross_filter_direction="single",
            active=True,
            description=f"{from_table}.{from_column} filters to {to_table}.{to_column}.",
        )
        for from_table, from_column, to_table, to_column in specs
    ]


def kpi_catalogue() -> list[dict[str, object]]:
    definitions = (
        (
            "KPI_FORECAST_DEMAND",
            "Forecast Demand",
            "Latest modelled demand expectation.",
            "SUM fact_demand_forecast[predicted_value]",
            "fact_demand_forecast",
            "predicted_value",
            "semi-additive",
            "kWh/MW",
            "#,##0.00",
            "contextual",
            "grid_operations",
            "Synthetic forecast output; respect timestamp grain.",
        ),
        (
            "KPI_FORECAST_MAE",
            "Forecast MAE",
            "Mean absolute forecast error.",
            "AVERAGE absolute actual minus predicted at forecast row grain.",
            "fact_demand_forecast",
            "predicted_value,actual_value",
            "non-additive",
            "target unit",
            "#,##0.00",
            "lower_is_better",
            "grid_operations",
            "Recalculate from row errors for selected context.",
        ),
        (
            "KPI_FORECAST_WAPE",
            "Forecast WAPE",
            "Weighted absolute percentage error.",
            "SUM absolute error divided by SUM actual.",
            "fact_demand_forecast",
            "predicted_value,actual_value",
            "non-additive",
            "percent",
            "0.00%",
            "lower_is_better",
            "data_and_model_governance",
            "Use DIVIDE; do not average child percentages.",
        ),
        (
            "KPI_HIGH_RISK_FEEDERS",
            "High-Risk Feeders",
            "Feeders in HIGH or CRITICAL outage-risk bands.",
            "COUNTROWS filtered fact_outage_risk.",
            "fact_outage_risk",
            "risk_band",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "grid_operations",
            "Risk bands are decision-support only.",
        ),
        (
            "KPI_CRITICAL_ASSETS",
            "Critical Asset Count",
            "Assets in CRITICAL health band.",
            "DISTINCTCOUNT asset where latest health_band is CRITICAL.",
            "fact_asset_health",
            "health_band",
            "semi-additive",
            "count",
            "#,##0",
            "lower_is_better",
            "asset_management",
            "Latest assessment context should be selected.",
        ),
        (
            "KPI_P1_MAINT",
            "P1 Maintenance Review Count",
            "Assets with P1 maintenance review priority.",
            "COUNTROWS filtered fact_maintenance_priority.",
            "fact_maintenance_priority",
            "priority",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "asset_management",
            "Review priority is not a work order.",
        ),
        (
            "KPI_P2_MAINT",
            "P2 Maintenance Review Count",
            "Assets with P2 maintenance review priority.",
            "COUNTROWS filtered fact_maintenance_priority.",
            "fact_maintenance_priority",
            "priority",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "asset_management",
            "Review priority is not a work order.",
        ),
        (
            "KPI_SAIFI",
            "SAIFI",
            "Customer interruptions per observed customer.",
            "SUM customer_interruptions divided by SUM population_denominator.",
            "fact_reliability_kpi",
            "customer_interruptions,population_denominator",
            "non-additive",
            "interruptions/customer",
            "0.000",
            "lower_is_better",
            "reliability_engineering",
            "Do not average entity SAIFI.",
        ),
        (
            "KPI_SAIDI",
            "SAIDI",
            "Interruption minutes per observed customer.",
            "SUM customer_interruption_minutes divided by SUM population_denominator.",
            "fact_reliability_kpi",
            "customer_interruption_minutes,population_denominator",
            "non-additive",
            "minutes/customer",
            "0.0",
            "lower_is_better",
            "reliability_engineering",
            "Do not average entity SAIDI.",
        ),
        (
            "KPI_CAIDI",
            "CAIDI",
            "Average duration per interrupted customer.",
            "SUM customer_interruption_minutes divided by SUM customer_interruptions.",
            "fact_reliability_kpi",
            "customer_interruption_minutes,customer_interruptions",
            "non-additive",
            "minutes/interruption",
            "0.0",
            "lower_is_better",
            "reliability_engineering",
            "Use numerator/denominator recalculation.",
        ),
        (
            "KPI_ASAI",
            "ASAI",
            "Availability index.",
            "1 minus ASUI recalculated from outage windows where available.",
            "fact_reliability_kpi",
            "asai",
            "non-additive",
            "ratio",
            "0.0000",
            "higher_is_better",
            "executive_leadership",
            "Synthetic observed-meter denominator.",
        ),
        (
            "KPI_UNPLANNED_OUTAGES",
            "Unplanned Outage Count",
            "Included unplanned outage events.",
            "SUM fact_reliability_kpi[unplanned_outage_count]",
            "fact_reliability_kpi",
            "unplanned_outage_count",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "reliability_engineering",
            "Avoid double-counting mixed hierarchy levels.",
        ),
        (
            "KPI_MEAN_RESTORATION",
            "Mean Restoration Duration",
            "Average restoration duration.",
            "Use outage event numerator and outage count.",
            "fact_reliability_kpi",
            "customer_interruption_minutes,outage_count",
            "non-additive",
            "minutes",
            "0.0",
            "lower_is_better",
            "reliability_engineering",
            "Not a simple average across entities.",
        ),
        (
            "KPI_RELIABILITY_SCORE",
            "Reliability Score",
            "Composite reliability score.",
            "Contextual score from source model.",
            "fact_reliability_kpi",
            "reliability_score",
            "non-additive",
            "score",
            "0.0",
            "higher_is_better",
            "executive_leadership",
            "Composite score is local methodology only.",
        ),
        (
            "KPI_ACTIVE_WARNING",
            "Active Warning Alerts",
            "Unsuppressed warning alerts.",
            "COUNTROWS warning alerts not suppressed.",
            "fact_monitoring_alert",
            "severity,alert_status",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "data_and_model_governance",
            "Local alert records only.",
        ),
        (
            "KPI_ACTIVE_HIGH",
            "Active High Alerts",
            "Unsuppressed high alerts.",
            "COUNTROWS high alerts not suppressed.",
            "fact_monitoring_alert",
            "severity,alert_status",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "data_and_model_governance",
            "Local alert records only.",
        ),
        (
            "KPI_ACTIVE_CRITICAL",
            "Active Critical Alerts",
            "Unsuppressed critical alerts.",
            "COUNTROWS critical alerts not suppressed.",
            "fact_monitoring_alert",
            "severity,alert_status",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "executive_leadership",
            "Local alert records only.",
        ),
        (
            "KPI_STALE_DATASETS",
            "Stale Dataset Count",
            "Datasets flagged stale by monitoring.",
            "COUNTROWS data_freshness checks with non-healthy status.",
            "fact_monitoring_check",
            "monitor_type,status",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "data_and_model_governance",
            "Monitoring profile is local.",
        ),
        (
            "KPI_SCHEMA_DRIFT",
            "Schema Drift Count",
            "Schema drift checks requiring review.",
            "COUNTROWS schema_drift checks with non-healthy status.",
            "fact_monitoring_check",
            "monitor_type,status",
            "additive",
            "count",
            "#,##0",
            "lower_is_better",
            "data_and_model_governance",
            "Local schema comparison only.",
        ),
        (
            "KPI_GROUNDED_RATE",
            "Grounded Assistant Response Rate",
            "Share of assistant responses grounded in evidence.",
            "Grounded responses divided by responses.",
            "fact_assistant_response",
            "response_status",
            "non-additive",
            "percent",
            "0.0%",
            "higher_is_better",
            "grid_operations",
            "Assistant is deterministic local template.",
        ),
        (
            "KPI_CITATION_COVERAGE",
            "Citation Coverage",
            "Average cited evidence coverage.",
            "AVERAGE citation_coverage at response grain.",
            "fact_assistant_response",
            "citation_coverage",
            "non-additive",
            "percent",
            "0.0%",
            "higher_is_better",
            "data_and_model_governance",
            "Citations point to repository-local evidence.",
        ),
    )
    return [
        {
            "kpi_id": item[0],
            "kpi_name": item[1],
            "business_definition": item[2],
            "technical_definition": item[3],
            "source_table": item[4],
            "source_columns": item[5],
            "aggregation_method": item[6],
            "unit": item[7],
            "format_string": item[8],
            "direction": item[9],
            "audience": item[10],
            "limitations": item[11],
        }
        for item in definitions
    ]


def _primary_key(table_name: str, rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    candidates = [
        column
        for column in rows[0]
        if column.endswith("_fact_id") or column.endswith("_key") or column.startswith("bridge_")
    ]
    return candidates[0] if candidates else ""


def _critical_fields(table_name: str) -> tuple[str, ...]:
    if table_name.startswith("fact_"):
        return ("run_key",)
    return ()


def _unknown_row(key_name: str, natural_name: str) -> dict[str, object]:
    return {key_name: UNKNOWN_KEY, natural_name: UNKNOWN, "synthetic_data_flag": True}


def _sorted_unique(values: Sequence[object]) -> list[str]:
    return sorted({str(value) for value in values if value not in (None, "")})


def _sorted_rows(
    rows: Iterable[Mapping[str, object]],
    key: str,
) -> list[dict[str, object]]:
    return sorted([dict(row) for row in rows], key=lambda item: str(item.get(key, "")))


def _model_row(
    component: str, model_name: object, target_name: object, target_unit: object, grain: object
) -> dict[str, object]:
    return {
        "model_key": stable_key("MDL", component, model_name, target_name),
        "component_name": component,
        "model_name": model_name or UNKNOWN,
        "model_version": "0.1.0",
        "target_name": target_name or UNKNOWN,
        "target_unit": target_unit or "",
        "entity_grain": grain or UNKNOWN,
        "synthetic_data_flag": True,
    }


def _date_key(timestamp: object) -> str:
    text = str(timestamp)
    if not text:
        return UNKNOWN_KEY
    return text[:10].replace("-", "")


def _time_key(timestamp: object) -> str:
    text = str(timestamp)
    if "T" not in text:
        return UNKNOWN_KEY
    return text.split("T", 1)[1][:5].replace(":", "")


def _daypart(hour: int) -> str:
    if hour < 6:
        return "overnight"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _manifest_run_id(component: str, manifest: dict[str, object]) -> str:
    keys = {
        "forecasting": "forecast_run_id",
        "asset_health": "run_id",
        "outage_prediction": "run_id",
        "reliability": "run_id",
        "monitoring": "monitoring_run_id",
        "genai": "assistant_run_id",
    }
    return str(manifest.get(keys[component], UNKNOWN))


def _schema_version(component: str) -> str:
    return {
        "forecasting": "4.0.0",
        "asset_health": "5.0.0",
        "outage_prediction": "6.0.0",
        "reliability": "7.0.0",
        "monitoring": "8.0.0",
        "genai": "9.0.0",
    }.get(component, "")


def _reason_family(reason: str) -> str:
    if "OUTAGE" in reason:
        return "outage"
    if "ALERT" in reason or "QUALITY" in reason or "SCHEMA" in reason:
        return "monitoring"
    if "INSUFFICIENT" in reason:
        return "data_completeness"
    return "operational"


def _metric_group(metric: str) -> str:
    if "drift" in metric:
        return "drift"
    if "rate" in metric:
        return "rate"
    if "status" in metric:
        return "status"
    return "measurement"
