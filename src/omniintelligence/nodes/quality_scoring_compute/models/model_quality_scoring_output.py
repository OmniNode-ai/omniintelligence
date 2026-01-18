"""Output model for Quality Scoring Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelQualityScoringOutput(BaseModel):
    """Output model for quality scoring operations.

    This model represents the result of scoring code quality.
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
    dimensions: dict[str, float] = Field(
        default_factory=dict,
        description="Quality scores by dimension (maintainability, complexity, etc.)",
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimension_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all dimension scores are within 0.0 to 1.0 range."""
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
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the scoring",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringOutput"]
