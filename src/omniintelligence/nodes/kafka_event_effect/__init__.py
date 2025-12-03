"""
Kafka Event Effect Node - ONEX Effect Node for Publishing Events to Kafka.

This package provides an ONEX-compliant effect node for publishing events
to Kafka/Redpanda topics with:
- Automatic topic routing with configurable prefix
- Correlation ID tracking for distributed tracing
- Delivery confirmation with callback mechanism
- Retry logic with exponential backoff
- Circuit breaker for resilience
- Dead-letter queue (DLQ) routing on failures
- Idempotent producer for exactly-once semantics

Usage:
    >>> from omniintelligence.nodes.kafka_event_effect import (
    ...     NodeKafkaEventEffect,
    ...     ModelKafkaEventInput,
    ...     ModelKafkaEventOutput,
    ...     ModelKafkaEventConfig,
    ... )
    >>>
    >>> node = NodeKafkaEventEffect(container=None)
    >>> await node.initialize()
    >>>
    >>> input_data = ModelKafkaEventInput(
    ...     topic="quality.assessed.v1",
    ...     event_type="QUALITY_ASSESSED",
    ...     payload={"quality_score": 0.87},
    ...     correlation_id=uuid4(),
    ... )
    >>>
    >>> output = await node.execute_effect(input_data)
    >>> assert output.success
    >>>
    >>> await node.shutdown()
"""

from omniintelligence.nodes.kafka_event_effect.v1_0_0.effect import (
    ModelKafkaEventConfig,
    ModelKafkaEventInput,
    ModelKafkaEventOutput,
    NodeKafkaEventEffect,
)

__all__ = [
    "ModelKafkaEventConfig",
    "ModelKafkaEventInput",
    "ModelKafkaEventOutput",
    "NodeKafkaEventEffect",
]
