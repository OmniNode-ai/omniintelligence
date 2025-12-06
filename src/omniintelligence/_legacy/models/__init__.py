"""
Intelligence Models Package.

Consolidated models for the omniintelligence system.

This module provides a unified import path for all intelligence models:

    # Preferred import
    from omniintelligence._legacy.models import (
        ModelIntent,
        ModelOrchestratorInput,
        ModelIntelligenceInput,
        ModelEventEnvelope,
        ModelQualityAssessmentRequest,
        ModelPatternDetectionRequest,
    )

Exports:
    Intelligence Adapter Models:
        - ModelIntelligenceConfig: Configuration for intelligence adapter
        - ModelIntelligenceOutput: Output for intelligence operations
        - ModelPatternDetection: Detected pattern structure
        - ModelIntelligenceMetrics: Execution metrics
        - ModelIntelligenceInput: Input contract for intelligence operations

    API Contract Models (migrated from omninode_bridge):
        Quality Assessment:
            - ModelQualityAssessmentRequest: Request for code quality assessment
            - ModelQualityAssessmentResponse: Response with quality scores
            - ArchitecturalCompliance: Architectural compliance details
            - MaintainabilityMetrics: Maintainability assessment metrics
            - OnexComplianceDetails: ONEX compliance details

        Performance Analysis:
            - ModelPerformanceAnalysisRequest: Request for performance baseline
            - ModelPerformanceAnalysisResponse: Response with performance metrics
            - BaselineMetrics: Performance baseline metrics (deprecated)
            - OptimizationOpportunity: Optimization opportunity with ROI

        Pattern Detection:
            - ModelPatternDetectionRequest: Request for pattern detection
            - ModelPatternDetectionResponse: Response with detected patterns
            - DetectedPattern: Single detected pattern
            - ArchitecturalComplianceDetails: Architectural compliance for patterns

        Enums:
            - ArchitecturalEra: Era classifications for temporal relevance
            - ValidationStatus: Validation status for quality assessment
            - PatternCategory: Pattern categories for detection

        Additional:
            - ModelHealthCheckResponse: Health check response
            - ModelErrorResponse: Standard error response

    Intent Models:
        - ModelIntent: Intent communication between nodes

    Reducer Models:
        - ModelReducerInput: Input for intelligence reducer
        - ModelReducerOutput: Output for intelligence reducer
        - ModelReducerConfig: Configuration for reducer

    Orchestrator Models:
        - ModelOrchestratorInput: Input for intelligence orchestrator
        - ModelOrchestratorOutput: Output for intelligence orchestrator
        - ModelOrchestratorConfig: Configuration for orchestrator

    Entity Models:
        - ModelEntity: Knowledge graph entity
        - ModelRelationship: Knowledge graph relationship

    FSM Models:
        - ModelFSMState: FSM state representation

    Quality Models:
        - ModelQualityScore: Quality assessment score

    Workflow Models:
        - ModelWorkflowStep: Workflow step definition
        - ModelWorkflowExecution: Workflow execution state

    Event Models:
        - ModelEventEnvelope: Base event envelope for Kafka messages
        - ModelEventMetadata, ModelEventSource: Event metadata
        - ModelCodeAnalysis*Payload: Code analysis event payloads
        - ModelPattern*Payload: Intelligence result payloads
"""

# Intelligence adapter configuration
# Entity models
from omniintelligence._legacy.models.model_entity import (
    ModelEntity,
    ModelRelationship,
)

# Event envelope models
from omniintelligence._legacy.models.model_event_envelope import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)

# FSM models
from omniintelligence._legacy.models.model_fsm_state import ModelFSMState

