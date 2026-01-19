"""
Legacy events module compatibility layer.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Import from ``omniintelligence.events`` instead when it becomes available.

This module provides backwards-compatible imports for code that references
the old ``_legacy.events`` module paths.

Migration Guide:
    The events module functionality is being migrated to the canonical
    ``omniintelligence.events`` location. Until the migration is complete,
    this module provides stub implementations and compatibility shims.
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.events module is deprecated. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

from omniintelligence._legacy.events import publisher

__all__ = ["publisher"]
