"""Quality Scoring Compute Node - Thin shell delegating to handler.

This node follows the ONEX declarative pattern where the node class is a thin
shell that delegates all logic to handler functions.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    handle_quality_scoring_compute,
)
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)


class NodeQualityScoringCompute(
    NodeCompute[ModelQualityScoringInput, ModelQualityScoringOutput]
):
    """Pure compute node for scoring code quality.

    Analyzes source code across six quality dimensions:
        - complexity: Cyclomatic complexity (inverted - lower is better)
        - maintainability: Code structure quality
        - documentation: Docstring and comment coverage
        - temporal_relevance: Code freshness indicators
        - patterns: ONEX pattern adherence
        - architectural: Module organization

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelQualityScoringInput
    ) -> ModelQualityScoringOutput:
        """Score code quality by delegating to handler function."""
        return handle_quality_scoring_compute(input_data)


__all__ = ["NodeQualityScoringCompute"]
