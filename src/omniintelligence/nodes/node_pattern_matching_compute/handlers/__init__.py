# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern Matching Compute Handlers.

Pure handler functions for pattern matching operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts code snippet and pattern library
    - Computes matches using keyword or regex algorithms
    - Returns typed PatternMatchingHandlerResult
    - Has no side effects (pure computation)

Matching Algorithms:
    - keyword_overlap: Score based on shared keywords (Jaccard similarity)
    - regex_match: Match pattern signatures as regex/substring

Operation Routing:
    - "match": keyword_overlap (categorical matching)
    - "similarity": keyword_overlap (with looser threshold)
    - "classify": keyword_overlap (categorization)
    - "validate": regex_match (structural validation)

Usage:
    from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
        HandlerPatternMatchingCompute,
        HandlerPatternMatching,
        ModelPatternMatchingRequest,
        PatternRecord,
        PatternMatchDetail,
    )

    # Using the compute handler (from node)
    input_data = ModelPatternMatchingInput(...)
    output = HandlerPatternMatchingCompute().handle(input_data)

    # Using the pure matching function directly
    patterns: list[PatternRecord] = [...]
    result = HandlerPatternMatching().handle(
        ModelPatternMatchingRequest(
            code_snippet="def foo(): return None",
            patterns=patterns,
            min_confidence=0.5,
            max_results=10,
            operation="match",
        )
    )
"""

from omniintelligence.nodes.node_pattern_matching_compute.handlers.exceptions import (
    PatternMatchingComputeError,
    PatternMatchingValidationError,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_compute import (
    HandlerPatternMatchingCompute,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_pattern_matching import (
    ALGORITHM_VERSION,
    HandlerPatternMatching,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.protocols import (
    PatternMatchDetail,
    PatternMatchingHandlerResult,
    PatternRecord,
    create_empty_handler_result,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_request import (
    ModelPatternMatchingRequest,
    PatternOperation,
)

__all__ = [
    "ALGORITHM_VERSION",
    "HandlerPatternMatching",
    "HandlerPatternMatchingCompute",
    "ModelPatternMatchingRequest",
    "PatternMatchDetail",
    "PatternMatchingComputeError",
    "PatternMatchingHandlerResult",
    "PatternMatchingValidationError",
    "PatternOperation",
    "PatternRecord",
    "create_empty_handler_result",
]
