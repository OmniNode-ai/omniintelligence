# Security Investigation: Secret Masking in Event Publisher

**Date**: 2025-11-05
**Priority**: 🔴 CRITICAL
**Status**: ⚠️ VULNERABILITY IDENTIFIED
**Reporter**: Claude Code (Polymorphic Agent)

---

## Executive Summary

**CRITICAL SECURITY GAP IDENTIFIED**: Event publisher (`event_publisher.py`) does NOT sanitize secrets before publishing events to Kafka, creating a potential data leak vector.

**Risk Level**: HIGH
**Affected Component**: `src/events/publisher/event_publisher.py`
**Impact**: Secrets (API keys, tokens, passwords) may leak into:
- Kafka event logs (persistent storage)
- Kafka UI (visible to developers)
- Dead Letter Queue (DLQ) events
- Downstream consumers
- Observability/telemetry platforms

---

## Investigation Findings

### 1. Existing Secret Masking Infrastructure ✅

**Good News**: Comprehensive secret sanitization infrastructure already exists!

**Location**: `src/server/services/log_sanitizer.py`

**Coverage**:
- ✅ 30+ regex patterns for secret detection
- ✅ OpenAI API keys (`sk-...`)
- ✅ GitHub tokens (`ghp_...`, `gho_...`, `github_pat_...`)
- ✅ AWS credentials (`AKIA...`, `aws_secret_access_key`)
- ✅ Database connection strings (PostgreSQL, MySQL, MongoDB, Redis)
- ✅ JWT tokens (`eyJ...`)
- ✅ Webhook URLs (Slack, Discord)
- ✅ Generic API keys/secrets
- ✅ Environment variables with sensitive names
- ✅ Passwords in URLs and configs

**Test Coverage**: 118 comprehensive tests (`tests/test_log_sanitizer.py`)

**Performance**:
- Sequential regex: ~0.1-0.5ms per line
- LRU cache: <0.01ms for repeated content
- Cache hit rate: >60% in production

**Current Usage**:
- ✅ `container_health_monitor.py` (line 43) - Sanitizes Slack alerts
- ❌ `event_publisher.py` - **NOT USED** (critical gap)

---

### 2. Critical Security Gap 🔴

**File**: `src/events/publisher/event_publisher.py`

**Vulnerable Code** (lines 395-411):

```python
def _serialize_event(self, envelope: ModelEventEnvelope) -> bytes:
    """
    Serialize event envelope to JSON bytes.

    Args:
        envelope: Event envelope to serialize

    Returns:
        JSON bytes
    """
    # Convert to dict (handles UUIDs, datetime, Pydantic models)
    event_dict = envelope.to_dict()  # ❌ RAW PAYLOAD - NO SANITIZATION

    # Serialize to JSON
    json_str = json.dumps(event_dict, default=str)  # ❌ NO SANITIZATION

    return json_str.encode("utf-8")  # ❌ SECRETS MAY BE ENCODED
```

**Also Vulnerable** (lines 413-456):

```python
async def _send_to_dlq(
    self, topic: str, envelope: ModelEventEnvelope, error_message: str
) -> None:
    """Send failed event to Dead Letter Queue."""
    dlq_payload = {
        "original_topic": topic,
        "original_envelope": envelope.to_dict(),  # ❌ NO SANITIZATION
        "error_message": error_message,
        ...
    }

    dlq_bytes = json.dumps(dlq_payload, default=str).encode("utf-8")  # ❌ NO SANITIZATION
```

---

### 3. Risk Assessment 🔴 HIGH

**Data Exposure Vectors**:

