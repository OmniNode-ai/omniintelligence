"""Output model for Pattern Matching Compute.

This module provides type-safe output models for pattern matching operations.
All models use strong typing to eliminate dict[str, Any].

ONEX Compliance:
    - Strong typing for all fields
    - Frozen immutable models
    - No dict[str, Any] usage
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

# Type alias for output matching algorithm types.
# Note: This differs from input's PatternMatchingOperation ("match", "similarity", "classify", "validate").
# Input operations describe the USER'S intent (what to do); this type describes the ALGORITHM used (how).
# In practice, algorithm details are tracked in matches[].algorithm_used (MatchAlgorithm type),
# making this metadata field optional. Set to None when algorithm is tracked per-match.
OutputMatchingAlgorithm = Literal[
    "exact_match",
    "fuzzy_match",
    "semantic_match",
    "regex_match",
    "pattern_score",
]

# UUID pattern for correlation_id validation
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class ModelPatternMatchingMetadata(BaseModel):
    """Typed metadata for pattern matching output.

    This model provides structured metadata about the matching operation,
    eliminating the need for dict[str, Any] or TypedDict.

    Attributes:
        status: Current status of the operation (e.g., 'completed', 'stub', 'error').
        message: Human-readable message about the matching result.
        tracking_url: URL for tracking stub implementation progress (for stub nodes).
        operation: The pattern matching operation that was performed.
        processing_time_ms: Time taken to process the matching in milliseconds.
        algorithm_version: Version of the matching algorithm used.
        model_name: Name of the embedding/matching model used.
        input_length: Character length of the input code snippet.
        input_line_count: Number of lines in the input code snippet.
        source_language: Programming language of the input code.
        source_file: Path to the source file being analyzed.
        patterns_analyzed: Total number of patterns analyzed.
        patterns_filtered: Number of patterns filtered out (below threshold).
        threshold_used: Confidence threshold used for filtering.
        correlation_id: Correlation ID for distributed tracing.
        timestamp_utc: UTC timestamp of when matching was performed.
    """

    # Operation status (used by stubs and real implementations)
    status: str = Field(
        default="completed",
        description="Status of the matching operation (e.g., 'completed', 'stub', 'error')",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message about the matching result",
    )
    tracking_url: str | None = Field(
        default=None,
        description="URL for tracking stub implementation progress (for stub nodes)",
    )
    operation: OutputMatchingAlgorithm | None = Field(
        default=None,
        description="The matching algorithm used (None when tracked per-match in matches[])",
    )

    # Processing info
    processing_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Time taken to process the matching in milliseconds",
    )
    algorithm_version: str | None = Field(
        default=None,
        description="Version of the matching algorithm used",
    )
    model_name: str | None = Field(
        default=None,
        description="Name of the embedding/matching model used",
    )

    # Input statistics
    input_length: int | None = Field(
        default=None,
        ge=0,
        description="Character length of the input code snippet",
    )
    input_line_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of lines in the input code snippet",
    )
    source_language: str | None = Field(
        default=None,
        description="Programming language of the input code",
    )
    source_file: str | None = Field(
        default=None,
        description="Path to the source file being analyzed",
    )

    # Matching statistics
    patterns_analyzed: int | None = Field(
        default=None,
        ge=0,
        description="Total number of patterns analyzed",
    )
    patterns_filtered: int | None = Field(
        default=None,
        ge=0,
        description="Number of patterns filtered out (below threshold)",
    )
    threshold_used: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence threshold used for filtering (0.0 to 1.0)",
    )

    # Request context
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    timestamp_utc: str | None = Field(
        default=None,
        description="UTC timestamp of when matching was performed (ISO 8601 format)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


# Algorithm types for match detail.
# Note: "semantic" is reserved for future implementation when embedding-based
# similarity matching is added. Currently only "keyword_overlap" and "regex_match"
# are actively used by the handler. The type includes "semantic" to support
# forward compatibility in output models.
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


class ModelPatternMatchingOutput(BaseModel):
    """Output model for pattern matching operations.

    This model represents the result of matching code patterns.
    Includes both simple (patterns_matched, pattern_scores) and
    rich (matches) representations for flexibility.
    """

    success: bool = Field(
        ...,
        description="Whether pattern matching succeeded",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="List of matched pattern names (simple representation)",
    )
    pattern_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each matched pattern (0.0 to 1.0)",
    )
    matches: list[ModelPatternMatch] = Field(
        default_factory=list,
        description="Rich match details including reasons and algorithms",
    )
    metadata: ModelPatternMatchingMetadata | None = Field(
        default=None,
        description="Typed metadata about the matching operation",
    )

    @field_validator("pattern_scores")
    @classmethod
    def validate_pattern_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all pattern scores are within 0.0 to 1.0 range.

        Note: This validator is necessary because Pydantic's Field(ge=0.0, le=1.0)
        constraints only apply to the dict type itself, not to dictionary VALUES.
        The `dict[str, float]` annotation provides no bounds on the float values,
        so explicit validation is required to enforce the 0.0-1.0 range.
        """
        for pattern_name, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Pattern score for '{pattern_name}' must be between 0.0 and 1.0, "
                    f"got {score}"
                )
        return v

    @model_validator(mode="after")
    def validate_pattern_scores_match_patterns(self) -> Self:
        """Validate that pattern_scores keys match patterns_matched list.

        Ensures consistency between the list of matched patterns and the
        dictionary containing their confidence scores. Every scored pattern
        must be in the matched patterns list.

        Note: Not all matched patterns require scores (scores are optional),
        but all scored patterns must be in the matched list.

        Returns:
            Self with validated pattern/score consistency.

        Raises:
            ValueError: If pattern_scores contains patterns not in patterns_matched.
        """
        patterns_set = set(self.patterns_matched)
        scores_keys = set(self.pattern_scores.keys())

        # Scores are optional, so we only check that scored patterns exist in matched
        extra_scores = scores_keys - patterns_set
        if extra_scores:
            raise ValueError(
                f"pattern_scores contains patterns not in patterns_matched: "
                f"{sorted(extra_scores)}"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "MatchAlgorithm",
    "ModelPatternMatch",
    "ModelPatternMatchingMetadata",
    "ModelPatternMatchingOutput",
    "OutputMatchingAlgorithm",
]
