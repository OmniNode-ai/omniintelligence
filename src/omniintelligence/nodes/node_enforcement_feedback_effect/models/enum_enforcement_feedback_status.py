# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Enforcement feedback status enum."""

from enum import Enum


class EnumEnforcementFeedbackStatus(str, Enum):
    """Status of the enforcement feedback processing."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NO_ADJUSTMENTS = "no_adjustments"
    NO_VIOLATIONS = "no_violations"
    ERROR = "error"


__all__ = ["EnumEnforcementFeedbackStatus"]
