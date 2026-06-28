"""Project-specific exception types."""


class GridReliabilityError(Exception):
    """Base exception for platform foundation failures."""


class ConfigurationError(GridReliabilityError):
    """Raised when local configuration is invalid or incomplete."""
