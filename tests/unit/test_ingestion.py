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
from grid_reliability.ingestion.discovery import discover_sources
from grid_reliability.ingestion.manifest import verify_source_manifest
from grid_reliability.ingestion.pipeline import main, run_ingestion
from grid_reliability.ingestion.readers import JsonlEventReader, read_dataset
from grid_reliability.validation.quality_codes import IssueCode, documented_issue_codes

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    shutil.copy(PROJECT_ROOT / "configs/base.yaml", tmp_path / "configs/base.yaml")
    shutil.copytree(PROJECT_ROOT / "configs/data_contracts", tmp_path / "configs/data_contracts")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


def _generate_sources(workspace: Path) -> None:
    generation_config = load_generation_config(
        PROJECT_ROOT / "configs/synthetic_data_ci.yaml",
        project_root=PROJECT_ROOT,
    )
    generate_datasets(
        replace(generation_config, output_root=Path("data/raw")), project_root=workspace
    )


def _write_ingestion_config(workspace: Path, **overrides: object) -> Path:
    values = {
        "profile": "test",
        "source_root": "data/raw",
        "interim_root": "data/interim",
        "quarantine_root": "data/quarantine",
        "report_root": "reports/ingestion",
        "contract_root": "configs/data_contracts",
        "manifest_filename": "_manifest.json",
        "verify_manifest_checksums": True,
        "require_manifest": True,
        "fail_on_missing_dataset": True,
        "fail_on_contract_error": True,
        "maximum_error_rate": 0.0,
        "batch_size": 3,
        "timezone": "UTC",
        "normalised_timestamp_format": "iso8601_utc",
        "run_id_strategy": "deterministic",
        "write_format": "jsonl",
    }
    values.update(overrides)
    path = workspace / "configs/ingestion_test.yaml"
    path.write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in values.items()), encoding="utf-8"
    )
    return path


