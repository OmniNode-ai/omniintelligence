"""Intelligence Adapter Handlers.

This module provides pluggable handlers for intelligence adapter operations.
Handlers implement the transformation and processing logic for specific operation types,
following the handler-based architecture pattern (Option C from ARCHITECTURE.md).

Handler Types:
    1. **Operation Handlers** (ProtocolMessageHandler implementations):
       - HandlerCodeAnalysisRequested: Handles CODE_ANALYSIS_REQUESTED events
       - HandlerUnknownEvent: Default handler for unrouted events

    2. **Transform Handlers** (pure functions):
       - transform_quality_response: Quality assessment response transformation
       - transform_pattern_response: Pattern detection response transformation
       - transform_performance_response: Performance analysis response transformation

Operation Handler Pattern:
    Operation handlers implement ProtocolMessageHandler and:
    - Receive ModelEventEnvelope from the runtime
    - Process the payload using transform handlers
    - Return ModelHandlerOutput.for_effect(events=...) with completion/failure events
    - Runtime publishes the returned events

Transform Handler Pattern:
    Transform handlers are pure functions that:
    - Accept raw response data from the intelligence service
    - Transform to canonical format for event publishing
    - Have no side effects (pure transformations)

Type Safety:
    All handler functions are typed with specific TypedDict return types:
    - transform_quality_response() -> QualityHandlerResponse
    - transform_pattern_response() -> PatternHandlerResponse
    - transform_performance_response() -> PerformanceHandlerResponse
    - validate_handler_result() -> ValidatedHandlerResponse

    These types enable mypy validation of handler return structures.

Usage:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        # Operation handlers (ProtocolMessageHandler)
        HandlerCodeAnalysisRequested,
        HandlerUnknownEvent,
        # Transform functions
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
"""

# Operation handlers (ProtocolMessageHandler implementations)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_code_analysis_requested import (
    HANDLER_ID as CODE_ANALYSIS_HANDLER_ID,
    HandlerCodeAnalysisRequested,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_unknown_event import (
    HANDLER_ID as UNKNOWN_EVENT_HANDLER_ID,
    HandlerUnknownEvent,
)

# Transform handlers (pure functions)
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
from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
    HandlerValidationError,
    MAX_ISSUES,
    SCORE_MAX,
    SCORE_MIN,
    _get_optional_field,
    _require_field,
    _require_float,
    _safe_bool,
    _safe_dict,
    _safe_float,
    _safe_list,
)
from omniintelligence.nodes.intelligence_adapter.handlers.validation import (
    validate_handler_result,
)

__all__ = [
    # Operation handlers
    "CODE_ANALYSIS_HANDLER_ID",
    "HandlerCodeAnalysisRequested",
    "HandlerUnknownEvent",
    "UNKNOWN_EVENT_HANDLER_ID",
    # Transform handlers
    "transform_pattern_response",
    "transform_performance_response",
    "transform_quality_response",
    "validate_handler_result",
    # Protocols and types
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
    # Utils
    "HandlerValidationError",
    "MAX_ISSUES",
    "SCORE_MAX",
    "SCORE_MIN",
    "_get_optional_field",
    "_require_field",
    "_require_float",
    "_safe_bool",
    "_safe_dict",
    "_safe_float",
    "_safe_list",
]
