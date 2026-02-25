# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Promotion tier enum for ContextItems.

Represents the tier a ContextItem may be promoted from/to.

Ticket: OMN-2395
"""

from __future__ import annotations

from enum import Enum


class EnumPromotionTier(str, Enum):
    """Tier of a ContextItem in the promotion lifecycle.

    Tier ordering (ascending quality confidence):
        QUARANTINE → VALIDATED → SHARED
        BLACKLISTED (terminal — no further promotion)
    """

    QUARANTINE = "quarantine"
    VALIDATED = "validated"
    SHARED = "shared"
    BLACKLISTED = "blacklisted"


__all__ = ["EnumPromotionTier"]
