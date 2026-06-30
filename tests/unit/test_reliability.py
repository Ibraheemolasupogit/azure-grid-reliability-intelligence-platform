from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from grid_reliability.common import ConfigurationError
from grid_reliability.data_generation.config import load_generation_config
from grid_reliability.data_generation.pipeline import generate_datasets
from grid_reliability.ingestion.config import load_ingestion_config
from grid_reliability.ingestion.pipeline import run_ingestion
from grid_reliability.reliability.config import load_reliability_config
from grid_reliability.reliability.data import load_inputs
from grid_reliability.reliability.kpis import merged_outage_minutes, reliability_kpis
from grid_reliability.reliability.outage_classification import classify_outages
from grid_reliability.reliability.pipeline import main, run_reliability
from grid_reliability.reliability.population import build_population

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_reliability_config_validation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    good = _write_reliability_config(workspace)
    config = load_reliability_config(good, project_root=workspace)
    assert config.period_frequency.value == "full"

    with pytest.raises(ConfigurationError, match="assessment_start"):
        load_reliability_config(
            _write_reliability_config(
                workspace,
                assessment_start="2026-01-02T00:00:00Z",
                assessment_end="2026-01-01T00:00:00Z",
            ),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="aggregation_levels"):
        load_reliability_config(
            _write_reliability_config(workspace, aggregation_levels=["asset"]),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="component_weights"):
        load_reliability_config(
            _write_reliability_config(
                workspace,
                component_weights={**_weights(), "availability": 0.3},
            ),
            project_root=workspace,
        )
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_reliability_config(
            _write_reliability_config(workspace, interim_root="../raw"),
            project_root=workspace,
        )


