class McudubbyError(Exception):
    """Base exception for mcudubby."""


class ConfigurationError(McudubbyError):
    """Raised when required configuration is missing."""


class BackendUnavailableError(McudubbyError):
    """Raised when an optional hardware backend is unavailable."""