1. **Kafka Topic Persistence**
   - Events stored in Kafka logs (retention: days to weeks)
   - Accessible via Redpanda Console UI (http://192.168.86.200:8080)
   - Visible to all developers with network access

2. **Dead Letter Queue (DLQ)**
   - Failed events with full payload sent to `{topic}.dlq`
   - Often reviewed during debugging
   - May be exported for analysis

3. **Event Consumers**
   - Multiple services consume events
   - May log event content
   - May forward to external systems

4. **Observability Platforms**
   - Event tracing/telemetry may capture payloads
   - Metrics systems may sample event data

**Sensitive Data at Risk**:

Based on event envelope schema (`model_event_envelope.py`):

```python
payload: T = Field(
    ...,
    description="Event-specific business data",
)
```

Examples from code:
- **Code content**: `"code_content": "class Test: pass"` (line 258)
  - May include API keys in configuration files
  - May include credentials in connection strings

- **Configuration data**:
  - Database URLs with passwords
  - API endpoint URLs with tokens

- **Error messages**:
  - Stack traces with environment variables
  - Connection failures exposing credentials

- **Metadata**:
  - User IDs, trace IDs (less critical but PII)

**Real-World Example**:

```python
# Event published via node_intelligence_adapter_effect.py (line 789)
await self.event_publisher.publish(
    event_type="dev.archon-intelligence.intelligence.code-analysis-completed.v1",
    payload={
        "code_content": """
            import os
            OPENAI_API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"  # ⚠️ EXPOSED
            DB_URL = "postgresql://admin:SecretPass123@db:5432/app"     # ⚠️ EXPOSED
        """,
        "analysis_result": {...}
    }
)
```

This event would be published to Kafka **WITHOUT sanitization**, exposing both secrets.

---

### 4. Event Flow Analysis

**Services Using EventPublisher**:

1. **node_intelligence_adapter_effect.py** (lines 789, 862)
   - Publishes code analysis events
   - Payload includes code content and analysis results

2. **lifecycle_events.py**
   - Service lifecycle events
   - May include configuration snapshots

**Topics Published To**:
- `dev.archon-intelligence.intelligence.code-analysis-requested.v1`
- `dev.archon-intelligence.intelligence.code-analysis-completed.v1`
- `dev.archon-intelligence.intelligence.code-analysis-failed.v1`
- Various DLQ topics: `{topic}.dlq`

---

### 5. PR #21 Review Status

**PR #21 Commit** (b2325be): "fix: Resolve all 8 PR #21 review issues via parallel agents"

**What Was Addressed**:
- ✅ Secret regex edge case patterns in `pre_push_intelligence.py`
- ✅ Memgraph service naming mismatch
- ✅ Absolute developer paths in docs
- ✅ Environment variable checks in kafka_consumer_service.py

**What Was MISSED**:
- ❌ Event publisher secret sanitization
- ❌ DLQ secret sanitization
- ❌ Event payload security review

**Conclusion**: This is an **overlooked critical security issue** from PR #21 review.

---

## Recommended Solution

### Implementation Strategy

**Approach**: Integrate existing `LogSanitizer` into `EventPublisher`

**Changes Required**:

1. **Import LogSanitizer** in `event_publisher.py`:
   ```python
   from src.server.services.log_sanitizer import get_log_sanitizer
   ```

2. **Update `_serialize_event()` method** (lines 395-411):
   ```python
   def _serialize_event(self, envelope: ModelEventEnvelope) -> bytes:
       """
       Serialize event envelope to JSON bytes with secret sanitization.

       Args:
           envelope: Event envelope to serialize

       Returns:
           JSON bytes with secrets masked
       """
       # Convert to dict (handles UUIDs, datetime, Pydantic models)
       event_dict = envelope.to_dict()

       # Serialize to JSON
       json_str = json.dumps(event_dict, default=str)

       # ✅ SANITIZE SECRETS BEFORE PUBLISHING
       sanitizer = get_log_sanitizer()
       sanitized_json = sanitizer.sanitize(json_str)

       return sanitized_json.encode("utf-8")
   ```

3. **Update `_send_to_dlq()` method** (lines 413-456):
   ```python
   async def _send_to_dlq(
       self, topic: str, envelope: ModelEventEnvelope, error_message: str
   ) -> None:
       """Send failed event to Dead Letter Queue with sanitization."""
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

       # ✅ SANITIZE DLQ PAYLOADS
       sanitizer = get_log_sanitizer()
       sanitized_dlq = sanitizer.sanitize(dlq_json)

       dlq_bytes = sanitized_dlq.encode("utf-8")

       # Produce to DLQ (no retry, best effort)
       if self.producer:
           self.producer.produce(topic=dlq_topic, value=dlq_bytes)
           self.producer.flush(timeout=5.0)
   ```

4. **Add Configuration** in `__init__()` (optional):
   ```python
   def __init__(
       self,
       ...,
       enable_sanitization: bool = True,  # ✅ NEW PARAMETER
   ):
       ...
       self.enable_sanitization = enable_sanitization
   ```

5. **Environment Variable** (`.env.example`):
   ```bash
   # Event sanitization (production recommended: true)
   ENABLE_EVENT_SANITIZATION=true
   ```

---

### Alternative: Deep Sanitization

If JSON-level sanitization is insufficient (e.g., nested Pydantic models):

```python
def _sanitize_dict_recursive(self, data: Any) -> Any:
    """Recursively sanitize secrets in nested data structures."""
    sanitizer = get_log_sanitizer()

    if isinstance(data, dict):
        return {k: self._sanitize_dict_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [self._sanitize_dict_recursive(item) for item in data]
    elif isinstance(data, str):
        return sanitizer.sanitize(data)
    else:
        return data

def _serialize_event(self, envelope: ModelEventEnvelope) -> bytes:
    event_dict = envelope.to_dict()

    # ✅ DEEP SANITIZATION
    sanitized_dict = self._sanitize_dict_recursive(event_dict)

    json_str = json.dumps(sanitized_dict, default=str)
    return json_str.encode("utf-8")
```

**Trade-off**:
- ✅ More thorough (catches nested secrets)
- ❌ Slower (recursive traversal)
- ❌ More complex

**Recommendation**: Start with JSON-level sanitization (simpler, faster), monitor for edge cases.

---

## Testing Requirements

### Unit Tests

**File**: `tests/events/publisher/test_event_publisher_sanitization.py`

```python
def test_api_key_sanitization_in_event_payload():
    """Test OpenAI API key is sanitized in event payload."""
    publisher = EventPublisher(...)

    payload = {
        "code": 'OPENAI_API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
    }

    envelope = publisher._create_event_envelope(
        event_type="test.event.v1",
        payload=payload
    )

    event_bytes = publisher._serialize_event(envelope)
    event_str = event_bytes.decode("utf-8")

    # Verify secret is masked
    assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in event_str
    assert "[OPENAI_API_KEY]" in event_str

def test_database_url_sanitization_in_dlq():
    """Test database password is sanitized in DLQ events."""
    publisher = EventPublisher(...)

    envelope = publisher._create_event_envelope(
        event_type="test.event.v1",
        payload={
            "db_url": "postgresql://admin:SecretPass123@db:5432/app"
        }
    )

    # Mock DLQ publish
    with patch.object(publisher.producer, 'produce') as mock_produce:
        await publisher._send_to_dlq(
            topic="test.topic",
            envelope=envelope,
            error_message="Test error"
        )

    # Verify password is masked in DLQ payload
    dlq_bytes = mock_produce.call_args[1]['value']
    dlq_str = dlq_bytes.decode("utf-8")

    assert "SecretPass123" not in dlq_str
    assert "[PASSWORD]" in dlq_str

def test_multiple_secrets_in_nested_payload():
    """Test multiple secrets in complex nested payload."""
    publisher = EventPublisher(...)

    payload = {
        "config": {
            "api_key": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "db": {
                "url": "postgresql://admin:secret@db:5432/app",
                "pool_size": 10
            }
        },
        "metadata": {
            "webhook": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        }
    }

    envelope = publisher._create_event_envelope(
        event_type="test.event.v1",
        payload=payload
    )

    event_bytes = publisher._serialize_event(envelope)
    event_str = event_bytes.decode("utf-8")

    # Verify all secrets are masked
    assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in event_str
    assert "secret" not in event_str
    assert "T00000000" not in event_str
    assert "[OPENAI_API_KEY]" in event_str
    assert "[PASSWORD]" in event_str
    assert "[SLACK_WEBHOOK_URL]" in event_str

def test_sanitization_can_be_disabled():
    """Test sanitization respects enable_sanitization flag."""
    publisher = EventPublisher(..., enable_sanitization=False)

    payload = {"api_key": "sk-1234567890abcdefghijklmnopqrstuvwxyz"}
    envelope = publisher._create_event_envelope(
        event_type="test.event.v1",
        payload=payload
    )

    event_bytes = publisher._serialize_event(envelope)
    event_str = event_bytes.decode("utf-8")

    # When disabled, secrets should NOT be masked
    assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" in event_str
    assert "[OPENAI_API_KEY]" not in event_str
```

### Integration Tests

**File**: `tests/integration/test_event_publisher_kafka_sanitization.py`

```python
async def test_event_published_to_kafka_is_sanitized():
    """Test actual Kafka event contains sanitized secrets."""
    publisher = EventPublisher(
        bootstrap_servers="localhost:29092",
        service_name="test-service",
        instance_id="test-instance"
    )

    # Publish event with secret
    await publisher.publish(
        event_type="test.event.v1",
        payload={
            "config": 'OPENAI_API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        }
    )

    # Consume event from Kafka
    consumer = create_test_consumer(topic="test.event.v1")
    message = consumer.poll(timeout=5.0)

    # Verify secret is masked in Kafka message
    event_str = message.value().decode("utf-8")
    assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in event_str
    assert "[OPENAI_API_KEY]" in event_str
```

---

## Performance Impact

**Benchmark** (based on LogSanitizer performance):

| Operation | Before | After (JSON-level) | Overhead |
|-----------|--------|-------------------|----------|
| Event serialization | ~0.5ms | ~1.0ms | +0.5ms (~100%) |
| Event publish (total) | ~50-100ms | ~50.5-100.5ms | +0.5% |
| Cache hit | ~0.5ms | ~0.51ms | +0.01ms (negligible) |

**Mitigations**:
- ✅ LogSanitizer uses LRU cache (>60% hit rate)
- ✅ Compiled regex patterns (fast matching)
- ✅ Negligible impact relative to network I/O (50-100ms)

**Conclusion**: Performance impact is **acceptable** (<1% overhead).

---

## Deployment Checklist

- [ ] 1. Implement sanitization in `event_publisher.py`
- [ ] 2. Add unit tests (4+ test cases)
- [ ] 3. Add integration test (Kafka round-trip)
- [ ] 4. Update `.env.example` with `ENABLE_EVENT_SANITIZATION`
- [ ] 5. Document in `EVENT_BUS_ARCHITECTURE.md`
- [ ] 6. Review all existing events in Kafka (manual audit)
- [ ] 7. Deploy to staging
- [ ] 8. Monitor performance metrics
- [ ] 9. Deploy to production
- [ ] 10. Add to security audit checklist

---

## Conclusion

**Critical Security Gap**: Event publisher lacks secret sanitization, exposing API keys, passwords, and tokens in Kafka events.

**Solution**: Integrate existing `LogSanitizer` (already production-ready, 118 tests) into `EventPublisher._serialize_event()` and `_send_to_dlq()`.

**Effort**: ~2-4 hours (implementation + tests)

**Impact**: Prevents data leaks, ensures compliance, protects production secrets.

**Recommendation**: Implement IMMEDIATELY (critical security issue).

---

**Next Steps**: Proceed with implementation?
