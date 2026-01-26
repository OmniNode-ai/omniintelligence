"""Configuration model for Pattern Extraction Compute Node.

This module provides immutable, validated configuration for pattern
extraction operations. Values control extraction behavior and thresholds.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelPatternExtractionConfig(BaseModel):
    """Frozen configuration for pattern extraction operations.

    Controls the behavior of pattern extraction including confidence
    thresholds, occurrence limits, and which pattern types to extract.

    Attributes:
        min_confidence: Minimum confidence score for extracted patterns.
            Patterns below this threshold are discarded.
        min_pattern_occurrences: Minimum times a pattern must appear
            to be considered significant. Filters out rare coincidences.
        max_insights_per_type: Maximum number of insights to return
            for each insight type. Prevents output explosion.
        extract_file_patterns: Whether to extract file access patterns.
        extract_error_patterns: Whether to extract error patterns.
        extract_architecture_patterns: Whether to extract architecture patterns.
        extract_tool_patterns: Whether to extract tool usage patterns.
        reference_time: Reference timestamp for temporal calculations.
            When None, uses current time.

    Example:
        >>> config = ModelPatternExtractionConfig(min_confidence=0.8)
        >>> config.min_pattern_occurrences
        2
    """

    min_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for extracted patterns (0.0 to 1.0)",
    )
    min_pattern_occurrences: int = Field(
        default=2,
        ge=1,
        description="Minimum occurrences required for a pattern to be significant",
    )
    max_insights_per_type: int = Field(
        default=50,
        ge=1,
        description="Maximum number of insights to return per insight type",
    )
    extract_file_patterns: bool = Field(
        default=True,
        description="Whether to extract file access patterns",
    )
    extract_error_patterns: bool = Field(
        default=True,
        description="Whether to extract error patterns",
    )
    extract_architecture_patterns: bool = Field(
        default=True,
        description="Whether to extract architecture patterns",
    )
    extract_tool_patterns: bool = Field(
        default=True,
        description="Whether to extract tool usage patterns",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Reference timestamp for temporal calculations. Uses current time when None.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternExtractionConfig"]
