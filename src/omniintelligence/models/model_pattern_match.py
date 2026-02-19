"""Typed pattern match result model for code pattern detection."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class PatternMatchMetadataDict(TypedDict, total=False):
    """Typed structure for pattern match metadata.

    Provides type-safe fields for pattern match metadata.
    """

    # Pattern classification
    pattern_category: str
    pattern_subcategory: str
    is_anti_pattern: bool

    # Match context
    function_name: str
    class_name: str
    module_name: str

    # Quality info
    severity: str  # "info", "warning", "error"
    recommendation: str

    # Detection info
    detection_method: str
    confidence: float


class ModelPatternMatch(BaseModel):
    """Typed pattern match result for code pattern detection.

    This model provides type-safe representation of detected patterns
    in code analysis and pattern learning operations.

    All fields use strong typing without dict[str, Any].

    Example:
        >>> match = ModelPatternMatch(
        ...     pattern_name="SINGLETON_PATTERN",
        ...     match_score=0.92,
        ...     matched_code="class Singleton: _instance = None ...",
        ...     source_path="src/patterns/singleton.py",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "pattern_name": "SINGLETON_PATTERN",
                "match_score": 0.92,
                "matched_code": "class Singleton: _instance = None ...",
                "source_path": "src/patterns/singleton.py",
            }
        },
    )

    pattern_name: str = Field(
        ...,
        min_length=1,
        description="Name of the matched pattern",
    )
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the pattern match (0.0 to 1.0)",
    )
    matched_code: str | None = Field(
        default=None,
        description="Code snippet that matched the pattern",
    )
    source_path: str | None = Field(
        default=None,
        min_length=1,
        description="Path to the source file containing the match",
    )
    line_start: int | None = Field(
        default=None,
        ge=1,
        description="Starting line number of the match",
    )
    line_end: int | None = Field(
        default=None,
        ge=1,
        description="Ending line number of the match",
    )
    metadata: PatternMatchMetadataDict = Field(
        default_factory=lambda: PatternMatchMetadataDict(),
        description="Additional metadata about the pattern match with typed fields",
    )


__all__ = ["ModelPatternMatch", "PatternMatchMetadataDict"]
