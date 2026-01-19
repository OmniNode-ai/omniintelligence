"""
Legacy publisher module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Import from ``omniintelligence.events.publisher`` instead when available.

This module provides the EventPublisher class with proper circuit breaker
behavior that only trips on transient infrastructure failures.
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.events.publisher module is deprecated. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

from omniintelligence._legacy.events.publisher.event_publisher import (
    EventPublisher,
    create_event_publisher,
)

__all__ = ["EventPublisher", "create_event_publisher"]
