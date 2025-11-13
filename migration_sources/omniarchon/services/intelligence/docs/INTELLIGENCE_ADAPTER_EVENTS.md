# Intelligence Adapter Event Contracts

**Version**: 1.0.0
**Status**: Production Ready
**Created**: 2025-10-21
**ONEX Compliance**: ✅ Fully Compliant

## Overview

Event contracts (Kafka event schemas) for the Intelligence Adapter Effect Node. Provides strongly-typed event models for code analysis operations with comprehensive validation, serialization, and topic routing.

### Event Types

| Event Type | Direction | Purpose |
|------------|-----------|---------|
| **CODE_ANALYSIS_REQUESTED** | Producer | Request code analysis operation |
| **CODE_ANALYSIS_COMPLETED** | Consumer | Analysis completed successfully |
| **CODE_ANALYSIS_FAILED** | Consumer | Analysis failed with error details |

### Key Features

- ✅ **Strong Typing**: Pydantic v2 models with comprehensive validation
- ✅ **Event Envelope Integration**: Uses `ModelEventEnvelope` from omniarchon
- ✅ **Kafka Topic Routing**: Automatic topic generation following ONEX patterns
- ✅ **Serialization Helpers**: JSON serialization/deserialization with UUID support
- ✅ **Correlation Tracking**: Full request-response correlation with UUID tracking
- ✅ **Error Handling**: Comprehensive error codes and retry logic
- ✅ **ONEX Compliance**: Follows ONEX naming conventions and architectural patterns

---

## Architecture

### Event Flow Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                     Intelligence Adapter                         │
│                      Effect Node (Producer)                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ 1. Publish CODE_ANALYSIS_REQUESTED
                      ↓
         ┌────────────────────────────────────┐
         │   Kafka Topic (dev.archon-...)     │
         └────────────────┬───────────────────┘
                          │
                          │ 2. Consume Request
                          ↓
         ┌────────────────────────────────────┐
         │   Analysis Worker (Consumer)       │
         │   - Quality Assessment             │
         │   - ONEX Compliance Check          │
         │   - Pattern Extraction             │
         └────────────────┬───────────────────┘
                          │
                          │ 3. Publish Result
                          ↓
         ┌────────────────────────────────────┐
         │   CODE_ANALYSIS_COMPLETED          │
         │        or                          │
         │   CODE_ANALYSIS_FAILED             │
         └────────────────┬───────────────────┘
                          │
                          │ 4. Consume Result
                          ↓
         ┌────────────────────────────────────┐
         │   Intelligence Adapter (Consumer)  │
         │   - Store Results                  │
         │   - Update Metrics                 │
         │   - Trigger Notifications          │
         └────────────────────────────────────┘
```

### Kafka Topics

**Topic Naming Convention**: `{env}.{service}.{domain}.{event_type}.{version}`

| Event Type | Topic Pattern | Example |
|------------|---------------|---------|
| CODE_ANALYSIS_REQUESTED | `{env}.archon-intelligence.intelligence.code-analysis-requested.v1` | `dev.archon-intelligence.intelligence.code-analysis-requested.v1` |
| CODE_ANALYSIS_COMPLETED | `{env}.archon-intelligence.intelligence.code-analysis-completed.v1` | `dev.archon-intelligence.intelligence.code-analysis-completed.v1` |
| CODE_ANALYSIS_FAILED | `{env}.archon-intelligence.intelligence.code-analysis-failed.v1` | `dev.archon-intelligence.intelligence.code-analysis-failed.v1` |

**Environment Prefixes**:
- `dev` - Development
- `staging` - Staging
- `production` - Production

---

## Event Schemas

### 1. CODE_ANALYSIS_REQUESTED

**Event Type**: `omninode.intelligence.event.code_analysis_requested.v1`
**Payload Model**: `ModelCodeAnalysisRequestPayload`

#### Payload Fields

```python
{
    "source_path": str,              # Required: File path or identifier
    "content": Optional[str],        # Optional: Code content (if not reading from file)
    "language": Optional[str],       # Optional: Programming language
    "operation_type": EnumAnalysisOperationType,  # Analysis type
    "options": Dict[str, Any],       # Analysis options
    "project_id": Optional[str],     # Project context
    "user_id": Optional[str]         # User authorization
}
```

#### Analysis Operation Types

```python
class EnumAnalysisOperationType(str, Enum):
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"
    ONEX_COMPLIANCE = "ONEX_COMPLIANCE"
    PATTERN_EXTRACTION = "PATTERN_EXTRACTION"
    ARCHITECTURAL_COMPLIANCE = "ARCHITECTURAL_COMPLIANCE"
    COMPREHENSIVE_ANALYSIS = "COMPREHENSIVE_ANALYSIS"  # Default
