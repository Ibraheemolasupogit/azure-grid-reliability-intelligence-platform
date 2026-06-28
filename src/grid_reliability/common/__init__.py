"""Shared foundation utilities for the grid reliability platform."""

from grid_reliability.common.environment import EnvironmentName, validate_environment_name
from grid_reliability.common.exceptions import ConfigurationError, GridReliabilityError
from grid_reliability.common.logging import configure_logging
from grid_reliability.common.paths import ProjectPaths, resolve_project_paths
from grid_reliability.common.settings import AppSettings, load_settings

__all__ = [
    "AppSettings",
    "ConfigurationError",
    "EnvironmentName",
    "GridReliabilityError",
    "ProjectPaths",
    "configure_logging",
    "load_settings",
    "resolve_project_paths",
    "validate_environment_name",
]
