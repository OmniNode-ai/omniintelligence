# Event Bus Quick Reference

**Quick guide for developers working with the ONEX event-driven architecture**

---

## Quick Links

- **Full Documentation**: [EVENT_BUS_ARCHITECTURE.md](./EVENT_BUS_ARCHITECTURE.md)
- **Event Catalog**: All 50+ event types documented
- **Implementation Roadmap**: 5-phase, 10-week plan
- **Schema Repository**: `/schemas/events/`

---

## 30-Second Overview

**What**: Unified event bus across 5 ONEX repositories using Redpanda (Kafka-compatible)

**Why**: Replace synchronous HTTP calls with scalable, resilient, event-driven communication

**Status**: Phase 0 (Planning) → Phase 1 starts Week 1

**Current State**:
- ✅ Redpanda cluster operational
- ✅ Intelligence service has Kafka consumer
- ✅ 8 event topics active (codegen domain)
- ⚠️ No schema registry yet
- ⚠️ Limited cross-repo integration

---

## 5 Repositories

| Repository | Role | Port(s) | Event Capability |
|------------|------|---------|------------------|
| **omniarchon** | Intelligence hub (quality, patterns, RAG) | 8051, 8053, 8055 | Producer + Consumer |
| **omninode_bridge** | Metadata stamping, event infrastructure | 8054, 9092 | Producer + Hosts Redpanda |
| **omnibase_core** | ONEX framework (Effect, Compute, Reducer, Orchestrator) | N/A | Framework-level events |
| **omnibase_spi** | Protocol contracts (zero dependencies) | N/A | Protocol definitions |
| **omnibase_infra** | Infrastructure services (discovery, health) | TBD | Service lifecycle events |

---

## Event Patterns

### 1. Request/Response (RPC-style)

**Use Case**: Synchronous-like communication with async benefits

**Flow**:
```
Service A → Request Topic → Service B → Response Topic → Service A
           (correlation_id: abc-123)
```

**Example**:
```python
# Publisher
await publish_event(
    topic="omninode.codegen.request.validate.v1",
    payload={"code": "class Test: pass"},
    correlation_id="abc-123"
)

# Wait for response
response = await wait_for_response(
    topic="omninode.codegen.response.validate.v1",
    correlation_id="abc-123",
    timeout=10.0
)
```

**Topics**:
- `omninode.codegen.request.{validate,analyze,pattern,mixin}.v1`
- `omninode.bridge.request.{stamp,verify}.v1`

---

### 2. Publish/Subscribe (Event Broadcasting)

**Use Case**: Notify multiple services of an event

**Flow**:
```
Service A → Event Topic → [Service B, Service C, Service D]
```

**Example**:
```python
# Publisher
await publish_event(
    topic="omninode.intelligence.event.quality_assessed.v1",
    payload={
        "entity_id": "doc-123",
        "quality_score": 0.92,
        "onex_compliance": 0.88
    }
)

# Multiple subscribers receive the same event
```

**Topics**:
- `omninode.intelligence.event.{quality_assessed,pattern_learned}.v1`
- `omninode.bridge.event.{metadata_stamped,document_processed}.v1`
- `omninode.search.event.{document_indexed}.v1`

---

### 3. Event Sourcing (Audit Trail)

**Use Case**: Immutable log of all events for replay/audit

**Flow**:
```
Service A → Audit Topic → Event Store (PostgreSQL)
          ↓
     Event persisted forever
```

**Example**:
```python
# Publish audit event
await publish_event(
    topic="omninode.audit.agent_execution.v1",
    payload={
        "agent_name": "agent-code-quality",
        "task": {...},
        "result": {...},
        "duration_ms": 1234
    }
)

# Events stored in PostgreSQL for replay
```

**Topics**:
- `omninode.audit.{agent_execution,quality_snapshot,pattern_creation}.v1`

---

## Event Schema Standard

**All events follow this envelope**:

```json
{
  "event_id": "uuid-v4",
  "event_type": "omninode.{domain}.{pattern}.{operation}.v1",
  "correlation_id": "uuid-v4",
  "causation_id": "uuid-v4",
  "timestamp": "2025-10-18T10:00:00.000Z",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "instance-123"
  },
  "metadata": {
    "trace_id": "uuid-v4",
    "user_id": "optional"
  },
  "payload": {
    // Event-specific data
  }
}
```

