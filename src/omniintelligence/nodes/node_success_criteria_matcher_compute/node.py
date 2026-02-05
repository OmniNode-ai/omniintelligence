"""Success Criteria Matcher Compute Node - Thin shell delegating to handler.

This node follows the ONEX declarative pattern where the node class is a thin
shell that delegates all logic to handler functions.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    handle_success_criteria_compute,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.models import (
    ModelSuccessCriteriaInput,
    ModelSuccessCriteriaOutput,
)


class NodeSuccessCriteriaMatcherCompute(
    NodeCompute[ModelSuccessCriteriaInput, ModelSuccessCriteriaOutput]
):
    """Pure compute node for matching success criteria against execution outcomes.

    Evaluates execution outcomes against a list of success criteria using
    configurable comparison operators:
        - equals/not_equals: Exact value comparison
        - greater_than/less_than/greater_or_equal/less_or_equal: Numeric comparison
        - contains/not_contains: Membership or substring tests
        - regex: Pattern matching
        - is_null/is_not_null: Null checks

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelSuccessCriteriaInput
    ) -> ModelSuccessCriteriaOutput:
        """Match criteria by delegating to handler function."""
        return handle_success_criteria_compute(input_data)


__all__ = ["NodeSuccessCriteriaMatcherCompute"]
