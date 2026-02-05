"""Type protocols for pattern matching handler results.

This module defines TypedDict structures for type-safe handler responses
and input pattern records. TypedDict is used because handlers return dicts,
not objects with methods.

Design Decisions:
    - PatternRecord: Lightweight representation of a pattern for matching
    - PatternMatchResult: Individual match with confidence and metadata
    - PatternMatchingHandlerResult: Full handler response structure
    - All scores normalized to 0.0-1.0 range for consistency
"""

from __future__ import annotations

from typing import Final, Literal, TypedDict

# Algorithm version constant for traceability
# Defined here to avoid circular imports (handler imports from protocols)
ALGORITHM_VERSION: Final[str] = "1.0.0"


class PatternRecord(TypedDict, total=False):
    """Lightweight pattern record for matching operations.

    This TypedDict defines the minimum pattern structure needed for
    matching. Patterns are provided by the caller (typically an orchestrator
    that fetches from pattern_storage).

    Required Attributes:
        pattern_id: Unique identifier for the pattern.
        signature: The pattern signature (text/regex/structure).
        domain: Domain where the pattern belongs.

    Optional Attributes:
        keywords: Extracted keywords for keyword-based matching.
        status: Pattern lifecycle status (validated, provisional, etc.).
        confidence: Original pattern confidence score.
        category: Pattern category for filtering.
    """

    # Required fields (total=False allows gradual population)
    pattern_id: str
    signature: str
    domain: str

    # Optional fields for enhanced matching
    keywords: list[str]
    status: str
    confidence: float
    category: str


class PatternMatchDetail(TypedDict):
    """Detailed information about a single pattern match.

    Provides rich context about why a pattern matched and with what
    confidence. Used in the output model for downstream processing.

    Attributes:
        pattern_id: Unique identifier of the matched pattern.
        pattern_name: Human-readable pattern name or signature excerpt.
        confidence: Match confidence score (0.0-1.0).
        category: Pattern category (e.g., "design_pattern", "anti_pattern").
        match_reason: Explanation of why this pattern matched.
        algorithm_used: Which matching algorithm produced this result.
    """

    pattern_id: str
    pattern_name: str
    confidence: float
    category: str
    match_reason: str
    algorithm_used: Literal["keyword_overlap", "regex_match", "semantic"]


class PatternMatchingHandlerResult(TypedDict):
    """Result structure for pattern matching handler.

    This TypedDict defines the guaranteed structure returned by
    the match_patterns function.

    Attributes:
        success: Whether the matching completed without errors.
        matches: List of detailed match results.
        patterns_analyzed: Total number of patterns checked.
        patterns_matched: Number of patterns that met threshold.
        patterns_filtered: Number of patterns filtered out.
        threshold_used: Confidence threshold applied.
        algorithm_version: Version of the matching algorithm.
    """

    success: bool
    matches: list[PatternMatchDetail]
    patterns_analyzed: int
    patterns_matched: int
    patterns_filtered: int
    threshold_used: float
    algorithm_version: str


def create_empty_handler_result(
    threshold: float = 0.5,
) -> PatternMatchingHandlerResult:
    """Create a result with no matches.

    Used when pattern library is empty or no patterns meet threshold.

    Args:
        threshold: The threshold that was used.

    Returns:
        Empty result structure.
    """
    return PatternMatchingHandlerResult(
        success=True,
        matches=[],
        patterns_analyzed=0,
        patterns_matched=0,
        patterns_filtered=0,
        threshold_used=threshold,
        algorithm_version=ALGORITHM_VERSION,
    )


__all__ = [
    "ALGORITHM_VERSION",
    "PatternMatchDetail",
    "PatternMatchingHandlerResult",
    "PatternRecord",
    "create_empty_handler_result",
]
