"""
Shared enums for omniintelligence.

All enums used across nodes for consistency and type safety.
"""

from enum import Enum, auto


class EnumFSMType(str, Enum):
    """FSM types handled by the intelligence reducer."""
    INGESTION = "INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"


class EnumOperationType(str, Enum):
    """Operation types handled by the intelligence orchestrator."""
    DOCUMENT_INGESTION = "DOCUMENT_INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"
    RELATIONSHIP_DETECTION = "RELATIONSHIP_DETECTION"
    VECTORIZATION = "VECTORIZATION"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"


class EnumIntentType(str, Enum):
    """Intent types for communication between nodes."""
    STATE_UPDATE = "STATE_UPDATE"
    WORKFLOW_TRIGGER = "WORKFLOW_TRIGGER"
    EVENT_PUBLISH = "EVENT_PUBLISH"
    CACHE_INVALIDATE = "CACHE_INVALIDATE"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    ERROR_NOTIFICATION = "ERROR_NOTIFICATION"


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


class EnumEntityType(str, Enum):
    """Entity types for knowledge graph."""
    DOCUMENT = "DOCUMENT"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    INTERFACE = "INTERFACE"
    TYPE = "TYPE"
    PATTERN = "PATTERN"
    PROJECT = "PROJECT"
    FILE = "FILE"
    DEPENDENCY = "DEPENDENCY"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"


class EnumRelationshipType(str, Enum):
    """Relationship types for knowledge graph."""
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    DEFINES = "DEFINES"
    USES = "USES"
    MATCHES_PATTERN = "MATCHES_PATTERN"
    SIMILAR_TO = "SIMILAR_TO"


class EnumQualityDimension(str, Enum):
    """Quality assessment dimensions."""
    MAINTAINABILITY = "MAINTAINABILITY"
    READABILITY = "READABILITY"
    COMPLEXITY = "COMPLEXITY"
    DOCUMENTATION = "DOCUMENTATION"
    TESTING = "TESTING"
    SECURITY = "SECURITY"


class EnumWorkflowStepType(str, Enum):
    """Workflow step types for Llama Index workflows."""
    VALIDATION = "VALIDATION"
    COMPUTE = "COMPUTE"
    EFFECT = "EFFECT"
    INTENT = "INTENT"
    PARALLEL = "PARALLEL"
    SEQUENTIAL = "SEQUENTIAL"
    CONDITIONAL = "CONDITIONAL"


class EnumCacheScope(str, Enum):
    """Cache scope types."""
    GLOBAL = "GLOBAL"
    WORKFLOW = "WORKFLOW"
    OPERATION = "OPERATION"
    ENTITY = "ENTITY"


class EnumErrorSeverity(str, Enum):
    """Error severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EnumMetricType(str, Enum):
    """Metric types for monitoring."""
    WORKFLOW = "WORKFLOW"
    PERFORMANCE = "PERFORMANCE"
    ERRORS = "ERRORS"
    RESOURCE = "RESOURCE"
    FSM = "FSM"
    LEASE = "LEASE"


__all__ = [
    "EnumFSMType",
    "EnumOperationType",
    "EnumIntentType",
    "EnumFSMAction",
    "EnumIngestionState",
    "EnumPatternLearningState",
    "EnumQualityAssessmentState",
    "EnumEntityType",
    "EnumRelationshipType",
    "EnumQualityDimension",
    "EnumWorkflowStepType",
    "EnumCacheScope",
    "EnumErrorSeverity",
    "EnumMetricType",
]
