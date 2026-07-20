class McuBubbyError(Exception):
    """Base exception for McuBubby."""


class ConfigurationError(McuBubbyError):
    """Raised when required configuration is missing."""


class BackendUnavailableError(McuBubbyError):
    """Raised when an optional hardware backend is unavailable."""
