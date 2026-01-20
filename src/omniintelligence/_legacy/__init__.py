"""
Legacy module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in v2.0.0.
    Migrate to canonical module paths before the next major release.

This module provides backwards-compatible imports for code that references
the old ``_legacy`` module paths. All implementations are re-exported from
their canonical locations.

Migration Status:
    - ``_legacy.utils`` -> Use ``omniintelligence.utils`` (AVAILABLE NOW)
    - ``_legacy.events`` -> Events module migration is in progress.
      The ``_legacy.events`` module remains the canonical location until
      ``omniintelligence.events`` is released.

Migration Guide:
    **Utils (migrate now)**::

        # OLD (deprecated):
        from omniintelligence._legacy.utils.log_sanitizer import LogSanitizer

        # NEW (use this):
        from omniintelligence.utils.log_sanitizer import LogSanitizer
        # Or via the utils package:
        from omniintelligence.utils import LogSanitizer

    **Events (migrate when available)**::

        # CURRENT (continue using until omniintelligence.events is available):
        from omniintelligence._legacy.events.publisher import EventPublisher

        # FUTURE (when omniintelligence.events is released):
        # from omniintelligence.events.publisher import EventPublisher

Timeline:
    - v1.x: _legacy module available with deprecation warnings
    - v2.0.0: _legacy module will be removed
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy module is deprecated and will be removed in v2.0.0. "
    "For utils: use omniintelligence.utils instead. "
    "For events: continue using _legacy.events until omniintelligence.events is released.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export submodules for backwards compatibility
# These imports trigger their own deprecation warnings
from omniintelligence._legacy import events, utils

__all__ = ["events", "utils"]
