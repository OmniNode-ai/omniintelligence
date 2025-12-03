"""
Event Envelope Models - Phase 1

Base event envelope models following EVENT_BUS_ARCHITECTURE.md specification.

Schema:
{
  "event_id": "uuid-v4",
  "event_type": "omninode.{domain}.{pattern}.{operation}.v1",
  "correlation_id": "uuid-v4",
  "causation_id": "uuid-v4",
  "timestamp": "2025-10-18T10:00:00.000Z",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "instance-123",
    "hostname": "archon-intelligence-abc123"
  },
  "metadata": {
    "trace_id": "uuid-v4",
    "span_id": "uuid-v4",
    "user_id": "optional",
    "tenant_id": "optional"
  },
  "payload": {}
}

Created: 2025-10-18
Reference: EVENT_BUS_ARCHITECTURE.md
"""

from datetime import UTC, datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Generic type for payload
T = TypeVar("T")


class ModelEventSource(BaseModel):
    """
    Event source metadata.

    Identifies the service instance that published the event.
    Used for tracing, debugging, and audit trail.
    """

    model_config = ConfigDict(frozen=True)  # Immutable after creation

    service: str = Field(
        ...,
        description="Service name (e.g., 'archon-intelligence')",
        examples=["archon-intelligence", "archon-bridge", "archon-search"],
    )

    instance_id: str = Field(
        ...,
        description="Service instance ID (e.g., 'instance-123', container ID)",
        examples=["instance-123", "container-abc123"],
    )

    hostname: Optional[str] = Field(
        default=None,
        description="Hostname or container name",
        examples=["archon-intelligence-abc123", "ip-10-0-1-42"],
    )


class ModelEventMetadata(BaseModel):
    """
    Event metadata for tracing, authorization, and multi-tenancy.

    Supports distributed tracing (trace_id, span_id) and optional
    authorization context (user_id, tenant_id).
    """

    model_config = ConfigDict(frozen=True)  # Immutable after creation

    trace_id: Optional[str] = Field(
        default=None,
        description="Distributed trace ID (OpenTelemetry format: 32 hex digits)",
        examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
        pattern=r"^[a-f0-9]{32}$",
    )

    span_id: Optional[str] = Field(
        default=None,
        description="Trace span ID (OpenTelemetry format: 16 hex digits)",
        examples=["00f067aa0ba902b7"],
        pattern=r"^[a-f0-9]{16}$",
    )

    user_id: Optional[str] = Field(
        default=None,
        description="User ID for authorization context",
        examples=["user-123", "auth0|abc123"],
    )

    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant ID for multi-tenancy",
        examples=["tenant-acme", "org-456"],
    )

    # Extensible metadata fields
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata fields for domain-specific requirements",
    )


class ModelEventEnvelope(BaseModel, Generic[T]):
    """
    Base event envelope following ONEX event bus specification.

    All events must use this envelope pattern for consistency across
    the ONEX ecosystem. Supports:
    - Correlation ID tracking for request/response flows
    - Causation ID tracking for event sourcing
    - Distributed tracing integration
    - Service source identification
    - Semantic versioning
    - Extensible metadata

    Type Parameters:
        T: Payload type (event-specific data)

    Event Naming Convention:
        {namespace}.{domain}.{pattern}.{operation}.{version}

        - namespace: Always "omninode"
        - domain: Service domain (codegen, intelligence, bridge, etc.)
        - pattern: Event pattern (request, response, event, audit)
        - operation: Specific operation (validate, stamp, indexed, etc.)
        - version: Semantic version (v1, v2, etc.)

    Examples:
        - omninode.codegen.request.validate.v1
        - omninode.intelligence.event.quality_assessed.v1
        - omninode.bridge.event.metadata_stamped.v1
        - omninode.audit.agent_execution.v1
    """

    model_config = ConfigDict(
        # Allow generic types
        arbitrary_types_allowed=True,
        # JSON schema generation
        json_schema_extra={
            "examples": [
                {
                    "event_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "omninode.codegen.request.validate.v1",
                    "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
                    "causation_id": None,
                    "timestamp": "2025-10-18T10:00:00.000Z",
                    "version": "1.0.0",
                    "source": {
                        "service": "archon-intelligence",
                        "instance_id": "instance-123",
                        "hostname": "archon-intelligence-abc123",
                    },
                    "metadata": {
                        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                        "span_id": "00f067aa0ba902b7",
                        "user_id": "user-123",
                        "tenant_id": "tenant-acme",
                    },
                    "payload": {
                        "code_content": "class Test: pass",
                        "node_type": "effect",
                        "language": "python",
                    },
                }
            ]
        },
    )

    event_id: UUID = Field(
        default_factory=uuid4,
        description="Unique event identifier (UUID v4)",
    )

    event_type: str = Field(
        ...,
        description="Fully-qualified event type (topic name)",
        examples=[
            "omninode.codegen.request.validate.v1",
            "omninode.intelligence.event.quality_assessed.v1",
            "omninode.bridge.event.metadata_stamped.v1",
        ],
        pattern=r"^omninode\.[a-z_-]+\.(request|response|event|audit)\.[a-z_-]+\.v\d+$",
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Links related events in request/response flow",
    )

    causation_id: Optional[UUID] = Field(
        default=None,
        description="ID of event that caused this event (event sourcing)",
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Event timestamp (ISO 8601 with millisecond precision, UTC)",
    )

    version: str = Field(
        default="1.0.0",
        description="Event schema version (semantic versioning)",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    source: ModelEventSource = Field(
        ...,
        description="Service that published the event",
    )

    metadata: Optional[ModelEventMetadata] = Field(
        default=None,
        description="Tracing, authorization, multi-tenancy data",
    )

    payload: T = Field(
        ...,
        description="Event-specific business data",
    )

    @field_validator("timestamp")
    @classmethod
    def ensure_utc_timezone(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC timezone-aware."""
        if v.tzinfo is None:
            # Assume naive datetime is UTC
            return v.replace(tzinfo=UTC)
        # Convert to UTC if different timezone
        return v.astimezone(UTC)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert event envelope to dictionary with JSON-serializable types.

        Returns:
            Dictionary with all fields, UUIDs as strings, datetime as ISO 8601
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "source": self.source.model_dump(),
            "metadata": self.metadata.model_dump() if self.metadata else None,
            "payload": (
                self.payload.model_dump()
                if hasattr(self.payload, "model_dump")
                else self.payload
            ),
        }


__all__ = [
    "ModelEventEnvelope",
    "ModelEventMetadata",
    "ModelEventSource",
]
