"""
FSM-related enums for omniintelligence.

Contains FSM types, actions, and state enums for various FSM workflows.
"""

from enum import Enum


class EnumFSMType(str, Enum):
    """FSM types handled by the intelligence reducer."""
    INGESTION = "INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"


class EnumFSMAction(str, Enum):
    """Generic FSM actions (specific FSMs may have additional actions)."""
    # Ingestion FSM actions
    START_PROCESSING = "START_PROCESSING"
    COMPLETE_INDEXING = "COMPLETE_INDEXING"
    REINDEX = "REINDEX"

    # Pattern Learning FSM actions
    ADVANCE_TO_MATCHING = "ADVANCE_TO_MATCHING"
    ADVANCE_TO_VALIDATION = "ADVANCE_TO_VALIDATION"
    ADVANCE_TO_TRACEABILITY = "ADVANCE_TO_TRACEABILITY"
    COMPLETE_LEARNING = "COMPLETE_LEARNING"
    RELEARN = "RELEARN"

    # Quality Assessment FSM actions
    START_ASSESSMENT = "START_ASSESSMENT"
    COMPLETE_SCORING = "COMPLETE_SCORING"
    STORE_RESULTS = "STORE_RESULTS"
    REASSESS = "REASSESS"

    # Common actions
    FAIL = "FAIL"
    RETRY = "RETRY"


class EnumIngestionState(str, Enum):
    """States for document ingestion FSM."""
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class EnumPatternLearningState(str, Enum):
    """States for pattern learning FSM (4 phases)."""
    FOUNDATION = "FOUNDATION"
    MATCHING = "MATCHING"
    VALIDATION = "VALIDATION"
    TRACEABILITY = "TRACEABILITY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EnumQualityAssessmentState(str, Enum):
    """States for quality assessment FSM."""
    RAW = "RAW"
    ASSESSING = "ASSESSING"
    SCORED = "SCORED"
    STORED = "STORED"
    FAILED = "FAILED"


__all__ = [
    "EnumFSMAction",
    "EnumFSMType",
    "EnumIngestionState",
    "EnumPatternLearningState",
    "EnumQualityAssessmentState",
]