```

#### Example

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "omninode.intelligence.event.code_analysis_requested.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-21T10:00:00.000Z",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "intelligence-adapter-001",
    "hostname": null
  },
  "payload": {
    "source_path": "src/services/intelligence/quality_service.py",
    "content": null,
    "language": "python",
    "operation_type": "COMPREHENSIVE_ANALYSIS",
    "options": {
      "include_metrics": true,
      "depth": "comprehensive",
      "quality_threshold": 0.8,
      "enable_caching": true
    },
    "project_id": "omniarchon",
    "user_id": "system"
  }
}
```

---

### 2. CODE_ANALYSIS_COMPLETED

**Event Type**: `omninode.intelligence.event.code_analysis_completed.v1`
**Payload Model**: `ModelCodeAnalysisCompletedPayload`

#### Payload Fields

```python
{
    "source_path": str,              # File path analyzed
    "quality_score": float,          # Quality score (0.0-1.0)
    "onex_compliance": float,        # ONEX compliance (0.0-1.0)
    "issues_count": int,             # Number of issues found
    "recommendations_count": int,    # Number of recommendations
    "processing_time_ms": float,     # Processing time in milliseconds
    "operation_type": EnumAnalysisOperationType,
    "complexity_score": Optional[float],      # Complexity (0.0-1.0)
    "maintainability_score": Optional[float], # Maintainability (0.0-1.0)
    "results_summary": Dict[str, Any],        # Detailed results
    "cache_hit": bool                         # Cache hit indicator
}
```

#### Example

```json
{
  "event_id": "770e8400-e29b-41d4-a716-446655440000",
  "event_type": "omninode.intelligence.event.code_analysis_completed.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "causation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-21T10:00:01.234Z",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "intelligence-adapter-001"
  },
  "payload": {
    "source_path": "src/services/intelligence/quality_service.py",
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
      "cognitive_complexity": 18,
      "pattern_matches": ["onex_effect_pattern", "async_transaction"],
      "anti_patterns": ["god_class"],
      "security_issues": []
    },
    "cache_hit": false
  }
}
```

---

### 3. CODE_ANALYSIS_FAILED

**Event Type**: `omninode.intelligence.event.code_analysis_failed.v1`
**Payload Model**: `ModelCodeAnalysisFailedPayload`

#### Payload Fields

```python
{
    "operation_type": EnumAnalysisOperationType,
    "source_path": str,              # File path that failed
    "error_message": str,            # Human-readable error
    "error_code": EnumAnalysisErrorCode,  # Machine-readable code
    "retry_allowed": bool,           # Retry eligibility
    "retry_count": int,              # Number of retries attempted
    "processing_time_ms": float,     # Time before failure
    "error_details": Dict[str, Any], # Stack trace, context
    "suggested_action": Optional[str] # Remediation suggestion
}
```

#### Error Codes

```python
class EnumAnalysisErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    PARSING_ERROR = "PARSING_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
```

#### Example

