"""
Legacy utils module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Use the canonical imports from ``omniintelligence.utils`` instead.

This module re-exports all utilities from their canonical locations for
backwards compatibility.

Migration Guide:
    Instead of::

        from omniintelligence._legacy.utils import LogSanitizer
        from omniintelligence._legacy.utils.log_sanitizer import sanitize_logs

    Use::

        from omniintelligence.utils import LogSanitizer
        from omniintelligence.utils.log_sanitizer import sanitize_logs
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.utils module is deprecated. "
    "Use omniintelligence.utils instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from canonical location for backwards compatibility
from omniintelligence.utils.log_sanitizer import (  # noqa: E402
    LogSanitizer,
    LogSanitizerSettings,
    get_log_sanitizer,
    get_sanitizer_settings,
    sanitize_logs,
)

__all__ = [
    "LogSanitizer",
    "LogSanitizerSettings",
    "get_log_sanitizer",
    "get_sanitizer_settings",
    "sanitize_logs",
]
