"""Public API for log sanitizer utilities.

Re-exports from legacy module for backwards compatibility.
The actual implementation resides in omniintelligence._legacy.utils.log_sanitizer.

Usage:
    from omniintelligence.utils.log_sanitizer import (
        LogSanitizer,
        get_log_sanitizer,
        sanitize_logs,
    )

    # Get global sanitizer instance
    sanitizer = get_log_sanitizer()

    # Sanitize text
    clean_text = sanitize_logs("sk-1234567890abcdefghij")
    # Returns: "[OPENAI_API_KEY]"
"""

from omniintelligence._legacy.utils.log_sanitizer import (
    LogSanitizer,
    get_log_sanitizer,
    sanitize_logs,
)

__all__ = ["LogSanitizer", "get_log_sanitizer", "sanitize_logs"]
