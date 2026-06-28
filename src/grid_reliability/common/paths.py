"""Project path resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved local filesystem paths used by the foundation layer."""

    project_root: Path
    data_root: Path
    output_root: Path
    raw_data: Path
    interim_data: Path
    processed_data: Path
    reports: Path


def resolve_project_root(start: Path | None = None) -> Path:
    """Resolve the repository root by walking up to `pyproject.toml`."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return current


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def resolve_project_paths(
    *,
    project_root: Path | None = None,
    data_root: str = "data",
    output_root: str = "outputs",
    raw_data: str = "data/raw",
    interim_data: str = "data/interim",
    processed_data: str = "data/processed",
    reports: str = "reports",
) -> ProjectPaths:
    """Resolve configured local directories without creating runtime data."""
    root = (project_root or resolve_project_root()).resolve()
    return ProjectPaths(
        project_root=root,
        data_root=_resolve_path(root, data_root),
        output_root=_resolve_path(root, output_root),
        raw_data=_resolve_path(root, raw_data),
        interim_data=_resolve_path(root, interim_data),
        processed_data=_resolve_path(root, processed_data),
        reports=_resolve_path(root, reports),
    )
