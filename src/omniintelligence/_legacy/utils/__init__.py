"""Utility modules for omniintelligence (legacy location).

This module imports directly from the local log_sanitizer implementation.
For the public API, use omniintelligence.utils instead.
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
