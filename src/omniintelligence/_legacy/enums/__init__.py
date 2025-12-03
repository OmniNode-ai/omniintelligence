"""
Intelligence Enums Package.

Consolidated enums for the omniintelligence system.

This module provides a unified import location for all enums:

    # Preferred imports
    from omniintelligence.enums import (
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
    are available from omniintelligence.models (canonical location)
"""

# Import from local enum files
from omniintelligence.enums.enum_cache import EnumCacheScope
from omniintelligence.enums.enum_entity import EnumEntityType, EnumRelationshipType
from omniintelligence.enums.enum_error import EnumErrorSeverity
from omniintelligence.enums.enum_fsm import (
    EnumFSMAction,
    EnumFSMType,
    EnumIngestionState,
    EnumPatternLearningState,
    EnumQualityAssessmentState,
)
from omniintelligence.enums.enum_intelligence_operation_type import (
    EnumIntelligenceOperationType,
)
from omniintelligence.enums.enum_intent import EnumIntentType
from omniintelligence.enums.enum_metric import EnumMetricType
from omniintelligence.enums.enum_operation import EnumOperationType
from omniintelligence.enums.enum_quality import EnumQualityDimension
from omniintelligence.enums.enum_workflow import EnumWorkflowStepType

# Note: Event enums (EnumCodeAnalysisEventType, EnumAnalysisOperationType, EnumAnalysisErrorCode)
# are intentionally NOT imported here to avoid circular dependencies.
# Import them directly from omniintelligence.models (canonical location)

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
