"""
Event Bus Foundation - Phase 1

Provides core event-driven architecture components for ONEX ecosystem:
- Base event models (ModelEventEnvelope, ModelEventSource, ModelEventMetadata)
- Schema registry integration (Redpanda Schema Registry)
- Event publisher base class (EventPublisher with retry/circuit breaker)
- Dead letter queue (DLQ) handling
- Event serialization/deserialization

Created: 2025-10-18
Architecture: EVENT_BUS_ARCHITECTURE.md
"""

from src.events.models.model_event_envelope import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)

__all__ = [
    "ModelEventEnvelope",
    "ModelEventSource",
    "ModelEventMetadata",
]
