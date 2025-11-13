# Structured Logging Implementation

**Status**: ✅ Complete
**Date**: 2025-11-06
**Scope**: Data Ingestion Pipeline (Kafka → Handler → Intelligence → Qdrant/Memgraph)

## Overview

Comprehensive structured logging has been added throughout the data ingestion pipeline to provide complete visibility into every step of the ingestion process, from Kafka event reception to database indexing.

## Implementation Summary

### 1. bulk_ingest_repository.py

**Changes**:
- Added correlation ID generation for entire ingestion workflow
- Structured logging with `extra={}` metadata for machine-readability
- Emoji indicators for visual scanning:
  - 🚀 Starting bulk ingestion
  - 📁 PHASE 1: FILE DISCOVERY
  - 📤 PHASE 2: BATCH PROCESSING & EVENT PUBLISHING
  - 📊 Progress tracking
  - 🔌 Kafka producer lifecycle
  - ✅ Success indicators
  - ❌ Failure indicators

**Key Metrics Logged**:
```python
extra={
    "correlation_id": correlation_id,
    "project_name": project_name,
    "files_discovered": files_discovered,
    "total_size_bytes": total_size_bytes,
    "batch_num": batch_num,
    "total_batches": total_batches,
    "percent": percent,
    "duration_ms": duration_ms,
    "files_per_second": files_per_second
}
```

### 2. tree_stamping_handler.py

**Changes**:
- Added structured event reception logging
- Correlation ID tracking throughout handler lifecycle
- Processing start/end logging with timing
- Success/failure logging with full context

**Key Metrics Logged**:
```python
extra={
    "event_type": event_type,
    "correlation_id": str(correlation_id),
    "file_count": len(files),
    "files_indexed": result.files_indexed,
    "vector_indexed": result.vector_indexed,
    "graph_indexed": result.graph_indexed,
    "cache_warmed": result.cache_warmed,
    "duration_ms": round(duration_ms, 2)
}
```

**Emoji Indicators**:
- 📥 Event received
- 🚀 Processing started
- ✅ Success
- ❌ Error/failure

### 3. tree_stamping_bridge.py

**Changes**:
- **Stage markers** with emoji for 6-stage pipeline:
  - 🔍 Stage 1/6: Validating inline content
  - 🧠 Stage 2/6: Generating intelligence
  - 📝 Stage 3/6: Stamping files with metadata
  - 💾 Stage 4-5/6: Indexing in Qdrant + Memgraph
  - 🔥 Stage 6/6: Warming cache
  - ✅ Stage completion with timing

- **Per-stage timing** tracking
- **Progress logging** for batch operations
- **Comprehensive metadata** for each stage

**Key Metrics Logged**:
```python
# Per-stage metrics
extra={
    "stage": 2,
    "total_files": len(file_paths),
    "batch_size": self.batch_size,
    "files_processed": len(intelligence_results),
    "duration_ms": round(stage_duration_ms, 2),
    "project_name": project_name
}

# Final summary
extra={
    "project_name": project_name,
    "files_indexed": len(intelligence_results),
    "total_duration_ms": duration_ms,
    "stage2_duration_ms": stage2_duration_ms,
    "stage3_duration_ms": stage3_duration_ms,
    "stage45_duration_ms": stage45_duration_ms,
    "files_per_second": files_per_second
}
```

### 4. kafka_consumer.py

**Changes**:
- Event reception logging with correlation IDs
- Handler routing decisions logged
- Success/failure logging with context
- Performance timing for event processing

**Key Metrics Logged**:
```python
extra={
    "event_type": event_type,
    "correlation_id": correlation_id,
    "topic": msg.topic(),
    "partition": msg.partition(),
    "offset": msg.offset(),
    "handler": handler.get_handler_name(),
    "duration_ms": round(elapsed_ms, 2),
    "status": "success" | "failed"
}
```

**Emoji Indicators**:
- 📥 Event received from Kafka
- 🔀 Routing event to handler
- 🎯 Routing to handler (with handler name)
- ✅ Event processed successfully
- ❌ Event not handled successfully
- ⚠️  Warnings (offset commit failed, handler returned false)

