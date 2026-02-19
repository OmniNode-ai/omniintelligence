"""Code analysis event type enum for Kafka topics."""

from enum import Enum


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


__all__ = ["EnumCodeAnalysisEventType"]
