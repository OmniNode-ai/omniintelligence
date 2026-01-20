"""Intelligence Adapter Handlers.

This module provides pluggable handlers for intelligence adapter operations.
Handlers implement the transformation and processing logic for specific operation types,
following the handler-based architecture pattern (Option C from ARCHITECTURE.md).

Handler Pattern:
    Each handler is a standalone module with pure functions that:
    - Accept raw response data from the intelligence service
    - Transform to canonical format for event publishing
    - Have no side effects (pure transformations)

Available Handlers:
    - handler_transform_quality: Quality assessment response transformation
    - handler_transform_pattern: Pattern detection response transformation
    - handler_transform_performance: Performance analysis response transformation

Usage:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_quality_response,
        transform_pattern_response,
        transform_performance_response,
    )

    quality_result = transform_quality_response(raw_quality_response)
    pattern_result = transform_pattern_response(raw_pattern_response)
    performance_result = transform_performance_response(raw_performance_response)
"""

from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_pattern import (
    transform_pattern_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_performance import (
    transform_performance_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_quality import (
    transform_quality_response,
)

__all__ = [
    "transform_pattern_response",
    "transform_performance_response",
    "transform_quality_response",
]
