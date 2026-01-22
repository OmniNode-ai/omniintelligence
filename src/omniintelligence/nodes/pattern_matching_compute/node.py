# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/10
# Status: Interface defined, implementation pending
"""Pattern Matching Compute - STUB compute node for pattern matching."""
from __future__ import annotations

import warnings
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.pattern_matching_compute.models import (
    ModelPatternMatchingInput,
    ModelPatternMatchingMetadata,
    ModelPatternMatchingOutput,
)

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/10"


class NodePatternMatchingCompute(NodeCompute[ModelPatternMatchingInput, ModelPatternMatchingOutput]):
    """STUB: Pure compute node for matching code patterns.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Match code against learned patterns
        - Return similarity scores and matches
        - Integrate with pattern learning pipeline
    """

    is_stub: ClassVar[bool] = True

    async def compute(
        self, input_data: ModelPatternMatchingInput
    ) -> ModelPatternMatchingOutput:
        """Compute pattern matching (STUB - returns empty result).

        Args:
            input_data: Typed input model for pattern matching (unused in stub).

        Returns:
            Typed ModelPatternMatchingOutput with success=True but no patterns matched.
        """
        warnings.warn(
            f"NodePatternMatchingCompute.compute() is a stub that returns empty "
            f"results. No actual pattern matching is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        # Return typed output model - minimal stub logic following declarative-node standard
        # Note: operation field is omitted because input operation types (match, similarity,
        # classify, validate) are different from output metadata operation types (exact_match,
        # fuzzy_match, etc.). The metadata.operation describes the algorithm used, not the
        # requested operation. For stubs, we leave it as None since no algorithm was executed.
        return ModelPatternMatchingOutput(
            success=True,
            patterns_matched=[],
            pattern_scores={},
            metadata=ModelPatternMatchingMetadata(
                status="stub",
                message=f"NodePatternMatchingCompute is not yet implemented. "
                f"Requested operation: {input_data.operation}",
                tracking_url=_STUB_TRACKING_URL,
            ),
        )


__all__ = ["NodePatternMatchingCompute"]
