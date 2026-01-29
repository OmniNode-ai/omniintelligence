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
    Patterns are split by lifecycle_state (from ModelLearnedPattern):
    - candidate_patterns: Any state except "validated" (draft, pending, rejected, etc.)
    - learned_patterns: lifecycle_state == "validated" (ready for production use)

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

    @classmethod
    def from_patterns(
        cls,
        all_patterns: list[ModelLearnedPattern],
        metrics: ModelPatternLearningMetrics,
        metadata: ModelPatternLearningMetadata,
        warnings: list[str] | None = None,
    ) -> ModelPatternLearningOutput:
        """Create output by automatically splitting patterns by lifecycle_state.

        This is a convenience factory for successful pattern learning operations.
        It automatically categorizes patterns based on their lifecycle_state.

        Args:
            all_patterns: All patterns to split (validated vs non-validated).
            metrics: Aggregated learning metrics.
            metadata: Processing metadata.
            warnings: Optional non-fatal warnings.

        Returns:
            ModelPatternLearningOutput with patterns split by validation state.

        Note:
            This factory always sets success=True. For failure cases where
            success=False is needed, use the constructor directly.
        """
        candidates = [p for p in all_patterns if p.lifecycle_state != "validated"]
        learned = [p for p in all_patterns if p.lifecycle_state == "validated"]
        return cls(
            success=True,
            candidate_patterns=candidates,
            learned_patterns=learned,
            metrics=metrics,
            metadata=metadata,
            warnings=warnings or [],
        )


__all__ = [
    "ModelPatternLearningOutput",
]