def test_ingestion_config_validates_paths_and_options(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    good = _write_ingestion_config(workspace)
    config = load_ingestion_config(good, project_root=workspace)
    assert config.batch_size == 3

    bad_path = _write_ingestion_config(workspace, source_root="../outside")
    with pytest.raises(ConfigurationError, match="safe relative path"):
        load_ingestion_config(bad_path, project_root=workspace)

    overlap = _write_ingestion_config(workspace, interim_root="data/raw/interim")
    with pytest.raises(ConfigurationError, match="must not overlap"):
        load_ingestion_config(overlap, project_root=workspace)

    bad_batch = _write_ingestion_config(workspace, batch_size=0)
    with pytest.raises(ConfigurationError, match="positive integer"):
        load_ingestion_config(bad_batch, project_root=workspace)

    bad_rate = _write_ingestion_config(workspace, maximum_error_rate=1.5)
    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        load_ingestion_config(bad_rate, project_root=workspace)

    bad_format = _write_ingestion_config(workspace, write_format="csv")
    with pytest.raises(ConfigurationError, match="write_format"):
        load_ingestion_config(bad_format, project_root=workspace)


def test_discovery_and_manifest_validation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_sources(workspace)
    config = load_ingestion_config(_write_ingestion_config(workspace), project_root=workspace)
    contracts = _contracts(workspace)
    source_root = workspace / config.source_root

    discovery = discover_sources(
        source_root=source_root,
        contracts=contracts,
        fail_on_missing_dataset=True,
        manifest_filename=config.manifest_filename,
    )
    assert [dataset.dataset_name for dataset in discovery.datasets] == sorted(contracts)
    assert not discovery.has_errors

    manifest = verify_source_manifest(
        source_root=source_root,
        manifest_filename=config.manifest_filename,
        contracts=contracts,
        require_manifest=True,
        verify_checksums=True,
        expected_project_name="azure-grid-reliability-intelligence-platform",
    )
    assert not manifest.has_errors

    (source_root / "unexpected.txt").write_text("ignored", encoding="utf-8")
    discovery_with_extra = discover_sources(
        source_root=source_root,
        contracts=contracts,
        fail_on_missing_dataset=True,
        manifest_filename=config.manifest_filename,
    )
    assert any(
        issue.issue_code == IssueCode.FILE_UNEXPECTED for issue in discovery_with_extra.issues
    )

    (source_root / "weather_data.csv").write_text("bad\n", encoding="utf-8")
    checksum_failure = verify_source_manifest(
        source_root=source_root,
        manifest_filename=config.manifest_filename,
        contracts=contracts,
        require_manifest=True,
        verify_checksums=True,
        expected_project_name="azure-grid-reliability-intelligence-platform",
    )
    assert any(
        issue.issue_code == IssueCode.MANIFEST_CHECKSUM_MISMATCH
        for issue in checksum_failure.issues
    )


def test_missing_and_malformed_manifest_are_classified(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_sources(workspace)
    contracts = _contracts(workspace)
    manifest_path = workspace / "data/raw/_manifest.json"
    manifest_path.unlink()
    missing = verify_source_manifest(
        source_root=workspace / "data/raw",
        manifest_filename="_manifest.json",
        contracts=contracts,
        require_manifest=True,
        verify_checksums=True,
        expected_project_name="azure-grid-reliability-intelligence-platform",
    )
    assert missing.issues[0].issue_code == IssueCode.MANIFEST_MISSING
    manifest_path.write_text("{not-json", encoding="utf-8")
    malformed = verify_source_manifest(
        source_root=workspace / "data/raw",
        manifest_filename="_manifest.json",
        contracts=contracts,
        require_manifest=True,
        verify_checksums=True,
        expected_project_name="azure-grid-reliability-intelligence-platform",
    )
    assert malformed.issues[0].issue_code == IssueCode.MANIFEST_MALFORMED


def test_readers_track_records_and_micro_batches(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_sources(workspace)
    contracts = _contracts(workspace)
    discovery = discover_sources(
        source_root=workspace / "data/raw",
        contracts=contracts,
        fail_on_missing_dataset=True,
        manifest_filename="_manifest.json",
    )
    smart = next(
        dataset for dataset in discovery.datasets if dataset.dataset_name == "smart_meter_events"
    )
    records = list(read_dataset(smart, ingestion_run_id="test", ingested_at=_utc_now()))
    assert records[0].source_record_number == 1
    assert records[0].parsed_record is not None
    batches = list(
        JsonlEventReader(smart, ingestion_run_id="test", ingested_at=_utc_now()).micro_batches(10)
    )
    assert len(batches[0]) == 10

    malformed_path = smart.path
    malformed_path.write_text('{"ok": true}\n{bad\n', encoding="utf-8")
    malformed = list(read_dataset(smart, ingestion_run_id="test", ingested_at=_utc_now()))
    assert any(record.parse_issues for record in malformed)

    malformed_path.write_text("", encoding="utf-8")
    empty = list(read_dataset(smart, ingestion_run_id="test", ingested_at=_utc_now()))
    assert empty[0].parse_issues[0].issue_code == IssueCode.EMPTY_FILE


def test_pipeline_writes_interim_reports_and_warning_status(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_sources(workspace)
    config = load_ingestion_config(_write_ingestion_config(workspace), project_root=workspace)
    result = run_ingestion(config, project_root=workspace)

    assert result.status.value == "PASSED_WITH_WARNINGS"
    assert result.metrics.total_metrics().source_records_discovered == 88
    assert result.metrics.total_metrics().valid_records == 88
    assert result.metrics.total_metrics().invalid_records == 0
    assert (workspace / "data/interim/smart_meter_events.jsonl").exists()
    assert result.metrics_path.exists()
    assert result.audit_manifest_path.exists()
    assert result.quality_report_path.exists()


def test_pipeline_quarantines_invalid_relationship_and_cli_exits_nonzero(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _generate_sources(workspace)
    smart_path = workspace / "data/raw/smart_meter_events.jsonl"
    first_line = json.loads(smart_path.read_text(encoding="utf-8").splitlines()[0])
    first_line["meter_id"] = "MTR-NOTIN-001-01-001"
    remaining = smart_path.read_text(encoding="utf-8").splitlines()[1:]
    smart_path.write_text(
        json.dumps(first_line, sort_keys=True, separators=(",", ":"))
        + "\n"
        + "\n".join(remaining)
        + "\n",
        encoding="utf-8",
    )
    manifest_path = workspace / "data/raw/_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"]["smart_meter_events"]["file_size_bytes"] = smart_path.stat().st_size
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    config_path = _write_ingestion_config(
        workspace,
        fail_on_contract_error=False,
        verify_manifest_checksums=False,
    )
    config = load_ingestion_config(config_path, project_root=workspace)
    result = run_ingestion(config, project_root=workspace, run_id="invalid")

    assert result.status.value == "FAILED_QUALITY_THRESHOLD"
    assert result.metrics.total_metrics().invalid_records == 1
    quarantine_file = workspace / "data/quarantine/invalid/smart_meter_events.jsonl"
    assert quarantine_file.exists()
    assert "FOREIGN_KEY_NOT_FOUND" in quarantine_file.read_text(encoding="utf-8")
    assert main(["--config", str(config_path), "--run-id", "cli-invalid"]) == 1


def test_issue_code_taxonomy_is_documented() -> None:
    documented = documented_issue_codes()
    assert documented["REQUIRED_FIELD_MISSING"]
    assert set(documented) >= {code.value for code in IssueCode}


def _contracts(workspace: Path) -> dict[str, dict[str, object]]:
    from grid_reliability.data_generation.contracts import load_contracts

    return load_contracts(workspace / "configs/data_contracts")


def _utc_now():
    from datetime import UTC, datetime

    return datetime.now(tz=UTC)
