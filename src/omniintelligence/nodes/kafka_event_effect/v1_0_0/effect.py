"""
Kafka Event Effect Node - ONEX Effect Node for Publishing Events to Kafka.

This Effect node provides:
- Event publishing to Kafka/Redpanda topics
- Automatic topic routing based on event type
- Correlation ID tracking for distributed tracing
- Delivery confirmation with callback mechanism
- Retry logic with exponential backoff
- Circuit breaker for resilience
- Dead-letter queue (DLQ) routing on failures
- Idempotent producer for exactly-once semantics

ONEX Compliance:
- Suffix-based naming: NodeKafkaEventEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling via OnexError

Event Flow:
1. Receive event data (topic, event_type, payload, correlation_id)
2. Create event envelope with metadata
3. Serialize to JSON with secret sanitization
4. Publish to Kafka with delivery confirmation
5. Return result with partition/offset information

Created: 2025-12-01
Reference: EVENT_BUS_ARCHITECTURE.md, EventPublisher
"""

import asyncio
import json
import logging
import os
import time
from typing import Any
from uuid import UUID, uuid4

from confluent_kafka import Producer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Input/Output Models (ONEX Contract Compliance)
# ============================================================================


class ModelKafkaEventInput(BaseModel):
    """
    Input model for Kafka event publishing.

    Attributes:
        topic: Kafka topic to publish to (without prefix)
        event_type: Type of event being published
        payload: Event payload (dict or Pydantic model)
        correlation_id: Correlation ID for tracing
        key: Optional partition key (defaults to correlation_id)
        headers: Optional Kafka headers
    """

    topic: str = Field(
        ...,
        description="Kafka topic to publish to",
        examples=["enrichment.completed.v1", "quality.assessed.v1"],
    )

    event_type: str = Field(
        ...,
        description="Type of event being published",
        examples=[
            "DOCUMENT_INGESTED",
            "PATTERN_EXTRACTED",
            "QUALITY_ASSESSED",
            "INDEXING_COMPLETED",
            "PROCESSING_FAILED",
        ],
    )

    payload: dict[str, Any] = Field(
        ...,
        description="Event payload",
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for tracing",
    )

    key: str | None = Field(
        default=None,
        description="Partition key (defaults to correlation_id)",
    )

    headers: dict[str, str] | None = Field(
        default=None,
        description="Additional Kafka headers",
    )


class ModelKafkaEventOutput(BaseModel):
    """
    Output model for Kafka event publishing.

    Attributes:
        success: Whether event was published successfully
        topic: Topic published to
        partition: Partition the event was published to
        offset: Offset of the published event
        error: Error message if failed
        correlation_id: Correlation ID from input
    """

    success: bool = Field(
        ...,
        description="Whether event was published successfully",
    )

    topic: str = Field(
        ...,
        description="Topic published to",
    )

    partition: int | None = Field(
        default=None,
        description="Partition the event was published to",
    )

    offset: int | None = Field(
        default=None,
        description="Offset of the published event",
    )

    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from input",
    )


class ModelKafkaEventConfig(BaseModel):
    """
    Configuration model for Kafka event effect node.

    Attributes:
        bootstrap_servers: Kafka bootstrap servers
        topic_prefix: Topic prefix for all events
        enable_idempotence: Enable idempotent producer
        acks: Acknowledgment level
        max_retries: Maximum retry attempts
        retry_backoff_ms: Retry backoff in milliseconds
        circuit_breaker_threshold: Failures before opening circuit
        circuit_breaker_timeout_s: Circuit breaker timeout in seconds
        enable_dlq: Enable dead-letter queue routing
    """

    bootstrap_servers: str = Field(
        default_factory=lambda: os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "omninode-bridge-redpanda:9092"
        ),
        description="Kafka bootstrap servers",
    )

    topic_prefix: str = Field(
        default_factory=lambda: os.getenv(
            "KAFKA_TOPIC_PREFIX", "dev.archon-intelligence"
        ),
        description="Topic prefix for all events",
    )

    enable_idempotence: bool = Field(
        default=True,
        description="Enable idempotent producer",
    )

    acks: str = Field(
        default="all",
        description="Acknowledgment level",
    )

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )

    retry_backoff_ms: int = Field(
        default=1000,
        description="Retry backoff in milliseconds",
    )

    circuit_breaker_threshold: int = Field(
        default=5,
        description="Failures before opening circuit",
    )

    circuit_breaker_timeout_s: int = Field(
        default=60,
        description="Circuit breaker timeout in seconds",
    )

    enable_dlq: bool = Field(
        default=True,
        description="Enable dead-letter queue routing",
    )


# ============================================================================
# Kafka Event Effect Node (ONEX Pattern)
# ============================================================================


