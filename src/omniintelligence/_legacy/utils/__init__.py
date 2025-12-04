"""Utility modules for omniintelligence (legacy location).

This module provides log sanitization utilities.
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