## Emoji Legend

| Emoji | Meaning | Usage |
|-------|---------|-------|
| 📥 | Event received | Kafka events, API requests |
| 🚀 | Processing started | Workflow initiation |
| 📁 | File discovery | Repository scanning |
| 📤 | Event publishing | Kafka producer |
| 📊 | Statistics/metrics | Progress tracking |
| 🔍 | Validation | Stage 1: Content validation |
| 🧠 | Intelligence | Stage 2: Intelligence generation |
| 📝 | Stamping | Stage 3: Metadata stamping |
| 💾 | Database write | Stage 4-5: Qdrant/Memgraph indexing |
| 🔥 | Cache warming | Stage 6: Cache pre-warming |
| 🔌 | Infrastructure | Kafka/DB connections |
| 🔀 | Routing | Event routing decisions |
| 🎯 | Handler selected | Specific handler chosen |
| ✅ | Success | Operation completed successfully |
| ❌ | Error/failure | Operation failed |
| ⚠️  | Warning | Non-critical issue |
| ⏱️  | Performance timing | Duration tracking |

## Correlation ID Flow

Correlation IDs flow through the entire pipeline:

```
bulk_ingest_repository.py
  ↓ (generates correlation_id)
Kafka Event
  ↓ (includes correlation_id in event payload)
kafka_consumer.py
  ↓ (extracts correlation_id from event)
tree_stamping_handler.py
  ↓ (passes correlation_id to bridge)
tree_stamping_bridge.py
  ↓ (logs with correlation_id at each stage)
```

## Testing

### 1. Basic Ingestion Test

```bash
# Run ingestion with verbose logging
python3 scripts/bulk_ingest_repository.py /test/path \
  --project-name test-project \
  --verbose

# Expected output:
# 🚀 Starting bulk ingestion workflow
# 📁 PHASE 1: FILE DISCOVERY
# ✅ Discovery complete: ...
# 📤 PHASE 2: BATCH PROCESSING & EVENT PUBLISHING
# 🔌 Initializing Kafka producer
# 📊 Progress: 1/10 batches (10%)
# 🔌 Shutting down Kafka producer
# 📊 PHASE 3: RESULTS SUMMARY
# ✅ All batches processed successfully!
```

### 2. Check Structured Logs

```bash
# View Kafka consumer logs with structured data
docker logs archon-intelligence-consumer-1 --tail 100 | grep "📥\|🚀\|✅\|❌"

# Expected output:
# 📥 Event received from Kafka
# 🎯 Routing to handler: TreeStampingHandler
# 📥 TreeStampingHandler received event
# 🚀 Processing INDEX_PROJECT_REQUESTED with 50 files
# (Then in bridge logs:)
# 🚀 Starting project indexing pipeline
# 🔍 Stage 1/6: Validating inline content
# ✅ Stage 1/6 Complete: Using 50 provided files
# 🧠 Stage 2/6: Generating intelligence for 50 files
# ✅ Stage 2/6 Complete: Generated intelligence for 50 files
# 📝 Stage 3/6: Stamping 50 files with metadata
# ✅ Stage 3/6 Complete: Stamped 50 files
# 💾 Stage 4-5/6: Indexing in Qdrant + Memgraph (parallel)
# ✅ Stage 4-5/6 Complete: Indexed 50 vectors, 50 graph nodes
# 🔥 Stage 6/6: Warming cache with common queries
# ✅ Stage 6/6 Complete: Cache warmed successfully
# ✅ Project indexing complete: test-project
# ✅ INDEX_PROJECT_COMPLETED published successfully
# ✅ Event processed successfully
```

### 3. Extract Metrics from Logs

```bash
# Extract correlation IDs
docker logs archon-intelligence-consumer-1 --tail 1000 | \
  grep -o '"correlation_id": "[^"]*"' | sort | uniq

# Extract stage timings
docker logs archon-intelligence-1 --tail 1000 | \
  grep -o '"stage.*duration_ms": [0-9.]*'

# Extract success/failure counts
docker logs archon-intelligence-consumer-1 --tail 1000 | \
  grep -o '"status": "[^"]*"' | sort | uniq -c
```

