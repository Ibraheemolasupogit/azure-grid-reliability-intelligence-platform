from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pytest
import yaml

from grid_reliability.common import ConfigurationError
from grid_reliability.common.environment import validate_environment_name
from grid_reliability.common.logging import JsonFormatter, configure_logging
from grid_reliability.common.paths import resolve_project_paths, resolve_project_root
from grid_reliability.common.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_package_imports() -> None:
    package = importlib.import_module("grid_reliability")

    assert package.__version__ == "0.1.0"


def test_load_settings_from_base_config() -> None:
    settings = load_settings(project_root=PROJECT_ROOT, environ={})

    assert settings.project_name == "azure-grid-reliability-intelligence-platform"
    assert settings.environment == "local"
    assert settings.paths.data_root == PROJECT_ROOT / "data"
    assert settings.azure_service_mapping["meter_ingestion"] == "Azure Event Hubs"
    assert "forecasting" in settings.planned_components


def test_environment_overrides_for_paths_and_logging() -> None:
    settings = load_settings(
        project_root=PROJECT_ROOT,
        environ={"APP_ENV": "test", "DATA_ROOT": "tmp/data", "LOG_LEVEL": "DEBUG"},
    )

    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert settings.paths.data_root == PROJECT_ROOT / "tmp/data"


def test_default_directory_resolution() -> None:
    paths = resolve_project_paths(project_root=PROJECT_ROOT)

    assert paths.raw_data == PROJECT_ROOT / "data/raw"
    assert paths.interim_data == PROJECT_ROOT / "data/interim"
    assert paths.processed_data == PROJECT_ROOT / "data/processed"
    assert paths.output_root == PROJECT_ROOT / "outputs"


def test_invalid_environment_handling() -> None:
    with pytest.raises(ConfigurationError, match="Unsupported APP_ENV"):
        validate_environment_name("productionish")


def test_logging_initialisation() -> None:
    configure_logging("INFO", json_logs=True)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) == 1


def test_json_formatter_outputs_structured_payload() -> None:
    record = logging.LogRecord(
        name="grid_reliability.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="quality gate",
        args=(),
        exc_info=None,
    )

    payload = yaml.safe_load(JsonFormatter().format(record))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "grid_reliability.test"
    assert payload["message"] == "quality gate"


def test_invalid_log_level_raises() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging("LOUD")


def test_project_root_resolution_from_nested_path() -> None:
    assert resolve_project_root(PROJECT_ROOT / "tests/unit") == PROJECT_ROOT


def test_missing_config_file_raises() -> None:
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_settings("missing.yaml", project_root=PROJECT_ROOT, environ={})


def test_invalid_config_section_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "base.yaml"
    config_path.write_text("project: invalid\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="section 'project' must be a mapping"):
        load_settings(config_path, project_root=PROJECT_ROOT, environ={})


def test_no_secret_values_committed() -> None:
    candidates = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "configs/base.yaml",
    ]
    suspicious_tokens = ("AccountKey=", "SharedAccessKey=", "-----BEGIN", "password=")

    for path in candidates:
        content = path.read_text(encoding="utf-8")
        assert not any(token in content for token in suspicious_tokens)
