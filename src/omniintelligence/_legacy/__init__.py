"""Legacy implementation modules for omniintelligence.

.. deprecated:: 0.1.0
    This module is deprecated and will be removed in v2.0.0.
    Use :mod:`omniintelligence.nodes` for canonical ONEX node implementations.

This module contains legacy implementation code migrated from omniarchon.
For new development, use the canonical nodes in :mod:`omniintelligence.nodes`.

See _legacy/DEPRECATION.md for migration guidance and timeline.
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy module is deprecated as of v0.1.0 and will be "
    "removed in v2.0.0. Use omniintelligence.nodes for canonical ONEX node "
    "implementations. See _legacy/DEPRECATION.md for migration guidance.",
    DeprecationWarning,
    stacklevel=2,
)
