"""Utility modules for omniintelligence.

This module contains log sanitization utilities.
For public API imports, use: omniintelligence.utils.log_sanitizer
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
