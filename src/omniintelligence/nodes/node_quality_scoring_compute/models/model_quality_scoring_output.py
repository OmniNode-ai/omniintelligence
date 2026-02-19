"""Output model for Quality Scoring Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from omniintelligence.nodes.node_quality_scoring_compute.handlers.protocols import (
    DimensionScores,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_metadata import (
    ModelQualityScoringMetadata,
)


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
        default_factory=lambda: {},
        description="Quality scores by dimension using the six-dimension standard: "
        "complexity, maintainability, documentation, temporal_relevance, patterns, architectural",
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimension_scores(
        cls, v: DimensionScores | dict[str, float]
    ) -> DimensionScores | dict[str, float]:
        """Validate dimension scores are within range and contain expected keys."""
        expected_dimensions = {
            "complexity",
            "maintainability",
            "documentation",
            "temporal_relevance",
            "patterns",
            "architectural",
        }

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

        for dimension_name, score in v.items():
            score_val = float(score)  # type: ignore[arg-type]
            if not 0.0 <= score_val <= 1.0:
                raise ValueError(
                    f"Dimension score for '{dimension_name}' must be between 0.0 and 1.0, "
                    f"got {score_val}"
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


__all__ = ["ModelQualityScoringOutput"]
