# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Re-export of EnumEvidenceTier from omnibase_core canonical location.

OMN-2134 is resolved: omnibase_core now exports EnumEvidenceTier from
omnibase_core.enums.pattern_learning. This module is a thin re-export
to preserve the omniintelligence.enums public surface.
"""

from omnibase_core.enums.pattern_learning import EnumEvidenceTier

__all__ = ["EnumEvidenceTier"]
