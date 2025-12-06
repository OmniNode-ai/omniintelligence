"""
Intelligence Enums Package.

Consolidated enums for the omniintelligence system.

This module provides a unified import location for all enums:

    # Preferred imports
    from omniintelligence._legacy.enums import (
        EnumFSMType,
        EnumOperationType,
        EnumIntelligenceOperationType,
        EnumIntentType,
    )

Exports:
    FSM Enums:
        - EnumFSMType: FSM types (INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT)
        - EnumFSMAction: FSM actions
        - EnumIngestionState: Document ingestion states
        - EnumPatternLearningState: Pattern learning 4-phase states
        - EnumQualityAssessmentState: Quality assessment states

    Operation Enums:
        - EnumOperationType: Orchestrator operation types
        - EnumIntentType: Intent communication types
        - EnumIntelligenceOperationType: Intelligence adapter operation types (45+)

    Entity Enums:
        - EnumEntityType: Knowledge graph entity types
        - EnumRelationshipType: Knowledge graph relationship types

    Workflow Enums:
        - EnumWorkflowStepType: Llama Index workflow step types
        - EnumCacheScope: Cache scope types

    Quality Enums:
        - EnumQualityDimension: Quality assessment dimensions

    System Enums:
        - EnumErrorSeverity: Error severity levels
        - EnumMetricType: Metric types for monitoring

Note:
    Event enums (EnumCodeAnalysisEventType, EnumAnalysisOperationType, EnumAnalysisErrorCode)
    are available from omniintelligence._legacy.models (canonical location)
"""

# Import from local enum files (relative imports within _legacy package)
from omniintelligence._legacy.enums.enum_cache import EnumCacheScope
from omniintelligence._legacy.enums.enum_entity import (
    EnumEntityType,
    EnumRelationshipType,
)
from omniintelligence._legacy.enums.enum_error import EnumErrorSeverity
from omniintelligence._legacy.enums.enum_fsm import (
    EnumFSMAction,
    EnumFSMType,
    EnumIngestionState,
    EnumPatternLearningState,
    EnumQualityAssessmentState,
)
from omniintelligence._legacy.enums.enum_intelligence_operation_type import (
    EnumIntelligenceOperationType,
)
from omniintelligence._legacy.enums.enum_intent import EnumIntentType
from omniintelligence._legacy.enums.enum_metric import EnumMetricType
from omniintelligence._legacy.enums.enum_operation import EnumOperationType
from omniintelligence._legacy.enums.enum_quality import EnumQualityDimension
from omniintelligence._legacy.enums.enum_workflow import EnumWorkflowStepType

# Note: Event enums (EnumCodeAnalysisEventType, EnumAnalysisOperationType, EnumAnalysisErrorCode)
# are intentionally NOT imported here to avoid circular dependencies.
# Import them directly from omniintelligence._legacy.models (canonical location)

__all__ = [
    "EnumCacheScope",
    "EnumEntityType",
    "EnumErrorSeverity",
    "EnumFSMAction",
    "EnumFSMType",
    "EnumIngestionState",
    "EnumIntelligenceOperationType",
    "EnumIntentType",
    "EnumMetricType",
    "EnumOperationType",
    "EnumPatternLearningState",
    "EnumQualityAssessmentState",
    "EnumQualityDimension",
    "EnumRelationshipType",
    "EnumWorkflowStepType",
]
