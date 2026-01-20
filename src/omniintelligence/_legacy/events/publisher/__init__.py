"""
Legacy publisher module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in v2.0.0.
    Continue using ``_legacy.events.publisher`` until ``omniintelligence.events.publisher`` is released.

This module provides the EventPublisher class with proper circuit breaker
behavior that only trips on transient infrastructure failures.

Current Usage (continue using)::

    from omniintelligence._legacy.events.publisher import EventPublisher

Future Usage (when omniintelligence.events is available)::

    from omniintelligence.events.publisher import EventPublisher
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.events.publisher module will be removed in v2.0.0. "
    "Continue using _legacy.events.publisher until omniintelligence.events is released.",
    DeprecationWarning,
    stacklevel=2,
)

from omniintelligence._legacy.events.publisher.event_publisher import (
    EventPublisher,
    create_event_publisher,
)

__all__ = ["EventPublisher", "create_event_publisher"]
