# Event-Driven Architecture - Intelligence Service

**Version**: 1.0.0
**Last Updated**: 2025-10-22
**Status**: Phase 4 Complete (8 operations, 24 event models)

## Overview

The Intelligence Service implements a comprehensive event-driven architecture using Kafka for asynchronous, scalable, and reliable message processing. This document covers the complete implementation across all phases.

## Architecture Components

### Core Components

1. **Event Models** (24 total)
   - Pydantic v2 models with strong typing
   - ONEX-compliant naming conventions
   - Event envelope integration
   - Validation and serialization

2. **Event Handlers** (11 total)
   - BaseResponsePublisher pattern
   - Async event processing
   - HTTP service integration
   - Metrics tracking

3. **Kafka Consumer**
   - Topic subscription and routing
   - Handler registry
   - Backpressure control (max 100 in-flight)
   - Graceful shutdown

4. **Event Router**
   - HybridEventRouter for publishing
   - Topic-based routing
   - Correlation ID tracking

## Phase 4: Bridge & Utility Events (Latest)

**Completed**: 2025-10-22
**Operations**: 8
**Event Models**: 24
**Handlers**: 3

### Bridge Intelligence Operations (3 operations)

#### 1. Generate Intelligence

**Purpose**: Generate OmniNode metadata intelligence for code/documents

**Topics**:
- Request: `dev.archon-intelligence.bridge.generate-intelligence-requested.v1`
- Completed: `dev.archon-intelligence.bridge.generate-intelligence-completed.v1`
- Failed: `dev.archon-intelligence.bridge.generate-intelligence-failed.v1`

**Event Models**:
- `ModelBridgeGenerateIntelligenceRequestPayload`
- `ModelBridgeGenerateIntelligenceCompletedPayload`
- `ModelBridgeGenerateIntelligenceFailedPayload`

**Handler**: `BridgeIntelligenceHandler`