def test_population_denominators_are_unique_and_hierarchical(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_reliability_config(_write_reliability_config(workspace), project_root=workspace)
    datasets, _, _ = load_inputs(workspace / config.interim_root, config)
    populations = build_population(datasets, config)

    feeder_populations = {
        item.entity.entity_id: item.observed_meter_count
        for item in populations
        if item.entity.entity_type.value == "feeder"
    }
    region_populations = {
        item.entity.entity_id: item.observed_meter_count
        for item in populations
        if item.entity.entity_type.value == "grid_region"
    }
    assert feeder_populations == {"FDR-NORTH-001-01": 3, "FDR-SOUTH-001-01": 3}
    assert region_populations == {"GRID-NORTH": 3, "GRID-SOUTH": 3}


def test_outage_classification_and_kpi_formulas(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    config = load_reliability_config(_write_reliability_config(workspace), project_root=workspace)
    outage = _outage("OUT-1", duration=60, customers=10)
    planned = {**outage, "outage_id": "OUT-2", "outage_type": "planned", "planned_flag": True}
    classified, excluded = classify_outages([outage, planned], config)
    assert excluded == 0
    assert [row.outage_type for row in classified] == ["unplanned", "planned"]

    kpis = reliability_kpis([classified[0]], population=5, period_minutes=120, config=config)
    assert kpis["saifi"] == 2
    assert kpis["saidi_minutes"] == 120
    assert kpis["caidi_minutes"] == 60
    assert kpis["asai"] == 0.5
    assert kpis["asui"] == 0.5
    assert kpis["ctaidi_minutes"] is None
    assert kpis["caifi"] is None


def test_overlap_merges_availability_windows(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    config = load_reliability_config(_write_reliability_config(workspace), project_root=workspace)
    first = classify_outages([_outage("OUT-1", duration=60, customers=1)], config)[0][0]
    second_raw = _outage("OUT-2", duration=60, customers=1)
    second_raw["outage_start"] = "2026-01-01T00:30:00Z"
    second_raw["restoration_time"] = "2026-01-01T01:30:00Z"
    second = classify_outages([second_raw], config)[0][0]
    minutes, overlaps = merged_outage_minutes([first, second])
    assert minutes == 90
    assert overlaps == 1


def test_pipeline_writes_outputs_metrics_manifest_and_reports(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    config = load_reliability_config(_write_reliability_config(workspace), project_root=workspace)
    result = run_reliability(config, project_root=workspace)

    assert result.result_count == 6
    assert result.kpi_path.exists()
    assert result.metrics_path.exists()
    assert result.manifest_path.exists()
    assert result.report_paths["performance"].exists()
    summary = result.system_summary
    assert summary["total_outages"] == 2
    assert summary["system_saifi"] == pytest.approx(20.1666666667)
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["counts_by_reliability_band"] == {"WEAK": 6}


def test_cli_success_filter_and_missing_input_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _generate_and_ingest(workspace)
    monkeypatch.chdir(workspace)
    config_path = _write_reliability_config(workspace)
    assert main(["--config", str(config_path), "--run-id", "cli-reliability"]) == 0
    assert (
        main(
            [
                "--config",
                str(config_path),
                "--aggregation-level",
                "feeder",
                "--entity-id",
                "FDR-NORTH-001-01",
                "--run-id",
                "north-feeder",
            ]
        )
        == 0
    )
    assert main(["--config", str(config_path), "--interim-root", "data/not-present"]) == 3


def _workspace(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs").mkdir(exist_ok=True)
    shutil.copy(PROJECT_ROOT / "configs/base.yaml", tmp_path / "configs/base.yaml")
    shutil.copytree(
        PROJECT_ROOT / "configs/data_contracts",
        tmp_path / "configs/data_contracts",
        dirs_exist_ok=True,
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


def _generate_and_ingest(workspace: Path) -> None:
    generation_config = load_generation_config(
        PROJECT_ROOT / "configs/synthetic_data_ci.yaml",
        project_root=PROJECT_ROOT,
    )
    generate_datasets(
        replace(generation_config, output_root=Path("data/raw")),
        project_root=workspace,
    )
    ingestion_config_path = _write_ingestion_config(workspace)
    ingestion_config = load_ingestion_config(ingestion_config_path, project_root=workspace)
    run_ingestion(ingestion_config, project_root=workspace)


def _write_ingestion_config(workspace: Path) -> Path:
    path = workspace / "configs/ingestion_test.yaml"
    path.write_text(
        "\n".join(
            [
                "profile: test",
                "source_root: data/raw",
                "interim_root: data/interim",
                "quarantine_root: data/quarantine",
                "report_root: reports/ingestion",
                "contract_root: configs/data_contracts",
                "manifest_filename: _manifest.json",
                "verify_manifest_checksums: true",
                "require_manifest: true",
                "fail_on_missing_dataset: true",
                "fail_on_contract_error: true",
                "maximum_error_rate: 0.0",
                "batch_size: 25",
                "timezone: UTC",
                "normalised_timestamp_format: iso8601_utc",
                "run_id_strategy: deterministic",
                "write_format: jsonl",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_reliability_config(workspace: Path, **overrides: object) -> Path:
    values = {
        "profile": "ci",
        "interim_root": "data/interim",
        "output_root": "outputs/reliability",
        "report_root": "reports/reliability",
        "assessment_start": "2026-01-01T00:00:00Z",
        "assessment_end": "2026-01-02T00:00:00Z",
        "aggregation_levels": ["grid_region", "substation", "feeder"],
        "period_frequency": "full",
        "include_planned_outages": True,
        "include_unplanned_outages": True,
        "customer_population_method": "observed_smart_meters",
        "minimum_population": 1,
        "minimum_outage_duration_minutes": 0,
        "maximum_outage_duration_minutes": 1440,
        "sustained_interruption_threshold_minutes": 5,
        "restoration_target_minutes": 180,
        "kpi_precision": 6,
        "score_direction": "higher_is_better",
        "component_weights": _weights(),
        "benchmark_method": "peer_median",
        "benchmark_scope": "entity_type",
        "reliability_band_thresholds": {"weak_max": 50, "watch_max": 70, "stable_max": 85},
        "minimum_data_completeness": 0.5,
        "schema_version": "7.0.0",
        "run_id_strategy": "deterministic",
        "max_reason_codes": 5,
    }
    values.update(overrides)
    path = workspace / "configs/reliability_test.yaml"
    path.write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in values.items()),
        encoding="utf-8",
    )
    return path


def _weights() -> dict[str, float]:
    return {
        "interruption_frequency": 0.25,
        "interruption_duration": 0.25,
        "restoration": 0.15,
        "availability": 0.20,
        "severe_weather_resilience": 0.05,
        "equipment_outage": 0.05,
        "data_completeness": 0.05,
    }


def _outage(outage_id: str, *, duration: int, customers: int) -> dict[str, object]:
    return {
        "outage_id": outage_id,
        "outage_start": "2026-01-01T00:00:00Z",
        "restoration_time": f"2026-01-01T{duration // 60:02d}:{duration % 60:02d}:00Z",
        "duration_minutes": duration,
        "grid_region": "GRID-NORTH",
        "substation_id": "SUB-NORTH-001",
        "feeder_id": "FDR-NORTH-001-01",
        "primary_asset_id": "AST-X",
        "outage_type": "unplanned",
        "cause_category": "equipment_failure",
        "customers_interrupted": customers,
        "estimated_load_lost_mw": 1.0,
        "planned_flag": False,
        "severe_weather_related": False,
        "protection_operated": True,
        "restoration_method": "field_repair",
        "incident_severity": "medium",
        "data_quality_flag": "GOOD",
        "schema_version": "2.0.0",
    }
