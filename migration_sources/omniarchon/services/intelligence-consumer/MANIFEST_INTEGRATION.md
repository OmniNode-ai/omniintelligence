# Manifest Intelligence Integration - Intelligence Consumer

**Status**: ✅ Routing Infrastructure Complete | 🔄 Handler Implementation Pending
**Date**: 2025-11-03
**Correlation ID**: d387a8ce-cf92-4853-9b20-d679fb7979c8

## Overview

Integrated manifest intelligence routing into the intelligence-consumer service to enable event-driven manifest generation. The consumer now subscribes to manifest intelligence topics and routes events to a dedicated handler.

## Changes Implemented

### 1. Configuration Updates (`src/config.py`)

Added three new Kafka topic properties:

```python
@property
def manifest_requested_topic(self) -> str:
    """Get the manifest intelligence request topic name."""
    return f"{self.kafka_topic_prefix}.intelligence.manifest.requested.v1"

@property
def manifest_completed_topic(self) -> str:
    """Get the manifest intelligence completion topic name."""
    return f"{self.kafka_topic_prefix}.intelligence.manifest.completed.v1"

@property
def manifest_failed_topic(self) -> str:
    """Get the manifest intelligence failed topic name."""
    return f"{self.kafka_topic_prefix}.intelligence.manifest.failed.v1"
```

Updated `get_subscribed_topics()` to include manifest topic:

```python
def get_subscribed_topics(self) -> list[str]:
    """Get list of topics to subscribe to."""
    return [
        self.enrichment_topic,
        self.code_analysis_topic,
        self.manifest_requested_topic,  # NEW
    ]
```

### 2. Consumer Publishing Methods (`src/consumer.py`)

Added two new methods for publishing manifest intelligence results:

**Success Publishing:**
```python
async def publish_manifest_completion(
    correlation_id: str,
    success: bool,
    manifest_data: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    partial_results: Optional[Dict[str, Any]] = None,
) -> None
```

**Failure Publishing:**
```python
async def publish_manifest_failure(
    correlation_id: str,
    error: str,
    partial_results: Optional[Dict[str, Any]] = None,
) -> None
```

**Key Features:**
- Publishes to `dev.archon-intelligence.intelligence.manifest.completed.v1`
- Publishes to `dev.archon-intelligence.intelligence.manifest.failed.v1`
- Supports partial results for graceful degradation
- Comprehensive structured logging

### 3. Routing Logic (`src/main.py`)

**Event Detection:**
Added manifest event detection in `_process_message()`:

```python
# Check if this is a manifest intelligence event
if (
    "manifest.requested" in topic
    or "manifest_intelligence_requested" in event_type.lower()
    or "manifest_intelligence_requested" in event_type_from_metadata.lower()
):
    await self._process_manifest_intelligence_event(event_data)
```

**Processing Method:**
Added `_process_manifest_intelligence_event()` with:
- Correlation ID tracking
- Event validation and logging
- Handler execution (placeholder until handler is ready)
- Success/failure event publishing
- Partial results support
- Performance metrics collection
- Error handling with retry logic

**Handler Initialization:**
Added placeholder for handler initialization in `start()` method:

```python
# Initialize manifest intelligence handler (uncomment when handler is ready)
# self.manifest_intelligence_handler = ManifestIntelligenceHandler(
#     postgres_url=self.config.postgres_url,
#     kafka_bootstrap=self.config.kafka_bootstrap_servers,
#     qdrant_url=self.config.qdrant_url,
# )
```

### 4. Infrastructure Setup

Created handlers package structure:
```
services/intelligence-consumer/src/handlers/
├── __init__.py
```

## Event Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      Event Producer                          │
│         (OmniNode Bridge or other service)                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓ Publishes manifest request
┌──────────────────────────────────────────────────────────────┐
│                    Kafka/Redpanda                            │
│   Topic: dev.archon-intelligence.intelligence.               │
│          manifest.requested.v1                               │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓ Consumes event
┌──────────────────────────────────────────────────────────────┐
│              Intelligence Consumer Service                   │
│                                                              │
│  1. EnrichmentConsumer receives message                     │
│  2. Routes to _process_manifest_intelligence_event()        │
│  3. Validates event structure                                │
│  4. Calls ManifestIntelligenceHandler.execute()             │
│     (currently placeholder)                                  │
│  5. Publishes completion/failure event                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓ Publishes result
┌──────────────────────────────────────────────────────────────┐
│                    Kafka/Redpanda                            │
│   Topic: dev.archon-intelligence.intelligence.               │
│          manifest.completed.v1 OR                            │
│          manifest.failed.v1                                  │
└──────────────────────────────────────────────────────────────┘
                         │
                         ↓ Consumed by downstream services
