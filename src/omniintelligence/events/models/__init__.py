"""Event models for Kafka message schemas."""

from omniintelligence.events.models.model_event_envelope import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)
from omniintelligence.events.models.intelligence_adapter_events import (
    EnumCodeAnalysisEventType,
    EnumAnalysisOperationType,
    EnumAnalysisErrorCode,
    ModelCodeAnalysisRequestPayload,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelPatternExtractionPayload,
    ModelInfrastructureScanPayload,
    ModelDiscoveryPayload,
    ModelSchemaDiscoveryPayload,
    IntelligenceAdapterEventHelpers,
    create_request_event,
    create_completed_event,
    create_failed_event,
)

__all__ = [
    # Event envelope models
    "ModelEventEnvelope",
    "ModelEventMetadata",
    "ModelEventSource",
    # Code analysis event types
    "EnumCodeAnalysisEventType",
    "EnumAnalysisOperationType",
    "EnumAnalysisErrorCode",
    # Code analysis payloads
    "ModelCodeAnalysisRequestPayload",
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    # Intelligence payloads
    "ModelPatternExtractionPayload",
    "ModelInfrastructureScanPayload",
    "ModelDiscoveryPayload",
    "ModelSchemaDiscoveryPayload",
    # Helpers
    "IntelligenceAdapterEventHelpers",
    # Convenience functions
    "create_request_event",
    "create_completed_event",
    "create_failed_event",
]
