"""
System Utilities Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for System Utilities operations:
- METRICS_REQUESTED/COMPLETED/FAILED: Retrieve system metrics
- KAFKA_HEALTH_REQUESTED/COMPLETED/FAILED: Check Kafka connectivity
- KAFKA_METRICS_REQUESTED/COMPLETED/FAILED: Get Kafka performance metrics

ONEX Compliance:
- Model-based naming: ModelSystem{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py pattern
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field

# Import from local event base to avoid circular imports

# Type-only import for type hints


# ============================================================================
# Enums
# ============================================================================


class EnumSystemUtilitiesEventType(str, Enum):
    """Event types for system utilities operations."""

    # System Metrics
    METRICS_REQUESTED = "METRICS_REQUESTED"
    METRICS_COMPLETED = "METRICS_COMPLETED"
    METRICS_FAILED = "METRICS_FAILED"

    # Kafka Health
    KAFKA_HEALTH_REQUESTED = "KAFKA_HEALTH_REQUESTED"
    KAFKA_HEALTH_COMPLETED = "KAFKA_HEALTH_COMPLETED"
    KAFKA_HEALTH_FAILED = "KAFKA_HEALTH_FAILED"

    # Kafka Metrics
    KAFKA_METRICS_REQUESTED = "KAFKA_METRICS_REQUESTED"
    KAFKA_METRICS_COMPLETED = "KAFKA_METRICS_COMPLETED"
    KAFKA_METRICS_FAILED = "KAFKA_METRICS_FAILED"


class EnumSystemUtilitiesErrorCode(str, Enum):
    """Error codes for system utilities operations."""

    INVALID_INPUT = "INVALID_INPUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    KAFKA_CONNECTION_ERROR = "KAFKA_CONNECTION_ERROR"
    METRICS_COLLECTION_FAILED = "METRICS_COLLECTION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"


# ============================================================================
# System Metrics Event Payloads
# ============================================================================


class ModelSystemMetricsRequestPayload(BaseModel):
    """
    Payload for METRICS_REQUESTED event.

    Attributes:
        include_detailed_metrics: Include detailed per-service metrics
        time_window_seconds: Time window for metric aggregation
        metric_types: Specific metric types to include
    """

    include_detailed_metrics: bool = Field(
        default=False, description="Include detailed per-service metrics"
    )

    time_window_seconds: int = Field(
        default=300,
        description="Time window for metric aggregation in seconds",
        ge=1,
        le=86400,  # Max 24 hours
    )

    metric_types: list[str] = Field(
        default_factory=lambda: ["cpu", "memory", "network", "kafka"],
        description="Specific metric types to include",
        examples=[["cpu", "memory", "kafka", "cache"]],
    )

    model_config = ConfigDict(frozen=False)


class ModelSystemMetricsCompletedPayload(BaseModel):
    """
    Payload for METRICS_COMPLETED event.

    Attributes:
        system_metrics: System-level metrics
        service_metrics: Per-service metrics
        kafka_metrics: Kafka-specific metrics
        cache_metrics: Cache performance metrics
        collection_time_ms: Time taken to collect metrics
        timestamp: Metrics collection timestamp
    """

    system_metrics: dict[str, Any] = Field(
        ...,
        description="System-level metrics",
        examples=[
            {
                "cpu_usage_percent": 45.2,
                "memory_usage_mb": 1024.5,
                "disk_usage_percent": 62.1,
            }
        ],
    )

    service_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-service metrics",
        examples=[
            {
                "intelligence": {"requests_per_second": 12.5, "avg_latency_ms": 45.2},
                "search": {"requests_per_second": 8.3, "avg_latency_ms": 78.1},
            }
        ],
    )

    kafka_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Kafka-specific metrics",
        examples=[
            {
                "messages_per_second": 150.5,
                "consumer_lag": 42,
                "producer_success_rate": 0.995,
            }
        ],
    )

    cache_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Cache performance metrics",
        examples=[
            {
                "hit_rate": 0.87,
                "memory_usage_mb": 128.3,
                "eviction_count": 245,
            }
        ],
    )

    collection_time_ms: float = Field(
        ..., description="Time taken to collect metrics", ge=0.0
    )

    timestamp: str = Field(
        ...,
        description="Metrics collection timestamp",
        examples=["2025-10-22T14:30:00Z"],
    )

    model_config = ConfigDict(frozen=True)


class ModelSystemMetricsFailedPayload(BaseModel):
    """
    Payload for METRICS_FAILED event.

    Attributes:
        error_message: Error description
        error_code: Error code
        retry_allowed: Whether retry is allowed
        collection_time_ms: Time taken before failure
        partial_metrics: Optional partial metrics collected
    """

    error_message: str = Field(..., description="Error description", min_length=1)

    error_code: EnumSystemUtilitiesErrorCode = Field(..., description="Error code")

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    collection_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    partial_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional partial metrics collected before failure",
    )

    model_config = ConfigDict(frozen=True)


class ModelKafkaHealthRequestPayload(BaseModel):
    """
    Payload for KAFKA_HEALTH_REQUESTED event.

    Attributes:
        check_producer: Check producer connectivity
        check_consumer: Check consumer connectivity
        check_topics: Check topic availability
        timeout_ms: Timeout for health check
    """

    check_producer: bool = Field(
        default=True, description="Check producer connectivity"
    )

    check_consumer: bool = Field(
        default=True, description="Check consumer connectivity"
    )

    check_topics: bool = Field(default=True, description="Check topic availability")

    timeout_ms: int = Field(
        default=5000,
        description="Timeout for health check in milliseconds",
        ge=100,
        le=30000,
    )

    model_config = ConfigDict(frozen=False)


class ModelKafkaHealthCompletedPayload(BaseModel):
    """
    Payload for KAFKA_HEALTH_COMPLETED event.

    Attributes:
        status: Overall health status
        producer_healthy: Producer connectivity status
        consumer_healthy: Consumer connectivity status
        topics_available: Number of topics available
        broker_count: Number of connected brokers
        health_details: Detailed health information
        check_time_ms: Time taken for health check
    """

    status: str = Field(
        ...,
        description="Overall health status",
        examples=["healthy", "degraded", "unhealthy"],
    )

    producer_healthy: bool = Field(..., description="Producer connectivity status")

    consumer_healthy: bool = Field(..., description="Consumer connectivity status")

    topics_available: int = Field(..., description="Number of topics available", ge=0)

    broker_count: int = Field(..., description="Number of connected brokers", ge=0)

    health_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed health information",
        examples=[
            {
                "bootstrap_servers": "localhost:9092",
                "cluster_id": "cluster-123",
                "controller_id": 1,
            }
        ],
    )

    check_time_ms: float = Field(..., description="Time taken for health check", ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelKafkaHealthFailedPayload(BaseModel):
    """
    Payload for KAFKA_HEALTH_FAILED event.

    Attributes:
        error_message: Error description
        error_code: Error code
        retry_allowed: Whether retry is allowed
        check_time_ms: Time taken before failure
        connection_details: Connection details for debugging
    """

    error_message: str = Field(..., description="Error description", min_length=1)

    error_code: EnumSystemUtilitiesErrorCode = Field(..., description="Error code")

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    check_time_ms: float = Field(..., description="Time taken before failure", ge=0.0)

    connection_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Connection details for debugging",
        examples=[
            {"bootstrap_servers": "localhost:9092", "last_error": "Connection refused"}
        ],
    )

    model_config = ConfigDict(frozen=True)


class ModelKafkaMetricsRequestPayload(BaseModel):
    """
    Payload for KAFKA_METRICS_REQUESTED event.

    Attributes:
        include_producer_metrics: Include producer performance metrics
        include_consumer_metrics: Include consumer performance metrics
        include_topic_metrics: Include per-topic metrics
        time_window_seconds: Time window for metric aggregation
    """

    include_producer_metrics: bool = Field(
        default=True, description="Include producer performance metrics"
    )

    include_consumer_metrics: bool = Field(
        default=True, description="Include consumer performance metrics"
    )

    include_topic_metrics: bool = Field(
        default=True, description="Include per-topic metrics"
    )

    time_window_seconds: int = Field(
        default=300,
        description="Time window for metric aggregation in seconds",
        ge=1,
        le=86400,
    )

    model_config = ConfigDict(frozen=False)


class ModelKafkaMetricsCompletedPayload(BaseModel):
    """
    Payload for KAFKA_METRICS_COMPLETED event.

    Attributes:
        producer_metrics: Producer performance metrics
        consumer_metrics: Consumer performance metrics
        topic_metrics: Per-topic metrics
        cluster_metrics: Cluster-level metrics
        collection_time_ms: Time taken to collect metrics
        timestamp: Metrics collection timestamp
    """

    producer_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Producer performance metrics",
        examples=[
            {
                "messages_sent": 12500,
                "bytes_sent": 1024000,
                "success_rate": 0.998,
                "avg_latency_ms": 12.5,
            }
        ],
    )

    consumer_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Consumer performance metrics",
        examples=[
            {
                "messages_consumed": 11800,
                "bytes_consumed": 980000,
                "consumer_lag": 45,
                "avg_processing_time_ms": 23.4,
            }
        ],
    )

    topic_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-topic metrics",
        examples=[
            {
                "dev.archon.intelligence.v1": {
                    "message_count": 5000,
                    "partition_count": 3,
                    "replication_factor": 2,
                }
            }
        ],
    )

    cluster_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Cluster-level metrics",
        examples=[
            {
                "broker_count": 3,
                "total_topics": 25,
                "total_partitions": 75,
                "under_replicated_partitions": 0,
            }
        ],
    )

    collection_time_ms: float = Field(
        ..., description="Time taken to collect metrics", ge=0.0
    )

    timestamp: str = Field(
        ...,
        description="Metrics collection timestamp",
        examples=["2025-10-22T14:30:00Z"],
    )

    model_config = ConfigDict(frozen=True)


class ModelKafkaMetricsFailedPayload(BaseModel):
    """
    Payload for KAFKA_METRICS_FAILED event.

    Attributes:
        error_message: Error description
        error_code: Error code
        retry_allowed: Whether retry is allowed
        collection_time_ms: Time taken before failure
        partial_metrics: Optional partial metrics collected
    """

    error_message: str = Field(..., description="Error description", min_length=1)

    error_code: EnumSystemUtilitiesErrorCode = Field(..., description="Error code")

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    collection_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    partial_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional partial metrics collected before failure",
    )

    model_config = ConfigDict(frozen=True)


class SystemUtilitiesEventHelpers:
    """Helper methods for creating System Utilities events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "system"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def _create_envelope(
        event_type: str,
        payload: BaseModel,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create event envelope with fallback for missing imports."""
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": event_type,
                "service": SystemUtilitiesEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-system-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )
        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumSystemUtilitiesEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{SystemUtilitiesEventHelpers.SERVICE_PREFIX}.{SystemUtilitiesEventHelpers.DOMAIN}.{event_suffix}.{SystemUtilitiesEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_metrics_request(
    include_detailed_metrics: bool = False,
    time_window_seconds: int = 300,
    metric_types: Optional[list[str]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create METRICS_REQUESTED event."""
    payload = ModelSystemMetricsRequestPayload(
        include_detailed_metrics=include_detailed_metrics,
        time_window_seconds=time_window_seconds,
        metric_types=metric_types or ["cpu", "memory", "network", "kafka"],
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.metrics_requested.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_metrics_completed(
    system_metrics: dict[str, Any],
    collection_time_ms: float,
    timestamp: str,
    correlation_id: UUID,
    service_metrics: Optional[dict[str, Any]] = None,
    kafka_metrics: Optional[dict[str, Any]] = None,
    cache_metrics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create METRICS_COMPLETED event."""
    payload = ModelSystemMetricsCompletedPayload(
        system_metrics=system_metrics,
        service_metrics=service_metrics or {},
        kafka_metrics=kafka_metrics or {},
        cache_metrics=cache_metrics or {},
        collection_time_ms=collection_time_ms,
        timestamp=timestamp,
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.metrics_completed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_metrics_failed(
    error_message: str,
    error_code: EnumSystemUtilitiesErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    collection_time_ms: float = 0.0,
    partial_metrics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create METRICS_FAILED event."""
    payload = ModelSystemMetricsFailedPayload(
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        collection_time_ms=collection_time_ms,
        partial_metrics=partial_metrics or {},
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.metrics_failed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_health_request(
    check_producer: bool = True,
    check_consumer: bool = True,
    check_topics: bool = True,
    timeout_ms: int = 5000,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create KAFKA_HEALTH_REQUESTED event."""
    payload = ModelKafkaHealthRequestPayload(
        check_producer=check_producer,
        check_consumer=check_consumer,
        check_topics=check_topics,
        timeout_ms=timeout_ms,
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_health_requested.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_health_completed(
    status: str,
    producer_healthy: bool,
    consumer_healthy: bool,
    topics_available: int,
    broker_count: int,
    check_time_ms: float,
    correlation_id: UUID,
    health_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create KAFKA_HEALTH_COMPLETED event."""
    payload = ModelKafkaHealthCompletedPayload(
        status=status,
        producer_healthy=producer_healthy,
        consumer_healthy=consumer_healthy,
        topics_available=topics_available,
        broker_count=broker_count,
        health_details=health_details or {},
        check_time_ms=check_time_ms,
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_health_completed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_health_failed(
    error_message: str,
    error_code: EnumSystemUtilitiesErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    check_time_ms: float = 0.0,
    connection_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create KAFKA_HEALTH_FAILED event."""
    payload = ModelKafkaHealthFailedPayload(
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        check_time_ms=check_time_ms,
        connection_details=connection_details or {},
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_health_failed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_metrics_request(
    include_producer_metrics: bool = True,
    include_consumer_metrics: bool = True,
    include_topic_metrics: bool = True,
    time_window_seconds: int = 300,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create KAFKA_METRICS_REQUESTED event."""
    payload = ModelKafkaMetricsRequestPayload(
        include_producer_metrics=include_producer_metrics,
        include_consumer_metrics=include_consumer_metrics,
        include_topic_metrics=include_topic_metrics,
        time_window_seconds=time_window_seconds,
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_metrics_requested.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_metrics_completed(
    collection_time_ms: float,
    timestamp: str,
    correlation_id: UUID,
    producer_metrics: Optional[dict[str, Any]] = None,
    consumer_metrics: Optional[dict[str, Any]] = None,
    topic_metrics: Optional[dict[str, Any]] = None,
    cluster_metrics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create KAFKA_METRICS_COMPLETED event."""
    payload = ModelKafkaMetricsCompletedPayload(
        producer_metrics=producer_metrics or {},
        consumer_metrics=consumer_metrics or {},
        topic_metrics=topic_metrics or {},
        cluster_metrics=cluster_metrics or {},
        collection_time_ms=collection_time_ms,
        timestamp=timestamp,
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_metrics_completed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_kafka_metrics_failed(
    error_message: str,
    error_code: EnumSystemUtilitiesErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    collection_time_ms: float = 0.0,
    partial_metrics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create KAFKA_METRICS_FAILED event."""
    payload = ModelKafkaMetricsFailedPayload(
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        collection_time_ms=collection_time_ms,
        partial_metrics=partial_metrics or {},
    )

    event_type = f"omninode.{SystemUtilitiesEventHelpers.DOMAIN}.{SystemUtilitiesEventHelpers.PATTERN}.kafka_metrics_failed.{SystemUtilitiesEventHelpers.VERSION}"

    return SystemUtilitiesEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )
