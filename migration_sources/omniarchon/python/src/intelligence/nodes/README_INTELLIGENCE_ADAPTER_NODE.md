# Intelligence Adapter Effect Node - Kafka Event Integration

**Status**: Phase 2 Complete ✅
**Created**: 2025-10-21
**Branch**: `feature/event-bus-integration`

## Overview

The Intelligence Adapter Effect Node (`NodeIntelligenceAdapterEffect`) is an ONEX-compliant Effect node that integrates Archon's intelligence services with event-driven architecture via Kafka. It provides:

- **Event Subscription**: Consumes `CODE_ANALYSIS_REQUESTED` events from Kafka
- **Intelligence Processing**: Routes requests to Archon intelligence services (quality, performance, patterns)
- **Event Publishing**: Publishes `CODE_ANALYSIS_COMPLETED` or `CODE_ANALYSIS_FAILED` events
- **Lifecycle Management**: Graceful startup/shutdown with offset management
- **Error Handling**: Comprehensive error handling with DLQ routing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  EVENT FLOW                             │
└─────────────────────────────────────────────────────────┘

1. Kafka Consumer (dev.archon-intelligence.intelligence.code-analysis-requested.v1)
   ↓
2. NodeIntelligenceAdapterEffect (Event Router)
   ↓
3. analyze_code() → Intelligence Services (localhost:8053)
   ├─ /assess/code (Quality assessment)
   ├─ /patterns/extract (Pattern detection)
   └─ /compliance/check (ONEX compliance)
   ↓
4. Event Publisher
   ├─ CODE_ANALYSIS_COMPLETED (Success)
   └─ CODE_ANALYSIS_FAILED (Error)
   ↓
5. Kafka Topics
   ├─ dev.archon-intelligence.intelligence.code-analysis-completed.v1
   ├─ dev.archon-intelligence.intelligence.code-analysis-failed.v1
   └─ *.dlq (Dead Letter Queue for unrecoverable errors)
```

## Event Contracts

### Input Event: CODE_ANALYSIS_REQUESTED

**Topic**: `dev.archon-intelligence.intelligence.code-analysis-requested.v1`
**Consumer Group**: `intelligence_adapter_consumers`

**Payload** (`ModelCodeAnalysisRequestPayload`):
```python
{
    "source_path": "src/api/endpoints.py",
    "content": "def hello(): pass",  # Optional
    "language": "python",  # Optional
    "operation_type": "COMPREHENSIVE_ANALYSIS",  # Enum
    "options": {
        "include_recommendations": True,
        "quality_threshold": 0.8
    },
    "project_id": "omniarchon",  # Optional
    "user_id": "system"  # Optional
}
```

### Output Event: CODE_ANALYSIS_COMPLETED

**Topic**: `dev.archon-intelligence.intelligence.code-analysis-completed.v1`

**Payload** (`ModelCodeAnalysisCompletedPayload`):
```python
{
    "source_path": "src/api/endpoints.py",
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "issues_count": 3,
    "recommendations_count": 5,
    "processing_time_ms": 1234.5,
    "operation_type": "COMPREHENSIVE_ANALYSIS",
    "complexity_score": 0.45,
    "maintainability_score": 0.78,
    "results_summary": {
        "total_lines": 245,
        "cyclomatic_complexity": 12,
        "pattern_matches": ["onex_effect_pattern"]
    },
    "cache_hit": False
}
```

### Output Event: CODE_ANALYSIS_FAILED

**Topic**: `dev.archon-intelligence.intelligence.code-analysis-failed.v1`

**Payload** (`ModelCodeAnalysisFailedPayload`):
```python
{
    "operation_type": "QUALITY_ASSESSMENT",
    "source_path": "src/broken/invalid_syntax.py",
    "error_message": "Failed to parse Python code: unexpected EOF",
    "error_code": "PARSING_ERROR",  # Enum
    "retry_allowed": False,
    "retry_count": 0,
    "processing_time_ms": 456.7,
    "error_details": {
        "exception_type": "SyntaxError",
        "line_number": 42
    },
    "suggested_action": "Verify source code syntax is valid"
}
```

## Usage

### Basic Usage (Event-Driven)

```python
import asyncio
from python.src.intelligence.nodes import NodeIntelligenceAdapterEffect

