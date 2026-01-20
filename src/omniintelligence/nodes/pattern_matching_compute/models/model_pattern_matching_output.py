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

# Type alias for pattern matching operations
PatternMatchingOperation = Literal[
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
    operation: PatternMatchingOperation | None = Field(
        default=None,
        description="The pattern matching operation that was performed",
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


class ModelPatternMatchingOutput(BaseModel):
    """Output model for pattern matching operations.

    This model represents the result of matching code patterns.
    """

    success: bool = Field(
        ...,
        description="Whether pattern matching succeeded",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="List of matched pattern names",
    )
    pattern_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each matched pattern (0.0 to 1.0)",
    )
    metadata: ModelPatternMatchingMetadata | None = Field(
        default=None,
        description="Typed metadata about the matching operation",
    )

    @field_validator("pattern_scores")
    @classmethod
    def validate_pattern_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all pattern scores are within 0.0 to 1.0 range."""
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
    "UUID_PATTERN",
    "ModelPatternMatchingMetadata",
    "ModelPatternMatchingOutput",
    "PatternMatchingOperation",
]
