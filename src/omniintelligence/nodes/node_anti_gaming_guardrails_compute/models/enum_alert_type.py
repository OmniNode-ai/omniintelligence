# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Alert type enum for anti-gaming guardrails (OMN-2563)."""

from __future__ import annotations

from enum import Enum


class EnumAlertType(str, Enum):
    """Types of anti-gaming alerts."""

    GOODHART_VIOLATION = "goodhart_violation"
    """Correlated metric pair diverged beyond threshold (Goodhart's Law)."""

    REWARD_HACKING = "reward_hacking"
    """Score improved but human acceptance did not improve accordingly."""

    DISTRIBUTIONAL_SHIFT = "distributional_shift"
    """Evidence input distribution shifted significantly from baseline."""

    DIVERSITY_CONSTRAINT_VIOLATION = "diversity_constraint_violation"
    """Evaluation draws from fewer than N distinct evidence source types."""


__all__ = ["EnumAlertType"]
