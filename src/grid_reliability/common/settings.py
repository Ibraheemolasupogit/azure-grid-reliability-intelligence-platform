"""Application settings loaded from local configuration and environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.environment import EnvironmentName, validate_environment_name
from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.paths import ProjectPaths, resolve_project_paths


@dataclass(frozen=True)
class AppSettings:
    """Typed foundation settings for local execution."""

    project_name: str
    environment: EnvironmentName
    timezone: str
    random_seed: int
    log_level: str
    json_logs: bool
    paths: ProjectPaths
    azure_service_mapping: dict[str, str]
    planned_components: tuple[str, ...]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file) or {}

    if not isinstance(raw_config, dict):
        raise ConfigurationError(f"Configuration file must contain a mapping: {path}")
    return raw_config


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section '{name}' must be a mapping.")
    return value


def _string_mapping(config: dict[str, Any], name: str) -> dict[str, str]:
    value = _section(config, name)
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ConfigurationError(f"Configuration section '{name}' must map strings to strings.")
    return dict(value)


def load_settings(
    config_path: Path | str = "configs/base.yaml",
    *,
    project_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> AppSettings:
    """Load typed application settings.

    Azure credentials are intentionally optional at this stage. Missing Azure
    environment variables do not prevent local foundation code from running.
    """
    root = (project_root or Path.cwd()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path

    env = environ if environ is not None else os.environ
    config = _read_yaml(path)

    project = _section(config, "project")
    runtime = _section(config, "runtime")
    path_config = _section(config, "paths")
    logging_config = _section(config, "logging")
    pipeline_components = _section(config, "pipeline_components")

    environment = validate_environment_name(
        env.get("APP_ENV", str(runtime.get("environment", "local")))
    )
    data_root = env.get("DATA_ROOT", str(path_config.get("data_root", "data")))
    output_root = env.get("OUTPUT_ROOT", str(path_config.get("output_root", "outputs")))

    planned = pipeline_components.get("planned", ())
    if not isinstance(planned, list) or not all(isinstance(item, str) for item in planned):
        raise ConfigurationError(
            "Configuration section 'pipeline_components.planned' must be a list."
        )

    return AppSettings(
        project_name=str(project.get("name", "azure-grid-reliability-intelligence-platform")),
        environment=environment,
        timezone=str(runtime.get("timezone", "UTC")),
        random_seed=int(runtime.get("random_seed", 42)),
        log_level=env.get("LOG_LEVEL", str(logging_config.get("level", "INFO"))),
        json_logs=bool(logging_config.get("json", False)),
        paths=resolve_project_paths(
            project_root=root,
            data_root=data_root,
            output_root=output_root,
            raw_data=str(path_config.get("raw_data", "data/raw")),
            interim_data=str(path_config.get("interim_data", "data/interim")),
            processed_data=str(path_config.get("processed_data", "data/processed")),
            reports=str(path_config.get("reports", "reports")),
        ),
        azure_service_mapping=_string_mapping(config, "azure_service_mapping"),
        planned_components=tuple(planned),
    )
