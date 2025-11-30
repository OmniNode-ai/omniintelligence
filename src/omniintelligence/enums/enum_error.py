"""
Error severity enums for omniintelligence.

Contains error severity levels.
"""

from enum import Enum


class EnumErrorSeverity(str, Enum):
    """Error severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


__all__ = [
    "EnumErrorSeverity",
]
