"""
Events Models Package

Exports event models and contracts for the Intelligence service.

Modules:
- intelligence_adapter_events: Event contracts for Intelligence Adapter Effect Node
- document_update_event: Document update event models
- model_event: Unified event model for event bus and Kafka
- model_routing_context: Routing context model

Created: 2025-10-21
"""

# Document Update Events
from .document_update_event import (
    DocumentUpdateEvent,
    DocumentUpdateType,
)

# Intelligence Adapter Event Contracts
from .intelligence_adapter_events import (  # Enums; Event Helpers; Payload Models; Convenience Functions
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    IntelligenceAdapterEventHelpers,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# Unified Event Model
from .model_event import ModelEvent

# Routing Context
from .model_routing_context import (
    ModelRoutingContext,
)

__all__ = [
    # Intelligence Adapter Events
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    "EnumCodeAnalysisEventType",
    "IntelligenceAdapterEventHelpers",
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
    "create_completed_event",
    "create_failed_event",
    "create_request_event",
    # Document Update Events
    "DocumentUpdateEvent",
    "DocumentUpdateEventType",
    # Unified Event Model
    "ModelEvent",
    # Routing Context
    "ModelRoutingContext",
]
