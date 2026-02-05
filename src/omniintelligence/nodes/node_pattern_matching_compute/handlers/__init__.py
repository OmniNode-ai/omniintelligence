"""Pattern Matching Compute Handlers.

This module provides pure handler functions for pattern matching operations.
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
        handle_pattern_matching_compute,
        match_patterns,
        PatternRecord,
        PatternMatchDetail,
    )

    # Using the compute handler (from node)
    input_data = ModelPatternMatchingInput(...)
    output = handle_pattern_matching_compute(input_data)

    # Using the pure matching function directly
    patterns: list[PatternRecord] = [...]
    result = match_patterns(
        code_snippet="def foo(): return None",
        patterns=patterns,
        min_confidence=0.5,
        max_results=10,
        operation="match",
    )
"""

from omniintelligence.nodes.node_pattern_matching_compute.handlers.exceptions import (
    PatternMatchingComputeError,
    PatternMatchingValidationError,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_compute import (
    handle_pattern_matching_compute,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_pattern_matching import (
    ALGORITHM_VERSION,
    PatternOperation,
    match_patterns,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.protocols import (
    PatternMatchDetail,
    PatternMatchingHandlerResult,
    PatternRecord,
    create_empty_handler_result,
    create_error_handler_result,
)

__all__ = [
    "ALGORITHM_VERSION",
    "PatternMatchDetail",
    "PatternMatchingComputeError",
    "PatternMatchingHandlerResult",
    "PatternMatchingValidationError",
    "PatternOperation",
    "PatternRecord",
    "create_empty_handler_result",
    "create_error_handler_result",
    "handle_pattern_matching_compute",
    "match_patterns",
]
