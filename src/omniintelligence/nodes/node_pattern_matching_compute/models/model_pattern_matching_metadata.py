"""ModelPatternMatchingMetadata - typed metadata for pattern matching output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# UUID pattern for correlation_id validation
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Type alias for output matching algorithm types.
OutputMatchingAlgorithm = Literal[
    "exact_match",
    "fuzzy_match",
    "semantic_match",
    "regex_match",
    "pattern_score",
]


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
