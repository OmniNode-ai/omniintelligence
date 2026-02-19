"""Log level enum for runtime configuration."""

from enum import StrEnum


class EnumLogLevel(StrEnum):
    """Log level enumeration for runtime configuration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


__all__ = ["EnumLogLevel"]
