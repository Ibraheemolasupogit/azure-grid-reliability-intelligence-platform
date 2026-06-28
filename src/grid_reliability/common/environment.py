"""Environment name validation."""

from typing import Literal

from grid_reliability.common.exceptions import ConfigurationError

EnvironmentName = Literal["local", "dev", "test", "staging", "prod"]

VALID_ENVIRONMENTS: frozenset[str] = frozenset({"local", "dev", "test", "staging", "prod"})


def validate_environment_name(value: str) -> EnvironmentName:
    """Return a supported environment name or raise a clear configuration error."""
    normalized = value.strip().lower()
    if normalized not in VALID_ENVIRONMENTS:
        valid = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ConfigurationError(f"Unsupported APP_ENV '{value}'. Expected one of: {valid}.")
    return normalized  # type: ignore[return-value]
