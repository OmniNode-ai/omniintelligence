"""Code analysis enums for intelligence adapter events.

This module contains enumerations used by the intelligence adapter
for event processing and error handling.

ONEX Compliance:
- Enum-based naming: Enum{Category}
- String-based enums for JSON serialization
- Integration with Pydantic models

Migration Note:
    These enums were extracted from the monolithic
    node_intelligence_adapter_effect.py as part of OMN-1437.
"""

from enum import Enum


class EnumAnalysisErrorCode(str, Enum):
    """Analysis error codes for failure events.

    Used in ModelCodeAnalysisFailedPayload to categorize the type
    of failure that occurred during code analysis.
    """

    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    SERVICE_ERROR = "service_error"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class EnumAnalysisOperationType(str, Enum):
    """Analysis operation types for code analysis requests.

    Defines the types of analysis that can be requested via
    CODE_ANALYSIS_REQUESTED events.

    Note:
        For the full list of intelligence operation types (45+),
        see EnumIntelligenceOperationType in enum_operation.py.
        This enum is specific to event-based analysis operations.
    """

    QUALITY_ASSESSMENT = "quality_assessment"
    PATTERN_DETECTION = "pattern_detection"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    ONEX_COMPLIANCE = "onex_compliance"
    PATTERN_EXTRACTION = "pattern_extraction"
    ARCHITECTURAL_COMPLIANCE = "architectural_compliance"


class EnumCodeAnalysisEventType(str, Enum):
    """Code analysis event types for Kafka topics.

    Maps to the three event types used by the intelligence adapter:
    - REQUESTED: Input event from external services
    - COMPLETED: Output event for successful analysis
    - FAILED: Output event for analysis failures

    Both short form (REQUESTED) and full form (CODE_ANALYSIS_REQUESTED)
    are provided for compatibility.
    """

    REQUESTED = "requested"
    COMPLETED = "completed"
    FAILED = "failed"
    # Aliases for compatibility with code using CODE_ANALYSIS_* prefixed names
    CODE_ANALYSIS_REQUESTED = "code_analysis_requested"
    CODE_ANALYSIS_COMPLETED = "code_analysis_completed"
    CODE_ANALYSIS_FAILED = "code_analysis_failed"


__all__ = [
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    "EnumCodeAnalysisEventType",
]