async def main():
    # Step 1: Create node
    node = NodeIntelligenceAdapterEffect(
        service_url="http://archon-intelligence:8053",
        bootstrap_servers="omninode-bridge-redpanda:9092"
    )

    # Step 2: Initialize Kafka consumer and publisher
    await node.initialize()

    # Step 3: Node now consumes events in background
    # Events are processed automatically:
    #   - CODE_ANALYSIS_REQUESTED → analyze_code() → CODE_ANALYSIS_COMPLETED/FAILED

    print(f"Node running: {node.is_running}")
    print(f"Topics: {node.consumer_config.topics}")
    print(f"Consumer group: {node.consumer_config.group_id}")

    # Step 4: Monitor metrics
    while True:
        await asyncio.sleep(10)
        metrics = node.get_metrics()
        print(f"Events processed: {metrics['events_processed']}")
        print(f"Analyses completed: {metrics['analysis_completed']}")
        print(f"Avg processing time: {metrics['avg_processing_time_ms']:.2f}ms")

    # Step 5: Graceful shutdown
    await node.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Direct Usage (Non-Event)

```python
import asyncio
from uuid import uuid4
from services.intelligence.onex.contracts.model_intelligence_input import ModelIntelligenceInput
from python.src.intelligence.nodes import NodeIntelligenceAdapterEffect

async def main():
    # Create node (no Kafka required for direct usage)
    node = NodeIntelligenceAdapterEffect(
        service_url="http://localhost:8053"
    )

    # Direct analysis without events
    input_data = ModelIntelligenceInput(
        operation_type="assess_code_quality",
        correlation_id=uuid4(),
        content="def hello(): pass",
        source_path="test.py",
        language="python",
        options={"include_recommendations": True}
    )

    output = await node.analyze_code(input_data)

    print(f"Success: {output.success}")
    print(f"Quality Score: {output.quality_score:.2f}")
    print(f"ONEX Compliance: {output.onex_compliance:.2f}")
    print(f"Issues: {len(output.issues)}")
    print(f"Recommendations: {len(output.recommendations)}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Custom Configuration

```python
from python.src.intelligence.nodes.node_intelligence_adapter_effect import (
    NodeIntelligenceAdapterEffect,
    ModelKafkaConsumerConfig
)

# Custom consumer configuration
consumer_config = ModelKafkaConsumerConfig(
    bootstrap_servers="localhost:9092",
    group_id="custom_intelligence_consumers",
    topics=[
        "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        "dev.archon-intelligence.intelligence.custom-analysis.v1"
    ],
    auto_offset_reset="earliest",  # Start from beginning
    enable_auto_commit=False,  # Manual offset control
    max_poll_records=20,  # Batch size
    session_timeout_ms=60000,  # 1 minute timeout
)

node = NodeIntelligenceAdapterEffect(
    service_url="http://archon-intelligence:8053",
    bootstrap_servers="localhost:9092",
    consumer_config=consumer_config
)

await node.initialize()
```

## Publishing Events (External Producers)

To trigger analysis via events from external services:

```python
from uuid import uuid4
from services.intelligence.src.events.models.intelligence_adapter_events import (
    create_request_event,
    EnumAnalysisOperationType
)
from src.events.publisher.event_publisher import EventPublisher

# Step 1: Create event publisher
publisher = EventPublisher(
    bootstrap_servers="omninode-bridge-redpanda:9092",
    service_name="my-service",
    instance_id="instance-1"
)

# Step 2: Create CODE_ANALYSIS_REQUESTED event
event = create_request_event(
    source_path="src/api/endpoints.py",
    content="def calculate_total(items): return sum(item.price for item in items)",
    language="python",
    operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    options={
        "include_recommendations": True,
        "quality_threshold": 0.8
    },
    correlation_id=uuid4()
)

# Step 3: Publish to Kafka
await publisher.publish(
    event_type=event["event_type"],
    payload=event["payload"],
    correlation_id=str(event["correlation_id"]),
    topic="dev.archon-intelligence.intelligence.code-analysis-requested.v1"
)

print(f"Published analysis request | correlation_id={event['correlation_id']}")

# Step 4: Close publisher
await publisher.close()
```

## Consuming Completed Events (External Consumers)

To consume analysis results from other services:

```python
import asyncio
import json
from confluent_kafka import Consumer

async def consume_completed_events():
    # Step 1: Create Kafka consumer
    consumer = Consumer({
        "bootstrap.servers": "omninode-bridge-redpanda:9092",
        "group.id": "external_analysis_consumers",
        "auto.offset.reset": "latest"
    })

    # Step 2: Subscribe to completion topic
    consumer.subscribe([
        "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
    ])

    # Step 3: Poll for messages
    while True:
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            continue

        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        # Step 4: Deserialize event
        event = json.loads(msg.value().decode("utf-8"))
        payload = event["payload"]

        print(f"Analysis completed | correlation_id={event['correlation_id']}")
        print(f"Quality score: {payload['quality_score']:.2f}")
        print(f"ONEX compliance: {payload['onex_compliance']:.2f}")
        print(f"Issues: {payload['issues_count']}")
        print(f"Processing time: {payload['processing_time_ms']:.2f}ms")

        # Commit offset
        consumer.commit()

