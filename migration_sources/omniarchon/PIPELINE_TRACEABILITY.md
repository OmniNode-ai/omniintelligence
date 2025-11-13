# Pipeline Traceability and Logging Guide

**Created**: 2025-11-12
**Purpose**: End-to-end tracing and observability for the ingestion pipeline

## Overview

The ingestion pipeline now has comprehensive logging and traceability from file discovery to storage. Every file gets a unique correlation ID that flows through all stages:

```
File Discovery → Kafka Event → Consumer → Handler → Search Service → Storage
     |               |            |          |           |             |
correlation_id → correlation_id → correlation_id → correlation_id → correlation_id
```

## Pipeline Stages

### Stage 1: Ingestion (bulk_ingest_repository.py)
- **Generates**: Per-file correlation IDs
- **Logs**: File discovery, content enrichment, batch creation, Kafka publishing
- **Key Actions**:
  - `file_discovered`: File found during discovery
  - `file_enriched`: Content read and checksummed
  - `large_file_excluded`: File too large for inline content
  - `batch_event_created`: Kafka event created
  - `publish`: Event published to Kafka

### Stage 2: Consumer (kafka_consumer.py)
- **Receives**: Events from Kafka with correlation IDs
- **Logs**: Event reception, handler routing, handler execution
- **Key Actions**:
  - `event_received`: Event consumed from Kafka
  - `routing_event`: Looking for appropriate handler
  - `handler_invoked`: Handler found and called
  - `handler_completed`: Handler finished successfully
  - `handler_failed`: Handler returned failure
  - `handler_exception`: Handler threw exception
  - `no_handler_found`: No handler available for event type

### Stage 3: Handler (document_indexing_handler.py)
- **Processes**: Individual files from events
- **Logs**: Service calls, vectorization, storage operations
- **Key Actions**: (handler-specific)

### Stage 4: Search Service (app.py)
- **Vectorizes**: File content into embeddings
- **Stores**: Vectors in Qdrant, nodes in Memgraph
- **Logs**: Embedding generation, storage operations

## Correlation ID Structure

