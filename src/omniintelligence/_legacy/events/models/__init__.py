"""
Event models for Kafka message schemas.

DEPRECATED: This module is kept for backwards compatibility.
Please import from omniintelligence._legacy.models instead:

    # Preferred import (for models)
    from omniintelligence._legacy.models import (
        ModelEventEnvelope,
        ModelCodeAnalysisRequestPayload,
    )

    # Preferred import (for enums)
    from omniintelligence._legacy.enums import (
        EnumCodeAnalysisEventType,
        EnumAnalysisOperationType,
    )

    # Deprecated import (still works)
    from omniintelligence._legacy.events.models import (
        ModelEventEnvelope,
        EnumCodeAnalysisEventType,
    )
"""

# Re-export all event models from the canonical location
from omniintelligence._legacy.models import (
    # Event envelope models
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
    # Event enums (also re-exported from models for convenience)
    EnumCodeAnalysisEventType,
    EnumAnalysisOperationType,
    EnumAnalysisErrorCode,
    # Code analysis payloads
    ModelCodeAnalysisRequestPayload,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    # Intelligence result payloads
    ModelPatternExtractionPayload,
    ModelInfrastructureScanPayload,
    ModelDiscoveryPayload,
    ModelSchemaDiscoveryPayload,
    # Helpers
    IntelligenceAdapterEventHelpers,
    # Convenience functions
    create_request_event,
    create_completed_event,
    create_failed_event,
)

__all__ = [
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    # Code analysis event types
    "EnumCodeAnalysisEventType",
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
    "create_failed_event",
    # Convenience functions
    "create_request_event",
]