if __name__ == "__main__":
    asyncio.run(consume_completed_events())
```

## Error Handling

### DLQ Routing

Unrecoverable errors are routed to Dead Letter Queue topics:

- `dev.archon-intelligence.intelligence.code-analysis-requested.v1.dlq`

**DLQ Payload Structure**:
```python
{
    "original_topic": "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
    "original_envelope": { /* Full event envelope */ },
    "error_message": "Failed to deserialize event payload",
    "error_timestamp": 1698765432.123,
    "service": "archon-intelligence",
    "instance_id": "intelligence-adapter-abc123",
    "retry_count": 3
}
```

### Manual DLQ Processing

```python
from confluent_kafka import Consumer
import json

consumer = Consumer({
    "bootstrap.servers": "omninode-bridge-redpanda:9092",
    "group.id": "dlq_manual_processors",
    "auto.offset.reset": "earliest"
})

consumer.subscribe([
    "dev.archon-intelligence.intelligence.code-analysis-requested.v1.dlq"
])

while True:
    msg = consumer.poll(timeout=1.0)
    if msg and not msg.error():
        dlq_payload = json.loads(msg.value().decode("utf-8"))

        print(f"DLQ message: {dlq_payload['error_message']}")
        print(f"Original topic: {dlq_payload['original_topic']}")
        print(f"Retry count: {dlq_payload['retry_count']}")

        # Manual intervention required
        # Inspect original_envelope, fix issue, and republish if needed

        consumer.commit()
```

## Metrics

### Available Metrics

```python
metrics = node.get_metrics()

# Event metrics
print(f"Events consumed: {metrics['events_consumed']}")
print(f"Events processed: {metrics['events_processed']}")
print(f"Events failed: {metrics['events_failed']}")

# Analysis metrics
print(f"Analyses completed: {metrics['analysis_completed']}")
print(f"Analyses failed: {metrics['analysis_failed']}")
print(f"DLQ routed: {metrics['dlq_routed']}")

# Performance metrics
print(f"Total processing time: {metrics['total_processing_time_ms']:.2f}ms")
print(f"Avg processing time: {metrics['avg_processing_time_ms']:.2f}ms")

# Consumer state
print(f"Is running: {metrics['is_running']}")
print(f"Consumer group: {metrics['consumer_group']}")
print(f"Topics: {metrics['topics_subscribed']}")
```

### Metrics Monitoring

```python
import asyncio

async def monitor_metrics(node: NodeIntelligenceAdapterEffect):
    """Monitor node metrics every 10 seconds."""
    while node.is_running:
        await asyncio.sleep(10)

        metrics = node.get_metrics()

        # Calculate success rate
        total = metrics["analysis_completed"] + metrics["analysis_failed"]
        success_rate = (
            metrics["analysis_completed"] / total * 100
            if total > 0 else 0.0
        )

        print(f"[METRICS] Processed: {total} | Success rate: {success_rate:.1f}% | "
              f"Avg time: {metrics['avg_processing_time_ms']:.2f}ms")

        # Alert on high failure rate
        if total > 10 and success_rate < 80.0:
            print(f"[ALERT] Low success rate: {success_rate:.1f}%")
```

## Testing

### Unit Test Example

```python
import pytest
from uuid import uuid4
from services.intelligence.onex.contracts.model_intelligence_input import ModelIntelligenceInput
from python.src.intelligence.nodes import NodeIntelligenceAdapterEffect

@pytest.mark.asyncio
async def test_analyze_code_success():
    """Test successful code analysis."""
    node = NodeIntelligenceAdapterEffect(
        service_url="http://localhost:8053"
    )

    input_data = ModelIntelligenceInput(
        operation_type="assess_code_quality",
        correlation_id=uuid4(),
        content="def hello(): pass",
        source_path="test.py",
        language="python"
    )

    output = await node.analyze_code(input_data)

    assert output.success
    assert output.correlation_id == input_data.correlation_id
    assert output.quality_score is not None
    assert 0.0 <= output.quality_score <= 1.0