**Service Integration**: Bridge Service (http://localhost:8054)

**Example**:
```python
from src.events.models.bridge_intelligence_events import create_generate_intelligence_request

event = create_generate_intelligence_request(
    source_path="src/api/server.py",
    content="def hello(): pass",
    language="python",
    metadata_options={"include_blake3_hash": True}
)
# Publish to Kafka topic
```

#### 2. Bridge Health Check

**Purpose**: Monitor bridge service health status

**Topics**:
- Request: `dev.archon-intelligence.bridge.bridge-health-requested.v1`
- Completed: `dev.archon-intelligence.bridge.bridge-health-completed.v1`
- Failed: `dev.archon-intelligence.bridge.bridge-health-failed.v1`

**Event Models**:
- `ModelBridgeHealthRequestPayload`
- `ModelBridgeHealthCompletedPayload`
- `ModelBridgeHealthFailedPayload`

#### 3. Capabilities Query

**Purpose**: Retrieve bridge service capabilities

**Topics**:
- Request: `dev.archon-intelligence.bridge.capabilities-requested.v1`
- Completed: `dev.archon-intelligence.bridge.capabilities-completed.v1`
- Failed: `dev.archon-intelligence.bridge.capabilities-failed.v1`

**Event Models**:
- `ModelBridgeCapabilitiesRequestPayload`
- `ModelBridgeCapabilitiesCompletedPayload`
- `ModelBridgeCapabilitiesFailedPayload`

### Document Processing Operations (2 operations)

#### 4. Process Document

**Purpose**: Process single document with entity extraction and embeddings

**Topics**:
- Request: `dev.archon-intelligence.document.process-document-requested.v1`
- Completed: `dev.archon-intelligence.document.process-document-completed.v1`
- Failed: `dev.archon-intelligence.document.process-document-failed.v1`

**Event Models**:
- `ModelDocumentProcessRequestPayload`
- `ModelDocumentProcessCompletedPayload`
- `ModelDocumentProcessFailedPayload`

**Handler**: `DocumentProcessingHandler`

**Service Integration**: Intelligence Service (http://localhost:8053)

**Example**:
```python
from src.events.models.document_processing_events import create_process_document_request

event = create_process_document_request(
    document_path="docs/README.md",
    content="# Project README",
    document_type="markdown",
    extract_entities=True,
    generate_embeddings=True
)
```

#### 5. Batch Index

**Purpose**: Batch index multiple documents with parallel processing

**Topics**:
- Request: `dev.archon-intelligence.document.batch-index-requested.v1`
- Completed: `dev.archon-intelligence.document.batch-index-completed.v1`
- Failed: `dev.archon-intelligence.document.batch-index-failed.v1`

**Event Models**:
- `ModelBatchIndexRequestPayload`
- `ModelBatchIndexCompletedPayload`
- `ModelBatchIndexFailedPayload`

**Features**:
- Parallel workers (1-32 configurable)
- Skip existing documents
- Batch size limit: 1000 documents
- Graceful degradation

### System Utilities Operations (3 operations)

#### 6. System Metrics

**Purpose**: Collect comprehensive system metrics

**Topics**:
- Request: `dev.archon-intelligence.system.metrics-requested.v1`
- Completed: `dev.archon-intelligence.system.metrics-completed.v1`
- Failed: `dev.archon-intelligence.system.metrics-failed.v1`

**Event Models**:
- `ModelSystemMetricsRequestPayload`
- `ModelSystemMetricsCompletedPayload`
- `ModelSystemMetricsFailedPayload`

**Handler**: `SystemUtilitiesHandler`

**Metrics Collected**:
- System: CPU, memory, disk, network
- Services: Per-service requests/latency
- Kafka: Messages/sec, lag, success rate
- Cache: Hit rate, memory, evictions

#### 7. Kafka Health

**Purpose**: Check Kafka connectivity and health

**Topics**:
- Request: `dev.archon-intelligence.system.kafka-health-requested.v1`
- Completed: `dev.archon-intelligence.system.kafka-health-completed.v1`
- Failed: `dev.archon-intelligence.system.kafka-health-failed.v1`

**Event Models**:
- `ModelKafkaHealthRequestPayload`
- `ModelKafkaHealthCompletedPayload`
- `ModelKafkaHealthFailedPayload`

**Health Checks**:
- Producer connectivity
- Consumer connectivity
- Topic availability
- Broker count

#### 8. Kafka Metrics

**Purpose**: Collect detailed Kafka performance metrics

**Topics**:
- Request: `dev.archon-intelligence.system.kafka-metrics-requested.v1`
- Completed: `dev.archon-intelligence.system.kafka-metrics-completed.v1`
- Failed: `dev.archon-intelligence.system.kafka-metrics-failed.v1`

**Event Models**:
- `ModelKafkaMetricsRequestPayload`
- `ModelKafkaMetricsCompletedPayload`
- `ModelKafkaMetricsFailedPayload`

**Metrics Collected**:
- Producer: Messages sent, bytes, success rate, latency
- Consumer: Messages consumed, lag, processing time
- Topics: Message count, partitions, replication
- Cluster: Brokers, topics, partitions, replication status

## Event Model Patterns

### Naming Conventions

**ONEX-Compliant Naming**:
- Event Models: `Model{Domain}{Operation}{Type}Payload`
- Enums: `Enum{Domain}{Category}`
- Event Files: `{domain}_{category}_events.py`
- Handler Files: `{domain}_{category}_handler.py`

**Examples**:
- `ModelBridgeGenerateIntelligenceRequestPayload`
- `EnumBridgeErrorCode`
- `bridge_intelligence_events.py`
- `bridge_intelligence_handler.py`

### Event Envelope Structure

All events use standardized envelope:

```python
{
    "event_id": "uuid",
    "event_type": "omninode.{domain}.{pattern}.{event_name}.{version}",
    "correlation_id": "uuid",
    "causation_id": "uuid or null",
    "timestamp": "ISO 8601 timestamp",
    "version": "1.0.0",
    "source": {
        "service": "archon-intelligence",
        "instance_id": "handler-instance-1",
        "hostname": "null or hostname"
    },
    "metadata": {},
    "payload": {
        # Event-specific data
    }
}
```

### Request/Completed/Failed Pattern

Each operation has 3 event types:

1. **Request**: Initiates operation
   - Required fields for operation
   - Optional configuration
   - Project/user context

2. **Completed**: Success response
   - Operation results
   - Processing metrics
   - Cache status

3. **Failed**: Error response
   - Error code (enum)
   - Error message (human-readable)
   - Retry allowed flag
   - Error details (for debugging)

## Handler Implementation Pattern

### Base Handler Structure

```python
class MyOperationHandler(BaseResponsePublisher):
    """Handle MY_OPERATION events."""

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.domain.operation-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.domain.operation-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.domain.operation-failed.v1"

    def __init__(self):
        super().__init__()
        self.http_client = None
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
        }

    def can_handle(self, event_type: str) -> bool:
        """Check if handler can process event type."""
        return event_type in [
            "OPERATION_REQUESTED",
            "domain.operation-requested",
        ]

    async def handle_event(self, event: Any) -> bool:
        """Process event and publish response."""
        start_time = time.perf_counter()
        correlation_id = self._get_correlation_id(event)
        payload = self._get_payload(event)

        try:
            # Perform operation
            result = await self._execute_operation(payload)

            # Publish success
            await self._publish_completed(correlation_id, result)

            self.metrics["events_handled"] += 1
            return True

        except Exception as e:
            # Publish failure
            await self._publish_failed(correlation_id, error)

            self.metrics["events_failed"] += 1
            return False

    async def shutdown(self):
        """Cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()
        await self._shutdown_publisher()
```

### Metrics Tracking

All handlers track:
- `events_handled`: Total successful events
- `events_failed`: Total failed events
- `total_processing_time_ms`: Cumulative processing time
- Operation-specific counters
- Success rate (calculated)
- Average processing time (calculated)

## Kafka Consumer Configuration

### Topic Subscriptions

**Phase 4 Topics** (8 new topics):

```python
# Bridge Intelligence
"dev.archon-intelligence.bridge.generate-intelligence-requested.v1"
"dev.archon-intelligence.bridge.bridge-health-requested.v1"
"dev.archon-intelligence.bridge.capabilities-requested.v1"

# Document Processing
"dev.archon-intelligence.document.process-document-requested.v1"
"dev.archon-intelligence.document.batch-index-requested.v1"

# System Utilities
"dev.archon-intelligence.system.metrics-requested.v1"
"dev.archon-intelligence.system.kafka-health-requested.v1"
"dev.archon-intelligence.system.kafka-metrics-requested.v1"
```

### Environment Variables

```bash
# Kafka Connection
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_CONSUMER_GROUP=archon-intelligence
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_ENABLE_AUTO_COMMIT=true

# Performance Tuning
KAFKA_MAX_POLL_RECORDS=500
KAFKA_SESSION_TIMEOUT_MS=30000
KAFKA_MAX_IN_FLIGHT=100  # Backpressure control

# Phase 4 Topics (optional overrides)
KAFKA_BRIDGE_GENERATE_INTELLIGENCE_REQUEST=...
KAFKA_BRIDGE_HEALTH_REQUEST=...
KAFKA_BRIDGE_CAPABILITIES_REQUEST=...
KAFKA_PROCESS_DOCUMENT_REQUEST=...
KAFKA_BATCH_INDEX_REQUEST=...
KAFKA_METRICS_REQUEST=...
KAFKA_KAFKA_HEALTH_REQUEST=...
KAFKA_KAFKA_METRICS_REQUEST=...
```

## Testing

### Unit Tests

**Location**: `services/intelligence/tests/test_phase4_handlers_integration.py`

**Coverage**:
- Handler initialization
- Event type matching (`can_handle`)
- Correlation ID extraction
- Payload extraction
- Metrics tracking
- Error handling
- Resource cleanup

**Run Tests**:
```bash
cd services/intelligence
pytest tests/test_phase4_handlers_integration.py -v
```

### Integration Tests

**Requirements**:
- Running Kafka broker
- Mock HTTP services (Bridge, Intelligence)
- Event router setup

**Marked Tests**:
```python
@pytest.mark.integration
@pytest.mark.skip(reason="Requires full infrastructure")
```

## Deployment

### Service Startup

The Kafka consumer initializes and registers all handlers automatically:

```python
from src.kafka_consumer import create_intelligence_kafka_consumer

# Create consumer
consumer = create_intelligence_kafka_consumer()

# Initialize handlers and connect to Kafka
await consumer.initialize()

# Start consuming events
await consumer.start()
```

### Handler Registry

Handlers are registered in order:

1. CodegenValidationHandler
2. CodegenAnalysisHandler
3. CodegenPatternHandler
4. CodegenMixinHandler
5. IntelligenceAdapterHandler
6. DocumentIndexingHandler
7. RepositoryCrawlerHandler
8. SearchHandler
9. **BridgeIntelligenceHandler** (Phase 4)
10. **DocumentProcessingHandler** (Phase 4)
11. **SystemUtilitiesHandler** (Phase 4)

### Health Monitoring

**Consumer Health**:
```bash
# Get consumer health
curl http://localhost:8053/kafka/consumer/health

# Response
{
  "status": "healthy",
  "is_running": true,
  "handlers_count": 11,
  "total_events": 1234,
  "events_failed": 5,
  "error_rate_percent": 0.41
}
```

**Handler Metrics**:
```bash
# Get specific handler metrics
curl http://localhost:8053/kafka/handler/BridgeIntelligenceHandler/metrics

# Response
{
  "events_handled": 150,
  "events_failed": 2,
  "generate_intelligence_successes": 100,
  "health_check_successes": 30,
  "capabilities_successes": 20,
  "success_rate": 0.987,
  "avg_processing_time_ms": 234.5
}
```

## Error Codes

### Bridge Intelligence Errors

```python
class EnumBridgeErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    BRIDGE_SERVICE_UNAVAILABLE = "BRIDGE_SERVICE_UNAVAILABLE"
    METADATA_GENERATION_FAILED = "METADATA_GENERATION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
```

### Document Processing Errors

```python
class EnumDocumentProcessingErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSING_ERROR = "PARSING_ERROR"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
```

### System Utilities Errors

```python
class EnumSystemUtilitiesErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    KAFKA_CONNECTION_ERROR = "KAFKA_CONNECTION_ERROR"
    METRICS_COLLECTION_FAILED = "METRICS_COLLECTION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
```

## Performance Characteristics

### Latency Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Generate Intelligence | <2000ms | ~500ms |
| Bridge Health Check | <500ms | ~100ms |
| Capabilities Query | <500ms | ~50ms |
| Process Document | <2000ms | ~800ms |
| Batch Index (100 docs) | <30000ms | ~15000ms |
| System Metrics | <1000ms | ~300ms |
| Kafka Health | <500ms | ~100ms |
| Kafka Metrics | <1000ms | ~250ms |

### Throughput

- **Max In-Flight**: 100 concurrent events
- **Target Events/Sec**: 50-100 per handler
- **Backpressure Trigger**: >100 in-flight events
- **Consumer Lag Alert**: >1000 messages

## Future Enhancements

### Phase 5 (Planned)

- Real-time analytics events
- ML model training events
- Cross-service workflow orchestration
- Event sourcing for audit trails
- CQRS pattern integration

### Optimization Opportunities

- Event batching for high-throughput operations
- Compression for large payloads
- Partitioning strategy optimization
- Dead letter queue for failed events
- Event replay for recovery

## References

- **Event Models**: `services/intelligence/src/events/models/`
- **Handlers**: `services/intelligence/src/handlers/`
- **Consumer**: `services/intelligence/src/kafka_consumer.py`
- **Tests**: `services/intelligence/tests/test_phase4_handlers_integration.py`
- **Base Event Envelope**: `python/src/events/models/model_event_envelope.py`
- **Hybrid Event Router**: `services/intelligence/src/events/hybrid_event_router.py`

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-22
**Maintainer**: Intelligence Service Team
**Status**: ✅ Phase 4 Complete
