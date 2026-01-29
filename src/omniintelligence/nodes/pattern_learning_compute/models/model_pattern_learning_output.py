"""Output model for Pattern Learning Compute.

Uses contract models from omnibase_core for canonical pattern representations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omnibase_core.models.pattern_learning import (
    ModelLearnedPattern,
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
)


class ModelPatternLearningOutput(BaseModel):
    """Output model for pattern learning operations.

    This model represents the result of pattern learning operations.
    Patterns are split into candidates (not yet validated) and learned
    (validated and ready for use).

    Attributes:
        success: Whether pattern learning succeeded.
        candidate_patterns: Patterns with lifecycle_state != "validated".
        learned_patterns: Patterns with lifecycle_state == "validated".
        metrics: Aggregated metrics from the learning process.
        metadata: Processing metadata (timestamps, thresholds used, etc.).
        warnings: Non-fatal warnings encountered during processing.
    """

    success: bool = Field(
        ...,
        description="Whether pattern learning succeeded",
    )
    candidate_patterns: list[ModelLearnedPattern] = Field(
        default_factory=list,
        description="Patterns not yet validated (lifecycle_state != validated)",
    )
    learned_patterns: list[ModelLearnedPattern] = Field(
        default_factory=list,
        description="Validated patterns ready for use (lifecycle_state == validated)",
    )
    metrics: ModelPatternLearningMetrics = Field(
        ...,
        description="Aggregated learning metrics",
    )
    metadata: ModelPatternLearningMetadata = Field(
        ...,
        description="Processing metadata",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during processing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelPatternLearningOutput",
]