### Batch-Level Correlation ID
- **Format**: UUID v4 (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
- **Scope**: Groups all files in a single batch
- **Location**: `event.correlation_id` in Kafka events

### File-Level Correlation ID
- **Format**: UUID v4 (unique per file)
- **Scope**: Tracks single file through entire pipeline
- **Location**: `file.correlation_id` in event payload files array

### Relationship
```json
{
  "correlation_id": "batch-12345",  // Batch-level ID
  "metadata": {
    "file_correlation_ids": [       // All file IDs in this batch
      "file-abc123",
      "file-def456",
      "file-ghi789"
    ]
  },
  "payload": {
    "files": [
      {
        "file_path": "/path/to/file1.py",
        "correlation_id": "file-abc123",        // File-level ID
        "batch_correlation_id": "batch-12345"   // Link back to batch
      },
      ...
    ]
  }
}
```

## Debug Mode

Enable comprehensive debugging with full event payload logging:

```bash
# Enable debug mode
export PIPELINE_DEBUG=true

# Run ingestion with debug logging
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --verbose
```

**Debug mode adds**:
- Full event payload logging (truncated content for large files)
- Per-operation timing
- Detailed error stack traces
- Service request/response logging

## Tracing a Single File

### Method 1: Filter logs by correlation ID

```bash
# Trace specific file through pipeline
correlation_id="abc-123-def-456"

# View all stages for this file
docker logs archon-kafka-consumer 2>&1 | grep "correlation_id=${correlation_id}"

# More comprehensive search across all services
./scripts/logs.sh trace ${correlation_id}
```

### Method 2: Use structured logging fields

All log entries include structured data as JSON:

```json
{
  "timestamp": "2025-11-12T10:30:45Z",
  "stage": "ingestion",
  "action": "file_enriched",
  "correlation_id": "abc-123",
  "result": "success",
  "duration_ms": 45.67,
  "file_path": "/path/to/file.py",
  "content_length": 1234,
  "checksum": "blake3:abcdef...",
  "language": "python"
}
```

Extract structured data:

```bash
# Get all events for correlation ID as JSON
docker logs archon-kafka-consumer 2>&1 \
  | grep "correlation_id=abc-123" \
  | grep "structured_data" \
  | python3 -c "
import json, sys
for line in sys.stdin:
    if 'structured_data' in line:
        # Extract JSON from log line
        data = json.loads(line.split('structured_data=')[1].split()[0])
        print(json.dumps(data, indent=2))
"
```

## Log Format Examples

### Successful File Processing

```
[Stage 1: Ingestion]
✅ [ingestion] file_enriched (45ms)
  correlation_id=abc-123 file_path=app.py content_length=1234 language=python

✅ [ingestion] batch_event_created
  correlation_id=batch-456 files_count=10 inline_content_count=9

✅ [ingestion] publish (123ms)
  correlation_id=batch-456 topic=dev.archon-intelligence.tree.index-project-requested.v1

[Stage 2: Consumer]
📥 [consumer] event_received
  correlation_id=batch-456 event_type=tree.index-project topic=...

🔄 [consumer] handler_invoked
  correlation_id=batch-456 handler=TreeStampingHandler

✅ [consumer] handler_completed (234ms)
  correlation_id=batch-456 handler=TreeStampingHandler

[Stage 3: Search Service]
🔍 [search] vectorization_started
  correlation_id=abc-123 file_path=app.py dimensions=1536

✅ [search] vector_stored
  correlation_id=abc-123 collection=archon_vectors point_id=...

✅ [search] node_created
  correlation_id=abc-123 node_type=FILE entity_id=...
```

### Failed Processing

```
[Stage 1: Ingestion]
⚠️  [ingestion] large_file_excluded (skipped)
  correlation_id=xyz-789 file_path=large.bin file_size_mb=5.2 threshold_mb=2.0

[Stage 2: Consumer]
❌ [consumer] handler_exception (failed)
  correlation_id=batch-456 handler=DocumentIndexingHandler
  error="Connection timeout" error_type="TimeoutError"
```

## Performance Metrics

Track pipeline performance with correlation IDs:

```bash
# Aggregate pipeline latency by stage
# Extract duration_ms for each stage and calculate averages

# Example metrics to track:
# - Ingestion time: file_discovered → publish
# - Consumer latency: event_received → handler_completed
# - Handler time: handler_invoked → handler_completed
# - End-to-end: file_discovered → vector_stored
```

## Troubleshooting

### "There shouldn't be a mystery" - Finding Lost Files

**Problem**: File ingested but not appearing in search results.

**Solution**: Trace the file's correlation ID through the pipeline:

```bash
# 1. Find the file's correlation ID from ingestion logs
grep "file_path=missing_file.py" scripts/logs/bulk_ingest.log | grep correlation_id

# 2. Trace through Kafka consumer
docker logs archon-kafka-consumer 2>&1 | grep "correlation_id=abc-123"

# 3. Check if vectorization succeeded
docker logs archon-search 2>&1 | grep "correlation_id=abc-123"

# 4. Verify storage
docker logs archon-search 2>&1 | grep "correlation_id=abc-123" | grep "vector_stored"
```

**Common failure points**:
- ❌ Large file excluded (check `large_file_excluded` log)
- ❌ Binary file skipped (check `file_skipped` with `reason=binary_or_unreadable`)
- ❌ Kafka publish failed (check `publish` result=failed)
- ❌ Handler not found (check `no_handler_found`)
- ❌ Vectorization timeout (check `handler_exception` with error_type=TimeoutError)
- ❌ Storage failed (check `vector_stored` result=failed)

### Missing Correlation IDs

If you see logs without correlation IDs:
1. **Old events**: Events published before this enhancement
2. **Legacy format**: Check for `request_id` or `trace_id` fields instead
3. **Fallback**: Consumer generates new correlation ID if missing

### Debug Mode Not Working

```bash
# Verify environment variable is set
echo $PIPELINE_DEBUG  # Should output "true"

# Restart services to pick up env var
docker compose restart archon-kafka-consumer
docker compose restart archon-search
docker compose restart archon-intelligence
```

## Best Practices

### 1. Always Use Correlation IDs in Logs

```python
# ✅ GOOD: Use log_pipeline_event utility
from scripts.lib.correlation_id import log_pipeline_event

log_pipeline_event(
    logger,
    logging.INFO,
    stage="my_service",
    action="processing_file",
    correlation_id=correlation_id,
    result="success",
    duration_ms=123.45,
    file_path="/path/to/file.py"
)

# ❌ BAD: Manual logging without correlation ID
logger.info(f"Processing file: /path/to/file.py")
```

### 2. Pass Correlation IDs Through All Function Calls

```python
# ✅ GOOD: Thread correlation ID through call stack
async def process_file(file_path: str, correlation_id: str):
    await vectorize_content(content, correlation_id)

async def vectorize_content(content: str, correlation_id: str):
    log_pipeline_event(logger, ..., correlation_id=correlation_id)
    ...

# ❌ BAD: Losing correlation ID in nested calls
async def process_file(file_path: str, correlation_id: str):
    await vectorize_content(content)  # Lost correlation_id!
```

### 3. Log at Critical Pipeline Stages

**Minimum required logs per stage**:
- **Entry**: Log when operation starts
- **Success**: Log when operation completes successfully
- **Failure**: Log when operation fails with error details
- **Duration**: Include timing for performance analysis

### 4. Use Structured Fields

```python
# ✅ GOOD: Structured fields for easy filtering
log_pipeline_event(
    logger, logging.INFO,
    stage="search", action="vector_created",
    correlation_id=correlation_id, result="success",
    collection="archon_vectors", point_id=point_id,
    dimensions=1536, duration_ms=45.67
)

# ❌ BAD: Unstructured string that's hard to parse
logger.info(f"Created vector in archon_vectors: {point_id} (1536 dims, 45.67ms)")
```

## Integration with Existing Tools

### Log Viewer Script

```bash
# View logs with correlation ID filtering
./scripts/logs.sh trace abc-123-def-456

# View only errors
./scripts/logs.sh errors

# Follow in real-time
./scripts/logs.sh follow
```

### Environment Verification

```bash
# Run comprehensive health check (includes correlation ID testing)
python3 scripts/verify_environment.py --verbose
```

### Performance Monitoring

```bash
# Track pipeline metrics
python3 scripts/monitor_performance.py
```

## Example: Complete File Journey

```bash
# 1. Start ingestion with debug mode
export PIPELINE_DEBUG=true
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name test-project \
  --verbose \
  > ingestion.log 2>&1

# 2. Extract a specific file's correlation ID
grep "file_path=app.py" ingestion.log | grep correlation_id | head -1
# Output: correlation_id=abc-123-def-456

# 3. Trace through consumer
docker logs archon-kafka-consumer 2>&1 \
  | grep "abc-123-def-456" \
  > consumer.log

# 4. Trace through search service
docker logs archon-search 2>&1 \
  | grep "abc-123-def-456" \
  > search.log

# 5. Verify completion
cat ingestion.log consumer.log search.log | grep "abc-123-def-456"
```

**Expected output showing full journey**:
```
✅ [ingestion] file_enriched (45ms) correlation_id=abc-123 ...
✅ [ingestion] batch_event_created correlation_id=batch-456 ...
✅ [ingestion] publish (123ms) correlation_id=batch-456 ...
📥 [consumer] event_received correlation_id=batch-456 ...
🔄 [consumer] handler_invoked correlation_id=batch-456 ...
✅ [consumer] handler_completed (234ms) correlation_id=batch-456 ...
🔍 [search] vectorization_started correlation_id=abc-123 ...
✅ [search] vector_stored correlation_id=abc-123 ...
✅ [search] node_created correlation_id=abc-123 ...
```

## Summary

**"There shouldn't be a mystery" - now there isn't!**

Every file has a unique correlation ID that tracks it through:
1. **Ingestion**: File discovered, content read, event created
2. **Kafka**: Event published and consumed
3. **Consumer**: Event routed to appropriate handler
4. **Handler**: File processed (vectorization, storage)
5. **Storage**: Vector and node creation confirmed

**To trace any file**: Just find its correlation ID and grep through logs.

**Debug mode**: Set `PIPELINE_DEBUG=true` for full payload logging.

**Zero mystery**: Complete visibility from ingestion to storage.
