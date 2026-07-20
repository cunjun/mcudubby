class McuBuddyError(Exception):
    """Base exception for McuBuddy."""


class ConfigurationError(McuBuddyError):
    """Raised when required configuration is missing."""


class BackendUnavailableError(McuBuddyError):
    """Raised when an optional hardware backend is unavailable."""
