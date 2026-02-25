# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Outcome enum for navigation path retrieval.

Ticket: OMN-2579
"""

from __future__ import annotations

from enum import Enum


class EnumNavigationOutcome(str, Enum):
    """Outcome of a prior navigation path.

    Values:
        SUCCESS: The navigation path completed successfully (goal reached).
        FAILURE: The navigation path failed (goal not reached or aborted).
        UNKNOWN: Outcome not recorded (legacy or incomplete entries).
    """

    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


__all__ = ["EnumNavigationOutcome"]