**Key Fields**:
- `correlation_id`: Links related events (request/response)
- `causation_id`: Event that caused this event (event sourcing)
- `payload`: Business data (varies by event type)

---

## Common Event Types

### Intelligence Domain

| Event | Topic | Pattern | Payload |
|-------|-------|---------|---------|
| Quality Assessed | `omninode.intelligence.event.quality_assessed.v1` | Pub/Sub | `{entity_id, quality_score, dimensions{}}` |
| Pattern Learned | `omninode.intelligence.event.pattern_learned.v1` | Pub/Sub | `{pattern_id, pattern_type, pattern_data{}}` |
| Code Validation | `omninode.codegen.request.validate.v1` | Request | `{code_content, node_type}` |

### Bridge Domain

| Event | Topic | Pattern | Payload |
|-------|-------|---------|---------|
| Metadata Stamped | `omninode.bridge.event.metadata_stamped.v1` | Pub/Sub | `{blake3_hash, namespace, content_type}` |
| Stamp Request | `omninode.bridge.request.stamp.v1` | Request | `{content, namespace}` |

### Search Domain

| Event | Topic | Pattern | Payload |
|-------|-------|---------|---------|
| Document Indexed | `omninode.search.event.document_indexed.v1` | Pub/Sub | `{document_id, collection, vector_dims}` |

### ONEX Domain

| Event | Topic | Pattern | Payload |
|-------|-------|---------|---------|
| Node Started | `omninode.onex.event.node_started.v1` | Event Source | `{node_type, node_name, contract{}}` |
| Node Completed | `omninode.onex.event.node_completed.v1` | Event Source | `{node_type, result{}, duration_ms}` |

---

## Publishing Events

### Basic Publishing

```python
from src.services.event_publisher import EventPublisher

publisher = EventPublisher()

await publisher.publish(
    topic="omninode.intelligence.event.quality_assessed.v1",
    payload={
        "entity_id": "doc-123",
        "quality_score": 0.92
    },
    correlation_id="optional-correlation-id"
)
```

### Batch Publishing

```python
events = [
    {"topic": "topic1", "payload": {...}},
    {"topic": "topic2", "payload": {...}},
]

await publisher.publish_batch(events)
```

### Request/Response

```python
from src.services.rpc_client import RPCClient

client = RPCClient()

response = await client.request(
    request_topic="omninode.codegen.request.validate.v1",
    response_topic="omninode.codegen.response.validate.v1",
    payload={"code": "class Test: pass"},
    timeout=10.0
)

print(response["quality_score"])
```

---

## Consuming Events

### Basic Consumer

```python
from src.services.event_consumer import EventConsumer

consumer = EventConsumer(
    topics=["omninode.intelligence.event.quality_assessed.v1"],
    group_id="my-consumer-group"
)

@consumer.handler("omninode.intelligence.event.quality_assessed.v1")
async def handle_quality_assessed(event):
    print(f"Quality score: {event['payload']['quality_score']}")
    # Process event
    return True  # Ack event

await consumer.start()
```

### Handler Registration

```python
class QualityEventHandler:
    def can_handle(self, event_type: str) -> bool:
        return event_type == "omninode.intelligence.event.quality_assessed.v1"

    async def handle_event(self, event_data: dict) -> bool:
        # Process event
        return True  # Ack

# Register handler
consumer.register_handler(QualityEventHandler())
```

---

## Configuration

### Environment Variables

```bash
# Kafka/Redpanda
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_CONSUMER_GROUP=archon-intelligence
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_MAX_IN_FLIGHT=100

# Topics (auto-configured, override if needed)
KAFKA_CODEGEN_VALIDATE_REQUEST=omninode.codegen.request.validate.v1
KAFKA_CODEGEN_VALIDATE_RESPONSE=omninode.codegen.response.validate.v1
```

### Docker Compose

```yaml
services:
  your-service:
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
    networks:
      - omninode_bridge_omninode-bridge-network  # Connect to Redpanda

networks:
  omninode_bridge_omninode-bridge-network:
    external: true
```

---