```json
{
  "event_id": "880e8400-e29b-41d4-a716-446655440000",
  "event_type": "omninode.intelligence.event.code_analysis_failed.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "causation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-21T10:00:00.456Z",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "intelligence-adapter-001"
  },
  "payload": {
    "operation_type": "QUALITY_ASSESSMENT",
    "source_path": "src/broken/invalid_syntax.py",
    "error_message": "Failed to parse Python code: unexpected EOF at line 42",
    "error_code": "PARSING_ERROR",
    "retry_allowed": false,
    "retry_count": 0,
    "processing_time_ms": 456.7,
    "error_details": {
      "exception_type": "SyntaxError",
      "line_number": 42,
      "column": 15,
      "stack_trace": "Traceback (most recent call last)..."
    },
    "suggested_action": "Verify source code syntax is valid"
  }
}
```

---

## Usage Examples

### Publishing CODE_ANALYSIS_REQUESTED

```python
from services.intelligence.src.events.models import (
    create_request_event,
    EnumAnalysisOperationType,
)

# Create and publish request event
event = create_request_event(
    source_path="src/api/endpoints.py",
    language="python",
    operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    options={
        "include_metrics": True,
        "depth": "comprehensive",
        "quality_threshold": 0.8,
    },
)

# Publish to Kafka
topic = "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
kafka_producer.send(topic, value=event)
```

### Publishing CODE_ANALYSIS_COMPLETED

```python
from services.intelligence.src.events.models import (
    create_completed_event,
    EnumAnalysisOperationType,
)
from uuid import UUID

# Create and publish completion event
event = create_completed_event(
    source_path="src/api/endpoints.py",
    quality_score=0.92,
    onex_compliance=0.88,
    issues_count=1,
    recommendations_count=3,
    processing_time_ms=567.8,
    operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    correlation_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
    results_summary={
        "total_lines": 150,
        "pattern_matches": ["onex_effect_pattern"],
    },
    cache_hit=False,
)

# Publish to Kafka
topic = "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
kafka_producer.send(topic, value=event)
```

### Publishing CODE_ANALYSIS_FAILED

```python
from services.intelligence.src.events.models import (
    create_failed_event,
    EnumAnalysisOperationType,
    EnumAnalysisErrorCode,
)
from uuid import UUID

# Create and publish failure event
event = create_failed_event(
    operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
    source_path="src/broken/file.py",
    error_message="File not found: src/broken/file.py",
    error_code=EnumAnalysisErrorCode.INVALID_INPUT,
    correlation_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
    retry_allowed=False,
    processing_time_ms=12.3,
    error_details={
        "exception_type": "FileNotFoundError",
        "errno": 2,
    },
    suggested_action="Verify file path exists and is accessible",
)

# Publish to Kafka
topic = "dev.archon-intelligence.intelligence.code-analysis-failed.v1"
kafka_producer.send(topic, value=event)
```

### Consuming Events

```python
from services.intelligence.src.events.models import (
    IntelligenceAdapterEventHelpers,
    EnumCodeAnalysisEventType,
    ModelCodeAnalysisCompletedPayload,
)

# Consume from Kafka
for message in kafka_consumer:
    event_envelope = message.value

    # Deserialize with type safety
    event_type, typed_payload = IntelligenceAdapterEventHelpers.deserialize_event(
        event_envelope
    )

    # Type-safe handling
    if event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value:
        # typed_payload is ModelCodeAnalysisCompletedPayload
        print(f"Quality: {typed_payload.quality_score:.2f}")
        print(f"ONEX: {typed_payload.onex_compliance:.2f}")
        store_results(typed_payload)
```

---

## Integration with Intelligence Adapter Effect Node

### Effect Node Implementation

