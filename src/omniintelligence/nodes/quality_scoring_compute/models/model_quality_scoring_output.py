"""Output model for Quality Scoring Compute.

This module provides type-safe output models for quality scoring operations.
All models use strong typing to eliminate dict[str, Any].

ONEX Compliance:
    - Strong typing for all fields
    - Frozen immutable models
    - No dict[str, Any] usage
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
    DimensionScores,
)


class ModelQualityScoringMetadata(BaseModel):
    """Typed metadata for quality scoring output.

    This model provides structured metadata about the scoring operation,
    eliminating the need for dict[str, Any].

    Attributes:
        status: Current status of the scoring operation (e.g., 'completed', 'stub', 'error').
        message: Human-readable message about the scoring result.
        tracking_url: URL for tracking stub implementation progress (for stub nodes).
        source_language: Programming language of the scored content.
        analysis_version: Version of the analysis algorithm used.
        processing_time_ms: Time taken to process the scoring in milliseconds.
    """

    status: str = Field(
        default="completed",
        description="Status of the scoring operation (e.g., 'completed', 'stub', 'error')",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message about the scoring result",
    )
    tracking_url: str | None = Field(
        default=None,
        description="URL for tracking stub implementation progress (for stub nodes)",
    )
    source_language: str | None = Field(
        default=None,
        description="Programming language of the scored content",
    )
    analysis_version: str | None = Field(
        default=None,
        description="Version of the analysis algorithm used",
    )
    processing_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Time taken to process the scoring in milliseconds",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelQualityScoringOutput(BaseModel):
    """Output model for quality scoring operations.

    This model represents the result of scoring code quality.
    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether quality scoring succeeded",
    )
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0 to 1.0)",
    )
    dimensions: DimensionScores | dict[str, float] = Field(
        default_factory=dict,
        description="Quality scores by dimension using the six-dimension standard: "
        "complexity, maintainability, documentation, temporal_relevance, patterns, architectural",
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimension_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate dimension scores are within range and contain expected keys.

        The six-dimension standard requires:
            - complexity: Cyclomatic complexity score
            - maintainability: Code structure and naming score
            - documentation: Docstring and comment coverage score
            - temporal_relevance: Code freshness score
            - patterns: ONEX pattern adherence score
            - architectural: Module organization score

        All scores must be between 0.0 and 1.0.
        """
        expected_dimensions = {
            "complexity",
            "maintainability",
            "documentation",
            "temporal_relevance",
            "patterns",
            "architectural",
        }

        # Check for missing or extra dimensions (only if dimensions are provided)
        if v:
            actual_dimensions = set(v.keys())
            missing = expected_dimensions - actual_dimensions
            extra = actual_dimensions - expected_dimensions

            if missing or extra:
                raise ValueError(
                    f"Invalid dimension keys. Missing: {missing or 'none'}, "
                    f"Extra: {extra or 'none'}. "
                    f"Expected six-dimension standard: {sorted(expected_dimensions)}"
                )

        # Validate score ranges
        for dimension_name, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Dimension score for '{dimension_name}' must be between 0.0 and 1.0, "
                    f"got {score}"
                )
        return v

    onex_compliant: bool = Field(
        default=False,
        description="Whether the code is ONEX compliant",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of quality improvement recommendations",
    )
    metadata: ModelQualityScoringMetadata | None = Field(
        default=None,
        description="Typed metadata about the scoring operation",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringMetadata", "ModelQualityScoringOutput"]
