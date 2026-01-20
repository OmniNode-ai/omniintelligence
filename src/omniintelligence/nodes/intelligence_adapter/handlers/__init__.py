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

Usage:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_quality_response,
    )

    result = transform_quality_response(raw_api_response)
"""

from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_quality import (
    transform_quality_response,
)

__all__ = [
    "transform_quality_response",
]
