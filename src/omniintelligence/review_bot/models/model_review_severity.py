# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ReviewSeverity enum for Code Intelligence Review Bot.

Defines severity levels for review findings. Severity governs how findings
affect CI outcomes in different enforcement modes.

OMN-2495: Implement ReviewFinding and ReviewScore Pydantic models.
"""

from __future__ import annotations

from enum import Enum


class ReviewSeverity(str, Enum):
    """Severity levels for review findings.

    Follows ONEX enum casing conventions (UPPER_CASE values).

    Severity rules:
    - BLOCKER findings cap ReviewScore at <= 50; zero blockers required for score > 80
    - BLOCKER findings fail CI gate in BLOCK enforcement mode
    - WARNING findings appear as PR comments in WARN/BLOCK modes
    - INFO findings are informational only, never affect CI
    """

    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


__all__ = ["ReviewSeverity"]
