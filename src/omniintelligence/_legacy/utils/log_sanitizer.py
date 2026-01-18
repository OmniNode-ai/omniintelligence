"""
Log Sanitization Service - Legacy Re-export Module

This module re-exports the log sanitizer from its canonical location.
The canonical implementation is in omniintelligence.utils.log_sanitizer.

For new code, import directly from the canonical location:
    from omniintelligence.utils.log_sanitizer import LogSanitizer, get_log_sanitizer

This legacy module exists for backward compatibility only.
"""

# Re-export from canonical location
from omniintelligence.utils.log_sanitizer import (
    LogSanitizer,
    get_log_sanitizer,
    sanitize_logs,
)

__all__ = [
    "LogSanitizer",
    "get_log_sanitizer",
    "sanitize_logs",
]
