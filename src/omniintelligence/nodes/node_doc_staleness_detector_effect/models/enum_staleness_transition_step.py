# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Staleness transition step enum for DocStalenessDetectorEffect.

Tracks the state of the atomic 3-step re-ingestion sequence for
CONTENT_CHANGED cases. Used by the staleness_transition_log for
crash-safe idempotent resume.

Ticket: OMN-2394
"""

from __future__ import annotations

from enum import Enum


class EnumStalenessTransitionStep(str, Enum):
    """Current step in the atomic staleness transition sequence."""

    PENDING = "pending"
    """Transition detected but not yet started."""

    INDEX_NEW = "index_new"
    """Step 1: New item is being indexed (or re-indexed after crash)."""

    VERIFY_NEW = "verify_new"
    """Step 2: New item confirmed in PostgreSQL + Qdrant."""

    BLACKLIST_OLD = "blacklist_old"
    """Step 3: Old item being blacklisted. Only executes after VERIFY_NEW."""

    COMPLETE = "complete"
    """All steps completed successfully. Old item blacklisted."""

    FAILED = "failed"
    """Transition failed after retries. Requires manual intervention."""


__all__ = ["EnumStalenessTransitionStep"]
