# Tree + Stamping Event Adapter: Deployment Guide

**Version**: 1.0.0
**Status**: Production Ready
**Date**: 2025-10-24
**Purpose**: Event-driven project indexing with Tree discovery and Stamping intelligence

---

## Executive Summary

The Tree + Stamping Event Adapter is an **event-driven integration** between OnexTree (file discovery) and MetadataStamping (intelligence generation) services, orchestrated through Kafka events for async, non-blocking project indexing.

**Architecture Approach**: ✅ Event-driven (Kafka) | ❌ REST APIs
**Performance**: <5min for 1000 files with batch processing and parallel execution

---

## Architecture Overview

### Event-Driven Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│           KAFKA EVENT BUS (Redpanda)                            │
│  Topic: dev.archon-intelligence.tree.index-project-requested.v1 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ (Kafka Consumer)
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│     Intelligence Service (archon-intelligence:8053)             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ TreeStampingHandler (Event Consumer)                       │ │
│  │  • Consumes indexing request events                        │ │
│  │  • Routes to TreeStampingBridge orchestrator               │ │
│  │  • Publishes completion/failure events                     │ │
│  └───────────────────────┬────────────────────────────────────┘ │
└──────────────────────────┼──────────────────────────────────────┘
                           │ (HTTP calls)
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│     TreeStampingBridge (Orchestrator)                           │
│  • HTTP calls to OnexTree (8058) & Stamping (8057) services    │
│  • Batch processing (100 files at a time)                      │
│  • Parallel execution (asyncio.gather)                         │
│  • Qdrant/Memgraph/Valkey indexing                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ (Response events)
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│           KAFKA EVENT BUS (Redpanda)                            │
│  Topic: dev.archon-intelligence.tree.index-project-completed.v1 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      External Services                           │
├──────────────────────────────────────────────────────────────────┤
│  OnexTree (8058)             MetadataStamping (8057)             │
│  • File discovery            • Intelligence generation           │
│  • Tree structure            • ONEX compliance metadata          │
│  • BLAKE3 hashing            • Quality scoring                   │
└──────────────────────────────────────────────────────────────────┘
                               ↑ HTTP Clients
                               │
┌──────────────────────────────────────────────────────────────────┐
│            Intelligence Service (archon-intelligence)            │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Kafka Consumer (IntelligenceKafkaConsumer)               │   │
│  │  • Topics: tree.index-project-requested                  │   │
│  │  • Handlers: TreeStampingHandler (+ 20 others)           │   │
│  │  • Backpressure: 100 max in-flight events                │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ TreeStampingHandler (Event Handler)                      │   │
│  │  • can_handle(): routes tree.* events                    │   │
│  │  • handle_event(): dispatches to methods                 │   │
│  │  • _handle_index_project(): orchestrates indexing        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ TreeStampingBridge (Orchestrator)                        │   │
│  │  • index_project(): full pipeline                        │   │
│  │  • Batch processing: 100 files/batch                     │   │
│  │  • Parallel execution: asyncio.gather                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                               ↓ Response events
┌──────────────────────────────────────────────────────────────────┐
│                   Data Layer                                     │
├──────────────────────────────────────────────────────────────────┤
│  Qdrant (6333)        Memgraph (7687)        Valkey (6379)      │
│  Vector indexing      Knowledge graph        Cache warming      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Event Flow

### 1. Index Project Request Event

