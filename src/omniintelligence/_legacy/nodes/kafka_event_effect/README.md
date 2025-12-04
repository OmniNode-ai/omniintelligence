# Kafka Event Effect Node

ONEX-compliant effect node for publishing events to Kafka/Redpanda topics.

## Overview

The Kafka Event Effect Node provides reliable event publishing to Kafka with:
- Automatic topic routing with configurable prefix
- Correlation ID tracking for distributed tracing
- Delivery confirmation with callback mechanism
- Retry logic with exponential backoff
- Circuit breaker for resilience
- Dead-letter queue (DLQ) routing on failures
- Idempotent producer for exactly-once semantics

## Features

### Event Publishing
- **Topic Routing**: Automatic topic prefix (e.g., `dev.archon-intelligence.quality.assessed.v1`)
- **Event Envelope**: Standard event envelope with metadata (event_id, timestamp, source)
- **Partition Keys**: Configurable partition keys for ordered delivery
- **Headers**: Support for custom Kafka headers

### Reliability
- **Delivery Confirmation**: Callback-based delivery confirmation with partition/offset
- **Retry Logic**: Exponential backoff retry (configurable max retries)
- **Circuit Breaker**: Prevents cascading failures (configurable threshold and timeout)
- **Dead-Letter Queue**: Routes unrecoverable failures to `.dlq` topics

### Configuration
- **Bootstrap Servers**: Via `KAFKA_BOOTSTRAP_SERVERS` env var
- **Topic Prefix**: Via `KAFKA_TOPIC_PREFIX` env var
- **Idempotence**: Enabled by default for exactly-once semantics
- **Acknowledgments**: `all` by default for durability

## Usage

### Basic Usage

```python
from uuid import uuid4
from omniintelligence.nodes.kafka_event_effect import (
    NodeKafkaEventEffect,
    ModelKafkaEventInput,
)

# Create and initialize node
node = NodeKafkaEventEffect(container=None)
await node.initialize()

# Publish event
input_data = ModelKafkaEventInput(
    topic="quality.assessed.v1",
    event_type="QUALITY_ASSESSED",
    payload={
        "quality_score": 0.87,
        "entity_id": "abc-123",
        "onex_compliance": 0.92,
    },
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)

if output.success:
    print(f"Published to partition {output.partition} at offset {output.offset}")
else:
    print(f"Failed: {output.error}")

await node.shutdown()
```

### Custom Configuration

```python
from omniintelligence.nodes.kafka_event_effect import (
    NodeKafkaEventEffect,
    ModelKafkaEventConfig,
)

config = ModelKafkaEventConfig(
    bootstrap_servers="localhost:9092",
    topic_prefix="test",
    enable_idempotence=True,
    acks="all",
    max_retries=5,
    retry_backoff_ms=2000,
    circuit_breaker_threshold=10,
    circuit_breaker_timeout_s=120,
    enable_dlq=True,
)

node = NodeKafkaEventEffect(container=None, config=config)
await node.initialize()
```

### With Custom Partition Key

```python
input_data = ModelKafkaEventInput(
    topic="pattern.matched.v1",
    event_type="PATTERN_MATCHED",
    payload={"pattern_type": "quality_issue", "severity": "high"},
    correlation_id=uuid4(),
    key="entity-123",  # Custom partition key for ordering
)

output = await node.execute_effect(input_data)
```

### Event Types Supported

```python
# Document ingestion
ModelKafkaEventInput(
    topic="enrichment.completed.v1",
    event_type="DOCUMENT_INGESTED",
    payload={
        "document_id": "doc-123",
        "entities_count": 42,
        "relationships_count": 18,
    },
    correlation_id=correlation_id,
)

# Pattern extraction
ModelKafkaEventInput(
    topic="pattern.extracted.v1",
    event_type="PATTERN_EXTRACTED",
    payload={
        "pattern_type": "architectural",
        "confidence": 0.95,
    },
    correlation_id=correlation_id,
)

# Quality assessment
ModelKafkaEventInput(
    topic="quality.assessed.v1",
    event_type="QUALITY_ASSESSED",
    payload={
        "quality_score": 0.87,
        "onex_compliance": 0.92,
    },
    correlation_id=correlation_id,
)

# Indexing completion
ModelKafkaEventInput(
    topic="enrichment.completed.v1",
    event_type="INDEXING_COMPLETED",
    payload={
        "document_id": "doc-123",
        "vector_count": 1024,
    },
    correlation_id=correlation_id,
)

# Processing failure
ModelKafkaEventInput(
    topic="enrichment.failed.v1",
    event_type="PROCESSING_FAILED",
    payload={
        "document_id": "doc-123",
        "error_message": "Vectorization failed",
    },
    correlation_id=correlation_id,
)
```

