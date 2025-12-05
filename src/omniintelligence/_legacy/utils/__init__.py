"""Legacy utility modules for omniintelligence.

NOTE: This is the legacy/internal implementation location.
For public API imports, use: omniintelligence.utils.log_sanitizer

This module contains the actual implementation of log sanitization utilities.
These utilities are pending migration to a canonical ONEX node structure.
"""

from omniintelligence._legacy.utils.log_sanitizer import (
    LogSanitizer,
    get_log_sanitizer,
    sanitize_logs,
)

__all__ = [
    "LogSanitizer",
    "get_log_sanitizer",
    "sanitize_logs",
]