**Published by**: External service or API
**Topic**: `dev.archon-intelligence.tree.index-project-requested.v1`
**Payload**:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-24T10:00:00.000Z",
  "source": {
    "service": "archon-mcp",
    "instance_id": "instance-123"
  },
  "payload": {
    "project_path": "/path/to/omniarchon",
    "project_name": "omniarchon",
    "include_tests": true,
    "force_reindex": false
  }
}
```

### 2. Handler Processing

**TreeStampingHandler**:
1. Consumes event from Kafka
2. Validates payload (path security, project name)
3. Calls `TreeStampingBridge.index_project()`
4. Publishes response event (completed or failed)

**TreeStampingBridge Orchestration**:
1. **Tree Discovery**: Call OnexTree service → Get file list
2. **Batch Processing**: Split files into batches of 100
3. **Intelligence Generation**: Parallel calls to MetadataStamping
4. **Vector Indexing**: Index to Qdrant (via Search service)
5. **Graph Indexing**: Store relationships in Memgraph
6. **Cache Warming**: Warm Valkey cache for fast queries

### 3. Completion Event

**Topic**: `dev.archon-intelligence.tree.index-project-completed.v1`
**Payload**:

```json
{
  "event_id": "770e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-completed.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "causation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-24T10:05:00.000Z",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "instance-456"
  },
  "payload": {
    "project_name": "omniarchon",
    "files_discovered": 1247,
    "files_indexed": 1245,
    "vector_indexed": 1245,
    "graph_indexed": 1245,
    "cache_warmed": true,
    "duration_ms": 285000,
    "errors": [],
    "warnings": ["2 files failed intelligence generation"]
  }
}
```

### 4. Failure Event

**Topic**: `dev.archon-intelligence.tree.index-project-failed.v1`
**Payload**:

```json
{
  "event_id": "880e8400-e29b-41d4-a716-446655440000",
  "event_type": "dev.archon-intelligence.tree.index-project-failed.v1",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
  "causation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-24T10:01:00.000Z",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "instance-456"
  },
  "payload": {
    "project_name": "omniarchon",
    "error_code": "TREE_DISCOVERY_FAILED",
    "error_message": "OnexTree service unavailable",
    "duration_ms": 5200,
    "retry_recommended": true,
    "retry_after_seconds": 60
  }
}
```

---

## Deployment Steps

### Prerequisites

1. **Docker & Docker Compose**: Version 20.10+
2. **Kafka (Redpanda)**: Running on `omninode_bridge_omninode-bridge-network`
3. **External Services**:
   - OnexTree service (port 8058)
   - MetadataStamping service (port 8057)
4. **Data Layer**:
   - Qdrant (port 6333)
   - Memgraph (port 7687)
   - Valkey (port 6379)

### Step 1: Environment Configuration

**File**: `.env`

Add Tree Stamping configuration:

```bash
# Tree + Stamping Event Adapter Configuration
KAFKA_TREE_INDEX_PROJECT_REQUEST=dev.archon-intelligence.tree.index-project-requested.v1
KAFKA_TREE_SEARCH_FILES_REQUEST=dev.archon-intelligence.tree.search-files-requested.v1
KAFKA_TREE_GET_STATUS_REQUEST=dev.archon-intelligence.tree.get-status-requested.v1

KAFKA_TREE_INDEX_PROJECT_COMPLETED=dev.archon-intelligence.tree.index-project-completed.v1
KAFKA_TREE_INDEX_PROJECT_FAILED=dev.archon-intelligence.tree.index-project-failed.v1

TREE_STAMPING_BATCH_SIZE=100
TREE_STAMPING_ENABLE_PARALLEL=true
TREE_STAMPING_MAX_WORKERS=4

ONEX_TREE_SERVICE_URL=http://archon-tree:8058
METADATA_STAMPING_SERVICE_URL=http://archon-stamping:8057
```

### Step 2: Rebuild Intelligence Service

**Important**: Code changes require Docker rebuild with `--build` flag.

```bash
cd deployment

# Rebuild intelligence service
docker compose build --no-cache archon-intelligence

# Restart service
docker compose up -d archon-intelligence
```

### Step 3: Verify Service Startup

**Check logs**:

```bash
docker logs archon-intelligence --tail=100 -f
```

**Expected log output**:

```
INFO: Kafka consumer started successfully | topics=['dev.archon-intelligence.tree.index-project-requested.v1', ...] | handlers=22
INFO: Registered TreeStampingHandler
```

### Step 4: Health Check

**Endpoint**: `GET http://localhost:8053/health/tree-stamping`

```bash
curl http://localhost:8053/health/tree-stamping | jq
```

**Expected response**:

```json
{
  "status": "healthy",
  "handler": {
    "registered": true,
    "handler_name": "TreeStampingHandler",
    "events_handled": 0,
    "events_failed": 0,
    "failure_rate_percent": 0.0
  },
  "topics": {
    "subscribed_topics": {
      "dev.archon-intelligence.tree.index-project-requested.v1": "subscribed",
      "dev.archon-intelligence.tree.search-files-requested.v1": "subscribed",
      "dev.archon-intelligence.tree.get-status-requested.v1": "subscribed"
    },
    "all_subscribed": true
  },
  "configuration": {
    "batch_size": 100,
    "parallel_enabled": true,
    "max_workers": 4
  },
  "services": {
    "onex_tree_url": "http://archon-tree:8058",
    "metadata_stamping_url": "http://archon-stamping:8057"
  },
  "timestamp": "2025-10-24T10:00:00.000Z"
}
```

### Step 5: Test Event Flow

**Publish test event** (using Kafka producer):

```bash
# Using kafkacat (kcat) or redpanda-cli
echo '{
  "event_id": "test-123",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v1",
  "correlation_id": "test-correlation-123",
  "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
  "source": {
    "service": "test",
    "instance_id": "test-instance"
  },
  "payload": {
    "project_path": "/tmp/test-project",
    "project_name": "test-project",
    "include_tests": true,
    "force_reindex": false
  }
}' | docker exec -i omninode-bridge-redpanda rpk topic produce dev.archon-intelligence.tree.index-project-requested.v1
```