```python
from typing import Any
from uuid import uuid4
from services.intelligence.src.events.models import (
    create_request_event,
    create_completed_event,
    create_failed_event,
    EnumAnalysisOperationType,
    EnumAnalysisErrorCode,
)

class NodeIntelligenceAdapterEffect:
    """Intelligence Adapter Effect Node with Kafka event publishing."""

    async def execute_effect(
        self,
        contract: ModelContractEffect,
    ) -> ModelResult:
        """Execute code analysis with event publishing."""

        # Generate correlation ID
        correlation_id = uuid4()

        # Publish request event
        request_event = create_request_event(
            source_path=contract.source_path,
            language=contract.language,
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            options=contract.options,
            correlation_id=correlation_id,
        )
        await self.kafka_producer.publish(request_event)

        try:
            # Execute analysis
            result = await self._analyze_code(contract)

            # Publish completion event
            completed_event = create_completed_event(
                source_path=contract.source_path,
                quality_score=result.quality_score,
                onex_compliance=result.onex_compliance,
                issues_count=len(result.issues),
                recommendations_count=len(result.recommendations),
                processing_time_ms=result.processing_time_ms,
                operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
                correlation_id=correlation_id,
                results_summary=result.to_dict(),
                cache_hit=result.from_cache,
            )
            await self.kafka_producer.publish(completed_event)

            return ModelResult(success=True, data=result)

        except Exception as e:
            # Publish failure event
            failed_event = create_failed_event(
                operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
                source_path=contract.source_path,
                error_message=str(e),
                error_code=self._classify_error(e),
                correlation_id=correlation_id,
                retry_allowed=self._is_retryable(e),
                processing_time_ms=0.0,
                error_details={
                    "exception_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
            )
            await self.kafka_producer.publish(failed_event)

            raise
```

---

## Kafka Configuration

### Producer Configuration

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8') if k else None,
    acks='all',  # Wait for all replicas
    retries=3,
    max_in_flight_requests_per_connection=1,
    compression_type='gzip',
)
```

### Consumer Configuration

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'dev.archon-intelligence.intelligence.code-analysis-*.v1',
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='intelligence-adapter-consumers',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
)
```

---

## Error Handling and Retry Logic

### Retry Strategy

```python
def should_retry(error_code: EnumAnalysisErrorCode, retry_count: int) -> bool:
    """Determine if analysis should be retried."""

    # Non-retryable errors
    non_retryable = {
        EnumAnalysisErrorCode.INVALID_INPUT,
        EnumAnalysisErrorCode.UNSUPPORTED_LANGUAGE,
        EnumAnalysisErrorCode.PARSING_ERROR,
    }

    if error_code in non_retryable:
        return False

    # Retry up to 3 times for retryable errors
    return retry_count < 3

def calculate_backoff(retry_count: int) -> float:
    """Calculate exponential backoff delay."""
    return min(2 ** retry_count, 60)  # Max 60 seconds
```

### Example: Retry Handler

```python
async def handle_failed_event(payload: ModelCodeAnalysisFailedPayload):
    """Handle failed analysis event with retry logic."""

    if not payload.retry_allowed:
        logger.error(f"Non-retryable error: {payload.error_code}")
        return

    if payload.retry_count >= 3:
        logger.error(f"Max retries exceeded for {payload.source_path}")
        send_alert(payload)
        return

    # Calculate backoff
    backoff_seconds = calculate_backoff(payload.retry_count)

    logger.info(f"Scheduling retry {payload.retry_count + 1}/3 in {backoff_seconds}s")

    # Schedule retry
    await asyncio.sleep(backoff_seconds)

    # Republish request with incremented retry count
    retry_event = create_request_event(
        source_path=payload.source_path,
        operation_type=payload.operation_type,
        # ... other params
    )
    await kafka_producer.publish(retry_event)
```

---

## Monitoring and Observability

### Metrics to Track

- **Event Publish Rate**: Events published per second
- **Event Processing Time**: Time from request to completion
- **Error Rate**: Failed events / total events
- **Retry Rate**: Retried events / failed events
- **Cache Hit Rate**: Cached results / total requests
- **Queue Depth**: Pending events in Kafka topics

### Example: Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

# Metrics
events_published = Counter(
    'intelligence_adapter_events_published_total',
    'Total events published',
    ['event_type', 'environment']
)

