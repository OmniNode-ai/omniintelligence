"""Input model for Quality Scoring Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_quality_scoring_compute.handlers.enum_onex_strictness_level import (
    OnexStrictnessLevel,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_dimension_weights import (
    ModelDimensionWeights,
)


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
        3. Defaults (lowest priority) - Standard weights and threshold when nothing set.

    Preset Levels:
        - STRICT: Production-ready, high quality bar (threshold 0.8).
        - STANDARD: Default balanced requirements (threshold 0.7).
        - LENIENT: Development/prototyping mode (threshold 0.5).
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
            "When set, overrides dimension_weights and onex_compliance_threshold."
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
            "Ignored when onex_preset is set."
        ),
    )
    min_quality_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringInput"]
