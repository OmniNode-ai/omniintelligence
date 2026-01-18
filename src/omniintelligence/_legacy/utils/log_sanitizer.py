"""
Legacy log_sanitizer module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Use the canonical import from ``omniintelligence.utils.log_sanitizer`` instead.

This module re-exports all log sanitization utilities from the canonical
location for backwards compatibility with code that may reference the old
``_legacy`` module paths.

Migration Guide:
    Instead of::

        from omniintelligence._legacy.utils.log_sanitizer import (
            LogSanitizer,
            get_log_sanitizer,
            sanitize_logs,
        )

    Use::

        from omniintelligence.utils.log_sanitizer import (
            LogSanitizer,
            get_log_sanitizer,
            sanitize_logs,
        )

The canonical implementation is located at:
    ``src/omniintelligence/utils/log_sanitizer.py``
"""

import warnings

warnings.warn(
    "Importing from omniintelligence._legacy.utils.log_sanitizer is deprecated. "
    "Use omniintelligence.utils.log_sanitizer instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the canonical module
from omniintelligence.utils.log_sanitizer import (  # noqa: E402
    LogSanitizer,
    get_log_sanitizer,
    sanitize_logs,
)

__all__ = [
    "get_log_sanitizer",
    "LogSanitizer",
    "sanitize_logs",
]
