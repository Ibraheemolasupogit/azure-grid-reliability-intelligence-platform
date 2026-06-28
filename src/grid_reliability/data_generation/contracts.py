"""Machine-readable data contract loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from grid_reliability.common.exceptions import ConfigurationError


def load_contract(path: Path | str) -> dict[str, Any]:
    contract_path = Path(path)
    if not contract_path.exists():
        raise ConfigurationError(f"Data contract not found: {contract_path}")
    with contract_path.open("r", encoding="utf-8") as contract_file:
        raw = yaml.safe_load(contract_file) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Data contract must contain a mapping: {contract_path}")
    for key in ("dataset", "schema_version", "fields", "format"):
        if key not in raw:
            raise ConfigurationError(f"Data contract {contract_path} missing required key: {key}")
    if not isinstance(raw["fields"], list):
        raise ConfigurationError(f"Data contract fields must be a list: {contract_path}")
    return raw


def load_contracts(directory: Path | str) -> dict[str, dict[str, Any]]:
    root = Path(directory)
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.yaml")):
        contract = load_contract(path)
        contracts[str(contract["dataset"])] = contract
    return contracts
