"""Event Infrastructure - Publishers and event models."""

from omniintelligence._legacy.events.publisher.event_publisher import (
    EventPublisher,
    create_event_publisher,
)

# Event models are now re-exported from the canonical location (omniintelligence.models)
from omniintelligence._legacy.models import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
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
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    # Code analysis event types
    "EnumCodeAnalysisEventType",
    # Publisher
    "EventPublisher",
    # Helpers
    "IntelligenceAdapterEventHelpers",
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    # Code analysis payloads
    "ModelCodeAnalysisRequestPayload",
    "ModelDiscoveryPayload",
    # Event envelope models
    "ModelEventEnvelope",
    "ModelEventMetadata",
    "ModelEventSource",
    "ModelInfrastructureScanPayload",
    # Intelligence payloads
    "ModelPatternExtractionPayload",
    "ModelSchemaDiscoveryPayload",
    "create_completed_event",
    "create_event_publisher",
    "create_failed_event",
    # Convenience functions
    "create_request_event",
]
