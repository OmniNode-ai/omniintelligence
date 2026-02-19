"""Analysis operation type enum for code analysis requests."""

from enum import Enum


class EnumAnalysisOperationType(str, Enum):
    """Analysis operation types for code analysis requests.

    Defines the types of analysis that can be requested via
    CODE_ANALYSIS_REQUESTED events.

    Note:
        For the full list of intelligence operation types (45+),
        see EnumIntelligenceOperationType in enum_intelligence_operation_type.py.
        This enum is specific to event-based analysis operations.
    """

    QUALITY_ASSESSMENT = "quality_assessment"
    PATTERN_DETECTION = "pattern_detection"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    ONEX_COMPLIANCE = "onex_compliance"
    PATTERN_EXTRACTION = "pattern_extraction"
    ARCHITECTURAL_COMPLIANCE = "architectural_compliance"


__all__ = ["EnumAnalysisOperationType"]