### 4. Monitor Pipeline Progress

```bash
# Watch logs in real-time with visual indicators
docker logs -f archon-intelligence-consumer-1 | \
  grep --line-buffered -E "📥|🚀|✅|❌|📊|🧠|📝|💾|🔥"

# Watch only stage transitions
docker logs -f archon-intelligence-1 | \
  grep --line-buffered "Stage [0-9]/6"
```

## Log Structure Example

### Full Event Processing Log Chain

```json
{
  "timestamp": "2025-11-06T10:30:00.123Z",
  "level": "INFO",
  "message": "📥 Event received from Kafka",
  "extra": {
    "event_type": "tree.index-project",
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "topic": "dev.archon-intelligence.tree.index-project-requested.v1",
    "partition": 0,
    "offset": 12345
  }
}

{
  "timestamp": "2025-11-06T10:30:00.150Z",
  "level": "INFO",
  "message": "🎯 Routing to handler: TreeStampingHandler",
  "extra": {
    "event_type": "tree.index-project",
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "handler": "TreeStampingHandler"
  }
}

{
  "timestamp": "2025-11-06T10:30:00.200Z",
  "level": "INFO",
  "message": "🚀 Processing INDEX_PROJECT_REQUESTED with 50 files (inline content)",
  "extra": {
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "project_name": "test-project",
    "file_count": 50,
    "include_tests": true,
    "force_reindex": false
  }
}

{
  "timestamp": "2025-11-06T10:30:00.250Z",
  "level": "INFO",
  "message": "🧠 Stage 2/6: Generating intelligence for 50 files (batch size: 100)",
  "extra": {
    "stage": 2,
    "total_files": 50,
    "batch_size": 100,
    "project_name": "test-project"
  }
}

{
  "timestamp": "2025-11-06T10:30:15.500Z",
  "level": "INFO",
  "message": "✅ Stage 2/6 Complete: Generated intelligence for 50 files",
  "extra": {
    "stage": 2,
    "files_processed": 50,
    "duration_ms": 15250.0,
    "project_name": "test-project"
  }
}

{
  "timestamp": "2025-11-06T10:30:45.750Z",
  "level": "INFO",
  "message": "✅ Project indexing complete: test-project",
  "extra": {
    "project_name": "test-project",
    "files_indexed": 50,
    "total_duration_ms": 45500,
    "stage2_duration_ms": 15250.0,
    "stage3_duration_ms": 8500.0,
    "stage45_duration_ms": 18750.0,
    "files_per_second": 1.1
  }
}

{
  "timestamp": "2025-11-06T10:30:45.800Z",
  "level": "INFO",
  "message": "✅ Event processed successfully",
  "extra": {
    "event_type": "tree.index-project",
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "duration_ms": 45600.0,
    "status": "success"
  }
}
```

## Benefits

1. **Full Pipeline Visibility**: Every step logged with correlation IDs
2. **Performance Tracking**: Stage-by-stage timing for bottleneck identification
3. **Machine-Readable**: Structured JSON metadata for automated analysis
4. **Human-Friendly**: Emoji indicators for quick visual scanning
5. **Debugging**: Correlation IDs enable end-to-end request tracing
6. **Metrics**: Progress tracking (X/Y files processed, percentages)
7. **Error Context**: Full context logged on failures for easier troubleshooting

## Files Modified

1. `/Volumes/PRO-G40/Code/omniarchon/scripts/bulk_ingest_repository.py`
2. `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src/handlers/tree_stamping_handler.py`
3. `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src/integrations/tree_stamping_bridge.py`
4. `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src/kafka_consumer.py`

## Next Steps

1. **Monitor Logs**: Watch ingestion process with new structured logging
2. **Extract Metrics**: Build dashboards from structured log data
3. **Set Alerts**: Create alerts based on correlation ID tracking and error rates
4. **Performance Analysis**: Analyze stage timings to identify bottlenecks
5. **Extend Coverage**: Add similar structured logging to other services

---

**Status**: ✅ Production Ready
**Coverage**: 100% of ingestion pipeline
**Correlation ID Flow**: End-to-end tracking enabled
