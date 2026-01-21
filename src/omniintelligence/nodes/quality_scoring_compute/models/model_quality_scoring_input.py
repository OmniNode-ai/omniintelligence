"""Input model for Quality Scoring Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ModelDimensionWeights(BaseModel):
    """Configurable weights for quality scoring dimensions.

    Weights control the relative importance of each quality dimension
    in the overall score calculation. All weights must sum to 1.0
    (within tolerance of 0.99-1.01).

    Default weights are ONEX-focused, prioritizing pattern adherence
    and type coverage for node development quality.
    """

    patterns: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight for ONEX pattern adherence scoring",
    )
    type_coverage: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for typing discipline scoring",
    )
    maintainability: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for code maintainability scoring",
    )
    complexity: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for complexity scoring (inverted - lower complexity is better)",
    )
    documentation: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Weight for documentation coverage scoring",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> ModelDimensionWeights:
        """Ensure all dimension weights sum to 1.0 within tolerance."""
        total = (
            self.patterns
            + self.type_coverage
            + self.maintainability
            + self.complexity
            + self.documentation
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Dimension weights must sum to 1.0 (got {total:.4f}). "
                f"Current weights: patterns={self.patterns}, "
                f"type_coverage={self.type_coverage}, "
                f"maintainability={self.maintainability}, "
                f"complexity={self.complexity}, "
                f"documentation={self.documentation}"
            )
        return self


class ModelQualityScoringInput(BaseModel):
    """Input model for quality scoring operations.

    This model represents the input for scoring code quality.
    Supports configurable dimension weights and scoring thresholds
    for flexible quality assessment.
    """

    source_path: str = Field(
        ...,
        min_length=1,
        description="Path to the source file being scored",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Source code content to score",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    dimension_weights: ModelDimensionWeights | None = Field(
        default=None,
        description="Custom weights for quality dimensions. Uses ONEX-focused defaults when None",
    )
    onex_compliance_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Score above this threshold sets onex_compliant=True",
    )
    min_quality_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelDimensionWeights", "ModelQualityScoringInput"]
