# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern state enum and governance constants for pattern storage.

This module defines the pattern lifecycle states and governance constants
used by the pattern_storage_effect node for pattern state management.

States follow the progression: candidate → provisional → validated

Reference:
    - OMN-1668: Pattern storage effect models
"""

from __future__ import annotations

from enum import StrEnum


class EnumPatternState(StrEnum):
    """Pattern lifecycle states for storage and promotion.

    States represent the maturity level of a pattern in the system:
    - CANDIDATE: Newly learned pattern, not yet verified
    - PROVISIONAL: Pattern has been verified but not fully validated
    - VALIDATED: Fully validated pattern ready for production use

    State Transitions:
        CANDIDATE → PROVISIONAL: Pattern passes initial verification
        PROVISIONAL → VALIDATED: Pattern meets all validation criteria
    """

    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    VALIDATED = "validated"


class PatternStorageGovernance:
    """Governance constants for pattern storage operations.

    These constants define the hard-coded governance rules for pattern
    storage decisions. They are intentionally not configurable to ensure
    consistent quality across all pattern storage operations.

    Attributes:
        MIN_CONFIDENCE: Minimum confidence threshold for storing patterns.
            Patterns below this threshold are rejected as low-quality.
    """

    MIN_CONFIDENCE: float = 0.5
    """Minimum confidence threshold for pattern storage (hard-coded governance constant)."""


__all__ = [
    "EnumPatternState",
    "PatternStorageGovernance",
]
