# Kafka Client Strategy - OmniNode Ecosystem

## Ecosystem Alignment

**omniclaude** and **omniarchon** both use `confluent-kafka ^2.6.0` for Kafka operations.

### Why confluent-kafka?

1. **Ecosystem Consistency**: omniclaude uses it as a fallback when aiokafka has listener issues
2. **Production-Grade**: Based on librdkafka (C library), battle-tested and high-performance
3. **Simple API**: Easy to use for testing and scripting
4. **No Docker Exec**: Direct publishing from Python without container access

### omniclaude Usage

**Primary**: `aiokafka` (async Python-native)
**Fallback**: `confluent-kafka` (C-based librdkafka wrapper)

From `omniclaude/agents/lib/kafka_confluent_client.py`:
```python
class ConfluentKafkaClient:
    """Useful when aiokafka struggles with host/advertised listeners."""

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        p = Producer({"bootstrap.servers": self.bootstrap_servers})
        data = json.dumps(payload).encode("utf-8")
        p.produce(topic, data)
        p.flush(10)
```

### omniarchon Usage

**Dev/Testing**: `confluent-kafka` for event publishing scripts
**Production**: Backend uses existing Kafka infrastructure

From `scripts/publish_test_event.py`:
```python
class EventPublisher:
    """Publish events to Kafka/Redpanda without docker exec."""

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "archon-test-publisher",
            "acks": "all",
            "compression.type": "snappy",
        }
        self.producer = Producer(self.config)
```

## Version Compatibility

| Package | omniclaude | omniarchon | Status |
|---------|-----------|-----------|---------|
| confluent-kafka | ^2.6.0 | ^2.6.0 | ✅ Aligned |
| aiokafka | ^0.10.0 | N/A | Different approach |

## When to Use What

### confluent-kafka (Both Repos)
- ✅ Testing and development scripts
- ✅ Simple sync publishing
- ✅ Fallback when async has issues
- ✅ CLI tools and utilities

### aiokafka (omniclaude Only)
- ✅ Async workflows
- ✅ Production event consumers
- ✅ Native Python integration

### Backend Kafka (omniarchon Only)
- ✅ Production intelligence handlers
- ✅ KafkaConsumerService
- ✅ Event routing infrastructure

## Alternative: kcat

**Native tool**: `brew install kcat`

**When to use**:
- Kafka infrastructure debugging
- Raw message inspection
- Metadata queries
- Consumer group management

**When NOT to use**:
- Application testing (use Python scripts)
- CI/CD pipelines (prefer Python for consistency)
- Structured event creation (use Python for validation)

## Installation

### omniclaude
```bash
cd omniclaude
poetry install --with kafka  # Installs confluent-kafka
```

### omniarchon
```bash
cd omniarchon/python
uv pip install --group dev  # Installs confluent-kafka
```

## Testing Event Flow

### Publish from omniclaude
```bash
cd omniclaude
python agents/parallel_execution/codegen_smoke.py --confluent --prd-file test.md
```

### Publish from omniarchon
```bash
cd omniarchon
python scripts/publish_test_event.py --event-type analyze --prd "Test PRD"
```

### Consume in omniarchon
Events are consumed by `KafkaConsumerService` and routed to appropriate handlers:
- `CodegenAnalysisHandler`
- `CodegenValidationHandler`
- `CodegenPatternHandler`
- `CodegenMixinHandler`

## See Also

- `MVP_PLAN_INTELLIGENCE_SERVICES_V2.md` - Event handler architecture
- `scripts/README_EVENT_PUBLISHING.md` - Publishing documentation
- `omniclaude/agents/lib/kafka_confluent_client.py` - Reference implementation
