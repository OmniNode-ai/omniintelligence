"""Output model for Pattern Learning Compute.

Uses contract models from omnibase_core for canonical pattern representations.
"""

from __future__ import annotations

from omnibase_core.enums.pattern_learning import EnumPatternLifecycleState
from omnibase_core.models.pattern_learning import (
    ModelLearnedPattern,
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
)
from pydantic import BaseModel, Field


class ModelPatternLearningOutput(BaseModel):
    """Output model for pattern learning operations.

    This model represents the result of pattern learning operations.
    Patterns are split by lifecycle_state (from ModelLearnedPattern):
    - candidate_patterns: CANDIDATE, PROVISIONAL, or DEPRECATED states
    - learned_patterns: VALIDATED state only (ready for production use)

    Attributes:
        success: Whether pattern learning succeeded.
        candidate_patterns: Patterns with lifecycle_state != VALIDATED.
        learned_patterns: Patterns with lifecycle_state == VALIDATED.
        metrics: Aggregated metrics from the learning process.
        metadata: Processing metadata (timestamps, thresholds used, etc.).
        warnings: Non-fatal warnings encountered during processing.

    Factory Methods:
        from_patterns: Create output for successful operations with auto-splitting.
        from_failure: Create output for failed operations with error handling.
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
            success=False is needed, use from_failure() instead.
        """
        candidates: list[ModelLearnedPattern] = []
        learned: list[ModelLearnedPattern] = []
        for p in all_patterns:
            if p.lifecycle_state == EnumPatternLifecycleState.VALIDATED:
                learned.append(p)
            else:
                candidates.append(p)
        return cls(
            success=True,
            candidate_patterns=candidates,
            learned_patterns=learned,
            metrics=metrics,
            metadata=metadata,
            warnings=warnings or [],
        )

    @classmethod
    def from_failure(
        cls,
        metrics: ModelPatternLearningMetrics,
        metadata: ModelPatternLearningMetadata,
        error_message: str,
        warnings: list[str] | None = None,
    ) -> ModelPatternLearningOutput:
        """Create output for failed pattern learning operations.

        This is a convenience factory for failed pattern learning operations.
        It creates an output with success=False, empty pattern lists, and
        the error message included in warnings.

        Args:
            metrics: Aggregated learning metrics (may be partial).
            metadata: Processing metadata.
            error_message: The primary error that caused the failure.
            warnings: Optional additional non-fatal warnings.

        Returns:
            ModelPatternLearningOutput with success=False and error in warnings.
        """
        all_warnings = [error_message]
        if warnings:
            all_warnings.extend(warnings)
        return cls(
            success=False,
            candidate_patterns=[],
            learned_patterns=[],
            metrics=metrics,
            metadata=metadata,
            warnings=all_warnings,
        )


__all__ = [
    "ModelPatternLearningOutput",
]
