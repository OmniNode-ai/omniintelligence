"""
ONEX-compliant event model for unified event publishing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

try:
    from omnibase_core.enums.enum_event_priority import EnumEventPriority
    from omnibase_core.enums.enum_protocol_event_type import EnumProtocolEventType
except ImportError:
    # Fallback for missing enums
    from enum import Enum

    class EnumEventPriority(str, Enum):
        CRITICAL = "CRITICAL"
        HIGH = "HIGH"
        NORMAL = "NORMAL"
        LOW = "LOW"

    class EnumProtocolEventType(str, Enum):
        CREATED = "CREATED"
        UPDATED = "UPDATED"
        DELETED = "DELETED"
        CUSTOM = "CUSTOM"


class ModelEvent(BaseModel):
    """
    Unified event model for both Event Bus and Kafka publishing.

    This model follows ONEX standards and provides a consistent
    structure for all events across the system.
    """

    # Core fields
    event_id: UUID = Field(
        default_factory=uuid4, description="Unique identifier for this event"
    )

    event_type: EnumProtocolEventType = Field(
        description="Type of event (e.g., CREATED, UPDATED, DELETED, CUSTOM)"
    )

    topic: str = Field(
        description="Target topic following onex.{domain}.{action}.{version} pattern"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event creation timestamp in UTC"
    )

    # Tracking fields
    correlation_id: Optional[UUID] = Field(
        default=None, description="Correlation ID for tracking related events"
    )

    causation_id: Optional[UUID] = Field(
        default=None, description="ID of the event that caused this one"
    )

    trace_id: Optional[str] = Field(
        default=None, description="Distributed tracing ID (W3C trace context)"
    )

    span_id: Optional[str] = Field(
        default=None, description="Span ID for distributed tracing"
    )

    # Source information
    source_service: str = Field(description="Service that generated this event")

    source_instance: Optional[str] = Field(
        default=None, description="Instance ID of the source service"
    )

    source_version: str = Field(
        default="1.0.0", description="Version of the source service"
    )

    # Event data
    payload_type: str = Field(
        description="Type of the payload (e.g., model class name)"
    )

    payload: Dict[str, Any] = Field(description="Event payload data")

    # Metadata
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Additional headers for routing or metadata"
    )

    priority: EnumEventPriority = Field(
        default=EnumEventPriority.NORMAL,
        description="Event priority for processing order",
    )

    ttl_seconds: Optional[int] = Field(
        default=None, description="Time-to-live in seconds (for expiring events)"
    )

    retry_count: int = Field(
        default=0, description="Number of times this event has been retried"
    )

    max_retries: int = Field(default=3, description="Maximum retry attempts allowed")

    # Versioning
    schema_version: str = Field(
        default="1.0.0", description="Version of this event schema"
    )

    # Security
    signature: Optional[str] = Field(
        default=None, description="Digital signature for event verification"
    )

    encrypted: bool = Field(
        default=False, description="Whether the payload is encrypted"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "123e4567-e89b-12d3-a456-426614174000",
                "event_type": "CREATED",
                "topic": "onex.generation.completed.v1",
                "timestamp": "2025-08-08T12:00:00Z",
                "correlation_id": "456e7890-e89b-12d3-a456-426614174000",
                "source_service": "generation-hub",
                "source_version": "1.0.0",
                "payload_type": "ModelGenerationResult",
                "payload": {
                    "tool_name": "contract_validator",
                    "status": "success",
                    "duration_ms": 1500,
                },
                "priority": "NORMAL",
                "schema_version": "1.0.0",
            }
        }
    )

    def to_kafka_headers(self) -> Dict[bytes, bytes]:
        """
        Convert headers for Kafka publishing.

        Returns:
            Dictionary with byte keys and values for Kafka
        """
        headers = {}

        # Add standard headers
        headers[b"event_id"] = str(self.event_id).encode()
        headers[b"event_type"] = self.event_type.value.encode()
        headers[b"timestamp"] = self.timestamp.isoformat().encode()
        headers[b"source_service"] = self.source_service.encode()
        headers[b"payload_type"] = self.payload_type.encode()

        # Add tracking headers if present
        if self.correlation_id:
            headers[b"correlation_id"] = str(self.correlation_id).encode()
        if self.causation_id:
            headers[b"causation_id"] = str(self.causation_id).encode()
        if self.trace_id:
            headers[b"trace_id"] = self.trace_id.encode()
        if self.span_id:
            headers[b"span_id"] = self.span_id.encode()

        # Add custom headers
        if self.headers:
            for key, value in self.headers.items():
                headers[f"x-{key}".encode()] = value.encode()

        return headers

    def to_event_bus_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for Event Bus publishing.

        Returns:
            Dictionary representation for in-memory Event Bus
        """
        return self.dict(exclude_none=True)

    def is_expired(self) -> bool:
        """
        Check if event has expired based on TTL.

        Returns:
            True if event has expired
        """
        if not self.ttl_seconds:
            return False

        age_seconds = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age_seconds > self.ttl_seconds

    def should_retry(self) -> bool:
        """
        Check if event should be retried on failure.

        Returns:
            True if retry is allowed
        """
        return self.retry_count < self.max_retries

    def increment_retry(self) -> "ModelEvent":
        """
        Create a new event with incremented retry count.

        Returns:
            New ModelEvent instance with updated retry count
        """
        return self.copy(update={"retry_count": self.retry_count + 1})