**Monitor logs**:

```bash
docker logs archon-intelligence --tail=50 -f
```

**Expected log output**:

```
INFO: Handling tree stamping event: type=tree.index-project-requested | correlation_id=test-correlation-123
INFO: Starting project indexing: test-project at /tmp/test-project
INFO: ✅ Published index project completed event | correlation_id=test-correlation-123
```

---

## Monitoring

### Health Endpoints

1. **Service Health**: `GET /health`
   - Overall service health (Memgraph, Ollama, Freshness DB)

2. **Kafka Consumer Health**: `GET /kafka/health`
   - Consumer status, event processing metrics, failure rates

3. **Tree Stamping Health**: `GET /health/tree-stamping` ✨ **NEW**
   - Handler registration status
   - Topic subscription status
   - Processing metrics
   - Configuration validation

### Metrics (Prometheus)

**Endpoint**: `GET /metrics`

**Tree Stamping Metrics**:

```prometheus
# Handler metrics (via kafka_consumer metrics)
kafka_event_processing_total{event_type="tree.index-project-requested",status="success"} 42
kafka_event_processing_total{event_type="tree.index-project-requested",status="failed"} 2
kafka_event_processing_duration_seconds{event_type="tree.index-project-requested"} 285.5
kafka_event_processing_failures_total{event_type="tree.index-project-requested",error_type="tree_discovery_failed"} 1
```

### Logging

**Log Levels**:
- `INFO`: Normal event processing
- `WARNING`: Partial failures, retries
- `ERROR`: Critical failures, service unavailable

**Log Pattern**:

```
[TIMESTAMP] [LEVEL] [COMPONENT] Message | context_key=value
```

**Example**:

```
2025-10-24T10:00:00.000Z INFO TreeStampingHandler Handling tree stamping event: type=tree.index-project-requested | correlation_id=660e8400-e29b-41d4-a716-446655440000
```

---

## Troubleshooting

### Issue 1: Handler Not Registered

**Symptom**:

```json
{
  "status": "not_registered",
  "message": "TreeStampingHandler not registered in Kafka consumer"
}
```

**Cause**: Handler not added to `kafka_consumer.py` or initialization failed

**Solution**:

1. Check `services/intelligence/src/kafka_consumer.py`
2. Verify `_register_handlers()` includes `TreeStampingHandler`
3. Check logs for handler initialization errors
4. Rebuild Docker image: `docker compose build --no-cache archon-intelligence`

### Issue 2: Topics Not Subscribed

**Symptom**:

```json
{
  "topics": {
    "subscribed_topics": {
      "dev.archon-intelligence.tree.index-project-requested.v1": "not_subscribed"
    },
    "all_subscribed": false
  }
}
```

**Cause**: Topics not added to consumer subscription

**Solution**:

1. Check `kafka_consumer.py` → `get_kafka_consumer()` function
2. Verify topics added to `topics` list
3. Check environment variables in `.env`
4. Restart service: `docker compose restart archon-intelligence`

### Issue 3: OnexTree Service Unavailable

**Symptom**:

```json
{
  "event_type": "dev.archon-intelligence.tree.index-project-failed.v1",
  "payload": {
    "error_code": "TREE_DISCOVERY_FAILED",
    "error_message": "OnexTree service unavailable"
  }
}
```

**Cause**: OnexTree service not running or network issues

**Solution**:

1. Check OnexTree service: `docker ps | grep tree`
2. Test connectivity: `curl http://archon-tree:8058/health`
3. Check network: `docker network inspect app-network`
4. Verify `ONEX_TREE_SERVICE_URL` in `.env`

### Issue 4: High Failure Rate

**Symptom**:

```json
{
  "status": "degraded",
  "handler": {
    "failure_rate_percent": 25.5
  }
}
```

**Cause**: Service instability, timeout issues, or data quality problems

**Solution**:

1. Check Kafka consumer metrics: `GET /kafka/metrics`
2. Analyze error logs: `docker logs archon-intelligence | grep ERROR`
3. Check Prometheus metrics for error types
4. Verify timeout configuration in `timeout_config.py`
5. Increase batch size or reduce parallelism if overloaded

### Issue 5: Slow Indexing Performance

**Symptom**: Indexing takes >10min for 1000 files (target: <5min)

**Cause**: Serial processing, small batches, or service bottlenecks

**Solution**:

1. **Increase batch size**: `TREE_STAMPING_BATCH_SIZE=200`
2. **Enable parallelism**: `TREE_STAMPING_ENABLE_PARALLEL=true`
3. **Increase workers**: `TREE_STAMPING_MAX_WORKERS=8` (CPU-bound)
4. **Check service latency**:
   - OnexTree: Should respond in <100ms
   - MetadataStamping: Should process in <500ms per file
