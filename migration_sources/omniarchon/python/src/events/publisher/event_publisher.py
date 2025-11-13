"""
Event Publisher Base Class - Phase 1

Unified event publisher for all ONEX services with:
- Retry logic with exponential backoff
- Circuit breaker integration
- Event validation against schemas
- Correlation ID tracking
- DLQ routing on failures
- Metrics tracking
- Batching support (future)

Created: 2025-10-18
Reference: EVENT_BUS_ARCHITECTURE.md Phase 1
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional, TypeVar
from uuid import UUID

from confluent_kafka import Producer
from pydantic import BaseModel
from src.events.models.model_event_envelope import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)
from src.server.services.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class EventPublisher:
    """
    Base event publisher with retry, circuit breaker, and validation.

    Provides unified event publishing across all ONEX services with:
    - Automatic retries with exponential backoff
    - Circuit breaker to prevent cascading failures
    - Event validation before publishing
    - Correlation ID tracking for request/response flows
    - Dead letter queue (DLQ) routing on persistent failures
    - Metrics tracking (events published, failures, latency)

    Usage:
        from config import settings
        publisher = EventPublisher(
            bootstrap_servers=settings.kafka_bootstrap_servers,
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
        hostname: Optional[str] = None,
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
        self.producer: Optional[Producer] = None

        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time: Optional[float] = None
        self._circuit_breaker_open = False

        # Metrics
        self.metrics = {
            "events_published": 0,
            "events_failed": 0,
            "events_sent_to_dlq": 0,
            "total_publish_time_ms": 0.0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
        }

        self._initialize_producer()

    def _initialize_producer(self) -> None:
        """Initialize Kafka producer with optimized configuration."""
        producer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            # Performance tuning
            "linger.ms": 10,  # Batch messages for 10ms for throughput
            "batch.size": 32768,  # 32KB batch size
            "compression.type": "lz4",  # Fast compression
            "acks": "all",  # Wait for all replicas (reliability)
            # Error handling
            "retries": 0,  # We handle retries manually
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
        payload: Any,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[ModelEventMetadata] = None,
        topic: Optional[str] = None,
        partition_key: Optional[str] = None,
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
        """
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.error(
                f"Circuit breaker is OPEN | service={self.service_name} | "
                f"failures={self._circuit_breaker_failures}"
            )
            raise RuntimeError("Circuit breaker is open, refusing to publish events")

        start_time = time.perf_counter()

        try:
            # Create event envelope
            envelope = self._create_event_envelope(
                event_type=event_type,
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
                metadata=metadata,
            )

            # Determine topic (default to event_type)
            publish_topic = topic or event_type

            # Serialize event
            event_bytes = self._serialize_event(envelope)

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
                # Publish failed after retries
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

        except Exception as e:
            self.metrics["events_failed"] += 1
            self._record_circuit_breaker_failure()

            logger.error(
                f"Event publish error | event_type={event_type} | error={e}",
                exc_info=True,
            )
            return False

    async def _publish_with_retry(
        self,
        topic: str,
        event_bytes: bytes,
        partition_key: Optional[str],
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

            except Exception as e:
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

        return False

    async def _produce_message(
        self, topic: str, value: bytes, key: Optional[bytes]
    ) -> None:
        """
        Produce message to Kafka asynchronously.

        Args:
            topic: Kafka topic
            value: Message value (bytes)
            key: Optional message key (bytes)

        Raises:
            Exception: If produce fails
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized")

        # Create future for delivery callback
        future = asyncio.get_event_loop().create_future()

        def delivery_callback(err, msg):
            """Delivery callback to set future result."""
            if err:
                future.set_exception(Exception(f"Kafka delivery failed: {err}"))
            else:
                future.set_result(msg)

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
        payload: Any,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[ModelEventMetadata] = None,
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
            correlation_id=correlation_id,
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

        except Exception as e:
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

    def get_metrics(self) -> dict[str, Any]:
        """
        Get publisher metrics.

        Returns:
            Dictionary with metrics:
            - events_published: Total events published successfully
            - events_failed: Total events that failed publishing
            - events_sent_to_dlq: Total events sent to DLQ
            - total_publish_time_ms: Cumulative publish time
            - avg_publish_time_ms: Average publish time per event
            - circuit_breaker_opens: Times circuit breaker opened
            - retries_attempted: Total retry attempts
            - circuit_breaker_status: Current circuit breaker status
        """
        total_events = self.metrics["events_published"] + self.metrics["events_failed"]
        avg_publish_time = (
            self.metrics["total_publish_time_ms"] / self.metrics["events_published"]
            if self.metrics["events_published"] > 0
            else 0.0
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
            except Exception as e:
                logger.error(f"Error flushing producer: {e}")

        logger.info(f"EventPublisher closed | metrics={self.get_metrics()}")


# ============================================================================
# Factory Functions
# ============================================================================


def create_event_publisher(
    bootstrap_servers: str,
    service_name: str,
    instance_id: str,
    **kwargs,
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