## Testing

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_event_handler():
    handler = QualityEventHandler()

    event_data = {
        "event_type": "omninode.intelligence.event.quality_assessed.v1",
        "payload": {"quality_score": 0.92}
    }

    result = await handler.handle_event(event_data)
    assert result is True
```

### Integration Testing

```python
@pytest.mark.kafka
@pytest.mark.integration
async def test_event_flow(kafka_producer, kafka_consumer):
    # Publish event
    await kafka_producer.send(
        "omninode.codegen.request.validate.v1",
        value={"correlation_id": "test-123", "payload": {...}}
    )

    # Consume response
    response = await kafka_consumer.consume_with_correlation(
        "omninode.codegen.response.validate.v1",
        correlation_id="test-123",
        timeout=10.0
    )

    assert response["quality_score"] > 0.8
```

---

## Troubleshooting

### Consumer Lag

**Symptom**: Events not processing in time

**Check**:
```bash
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence
```

**Fix**:
- Scale consumers horizontally
- Increase `max_in_flight` (backpressure control)
- Check for slow event handlers

---

### DLQ Events

**Symptom**: Events in dead letter queue

**Check**:
```bash
docker exec omninode-bridge-redpanda rpk topic consume omninode.*.dlq --num 10
```

**Fix**:
1. Analyze error patterns
2. Fix schema or consumer code
3. Reprocess from DLQ:
   ```bash
   python scripts/reprocess_dlq.py --dlq-topic omninode.codegen.request.validate.v1.dlq
   ```

---

### Schema Validation Errors

**Symptom**: Events rejected by schema validation

**Check**:
```bash
# View schema
curl http://localhost:8084/subjects/omninode.codegen.request.validate.v1-value/versions/latest
```

**Fix**:
1. Check event payload against schema
2. Update schema if compatible change
3. Bump version if breaking change

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Event Publishing Latency (p95) | <50ms | TBD |
| Event Processing Latency (p95) | <500ms | TBD |
| Event Throughput | >10,000/sec | TBD |
| Consumer Lag (p99) | <5 seconds | TBD |
| Dead Letter Rate | <0.1% | TBD |

---

## CLI Tools

### Publish Test Event

```bash
./scripts/publish_event.sh \
  --topic omninode.codegen.request.validate.v1 \
  --payload '{"code":"class Test: pass"}' \
  --correlation-id $(uuidgen)
```

### Consume Events

```bash
./scripts/consume_events.sh \
  --topic omninode.intelligence.event.quality_assessed.v1 \
  --group test-consumer
```

### View Consumer Groups

```bash
docker exec omninode-bridge-redpanda rpk group list
```

### View Topics

```bash
docker exec omninode-bridge-redpanda rpk topic list
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- Schema Registry setup
- Event publishing infrastructure
- DLQ implementation
- SPI protocol updates

### Phase 2: Producers (Weeks 3-4)
- Intelligence event publishers
- Search event publishers
- Bridge event publishers
- ONEX + Audit event sourcing

### Phase 3: Consumers (Weeks 5-6)
- Request/response handlers
- Pub/sub subscriptions
- Event-driven workflows

### Phase 4: Migration (Weeks 7-8)
- Replace sync HTTP calls with events
- Performance benchmarks
- Backward compatibility

### Phase 5: Advanced Patterns (Weeks 9-10)
- Saga pattern (distributed transactions)
- CQRS (read/write separation)
- Event replay capability
- Complete observability

---

## Next Steps

**Developers**:
1. Read full architecture doc: [EVENT_BUS_ARCHITECTURE.md](./EVENT_BUS_ARCHITECTURE.md)
2. Review event catalog for your domain
3. Plan event integration for your service

**Phase 1 Contributors**:
1. Schema Registry setup (Week 1, Days 1-2)
2. EventPublisher base class (Week 1, Days 3-4)
3. DLQ infrastructure (Week 1, Day 5)
4. SPI protocol updates (Week 2, Days 1-2)

---

## References

- [Full Architecture Documentation](./EVENT_BUS_ARCHITECTURE.md)
- [Kafka Test Setup](../testing/KAFKA_TEST_SETUP.md)
- [Intelligence Kafka Consumer](../../services/intelligence/src/kafka_consumer.py)
- [Redpanda Documentation](https://docs.redpanda.com/)

---

**Last Updated**: 2025-10-18
**Maintained By**: ONEX Architecture Team
