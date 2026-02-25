# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Heuristic method enum for contribution attribution.

Ticket: OMN-1670
"""

from enum import Enum


class EnumHeuristicMethod(str, Enum):
    """Heuristic method for contribution attribution.

    These methods distribute credit among patterns injected during a session.
    This is explicitly a HEURISTIC, not causal attribution - multi-injection
    sessions make true causal attribution impossible without controlled experiments.

    Attributes:
        EQUAL_SPLIT: Equal credit to all patterns (1/N each)
        RECENCY_WEIGHTED: More credit to later patterns (linear ramp)
        FIRST_MATCH: All credit to the first pattern

    Confidence levels reflect the inherent uncertainty:
        - EQUAL_SPLIT: 0.5 (moderate - at least it's fair)
        - RECENCY_WEIGHTED: 0.4 (lower - recency bias is an assumption)
        - FIRST_MATCH: 0.3 (lowest - ignores all but one pattern)

    Example:
        >>> from omniintelligence.enums import EnumHeuristicMethod
        >>> method = EnumHeuristicMethod.EQUAL_SPLIT
        >>> assert method.value == "equal_split"

    Note:
        Values match the heuristic_method column in pattern_injections table.

    See Also:
        - OMN-1679: FEEDBACK-004 contribution heuristic implementation
    """

    EQUAL_SPLIT = "equal_split"
    RECENCY_WEIGHTED = "recency_weighted"
    FIRST_MATCH = "first_match"


# Confidence scores for each heuristic method
HEURISTIC_CONFIDENCE: dict[str, float] = {
    EnumHeuristicMethod.EQUAL_SPLIT.value: 0.5,
    EnumHeuristicMethod.RECENCY_WEIGHTED.value: 0.4,
    EnumHeuristicMethod.FIRST_MATCH.value: 0.3,
}


__all__ = ["EnumHeuristicMethod", "HEURISTIC_CONFIDENCE"]