@pytest.mark.asyncio
async def test_kafka_lifecycle():
    """Test Kafka consumer lifecycle management."""
    node = NodeIntelligenceAdapterEffect(
        bootstrap_servers="localhost:9092"
    )

    # Initialize
    await node.initialize()
    assert node.is_running
    assert node.kafka_consumer is not None
    assert node.event_publisher is not None

    # Shutdown
    await node.shutdown()
    assert not node.is_running
```

### Integration Test Example

See `/services/intelligence/tests/test_intelligence_adapter_kafka.py` for comprehensive integration tests.

## Configuration

### Environment Variables

```bash
# Intelligence service
INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053

# Kafka
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_CONSUMER_GROUP=intelligence_adapter_consumers

# Event topics
KAFKA_TOPIC_ANALYSIS_REQUESTED=dev.archon-intelligence.intelligence.code-analysis-requested.v1
KAFKA_TOPIC_ANALYSIS_COMPLETED=dev.archon-intelligence.intelligence.code-analysis-completed.v1
KAFKA_TOPIC_ANALYSIS_FAILED=dev.archon-intelligence.intelligence.code-analysis-failed.v1

# Consumer settings
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_ENABLE_AUTO_COMMIT=false
KAFKA_MAX_POLL_RECORDS=10
KAFKA_SESSION_TIMEOUT_MS=30000
KAFKA_MAX_POLL_INTERVAL_MS=300000
```

## Deployment

### Docker Compose

```yaml
services:
  intelligence-adapter:
    image: archon-intelligence-adapter:latest
    environment:
      - INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
      - KAFKA_CONSUMER_GROUP=intelligence_adapter_consumers
    depends_on:
      - archon-intelligence
      - omninode-bridge-redpanda
    networks:
      - archon-network
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intelligence-adapter
spec:
  replicas: 3  # Horizontal scaling
  selector:
    matchLabels:
      app: intelligence-adapter
  template:
    metadata:
      labels:
        app: intelligence-adapter
    spec:
      containers:
      - name: intelligence-adapter
        image: archon-intelligence-adapter:latest
        env:
        - name: INTELLIGENCE_SERVICE_URL
          value: "http://archon-intelligence:8053"
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka:9092"
        - name: KAFKA_CONSUMER_GROUP
          value: "intelligence_adapter_consumers"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

## Troubleshooting

### Consumer Not Starting

**Symptom**: `await node.initialize()` fails or hangs

**Solutions**:
1. Check Kafka connectivity: `nc -zv omninode-bridge-redpanda 9092`
2. Verify topics exist: `kafka-topics --bootstrap-server localhost:9092 --list`
3. Check consumer group: `kafka-consumer-groups --bootstrap-server localhost:9092 --group intelligence_adapter_consumers --describe`
4. Review logs for connection errors

### Events Not Being Processed

**Symptom**: `events_consumed` increases but `events_processed` remains 0

**Solutions**:
1. Check event payload format matches `ModelCodeAnalysisRequestPayload`
2. Verify `correlation_id` is present in event envelope
3. Review error logs for deserialization failures
4. Check DLQ for routed messages

### High Processing Time

**Symptom**: `avg_processing_time_ms` > 5000ms

**Solutions**:
1. Check intelligence service health: `curl http://archon-intelligence:8053/health`
2. Monitor intelligence service response times
3. Consider increasing `max_poll_records` for batching
4. Enable caching in intelligence services (Valkey)

### Offset Not Committing

**Symptom**: Consumer re-processes same messages after restart

**Solutions**:
1. Verify `enable_auto_commit=False` and manual commits are working
2. Check commit errors in logs
3. Increase `session_timeout_ms` if processing takes long
4. Review `max_poll_interval_ms` configuration

## Future Enhancements

- [ ] Batch processing for multiple events
- [ ] Parallel analysis execution (multi-threading)
- [ ] Intelligent retry strategies with exponential backoff
- [ ] Circuit breaker integration for intelligence service calls
- [ ] Real-time metrics export (Prometheus/Grafana)
- [ ] Event deduplication based on correlation ID
- [ ] Priority queue support for urgent analyses

## References

- **Event Contracts**: `/services/intelligence/src/events/models/intelligence_adapter_events.py`
- **Input Models**: `/services/intelligence/onex/contracts/model_intelligence_input.py`
- **Output Models**: `/python/src/intelligence/models/model_intelligence_output.py`
- **Event Publisher**: `/python/src/events/publisher/event_publisher.py`
- **Event Architecture**: `EVENT_BUS_ARCHITECTURE.md`
- **ONEX Patterns**: `ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md`

---

**Phase 2 Complete** ✅
**Next**: Agent 1 will implement full intelligence service integration in `analyze_code()` method.
