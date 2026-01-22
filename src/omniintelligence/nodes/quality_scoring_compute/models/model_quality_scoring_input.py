"""Input model for Quality Scoring Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from omniintelligence.nodes.quality_scoring_compute.handlers.enum_onex_strictness_level import (
    OnexStrictnessLevel,
)


class ModelDimensionWeights(BaseModel):
    """Configurable weights for quality scoring dimensions.

    Weights control the relative importance of each quality dimension
    in the overall score calculation. All weights must sum to 1.0
    (within tolerance of 0.99-1.01).

    Default weights follow the six-dimension standard:
        - complexity (0.20): Cyclomatic complexity scoring
        - maintainability (0.20): Code structure and naming
        - documentation (0.15): Docstring and comment coverage
        - temporal_relevance (0.15): Code freshness indicators
        - patterns (0.15): ONEX pattern adherence
        - architectural (0.15): Module organization and structure
    """

    complexity: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for complexity scoring (inverted - lower complexity is better)",
    )
    maintainability: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for code maintainability scoring",
    )
    documentation: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for documentation coverage scoring",
    )
    temporal_relevance: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for temporal relevance scoring - code freshness and staleness",
    )
    patterns: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for ONEX pattern adherence scoring",
    )
    architectural: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for architectural compliance scoring",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> ModelDimensionWeights:
        """Ensure all dimension weights sum to 1.0 within tolerance."""
        total = (
            self.complexity
            + self.maintainability
            + self.documentation
            + self.temporal_relevance
            + self.patterns
            + self.architectural
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Dimension weights must sum to 1.0 (got {total:.4f}). "
                f"Current weights: complexity={self.complexity}, "
                f"maintainability={self.maintainability}, "
                f"documentation={self.documentation}, "
                f"temporal_relevance={self.temporal_relevance}, "
                f"patterns={self.patterns}, "
                f"architectural={self.architectural}"
            )
        return self


class ModelQualityScoringInput(BaseModel):
    """Input model for quality scoring operations.

    This model represents the input for scoring code quality.
    Supports configurable dimension weights and scoring thresholds
    for flexible quality assessment.

    Configuration Precedence:
        When determining weights and thresholds, the following precedence applies:
        1. onex_preset (highest priority) - When set, overrides both dimension_weights
           and onex_compliance_threshold with preset values.
        2. dimension_weights / onex_compliance_threshold - Manual configuration.
        3. Defaults (lowest priority) - Standard weights (0.20/0.20/0.15/0.15/0.15/0.15)
           and threshold (0.7) when nothing else is specified.

    Preset Levels:
        - STRICT: Production-ready, high quality bar (threshold 0.8).
          Emphasizes documentation and patterns.
        - STANDARD: Default balanced requirements (threshold 0.7).
          Equal distribution across all dimensions.
        - LENIENT: Development/prototyping mode (threshold 0.5).
          More forgiving on documentation and pattern requirements.
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
    onex_preset: OnexStrictnessLevel | None = Field(
        default=None,
        description=(
            "ONEX strictness preset (strict/standard/lenient). "
            "When set, overrides dimension_weights and onex_compliance_threshold. "
            "Use 'strict' for production, 'standard' for regular development, "
            "'lenient' for prototyping."
        ),
    )
    dimension_weights: ModelDimensionWeights | None = Field(
        default=None,
        description=(
            "Custom weights for quality dimensions. Uses ONEX-focused defaults when None. "
            "Ignored when onex_preset is set."
        ),
    )
    onex_compliance_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Score above this threshold sets onex_compliant=True. "
            "Ignored when onex_preset is set (preset provides its own threshold)."
        ),
    )
    min_quality_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelDimensionWeights", "ModelQualityScoringInput", "OnexStrictnessLevel"]
