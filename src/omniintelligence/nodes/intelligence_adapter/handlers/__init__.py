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
    - validation: Handler return value validation utilities
    - protocols: TypedDict definitions for type-safe handler responses

Type Safety:
    All handler functions are typed with specific TypedDict return types:
    - transform_quality_response() -> QualityHandlerResponse
    - transform_pattern_response() -> PatternHandlerResponse
    - transform_performance_response() -> PerformanceHandlerResponse
    - validate_handler_result() -> ValidatedHandlerResponse

    These types enable mypy validation of handler return structures.

Usage:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_quality_response,
        transform_pattern_response,
        transform_performance_response,
        validate_handler_result,
        # Type protocols for type hints
        QualityHandlerResponse,
        PerformanceHandlerResponse,
        PatternHandlerResponse,
        ValidatedHandlerResponse,
    )

    quality_result = transform_quality_response(raw_quality_response)
    validated_result = validate_handler_result(quality_result, "assess_code_quality")
    # validated_result is guaranteed to have all expected keys with proper types
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
from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
    AnyHandlerResponse,
    AnyResultData,
    BaseHandlerResponse,
    PatternHandlerResponse,
    PatternResultData,
    PerformanceBaselineMetrics,
    PerformanceHandlerResponse,
    PerformanceOpportunity,
    PerformanceResultData,
    QualityHandlerResponse,
    QualityResultData,
    ValidatedHandlerResponse,
)
from omniintelligence.nodes.intelligence_adapter.handlers.validation import (
    validate_handler_result,
)

__all__ = [
    "AnyHandlerResponse",
    "AnyResultData",
    "BaseHandlerResponse",
    "PatternHandlerResponse",
    "PatternResultData",
    "PerformanceBaselineMetrics",
    "PerformanceHandlerResponse",
    "PerformanceOpportunity",
    "PerformanceResultData",
    "QualityHandlerResponse",
    "QualityResultData",
    "ValidatedHandlerResponse",
    "transform_pattern_response",
    "transform_performance_response",
    "transform_quality_response",
    "validate_handler_result",
]