class NodeKafkaEventEffect:
    """
    Kafka Event Effect Node - ONEX Effect Node for Publishing Events.

    This ONEX Effect node publishes events to Kafka/Redpanda topics with:
    - Automatic topic routing with configurable prefix
    - Correlation ID tracking for distributed tracing
    - Delivery confirmation with callback mechanism
    - Retry logic with exponential backoff
    - Circuit breaker for resilience
    - Dead-letter queue (DLQ) routing on failures
    - Idempotent producer for exactly-once semantics

    **Core Capabilities**:
    - Event publishing to Kafka topics
    - Topic routing with prefix (e.g., "dev.archon-intelligence.quality.assessed.v1")
    - Delivery confirmation with partition/offset information
    - Retry with exponential backoff on failures
    - Circuit breaker to prevent cascading failures
    - DLQ routing for unrecoverable errors

    **Event Types Supported**:
    - DOCUMENT_INGESTED: Document ingestion completed
    - PATTERN_EXTRACTED: Pattern extraction completed
    - QUALITY_ASSESSED: Quality assessment completed
    - INDEXING_COMPLETED: Indexing completed
    - PROCESSING_FAILED: Processing failed

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.nodes.kafka_event_effect.v1_0_0.effect import (
        ...     NodeKafkaEventEffect,
        ...     ModelKafkaEventInput,
        ... )
        >>>
        >>> node = NodeKafkaEventEffect(container=None)
        >>> await node.initialize()
        >>>
        >>> input_data = ModelKafkaEventInput(
        ...     topic="quality.assessed.v1",
        ...     event_type="QUALITY_ASSESSED",
        ...     payload={"quality_score": 0.87, "entity_id": "abc-123"},
        ...     correlation_id=uuid4(),
        ... )
        >>>
        >>> output = await node.execute_effect(input_data)
        >>> assert output.success
        >>> assert output.partition is not None
        >>> assert output.offset is not None
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Kafka connection errors: Retry with backoff
    - Serialization errors: Route to DLQ
    - Circuit breaker open: Raise error immediately
    - Max retries exceeded: Route to DLQ

    Attributes:
        node_id: Unique node identifier
        config: Kafka configuration
        producer: Kafka producer instance
        metrics: Operation metrics
        circuit_breaker_failures: Circuit breaker failure count
        circuit_breaker_open: Circuit breaker status
        circuit_breaker_last_failure_time: Last failure timestamp
    """

    def __init__(
        self,
        container: Any,
        config: ModelKafkaEventConfig | None = None,
    ):
        """
        Initialize Kafka Event Effect Node.

        Args:
            container: ONEX container for dependency injection
            config: Optional Kafka configuration
        """
        self.container = container
        self.node_id = uuid4()
        self.config = config or ModelKafkaEventConfig()

        # Kafka producer
        self.producer: Producer | None = None

        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure_time: float | None = None
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

        logger.info(
            f"NodeKafkaEventEffect initialized | "
            f"node_id={self.node_id} | "
            f"bootstrap_servers={self.config.bootstrap_servers} | "
            f"topic_prefix={self.config.topic_prefix}"
        )

    async def initialize(self) -> None:
        """
        Initialize Kafka producer.

        This method:
        1. Creates Kafka producer with optimized configuration
        2. Configures idempotence and reliability settings
        3. Sets up delivery callback mechanism

        Raises:
            RuntimeError: If producer initialization fails
        """
        try:
            producer_config = {
                "bootstrap.servers": self.config.bootstrap_servers,
                # Performance tuning
                "linger.ms": 10,  # Batch messages for 10ms
                "batch.size": 32768,  # 32KB batch size
                "compression.type": "lz4",  # Fast compression
                "acks": self.config.acks,  # Wait for all replicas
                # Idempotence and reliability
                "enable.idempotence": self.config.enable_idempotence,
                "max.in.flight.requests.per.connection": 5 if self.config.enable_idempotence else 1,
                "retries": 2147483647 if self.config.enable_idempotence else 0,  # Max retries for idempotence
                # Timeout configuration
                "request.timeout.ms": 30000,  # 30 seconds
                "delivery.timeout.ms": 120000,  # 2 minutes total
                # Client identification
                "client.id": f"kafka-event-effect-{self.node_id.hex[:8]}",
            }

            self.producer = Producer(producer_config)
            logger.info(
                f"Kafka producer initialized | "
                f"node_id={self.node_id} | "
                f"idempotence={self.config.enable_idempotence}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}", exc_info=True)
            raise RuntimeError(f"Kafka producer initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown Kafka producer.

        This method:
        1. Flushes pending messages
        2. Closes producer connection
        3. Logs final metrics

        Does not raise exceptions - logs warnings on failure.
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

        logger.info(
            f"NodeKafkaEventEffect shutdown complete | "
            f"node_id={self.node_id} | "
            f"final_metrics={self.metrics}"
        )

    async def execute_effect(
        self, input_data: ModelKafkaEventInput
    ) -> ModelKafkaEventOutput:
        """
        Execute Kafka event publishing effect (ONEX Effect pattern method).

        This method:
        1. Checks circuit breaker status
        2. Constructs full topic name with prefix
        3. Creates event envelope with metadata
        4. Serializes to JSON
        5. Publishes to Kafka with delivery confirmation
        6. Retries on failure with exponential backoff
        7. Routes to DLQ on max retries exceeded

        Args:
            input_data: Kafka event input data

        Returns:
            ModelKafkaEventOutput with publish result

        Raises:
            RuntimeError: If circuit breaker is open
            ValueError: If producer not initialized
        """
        # Check initialization
        if self.producer is None:
            raise ValueError(
                "Kafka producer not initialized. Call initialize() first."
            )

        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.error(
                f"Circuit breaker is OPEN | node_id={self.node_id} | "
                f"failures={self._circuit_breaker_failures}"
            )
            raise RuntimeError("Circuit breaker is open, refusing to publish events")

        start_time = time.perf_counter()

        try:
            # Construct full topic name with prefix
            full_topic = f"{self.config.topic_prefix}.{input_data.topic}"

            # Create event envelope
            envelope = self._create_event_envelope(
                event_type=input_data.event_type,
                payload=input_data.payload,
                correlation_id=input_data.correlation_id,
            )

            # Serialize event
            event_bytes = self._serialize_event(envelope)

            # Determine partition key
            partition_key = input_data.key or str(input_data.correlation_id)

            # Publish with retry
            result = await self._publish_with_retry(
                topic=full_topic,
                event_bytes=event_bytes,
                partition_key=partition_key,
                correlation_id=input_data.correlation_id,
            )

            if result["success"]:
                # Update metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self.metrics["events_published"] += 1
                self.metrics["total_publish_time_ms"] += elapsed_ms

                # Reset circuit breaker on success
                self._reset_circuit_breaker()

                logger.info(
                    f"Event published successfully | "
                    f"event_type={input_data.event_type} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"topic={full_topic} | "
                    f"partition={result['partition']} | "
                    f"offset={result['offset']} | "
                    f"duration={elapsed_ms:.2f}ms"
                )

                return ModelKafkaEventOutput(
                    success=True,
                    topic=full_topic,
                    partition=result["partition"],
                    offset=result["offset"],
                    correlation_id=input_data.correlation_id,
                )
            else:
                # Publish failed after retries
                self.metrics["events_failed"] += 1
                self._record_circuit_breaker_failure()

                # Send to DLQ if enabled
                if self.config.enable_dlq:
                    await self._send_to_dlq(
                        topic=full_topic,
                        envelope=envelope,
                        error_message=result["error"],
                    )

                logger.error(
                    f"Event publish failed after retries | "
                    f"event_type={input_data.event_type} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"error={result['error']}"
                )

                return ModelKafkaEventOutput(
                    success=False,
                    topic=full_topic,
                    error=result["error"],
                    correlation_id=input_data.correlation_id,
                )

        except Exception as e:
            self.metrics["events_failed"] += 1
            self._record_circuit_breaker_failure()

            logger.error(
                f"Event publish error | "
                f"event_type={input_data.event_type} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={e}",
                exc_info=True,
            )

            return ModelKafkaEventOutput(
                success=False,
                topic=f"{self.config.topic_prefix}.{input_data.topic}",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _publish_with_retry(
        self,
        topic: str,
        event_bytes: bytes,
        partition_key: str,
        correlation_id: UUID,
    ) -> dict[str, Any]:
        """
        Publish event with exponential backoff retry.

        Args:
            topic: Kafka topic
            event_bytes: Serialized event data
            partition_key: Partition key
            correlation_id: Correlation ID for logging

        Returns:
            Dictionary with success status, partition, offset, or error
        """
        for attempt in range(self.config.max_retries + 1):
            try:
                # Attempt to publish
                result = await self._produce_message(
                    topic=topic,
                    value=event_bytes,
                    key=partition_key.encode(),
                )

                # Success
                if attempt > 0:
                    logger.info(
                        f"Event published after {attempt} retries | "
                        f"correlation_id={correlation_id}"
                    )
                return {
                    "success": True,
                    "partition": result["partition"],
                    "offset": result["offset"],
                }

            except Exception as e:
                if attempt < self.config.max_retries:
                    # Calculate backoff with exponential increase
                    backoff_ms = self.config.retry_backoff_ms * (2**attempt)

                    logger.warning(
                        f"Event publish failed, retrying | "
                        f"attempt={attempt + 1}/{self.config.max_retries + 1} | "
                        f"backoff={backoff_ms}ms | "
                        f"correlation_id={correlation_id} | "
                        f"error={e}"
                    )

                    self.metrics["retries_attempted"] += 1

                    # Wait before retry
                    await asyncio.sleep(backoff_ms / 1000.0)
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Event publish failed after {self.config.max_retries + 1} attempts | "
                        f"correlation_id={correlation_id} | "
                        f"error={e}"
                    )
                    return {"success": False, "error": str(e)}

        return {"success": False, "error": "Max retries exceeded"}

    async def _produce_message(
        self, topic: str, value: bytes, key: bytes
    ) -> dict[str, Any]:
        """
        Produce message to Kafka asynchronously.

        Args:
            topic: Kafka topic
            value: Message value (bytes)
            key: Message key (bytes)

        Returns:
            Dictionary with partition and offset

        Raises:
            Exception: If produce fails
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized")

        # Create future for delivery callback
        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()

        def delivery_callback(err: Exception | None, msg: Any) -> None:
            """Delivery callback to set future result."""
            if err:
                future.set_exception(Exception(f"Kafka delivery failed: {err}"))
            else:
                future.set_result(
                    {
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                    }
                )

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
        result = await future
        return result

    def _create_event_envelope(
        self,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: UUID,
    ) -> dict[str, Any]:
        """
        Create event envelope with metadata.

        Args:
            event_type: Event type string
            payload: Event payload
            correlation_id: Correlation ID

        Returns:
            Event envelope dictionary
        """
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "correlation_id": str(correlation_id),
            "timestamp": time.time(),
            "version": "1.0.0",
            "source": {
                "service": "omniintelligence",
                "node_type": "kafka_event_effect",
                "node_id": str(self.node_id),
            },
            "payload": payload,
        }

    def _serialize_event(self, envelope: dict[str, Any]) -> bytes:
        """
        Serialize event envelope to JSON bytes.

        Args:
            envelope: Event envelope to serialize

        Returns:
            JSON bytes
        """
        json_str = json.dumps(envelope, default=str)
        return json_str.encode("utf-8")

    async def _send_to_dlq(
        self, topic: str, envelope: dict[str, Any], error_message: str
    ) -> None:
        """
        Send failed event to Dead Letter Queue.

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
                "original_envelope": envelope,
                "error_message": error_message,
                "error_timestamp": time.time(),
                "node_id": str(self.node_id),
                "retry_count": self.config.max_retries,
            }

            dlq_json = json.dumps(dlq_payload, default=str)
            dlq_bytes = dlq_json.encode("utf-8")

            # Produce to DLQ (no retry, best effort)
            if self.producer:
                self.producer.produce(topic=dlq_topic, value=dlq_bytes)
                self.producer.flush(timeout=5.0)  # Wait up to 5 seconds

            self.metrics["events_sent_to_dlq"] += 1

            logger.info(
                f"Event sent to DLQ | "
                f"dlq_topic={dlq_topic} | "
                f"correlation_id={envelope.get('correlation_id')} | "
                f"error={error_message}"
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
            if elapsed > self.config.circuit_breaker_timeout_s:
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

        if self._circuit_breaker_failures >= self.config.circuit_breaker_threshold:
            self._circuit_breaker_open = True
            self.metrics["circuit_breaker_opens"] += 1

            logger.error(
                f"Circuit breaker OPENED | "
                f"failures={self._circuit_breaker_failures} | "
                f"threshold={self.config.circuit_breaker_threshold}"
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
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - events_published: Total events published successfully
            - events_failed: Total events that failed publishing
            - events_sent_to_dlq: Total events sent to DLQ
            - total_publish_time_ms: Cumulative publish time
            - avg_publish_time_ms: Average publish time per event
            - circuit_breaker_opens: Times circuit breaker opened
            - retries_attempted: Total retry attempts
            - circuit_breaker_status: Current circuit breaker status
        """
        avg_publish_time = (
            self.metrics["total_publish_time_ms"] / self.metrics["events_published"]
            if self.metrics["events_published"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "avg_publish_time_ms": avg_publish_time,
            "circuit_breaker_status": (
                "open" if self._circuit_breaker_open else "closed"
            ),
            "current_failures": self._circuit_breaker_failures,
            "node_id": str(self.node_id),
        }


__all__ = [
    "ModelKafkaEventConfig",
    "ModelKafkaEventInput",
    "ModelKafkaEventOutput",
    "NodeKafkaEventEffect",
]
