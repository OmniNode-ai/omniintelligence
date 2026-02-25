# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern Matching Compute Node - Thin shell delegating to handler.

This node follows the ONEX declarative pattern where the node class is a thin
shell that delegates all logic to handler functions.

Matching Algorithms:
    - keyword_overlap: Score based on shared keywords (Jaccard similarity)
    - regex_match: Match pattern signatures as regex/substring

Operation Routing:
    - "match": keyword_overlap (categorical matching)
    - "similarity": keyword_overlap (with looser threshold)
    - "classify": keyword_overlap (categorization)
    - "validate": regex_match (structural validation)
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
    handle_pattern_matching_compute,
)
from omniintelligence.nodes.node_pattern_matching_compute.models import (
    ModelPatternMatchingInput,
    ModelPatternMatchingOutput,
)


class NodePatternMatchingCompute(
    NodeCompute[ModelPatternMatchingInput, ModelPatternMatchingOutput]
):
    """Pure compute node for matching code patterns.

    Matches code against a pattern library using keyword overlap or
    regex-based algorithms. The operation type determines the matching
    strategy used.

    Supported Operations:
        - match: Find patterns matching the code (keyword_overlap)
        - similarity: Compute similarity scores (keyword_overlap)
        - classify: Classify code into pattern categories (keyword_overlap)
        - validate: Validate code structure against patterns (regex_match)

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelPatternMatchingInput
    ) -> ModelPatternMatchingOutput:
        """Match code against patterns by delegating to handler function."""
        return handle_pattern_matching_compute(input_data)


__all__ = ["NodePatternMatchingCompute"]