# Intelligence adapter event models
from omniintelligence._legacy.models.model_intelligence_adapter_events import (
    # Enums
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    # Helpers
    IntelligenceAdapterEventHelpers,
    # Event payload models
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
    # Intelligence result payloads
    ModelDiscoveryPayload,
    ModelInfrastructureScanPayload,
    ModelPatternExtractionPayload,
    ModelSchemaDiscoveryPayload,
    # Convenience functions
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# API contract models (migrated from omninode_bridge)
from omniintelligence._legacy.models.model_intelligence_api_contracts import (
    # Quality Assessment
    ArchitecturalCompliance,
    # Pattern Detection
    ArchitecturalComplianceDetails,
    # Enums
    ArchitecturalEra,
    # Performance Analysis
    BaselineMetrics,
    DetectedPattern,
    MaintainabilityMetrics,
    # Additional
    ModelErrorResponse,
    ModelHealthCheckResponse,
    ModelPatternDetectionRequest,
    ModelPatternDetectionResponse,
    ModelPerformanceAnalysisRequest,
    ModelPerformanceAnalysisResponse,
    ModelQualityAssessmentRequest,
    ModelQualityAssessmentResponse,
    OnexComplianceDetails,
    OptimizationOpportunity,
    PatternCategory,
    ValidationStatus,
)
from omniintelligence._legacy.models.model_intelligence_config import (
    ModelIntelligenceConfig,
)

# Intelligence adapter input
from omniintelligence._legacy.models.model_intelligence_input import (
    ModelIntelligenceInput,
)

# Intelligence adapter output
from omniintelligence._legacy.models.model_intelligence_output import (
    ModelIntelligenceMetrics,
    ModelIntelligenceOutput,
    ModelPatternDetection,
)

# Intent models
from omniintelligence._legacy.models.model_intent import ModelIntent

# Orchestrator models
from omniintelligence._legacy.models.model_orchestrator import (
    ModelOrchestratorConfig,
    ModelOrchestratorInput,
    ModelOrchestratorOutput,
)

# Quality models
from omniintelligence._legacy.models.model_quality_score import ModelQualityScore

# Reducer models
from omniintelligence._legacy.models.model_reducer import (
    ModelReducerConfig,
    ModelReducerInput,
    ModelReducerOutput,
)

# Workflow models
from omniintelligence._legacy.models.model_workflow import (
    ModelWorkflowExecution,
    ModelWorkflowStep,
)

__all__ = [
    # API contract models - Quality Assessment
    "ArchitecturalCompliance",
    "ArchitecturalComplianceDetails",
    # API contract enums
    "ArchitecturalEra",
    "BaselineMetrics",
    "DetectedPattern",
    # Event enums
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    "EnumCodeAnalysisEventType",
    # Event helpers
    "IntelligenceAdapterEventHelpers",
    "MaintainabilityMetrics",
    # Code analysis event payloads
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
    "ModelDiscoveryPayload",
    # Entity models
    "ModelEntity",
    "ModelErrorResponse",
    # Event envelope models
    "ModelEventEnvelope",
    "ModelEventMetadata",
    "ModelEventSource",
    # FSM models
    "ModelFSMState",
    "ModelHealthCheckResponse",
    "ModelInfrastructureScanPayload",
    # Intelligence adapter models
    "ModelIntelligenceConfig",
    "ModelIntelligenceInput",
    "ModelIntelligenceMetrics",
    "ModelIntelligenceOutput",
    # Intent models
    "ModelIntent",
    # Orchestrator models
    "ModelOrchestratorConfig",
    "ModelOrchestratorInput",
    "ModelOrchestratorOutput",
    "ModelPatternDetection",
    "ModelPatternDetectionRequest",
    "ModelPatternDetectionResponse",
    # Intelligence result payloads
    "ModelPatternExtractionPayload",
    "ModelPerformanceAnalysisRequest",
    "ModelPerformanceAnalysisResponse",
    "ModelQualityAssessmentRequest",
    "ModelQualityAssessmentResponse",
    # Quality models
    "ModelQualityScore",
    # Reducer models
    "ModelReducerConfig",
    "ModelReducerInput",
    "ModelReducerOutput",
    "ModelRelationship",
    "ModelSchemaDiscoveryPayload",
    # Workflow models
    "ModelWorkflowExecution",
    "ModelWorkflowStep",
    "OnexComplianceDetails",
    "OptimizationOpportunity",
    "PatternCategory",
    "ValidationStatus",
    # Convenience functions
    "create_completed_event",
    "create_failed_event",
    "create_request_event",
]