## Integration with ONEX Workflows

### Document Ingestion Workflow

```yaml
- name: publish_completion_event
  type: effect
  description: Publish document ingestion completion event to Kafka
  effect_node: kafka_event_effect
  input:
    topic: enrichment.completed.v1
    event_type: DOCUMENT_INGESTED
    payload:
      document_id: ${input.document_id}
      entities_count: ${extraction_result.entities.length}
      relationships_count: ${relationship_result.relationships.length}
      vectorized: ${vectorization_result.success}
    correlation_id: ${input.correlation_id}
```

### Error Handling

```yaml
error_handling:
  on_step_failure:
    - name: publish_error_event
      type: effect
      effect_node: kafka_event_effect
      input:
        topic: enrichment.failed.v1
        event_type: DOCUMENT_INGESTION_FAILED
        payload:
          document_id: ${input.document_id}
          failed_step: ${error.step}
          error_message: ${error.message}
        correlation_id: ${input.correlation_id}
```

## Monitoring

### Metrics

```python
metrics = node.get_metrics()

print(f"Events published: {metrics['events_published']}")
print(f"Events failed: {metrics['events_failed']}")
print(f"Avg publish time: {metrics['avg_publish_time_ms']:.2f}ms")
print(f"Circuit breaker: {metrics['circuit_breaker_status']}")
print(f"DLQ routed: {metrics['events_sent_to_dlq']}")
print(f"Retries: {metrics['retries_attempted']}")
```

### Circuit Breaker

The circuit breaker opens after a configurable threshold of consecutive failures:

```python
# Circuit breaker configuration
config = ModelKafkaEventConfig(
    circuit_breaker_threshold=5,      # Open after 5 failures
    circuit_breaker_timeout_s=60,     # Reset after 60 seconds
)

# Check circuit breaker status
metrics = node.get_metrics()
if metrics['circuit_breaker_status'] == 'open':
    print("Circuit breaker is open - service degraded")
```

## Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: `omninode-bridge-redpanda:9092`)
- `KAFKA_TOPIC_PREFIX`: Topic prefix for all events (default: `dev.archon-intelligence`)

## Event Envelope Format

All published events follow this envelope format:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "QUALITY_ASSESSED",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1701446400.123,
  "version": "1.0.0",
  "source": {
    "service": "omniintelligence",
    "node_type": "kafka_event_effect",
    "node_id": "abc123..."
  },
  "payload": {
    "quality_score": 0.87,
    "entity_id": "abc-123"
  }
}
```

## Dead-Letter Queue

Failed events are routed to DLQ topics with `.dlq` suffix:

**Original topic**: `dev.archon-intelligence.quality.assessed.v1`
**DLQ topic**: `dev.archon-intelligence.quality.assessed.v1.dlq`

DLQ payload includes:
- Original envelope
- Error message and timestamp
- Retry count
- Node ID for debugging

## Testing

Run tests with:

```bash
uv run pytest tests/nodes/kafka_event_effect/ -v
```

Test coverage:
- Initialization and configuration
- Event publishing with delivery confirmation
- Retry logic with exponential backoff
- Circuit breaker behavior
- Dead-letter queue routing
- Metrics tracking
- Edge cases and error handling

## Architecture

### ONEX Compliance

- **Naming**: `NodeKafkaEventEffect` (suffix-based)
- **Pattern**: Effect node with `execute_effect()` method
- **Typing**: Strong typing with Pydantic models
- **Correlation**: Preserves correlation IDs for distributed tracing
- **Error Handling**: Comprehensive error handling with circuit breaker

### Dependencies

- `confluent-kafka`: Kafka client library
- `pydantic`: Data validation and settings management

## References

- **EventPublisher**: `/src/omniintelligence/events/publisher/event_publisher.py`
- **Event Models**: `/src/omniintelligence/models/model_event_envelope.py`
- **Contract**: `/src/omniintelligence/nodes/kafka_event_effect/v1_0_0/contracts/effect_contract.yaml`
- **Tests**: `/tests/nodes/kafka_event_effect/test_kafka_event_effect.py`