┌──────────────────────────────────────────────────────────────┐
│              Event Consumers (OmniDash, etc.)                │
└──────────────────────────────────────────────────────────────┘
```

## Event Schemas

### Request Event
```json
{
  "event_type": "omninode.intelligence.event.manifest_intelligence_requested.v1",
  "correlation_id": "uuid-v4",
  "timestamp": "2025-11-03T12:00:00Z",
  "payload": {
    "options": {
      "repository_path": "/path/to/repo",
      "include_quality": true,
      "include_performance": true,
      "include_freshness": true
    }
  }
}
```

### Success Response
```json
{
  "event_type": "omninode.intelligence.event.manifest_intelligence_completed.v1",
  "correlation_id": "uuid-v4",
  "timestamp": "2025-11-03T12:05:00Z",
  "payload": {
    "success": true,
    "manifest_data": {
      "quality_metrics": {...},
      "performance_metrics": {...},
      "freshness_metrics": {...}
    },
    "partial_results": null,
    "error_message": null
  }
}
```

### Failure Response
```json
{
  "event_type": "omninode.intelligence.event.manifest_intelligence_failed.v1",
  "correlation_id": "uuid-v4",
  "timestamp": "2025-11-03T12:05:00Z",
  "payload": {
    "error_message": "Handler not initialized",
    "error_code": "PROCESSING_ERROR",
    "partial_results": {
      "quality_metrics": {...}
    }
  }
}
```

## Next Steps

### Required for Production

1. **Implement ManifestIntelligenceHandler**
   - Location: `services/intelligence-consumer/src/handlers/manifest_intelligence_handler.py`
   - Required methods:
     - `__init__(postgres_url, kafka_bootstrap, qdrant_url)`
     - `async execute(correlation_id, options) -> Dict[str, Any]`
   - Should integrate with:
     - PostgreSQL for pattern traceability
     - Qdrant for vector intelligence
     - Intelligence service APIs

2. **Uncomment Handler Integration**
   - Uncomment import in `main.py` line 24
   - Uncomment handler initialization in `start()` method (lines 88-92)
   - Uncomment handler execution in `_process_manifest_intelligence_event()` (lines 1133-1170)
   - Remove placeholder completion (lines 1172-1183)

3. **Add Configuration**
   - Add to `config.py`:
     ```python
     postgres_url: str = Field(
         default="postgresql://user:pass@host:port/db",
         description="PostgreSQL connection URL"
     )
     qdrant_url: str = Field(
         default="http://qdrant:6333",
         description="Qdrant vector database URL"
     )
     ```

4. **Testing**
   - Unit tests for manifest event processing
   - Integration tests with handler
   - End-to-end tests with Kafka events
   - Error handling and retry logic tests

### Optional Enhancements

1. **Event Validation**
   - Add manifest event schema validation to `_is_valid_event_schema()`
   - Add required options validation

2. **Metrics & Monitoring**
   - Add manifest processing metrics to health endpoint
   - Add processing time histograms
   - Add success/failure rate tracking

3. **Configuration Tuning**
   - Adjust consumer timeout for long-running manifest generation
   - Configure retry backoff for manifest operations
   - Add manifest-specific circuit breaker thresholds

## Testing

### Manual Testing (Current State)

With handler placeholder, you can test the routing:

```bash
# 1. Start consumer
docker compose up archon-intelligence-consumer

# 2. Produce test event
kafkacat -P -b 192.168.86.200:29092 \
  -t dev.archon-intelligence.intelligence.manifest.requested.v1 <<EOF
{
  "event_type": "omninode.intelligence.event.manifest_intelligence_requested.v1",
  "correlation_id": "test-123",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "payload": {
    "options": {
      "repository_path": "/test"
    }
  }
}
EOF

# 3. Check logs
docker logs -f archon-intelligence-consumer | grep manifest

# 4. Verify completion event published
kafkacat -C -b 192.168.86.200:29092 \
  -t dev.archon-intelligence.intelligence.manifest.completed.v1 \
  -o end
```

Expected log output:
```
manifest_intelligence_event_processing_started
manifest_intelligence_handler_not_yet_implemented
manifest_completion_published
```

### Integration Testing (After Handler Ready)

```bash
# Run integration test suite
pytest services/intelligence-consumer/tests/test_manifest_integration.py -v
```

## Files Modified

1. `services/intelligence-consumer/src/config.py` - Added manifest topics and subscription
2. `services/intelligence-consumer/src/consumer.py` - Added publishing methods
3. `services/intelligence-consumer/src/main.py` - Added routing and processing logic
4. `services/intelligence-consumer/src/handlers/__init__.py` - Created handlers package

## Success Criteria

- ✅ Consumer subscribes to manifest intelligence topic
- ✅ Routing logic detects and routes manifest events
- ✅ Response publishing methods implemented
- ✅ Proper error handling and logging
- ✅ No breaking changes to existing functionality
- ✅ Placeholder handler allows testing without implementation
- 🔄 Handler initialization ready (commented out)
- 🔄 Handler integration ready (commented out)

## Notes

- All handler integration code is commented with clear instructions
- Placeholder implementation allows immediate testing of routing infrastructure
- Partial results support enables graceful degradation
- Comprehensive logging for debugging and monitoring
- Follows existing patterns for code-analysis and enrichment events

## Related Documents

- Parallel Task: ManifestIntelligenceHandler implementation
- Related Services: archon-intelligence, archon-bridge
- Topics: manifest.requested, manifest.completed, manifest.failed