processing_time = Histogram(
    'intelligence_adapter_processing_seconds',
    'Analysis processing time',
    ['operation_type']
)

error_rate = Counter(
    'intelligence_adapter_errors_total',
    'Total analysis errors',
    ['error_code', 'retry_allowed']
)

# Usage
events_published.labels(
    event_type='CODE_ANALYSIS_REQUESTED',
    environment='production'
).inc()

processing_time.labels(
    operation_type='COMPREHENSIVE_ANALYSIS'
).observe(1.234)

error_rate.labels(
    error_code='PARSING_ERROR',
    retry_allowed='false'
).inc()
```

---

## Testing

### Unit Tests

```python
import pytest
from services.intelligence.src.events.models import (
    ModelCodeAnalysisRequestPayload,
    EnumAnalysisOperationType,
)

def test_request_payload_validation():
    """Test request payload validation."""

    # Valid payload
    payload = ModelCodeAnalysisRequestPayload(
        source_path="src/test.py",
        language="python",
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
    )
    assert payload.source_path == "src/test.py"

    # Invalid: empty source_path
    with pytest.raises(ValueError):
        ModelCodeAnalysisRequestPayload(
            source_path="",
            language="python",
        )
```

### Integration Tests

```python
async def test_event_publishing_flow():
    """Test complete event publishing flow."""

    # Publish request
    request_event = create_request_event(
        source_path="src/test.py",
        language="python",
    )

    correlation_id = UUID(request_event["correlation_id"])

    # Simulate processing
    completed_event = create_completed_event(
        source_path="src/test.py",
        quality_score=0.9,
        onex_compliance=0.85,
        issues_count=0,
        recommendations_count=2,
        processing_time_ms=100.0,
        operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        correlation_id=correlation_id,
    )

    # Verify correlation
    assert completed_event["correlation_id"] == str(correlation_id)

    # Verify payload
    payload_data = completed_event["payload"]
    assert payload_data["quality_score"] == 0.9
    assert payload_data["onex_compliance"] == 0.85
```

---

## ONEX Compliance Checklist

- ✅ **Model Naming**: `Model{Type}Payload` pattern
- ✅ **Enum Naming**: `Enum{Type}` pattern
- ✅ **Strong Typing**: Pydantic v2 with comprehensive validation
- ✅ **Event Envelope**: Integration with `ModelEventEnvelope`
- ✅ **Topic Routing**: Follows `{env}.{service}.{domain}.{event}.{version}` pattern
- ✅ **Correlation Tracking**: UUID-based correlation and causation IDs
- ✅ **Error Handling**: Comprehensive error codes and retry logic
- ✅ **Documentation**: Complete API docs with examples
- ✅ **Testing**: Unit and integration test coverage
- ✅ **Serialization**: JSON serialization with UUID support
- ✅ **Immutability**: Frozen models where appropriate
- ✅ **Validation**: Field validators and constraints

---

## Future Enhancements

### Phase 2 Improvements

1. **Schema Registry Integration**: Avro schema evolution support
2. **Dead Letter Queue**: Failed event handling with DLQ
3. **Event Replay**: Replay capability for debugging and recovery
4. **Enhanced Metrics**: Detailed performance and quality metrics
5. **Circuit Breaker**: Automatic circuit breaking for failing services
6. **Rate Limiting**: Per-user and per-project rate limits
7. **Audit Trail**: Comprehensive audit logging for compliance
8. **Multi-tenancy**: Tenant isolation and resource quotas

---

## References

- [omninode_bridge Event Patterns](../../../../../omninode_bridge/src/omninode_bridge/services/metadata_stamping/events/models.py)
- [ModelEventEnvelope](../../../../../python/src/events/models/model_event_envelope.py)
- [EVENT_BUS_ARCHITECTURE.md](../../../../../docs/EVENT_BUS_ARCHITECTURE.md)
- [ONEX Architecture Guide](../../../../../docs/onex/ONEX_GUIDE.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-21
**Maintainer**: Archon Intelligence Team
