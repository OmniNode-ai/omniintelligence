"""
Event Publisher Base Class - Legacy Compatibility Layer.

Unified event publisher for all ONEX services with:
- Retry logic with exponential backoff
- Circuit breaker integration (trips ONLY on transient failures)
- Event validation against schemas
- Correlation ID tracking
- DLQ routing on failures
- Metrics tracking
- Log sanitization for secrets

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Import from ``omniintelligence.events.publisher`` instead when available.

Circuit Breaker Behavior:
    The circuit breaker ONLY trips on transient infrastructure errors:
    - Network connection failures
    - Broker unavailable
    - Timeouts during publish

    The circuit breaker does NOT trip on data/programming errors:
    - Envelope validation errors (bad payload structure)
    - Serialization errors (JSON encoding failures)
    - Schema validation errors

    This distinction is critical because infrastructure errors may resolve
    with retries or after a cooldown period, while data errors require
    code/data fixes and will never self-heal.

Reference: EVENT_BUS_ARCHITECTURE.md Phase 1
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import warnings
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

try:
    from confluent_kafka import Producer

    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    Producer = None  # type: ignore[misc, assignment]

# Import log sanitizer from canonical location
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

warnings.warn(
    "Importing from omniintelligence._legacy.events.publisher will be removed in v2.0.0. "
    "Continue using _legacy.events.publisher until omniintelligence.events is released.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


class PublisherCounters(TypedDict):
    """Mutable counters tracked by EventPublisher during its lifetime."""

    events_published: int
    events_failed: int
    events_sent_to_dlq: int
    total_publish_time_ms: float
    circuit_breaker_opens: int
    retries_attempted: int
    serialization_errors: int
    envelope_errors: int


class PublisherMetrics(PublisherCounters):
    """Full metrics snapshot returned by ``EventPublisher.get_metrics()``."""

    total_events: int
    avg_publish_time_ms: float
    circuit_breaker_status: str
    current_failures: int


class ModelEventSource(BaseModel):
    """Event source metadata."""

    service: str = Field(..., description="Publishing service name")
    instance_id: str = Field(..., description="Service instance ID")
    hostname: str | None = Field(default=None, description="Optional hostname")


class ModelEventMetadata(BaseModel):
    """Event metadata."""

    custom: dict[str, object] = Field(default_factory=dict)


class ModelEventEnvelope(BaseModel):
    """Event envelope wrapping payload with metadata."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(..., description="Fully-qualified event type")
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: ModelEventSource
    metadata: ModelEventMetadata | None = Field(default=None)
    payload: Any = Field(
        ..., description="Event payload"
    )  # any-ok: arbitrary event payload, serialized manually in to_dict()

    def to_dict(self) -> dict[str, object]:
        """Convert envelope to dictionary for serialization."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "timestamp": self.timestamp.isoformat(),
            "source": {
                "service": self.source.service,
                "instance_id": self.source.instance_id,
                "hostname": self.source.hostname,
            },
            "metadata": self.metadata.model_dump() if self.metadata else None,
            "payload": (
                self.payload.model_dump()
                if hasattr(self.payload, "model_dump")
                else self.payload
            ),
        }


class EventPublisher:
    """
    Base event publisher with retry, circuit breaker, and validation.

    Provides unified event publishing across all ONEX services with:
    - Automatic retries with exponential backoff
    - Circuit breaker to prevent cascading failures (transient errors only)
    - Event validation before publishing
    - Correlation ID tracking for request/response flows
    - Dead letter queue (DLQ) routing on persistent failures
    - Metrics tracking (events published, failures, latency)
    - Secret sanitization in event payloads

    Circuit Breaker Design:
        The circuit breaker ONLY trips on transient infrastructure errors:
        - Network connection failures
        - Broker unavailable
        - Timeouts during publish

        The circuit breaker does NOT trip on data/programming errors:
        - Envelope validation errors (bad payload structure)
        - Serialization errors (JSON encoding failures)
        - Schema validation errors

    Usage:
        publisher = EventPublisher(
            bootstrap_servers="192.168.86.200:29092",
            service_name="archon-intelligence",
            instance_id="instance-123"
        )

        await publisher.publish(
            event_type="omninode.intelligence.event.quality_assessed.v1",
            payload={"quality_score": 0.87, "entity_id": "abc-123"},
            correlation_id=correlation_id,
        )

        await publisher.close()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        service_name: str,
        instance_id: str,
        hostname: str | None = None,
        max_retries: int = 3,
        retry_backoff_ms: int = 1000,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout_s: int = 60,
        enable_dlq: bool = True,
        enable_sanitization: bool = True,
    ):
        """
        Initialize event publisher.

        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            service_name: Name of publishing service (e.g., "archon-intelligence")
            instance_id: Service instance ID
            hostname: Optional hostname/container name
            max_retries: Maximum retry attempts before DLQ (default: 3)
            retry_backoff_ms: Base backoff time in milliseconds (default: 1000)
            circuit_breaker_threshold: Failures before opening circuit (default: 5)
            circuit_breaker_timeout_s: Circuit breaker timeout in seconds (default: 60)
            enable_dlq: Enable dead letter queue routing (default: True)
            enable_sanitization: Enable secret sanitization in event payloads (default: True)
        """
        self.bootstrap_servers = bootstrap_servers
        self.service_name = service_name
        self.instance_id = instance_id
        self.hostname = hostname
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout_s = circuit_breaker_timeout_s
        self.enable_dlq = enable_dlq
        self.enable_sanitization = enable_sanitization

        # Kafka producer
        self.producer: Producer | None = None

        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time: float | None = None
        self._circuit_breaker_open = False

        # Metrics
        self.metrics: PublisherCounters = {
            "events_published": 0,
            "events_failed": 0,
            "events_sent_to_dlq": 0,
            "total_publish_time_ms": 0.0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
            "serialization_errors": 0,
            "envelope_errors": 0,
        }

        self._initialize_producer()

    def _initialize_producer(self) -> None:
        """Initialize Kafka producer with optimized configuration."""
        if not KAFKA_AVAILABLE:
            logger.warning("Kafka not available, producer not initialized")
            return

        producer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            # Performance tuning
            "linger.ms": 10,  # Batch messages for 10ms for throughput
            "batch.size": 32768,  # 32KB batch size
            "compression.type": "lz4",  # Fast compression
            "acks": "all",  # Wait for all replicas (reliability)
            # Idempotent delivery (requires retries > 0, using default)
            # Note: We also implement application-level retries in _publish_with_retry
            # for catching exceptions. Producer-level retries handle transient network
            # issues internally, while app-level retries handle higher-level failures.
            "enable.idempotence": True,  # Prevent duplicate messages
            # Timeout configuration
            "request.timeout.ms": 30000,  # 30 seconds
            "delivery.timeout.ms": 120000,  # 2 minutes total
            # Client identification
            "client.id": f"{self.service_name}-{self.instance_id}",
        }

        self.producer = Producer(producer_config)
        logger.info(
            f"EventPublisher initialized | service={self.service_name} | "
            f"instance={self.instance_id} | bootstrap={self.bootstrap_servers}"
        )

    async def publish(
        self,
        event_type: str,
        payload: object,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: ModelEventMetadata | None = None,
        topic: str | None = None,
        partition_key: str | None = None,
    ) -> bool:
        """
        Publish event to Kafka with retry and circuit breaker.

        Args:
            event_type: Fully-qualified event type (e.g., "omninode.codegen.request.validate.v1")
            payload: Event payload (dict or Pydantic model)
            correlation_id: Optional correlation ID (UUID, generated if not provided)
            causation_id: Optional causation ID (UUID) for event sourcing
            metadata: Optional event metadata
            topic: Optional topic override (defaults to event_type)
            partition_key: Optional partition key for ordering

        Returns:
            True if published successfully, False otherwise

        Raises:
            RuntimeError: If circuit breaker is open
            ValueError: If envelope creation or serialization fails (data errors).
                These are programming/data errors that do NOT trip the circuit breaker.

        Circuit Breaker Behavior:
            The circuit breaker ONLY trips on transient infrastructure errors:
            - Network connection failures
            - Broker unavailable
            - Timeouts during publish

            The circuit breaker does NOT trip on data/programming errors:
            - Envelope validation errors (bad payload structure)
            - Serialization errors (JSON encoding failures)
            - Schema validation errors

            This distinction is important because infrastructure errors may resolve
            with retries or after a cooldown period, while data errors require
            code/data fixes and will never self-heal.
        """
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.error(
                f"Circuit breaker is OPEN | service={self.service_name} | "
                f"failures={self._circuit_breaker_failures}"
            )
            raise RuntimeError("Circuit breaker is open, refusing to publish events")

        start_time = time.perf_counter()

        # =====================================================================
        # PHASE 1: Envelope Creation & Serialization (Data Errors)
        # These are programming/data errors that will NOT resolve by retrying.
        # Do NOT trip the circuit breaker for these errors.
        # =====================================================================
        try:
            # Create event envelope
            envelope = self._create_event_envelope(
                event_type=event_type,
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
                metadata=metadata,
            )
        except (ValueError, TypeError) as e:
            # Envelope creation failed (validation error, bad data)
            # This is a programming/data error - do NOT trip circuit breaker
            self.metrics["events_failed"] += 1
            self.metrics["envelope_errors"] += 1
            logger.error(
                f"Event envelope creation failed (data error, circuit breaker NOT tripped) | "
                f"event_type={event_type} | error={e}",
                exc_info=True,
            )
            raise ValueError(f"Event envelope creation failed: {e}") from e
        except Exception as e:
            # Any other envelope creation error is also a data error
            # Intentionally broad: catch-all for unexpected envelope creation failures
            self.metrics["events_failed"] += 1
            self.metrics["envelope_errors"] += 1
            logger.error(
                f"Event envelope creation failed (unexpected error, circuit breaker NOT tripped) | "
                f"event_type={event_type} | error={e}",
                exc_info=True,
            )
            raise ValueError(f"Event envelope creation failed: {e}") from e

        # Determine topic (default to event_type)
        publish_topic = topic or event_type

        try:
            # Serialize event
            event_bytes = self._serialize_event(envelope)
        except (TypeError, ValueError) as e:
            # Serialization failed (JSON encoding error, bad data types)
            # Note: json.dumps() raises TypeError/ValueError, not JSONDecodeError
            # (JSONDecodeError is for decoding/parsing, not encoding)
            # This is a programming/data error - do NOT trip circuit breaker
            self.metrics["events_failed"] += 1
            self.metrics["serialization_errors"] += 1
            logger.error(
                f"Event serialization failed (data error, circuit breaker NOT tripped) | "
                f"event_type={event_type} | correlation_id={envelope.correlation_id} | error={e}",
                exc_info=True,
            )
            raise ValueError(f"Event serialization failed: {e}") from e
        except Exception as e:
            # Any other serialization error is also a data error
            # Intentionally broad: catch-all for unexpected serialization failures
            self.metrics["events_failed"] += 1
            self.metrics["serialization_errors"] += 1
            logger.error(
                f"Event serialization failed (unexpected error, circuit breaker NOT tripped) | "
                f"event_type={event_type} | correlation_id={envelope.correlation_id} | error={e}",
                exc_info=True,
            )
            raise ValueError(f"Event serialization failed: {e}") from e

        # =====================================================================
        # PHASE 2: Infrastructure Operations (Transient Errors)
        # These are network/broker errors that MAY resolve by retrying.
        # ONLY trip the circuit breaker for these errors.
        # =====================================================================
        try:
            # Publish with retry
            success = await self._publish_with_retry(
                topic=publish_topic,
                event_bytes=event_bytes,
                partition_key=partition_key,
                envelope=envelope,
            )

            if success:
                # Update metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self.metrics["events_published"] += 1
                self.metrics["total_publish_time_ms"] += elapsed_ms

                # Reset circuit breaker on success
                self._reset_circuit_breaker()

                logger.info(
                    f"Event published successfully | event_type={event_type} | "
                    f"correlation_id={envelope.correlation_id} | "
                    f"topic={publish_topic} | duration={elapsed_ms:.2f}ms"
                )
                return True
            else:
                # Publish failed after retries - this IS an infrastructure failure
                # Trip the circuit breaker
                self.metrics["events_failed"] += 1
                self._record_circuit_breaker_failure()

                # Send to DLQ if enabled
                if self.enable_dlq:
                    await self._send_to_dlq(
                        topic=publish_topic,
                        envelope=envelope,
                        error_message="Failed after max retries",
                    )

                logger.error(
                    f"Event publish failed after retries | event_type={event_type} | "
                    f"correlation_id={envelope.correlation_id}"
                )
                return False

        except asyncio.CancelledError:
            # Task cancellation during publish - must re-raise to preserve cancellation semantics
            logger.info(
                f"Event publish cancelled | event_type={event_type} | "
                f"correlation_id={envelope.correlation_id}"
            )
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            # Infrastructure error during publish (connection, timeout, broker error)
            # This IS a transient error - trip the circuit breaker
            self.metrics["events_failed"] += 1
            self._record_circuit_breaker_failure()

            logger.error(
                f"Event publish infrastructure error (circuit breaker tripped) | "
                f"event_type={event_type} | correlation_id={envelope.correlation_id} | error={e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            # Intentionally broad: catch any unexpected error during infrastructure operations
            # Treat unexpected errors as potentially transient and trip the circuit breaker
            self.metrics["events_failed"] += 1
            self._record_circuit_breaker_failure()

            logger.error(
                f"Event publish unexpected error (circuit breaker tripped) | "
                f"event_type={event_type} | correlation_id={envelope.correlation_id} | error={e}",
                exc_info=True,
            )
            return False

    async def _publish_with_retry(
        self,
        topic: str,
        event_bytes: bytes,
        partition_key: str | None,
        envelope: ModelEventEnvelope,
    ) -> bool:
        """
        Publish event with exponential backoff retry.

        Args:
            topic: Kafka topic
            event_bytes: Serialized event data
            partition_key: Optional partition key
            envelope: Event envelope for logging

        Returns:
            True if published successfully, False after max retries
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Attempt to publish
                await self._produce_message(
                    topic=topic,
                    value=event_bytes,
                    key=partition_key.encode() if partition_key else None,
                )

                # Success
                if attempt > 0:
                    logger.info(
                        f"Event published after {attempt} retries | "
                        f"correlation_id={envelope.correlation_id}"
                    )
                return True

            except (ConnectionError, TimeoutError, OSError) as e:
                # Network-related errors are retryable
                if attempt < self.max_retries:
                    # Calculate backoff with exponential increase
                    backoff_ms = self.retry_backoff_ms * (2**attempt)

                    logger.warning(
                        f"Event publish failed, retrying | attempt={attempt + 1}/{self.max_retries + 1} | "
                        f"backoff={backoff_ms}ms | correlation_id={envelope.correlation_id} | "
                        f"error={e}"
                    )

                    self.metrics["retries_attempted"] += 1

                    # Wait before retry
                    await asyncio.sleep(backoff_ms / 1000.0)
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Event publish failed after {self.max_retries + 1} attempts | "
                        f"correlation_id={envelope.correlation_id} | error={e}"
                    )
                    return False
            except asyncio.CancelledError:
                # Task cancellation during retry - must re-raise to preserve cancellation semantics
                logger.info(
                    f"Event publish retry cancelled | attempt={attempt + 1}/{self.max_retries + 1} | "
                    f"correlation_id={envelope.correlation_id}"
                )
                raise
            except Exception as e:
                # Intentionally broad: treat any unexpected error as retryable
                if attempt < self.max_retries:
                    backoff_ms = self.retry_backoff_ms * (2**attempt)

                    logger.warning(
                        f"Event publish failed (unexpected), retrying | attempt={attempt + 1}/{self.max_retries + 1} | "
                        f"backoff={backoff_ms}ms | correlation_id={envelope.correlation_id} | "
                        f"error={e}"
                    )

                    self.metrics["retries_attempted"] += 1
                    await asyncio.sleep(backoff_ms / 1000.0)
                else:
                    logger.error(
                        f"Event publish failed after {self.max_retries + 1} attempts | "
                        f"correlation_id={envelope.correlation_id} | error={e}"
                    )
                    return False

        return False

    async def _produce_message(
        self, topic: str, value: bytes, key: bytes | None
    ) -> None:
        """
        Produce message to Kafka asynchronously.

        Args:
            topic: Kafka topic
            value: Message value (bytes)
            key: Optional message key (bytes)

        Raises:
            RuntimeError: If producer not initialized
            Exception: If produce fails
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized")

        # Create future for delivery callback
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        # any-ok: confluent-kafka callback signature
        def delivery_callback(err: Any, _msg: Any) -> None:
            """Delivery callback to set future result."""
            if err:
                loop.call_soon_threadsafe(
                    future.set_exception,
                    Exception(f"Kafka delivery failed: {err}"),
                )
            else:
                loop.call_soon_threadsafe(future.set_result, True)

        # Produce message (non-blocking)
        self.producer.produce(
            topic=topic,
            value=value,
            key=key,
            callback=delivery_callback,
        )

        # Poll to trigger callback
        self.producer.poll(0)

        # Wait for delivery
        await future

    def _create_event_envelope(
        self,
        event_type: str,
        payload: object,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: ModelEventMetadata | None = None,
    ) -> ModelEventEnvelope:
        """
        Create event envelope with source metadata.

        Args:
            event_type: Event type string
            payload: Event payload
            correlation_id: Optional correlation ID (UUID)
            causation_id: Optional causation ID (UUID)
            metadata: Optional metadata

        Returns:
            ModelEventEnvelope instance

        Raises:
            ValueError: If envelope creation fails due to invalid data
        """
        # Create source metadata
        source = ModelEventSource(
            service=self.service_name,
            instance_id=self.instance_id,
            hostname=self.hostname,
        )

        # Create envelope with UUID objects directly
        envelope = ModelEventEnvelope(
            event_type=event_type,
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
            source=source,
            metadata=metadata,
            payload=payload,
        )

        return envelope

    def _serialize_event(self, envelope: ModelEventEnvelope) -> bytes:
        """
        Serialize event envelope to JSON bytes with secret sanitization.

        Applies LogSanitizer to remove sensitive data (API keys, passwords,
        tokens) from event payloads before publishing to Kafka. This prevents
        secrets from leaking into:
        - Kafka topic logs (persistent storage)
        - Kafka UI (visible to developers)
        - Downstream consumers
        - Observability/telemetry platforms

        Args:
            envelope: Event envelope to serialize

        Returns:
            JSON bytes with secrets masked (e.g., "sk-abc123..." -> "[OPENAI_API_KEY]")

        Raises:
            ValueError: If serialization fails
        """
        # Convert to dict (handles UUIDs, datetime, Pydantic models)
        event_dict = envelope.to_dict()

        # Serialize to JSON
        json_str = json.dumps(event_dict, default=str)

        # Sanitize secrets before publishing (if enabled)
        json_str = self._sanitize_json(json_str)

        return json_str.encode("utf-8")

    def _sanitize_json(self, json_str: str) -> str:
        """
        Sanitize JSON string to remove sensitive data.

        Applies LogSanitizer to mask secrets (API keys, passwords, tokens)
        if sanitization is enabled.

        Args:
            json_str: JSON string to sanitize

        Returns:
            Sanitized JSON string (or original if sanitization disabled)
        """
        if self.enable_sanitization:
            sanitizer = get_log_sanitizer()
            return sanitizer.sanitize(json_str)
        return json_str

    async def _send_to_dlq(
        self, topic: str, envelope: ModelEventEnvelope, error_message: str
    ) -> None:
        """
        Send failed event to Dead Letter Queue with secret sanitization.

        DLQ events are sanitized to prevent secrets from leaking during
        debugging and error analysis. This is critical because DLQ events
        are often exported, shared, or logged for troubleshooting.

        Args:
            topic: Original topic
            envelope: Event envelope
            error_message: Error description
        """
        dlq_topic = f"{topic}.dlq"

        try:
            # Create DLQ payload with error metadata
            dlq_payload = {
                "original_topic": topic,
                "original_envelope": envelope.to_dict(),
                "error_message": error_message,
                "error_timestamp": time.time(),
                "service": self.service_name,
                "instance_id": self.instance_id,
                "retry_count": self.max_retries,
            }

            dlq_json = json.dumps(dlq_payload, default=str)

            # Sanitize secrets in DLQ payload (if enabled)
            dlq_json = self._sanitize_json(dlq_json)

            dlq_bytes = dlq_json.encode("utf-8")

            # Produce to DLQ (no retry, best effort)
            if self.producer:
                self.producer.produce(topic=dlq_topic, value=dlq_bytes)
                self.producer.flush(timeout=5.0)  # Wait up to 5 seconds

            self.metrics["events_sent_to_dlq"] += 1

            logger.info(
                f"Event sent to DLQ | dlq_topic={dlq_topic} | "
                f"correlation_id={envelope.correlation_id} | error={error_message}"
            )

        except (ConnectionError, TimeoutError, OSError) as e:
            # Network errors during DLQ send are logged but don't propagate
            logger.error(
                f"Failed to send event to DLQ (network error) | dlq_topic={dlq_topic} | error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: DLQ send must never raise, any error is logged only
            logger.error(
                f"Failed to send event to DLQ | dlq_topic={dlq_topic} | error={e}",
                exc_info=True,
            )

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_breaker_open:
            return False

        # Check if timeout has elapsed
        if self._circuit_breaker_last_failure_time:
            elapsed = time.time() - self._circuit_breaker_last_failure_time
            if elapsed > self.circuit_breaker_timeout_s:
                # Reset circuit breaker
                logger.info(
                    f"Circuit breaker reset after timeout | elapsed={elapsed:.1f}s"
                )
                self._reset_circuit_breaker()
                return False

        return True

    def _record_circuit_breaker_failure(self) -> None:
        """Record a failure for circuit breaker tracking."""
        self._circuit_breaker_failures += 1
        self._circuit_breaker_last_failure_time = time.time()

        if self._circuit_breaker_failures >= self.circuit_breaker_threshold:
            self._circuit_breaker_open = True
            self.metrics["circuit_breaker_opens"] += 1

            logger.error(
                f"Circuit breaker OPENED | failures={self._circuit_breaker_failures} | "
                f"threshold={self.circuit_breaker_threshold}"
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker after successful publish."""
        if self._circuit_breaker_failures > 0 or self._circuit_breaker_open:
            logger.info("Circuit breaker reset after successful publish")

        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time = None
        self._circuit_breaker_open = False

    def get_metrics(self) -> PublisherMetrics:
        """
        Get publisher metrics.

        Returns:
            PublisherMetrics with all counter values plus computed fields:
            - events_published: Total events published successfully
            - events_failed: Total events that failed publishing
            - events_sent_to_dlq: Total events sent to DLQ
            - total_publish_time_ms: Cumulative publish time
            - avg_publish_time_ms: Average publish time per event
            - circuit_breaker_opens: Times circuit breaker opened
            - retries_attempted: Total retry attempts
            - circuit_breaker_status: Current circuit breaker status
            - serialization_errors: Count of serialization failures (not circuit breaker)
            - envelope_errors: Count of envelope creation failures (not circuit breaker)
            - total_events: Sum of published and failed events
            - current_failures: Current circuit breaker failure count
        """
        published = self.metrics["events_published"]
        failed = self.metrics["events_failed"]
        total_events = published + failed
        avg_publish_time = (
            self.metrics["total_publish_time_ms"] / published if published > 0 else 0.0
        )

        return {
            **self.metrics,
            "total_events": total_events,
            "avg_publish_time_ms": avg_publish_time,
            "circuit_breaker_status": (
                "open" if self._circuit_breaker_open else "closed"
            ),
            "current_failures": self._circuit_breaker_failures,
        }

    async def close(self) -> None:
        """
        Close publisher and flush pending messages.

        Ensures all pending messages are delivered before shutdown.
        """
        if self.producer:
            try:
                logger.info("Flushing pending messages before shutdown")
                # Flush with 10 second timeout
                remaining = self.producer.flush(timeout=10.0)
                if remaining > 0:
                    logger.warning(
                        f"{remaining} messages failed to flush before shutdown"
                    )
                else:
                    logger.info("All messages flushed successfully")
            except (ConnectionError, TimeoutError, OSError) as e:
                # Network errors during flush are logged but don't propagate
                logger.error(f"Network error flushing producer: {e}")
            except Exception as e:
                # Intentionally broad: cleanup must never raise
                logger.error(f"Error flushing producer: {e}")

        logger.info(f"EventPublisher closed | metrics={self.get_metrics()}")


# ============================================================================
# Factory Functions
# ============================================================================


def create_event_publisher(
    bootstrap_servers: str,
    service_name: str,
    instance_id: str,
    **kwargs: Any,  # any-ok: factory forwarding arbitrary kwargs
) -> EventPublisher:
    """
    Create event publisher instance.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        service_name: Service name
        instance_id: Instance ID
        **kwargs: Additional EventPublisher arguments

    Returns:
        Configured EventPublisher instance
    """
    return EventPublisher(
        bootstrap_servers=bootstrap_servers,
        service_name=service_name,
        instance_id=instance_id,
        **kwargs,
    )