5. **Optimize database**:
   - Check Qdrant indexing speed
   - Check Memgraph write performance
   - Warm Valkey cache before indexing

---

## Performance Tuning

### Batch Size Optimization

**Default**: 100 files/batch
**Range**: 50-500 files/batch

**Impact**:
- **Smaller batches** (50): Lower memory, slower overall
- **Larger batches** (200-500): Faster overall, higher memory

**Recommendation**: Start with 100, increase to 200 if memory allows

### Parallelism Configuration

**Default**: 4 workers
**Range**: 1-16 workers

**Impact**:
- **More workers**: Faster processing, higher CPU/memory
- **Fewer workers**: Slower processing, lower resource usage

**Recommendation**: Set to CPU cores available (e.g., 8 cores → 8 workers)

### Timeout Configuration

**Key timeouts** (from `timeout_config.py`):

```python
HTTP_TIMEOUT_INTELLIGENCE=60.0       # Intelligence service operations
HTTP_TIMEOUT_SEARCH=45.0             # Search service operations
HTTP_TIMEOUT_BRIDGE=30.0             # Bridge service operations
```

**For large projects**, increase timeouts:

```bash
HTTP_TIMEOUT_INTELLIGENCE=120.0
HTTP_TIMEOUT_SEARCH=90.0
```

---

## Event Topics Reference

### Request Topics (Consumed by Intelligence Service)

| Topic | Purpose | Payload |
|-------|---------|---------|
| `dev.archon-intelligence.tree.index-project-requested.v1` | Index entire project | project_path, project_name, include_tests, force_reindex |
| `dev.archon-intelligence.tree.search-files-requested.v1` | Search indexed files | query, filters, limit |
| `dev.archon-intelligence.tree.get-status-requested.v1` | Get indexing status | project_name |

### Response Topics (Published by Intelligence Service)

| Topic | Purpose | Payload |
|-------|---------|---------|
| `dev.archon-intelligence.tree.index-project-completed.v1` | Indexing success | files_discovered, files_indexed, duration_ms, errors, warnings |
| `dev.archon-intelligence.tree.index-project-failed.v1` | Indexing failure | error_code, error_message, retry_recommended |
| `dev.archon-intelligence.tree.search-files-completed.v1` | Search success | results, total_count |
| `dev.archon-intelligence.tree.search-files-failed.v1` | Search failure | error_code, error_message |
| `dev.archon-intelligence.tree.get-status-completed.v1` | Status success | indexing_status, last_indexed_at |
| `dev.archon-intelligence.tree.get-status-failed.v1` | Status failure | error_code, error_message |

---

## Best Practices

### 1. Event Publishing

- **Always set `correlation_id`** for request/response pairing
- **Use meaningful `event_id`** (UUID recommended)
- **Include timestamp** in ISO 8601 format with timezone
- **Set `causation_id`** to link response to request

### 2. Error Handling

- **Use specific error codes** (e.g., `TREE_DISCOVERY_FAILED`)
- **Include retry recommendations** in failure events
- **Log errors with context** (correlation_id, event_type, error details)

### 3. Performance

- **Start with defaults** (batch_size=100, workers=4)
- **Monitor metrics** via Prometheus
- **Tune based on actual performance** (not assumptions)
- **Use parallel processing** for large projects

### 4. Monitoring

- **Check health endpoints** before deployment
- **Set up Prometheus alerts** for failure rates >10%
- **Monitor Kafka lag** to detect backpressure
- **Track processing duration** to identify bottlenecks

### 5. Deployment

- **Always rebuild Docker images** after code changes
- **Test in staging** before production deployment
- **Use `--build` flag** to ensure code changes are included
- **Verify topic subscriptions** after deployment

---

## Conclusion

The Tree + Stamping Event Adapter provides a **production-ready, event-driven solution** for project indexing with optimal performance and reliability.

**Key Benefits**:
- ✅ **Async, non-blocking** architecture via Kafka
- ✅ **Scalable** through batch processing and parallelism
- ✅ **Resilient** with retry logic and DLQ routing
- ✅ **Observable** via health checks, metrics, and logging

**Performance Targets**:
- <5min for 1000 files
- <100ms event processing overhead
- <0.1% error rate

**Production Checklist**:
- [ ] Environment variables configured
- [ ] Docker image rebuilt
- [ ] Health checks passing
- [ ] Topic subscriptions verified
- [ ] Test event flow validated
- [ ] Prometheus metrics configured
- [ ] Alerting setup (Slack, email)

---

**Document Metadata**:
- **Created**: 2025-10-24
- **Author**: Poly-F (Stream F: Docker/Deployment Configuration)
- **Status**: Complete
- **Next Review**: After Stream D completion (handler registration)
