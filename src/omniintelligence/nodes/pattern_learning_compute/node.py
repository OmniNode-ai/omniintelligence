"""Pattern Learning Compute - Thin declarative COMPUTE node shell.

This node follows the ONEX declarative pattern where the node is a thin shell
that delegates ALL business logic to handler functions. The node contains
no custom routing, iteration, or computation logic.

Pattern: "Thin shell, fat handler"

All aggregation logic is implemented in:
    handlers/handler_pattern_learning.py

SEMANTIC NOTE:
    This node AGGREGATES and SUMMARIZES observed patterns.
    It does NOT perform statistical learning or weight updates.
    See handler docstrings for the semantic framing.

Ticket: OMN-1663
"""

from __future__ import annotations

from datetime import UTC, datetime

from omnibase_core.enums.pattern_learning import EnumPatternLearningStatus
from omnibase_core.models.container import ModelONEXContainer
from omnibase_core.models.pattern_learning import (
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
)
from omnibase_core.models.primitives import ModelSemVer
from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.pattern_learning_compute.handlers import (
    PatternLearningComputeError,
    PatternLearningValidationError,
    aggregate_patterns,
)
from omniintelligence.nodes.pattern_learning_compute.models import (
    ModelPatternLearningInput,
    ModelPatternLearningOutput,
)


class NodePatternLearningCompute(
    NodeCompute[ModelPatternLearningInput, ModelPatternLearningOutput]
):
    """Thin declarative shell for pattern aggregation.

    All business logic is delegated to the aggregate_patterns handler.
    This node only provides the ONEX container interface.

    SEMANTIC NOTE:
        This node aggregates and summarizes observed patterns.
        It does NOT perform statistical learning. See handler docstrings.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the compute node with ONEX container."""
        super().__init__(container)

    async def compute(
        self, input_data: ModelPatternLearningInput
    ) -> ModelPatternLearningOutput:
        """Aggregate patterns by delegating to handler.

        Args:
            input_data: Training data and learning parameters.

        Returns:
            Pattern learning output with candidate and learned patterns,
            or an error response if validation/computation fails.
        """
        try:
            result = aggregate_patterns(
                training_data=list(input_data.training_data),
                parameters=input_data.learning_parameters,
            )
            return ModelPatternLearningOutput(
                success=result["success"],
                candidate_patterns=result["candidate_patterns"],
                learned_patterns=result["learned_patterns"],
                metrics=result["metrics"],
                metadata=result["metadata"],
                warnings=result.get("warnings", []),
            )
        except PatternLearningValidationError as e:
            return _build_error_response("validation_error", str(e))
        except PatternLearningComputeError as e:
            return _build_error_response("compute_error", str(e))


def _build_error_response(
    error_type: str,
    error_message: str,
) -> ModelPatternLearningOutput:
    """Build an error response for failed pattern learning.

    Args:
        error_type: Type of error (validation_error or compute_error).
        error_message: Human-readable error message.

    Returns:
        ModelPatternLearningOutput with success=False and error details.
    """
    metrics = ModelPatternLearningMetrics(
        input_count=0,
        cluster_count=0,
        candidate_count=0,
        learned_count=0,
        discarded_count=0,
        merged_count=0,
        mean_confidence=0.0,
        mean_label_agreement=0.0,
        mean_cluster_cohesion=0.0,
        processing_time_ms=0.0,
    )

    metadata = ModelPatternLearningMetadata(
        status=EnumPatternLearningStatus.FAILED,
        model_version=ModelSemVer(major=1, minor=0, patch=0),
        timestamp=datetime.now(UTC),
        deduplication_threshold_used=0.0,
        promotion_threshold_used=0.0,
        training_samples=0,
        validation_samples=0,
        convergence_achieved=False,
        early_stopped=True,
        final_epoch=0,
    )

    return ModelPatternLearningOutput(
        success=False,
        candidate_patterns=[],
        learned_patterns=[],
        metrics=metrics,
        metadata=metadata,
        warnings=[f"{error_type}: {error_message}"],
    )


__all__ = ["NodePatternLearningCompute"]
