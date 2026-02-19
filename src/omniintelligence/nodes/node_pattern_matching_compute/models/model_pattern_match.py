"""ModelPatternMatch - detailed information about a single pattern match."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Algorithm types for match detail.
MatchAlgorithm = Literal["keyword_overlap", "regex_match", "semantic"]


class ModelPatternMatch(BaseModel):
    """Detailed information about a single pattern match.

    Provides rich context about why a pattern matched and with what
    confidence. Used for downstream processing that needs more than
    just pattern names and scores.

    Attributes:
        pattern_id: Unique identifier of the matched pattern.
        pattern_name: Human-readable pattern name or signature excerpt.
        confidence: Match confidence score (0.0-1.0).
        category: Pattern category (e.g., "design_pattern", "anti_pattern").
        match_reason: Explanation of why this pattern matched.
        algorithm_used: Which matching algorithm produced this result.
    """

    pattern_id: str = Field(
        ...,
        description="Unique identifier of the matched pattern",
    )
    pattern_name: str = Field(
        ...,
        description="Human-readable pattern name or signature excerpt",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Match confidence score (0.0-1.0)",
    )
    category: str = Field(
        default="uncategorized",
        description="Pattern category (e.g., 'design_pattern', 'anti_pattern')",
    )
    match_reason: str = Field(
        default="",
        description="Explanation of why this pattern matched",
    )
    algorithm_used: MatchAlgorithm = Field(
        default="keyword_overlap",
        description="Which matching algorithm produced this result",
    )

    model_config = {"frozen": True, "extra": "forbid"}
