"""
Legacy events module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in v2.0.0.
    Continue using ``_legacy.events`` until ``omniintelligence.events`` is released.

This module provides backwards-compatible imports for code that references
the old ``_legacy.events`` module paths.

Migration Status:
    The events module functionality is being migrated to the canonical
    ``omniintelligence.events`` location. **Until that migration is complete,
    this module (``_legacy.events``) remains the canonical location for
    event publishing functionality.**

Current Usage (continue using)::

    from omniintelligence._legacy.events.publisher import EventPublisher

Future Usage (when omniintelligence.events is available)::

    from omniintelligence.events.publisher import EventPublisher

Timeline:
    - v1.x: _legacy.events is the canonical location (deprecation warning is informational)
    - v2.0.0: omniintelligence.events will be available, _legacy.events will be removed
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.events module will be removed in v2.0.0. "
    "Continue using _legacy.events until omniintelligence.events is released.",
    DeprecationWarning,
    stacklevel=2,
)

from omniintelligence._legacy.events import publisher

__all__ = ["publisher"]
