# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Bootstrap tier enum for context items.

Determines the starting trust tier for a newly indexed context item
based on the source_ref pattern. VALIDATED is an optimistic grant for
high-trust sources (CLAUDE.md, design docs); QUARANTINE requires
scored runs before promotion.

Ticket: OMN-2393
"""

from __future__ import annotations

from enum import Enum


class EnumBootstrapTier(str, Enum):
    """Starting tier for a newly indexed context item."""

    VALIDATED = "VALIDATED"
    """Source is trusted (CLAUDE.md, design docs). Optimistic grant.
    Demotion via hurt_rate still applies."""

    QUARANTINE = "QUARANTINE"
    """Source requires scored runs before promotion to VALIDATED."""


__all__ = ["EnumBootstrapTier"]
