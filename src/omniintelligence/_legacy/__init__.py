"""
Legacy module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Import from ``omniintelligence.utils`` or ``omniintelligence.events``
    instead.

This module provides backwards-compatible imports for code that references
the old ``_legacy`` module paths. All implementations are re-exported from
their canonical locations.

Available Submodules:
    - ``_legacy.utils`` -> Use ``omniintelligence.utils`` instead
    - ``_legacy.events`` -> Use ``omniintelligence.events`` instead (when available)

Migration Guide:
    Instead of::

        from omniintelligence._legacy.utils.log_sanitizer import LogSanitizer

    Use::

        from omniintelligence.utils.log_sanitizer import LogSanitizer
        # Or via the utils package:
        from omniintelligence.utils import LogSanitizer
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy module is deprecated. "
    "Import from omniintelligence.utils or omniintelligence.events instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export submodules for backwards compatibility
# These imports trigger their own deprecation warnings
from omniintelligence._legacy import events, utils

__all__ = ["events", "utils"]
