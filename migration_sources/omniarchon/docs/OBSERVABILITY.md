# Archon Observability & Monitoring Guide

**Version**: 1.0.0 | **Last Updated**: October 2025 | **Architecture**: Event-Driven Microservices

## Overview

Comprehensive validation and monitoring tools for the Archon Intelligence Platform. This guide covers automated validation scripts, health monitoring, data integrity checks, and troubleshooting procedures for production deployments.

**Core Principles**:
- **Proactive Monitoring**: Detect issues before they impact users
- **Multi-Layer Validation**: Services, data stores, event pipeline, search functionality
- **Automated Health Checks**: CI/CD integration and continuous monitoring
- **Graceful Degradation**: Services continue operating when dependencies are unavailable

## Validation Scripts

### validate_data_integrity.py

**Purpose**: Python-based data layer validation with automated health checks

**Location**: `/scripts/validate_data_integrity.py`

**Usage**:
```bash
# Quick validation (recommended for regular checks)
poetry run python3 scripts/validate_data_integrity.py

# Detailed validation with verbose output
poetry run python3 scripts/validate_data_integrity.py --verbose

# JSON output for automation/CI/CD
poetry run python3 scripts/validate_data_integrity.py --json
```

**Validates**:
- ✅ **Qdrant Vector Database** - Vector collection coverage and point counts
- ✅ **Search Service** - File path retrieval rate from search results
- ✅ **Metadata Filtering** - Language and project-based filtering

**Exit Codes**:
- `0` - Healthy (3-4 components working)
- `1` - Degraded (2 components working)
- `2` - Unhealthy (0-1 components working)

**When to Use**:
- After data ingestion operations
- Deployment verification
- Regular health checks (recommended: every 5 minutes)
- Troubleshooting search or vector issues

**Example Output**:
```
🔍 Archon Data Integrity Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Qdrant: HEALTHY
   Vectors: 25,249 indexed
   Collections: archon_vectors

✅ Search: HEALTHY
   Query success rate: 100%
   Average latency: 125ms

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Status: HEALTHY (3/3 components)
```

**See Also**: `docs/VALIDATION_SCRIPT.md` for detailed usage guide

### validate_integrations.sh

**Purpose**: Comprehensive integration testing across all services

**Location**: `/scripts/validate_integrations.sh`

**Usage**:
```bash
# Standard validation
./scripts/validate_integrations.sh

# Verbose mode with detailed output
./scripts/validate_integrations.sh --verbose

# Skip specific checks
./scripts/validate_integrations.sh --skip-kafka
```

**Validates**:
- ✅ **Core Services** - Intelligence, Bridge, Search, LangExtract services
- ✅ **Data Stores** - Qdrant, Memgraph, Valkey cache
- ✅ **Event Pipeline** - Kafka/Redpanda broker, topics, consumer health
- ✅ **Search Integration** - RAG search, vector search, metadata filtering
- ✅ **Cache Layer** - Valkey distributed cache health and metrics

**Exit Codes**:
- `0` - All integrations healthy
- `1` - One or more integrations failed

**When to Use**:
- Post-deployment validation
- CI/CD pipeline integration
- Comprehensive system health checks
- Pre-release validation

**Example Output**:
```
🏥 Archon Integration Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1/5] Service Health Checks
✅ archon-intelligence (8053): healthy
✅ archon-bridge (8054): healthy
✅ archon-search (8055): healthy
✅ archon-langextract (8156): healthy

[2/5] Data Store Validation
✅ Qdrant (6333): 25,249 vectors
✅ Memgraph (7687): connected
✅ Valkey (6379): cache operational

[3/5] Kafka Pipeline
✅ Broker: healthy
✅ Topics: 8/8 configured
✅ Consumer: processing events

[4/5] Search Functionality
✅ RAG search: operational
✅ Vector search: <100ms latency
✅ Metadata filters: working

[5/5] Performance Metrics
✅ Cache hit rate: 67%
✅ Average query time: 125ms
✅ Memory usage: nominal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: ALL SYSTEMS OPERATIONAL ✅
```

## Health Endpoints

### Service Health Checks

All Archon services expose standardized health endpoints at `/health`:

| Service | Endpoint | Port |
|---------|----------|------|
| Intelligence | `http://localhost:8053/health` | 8053 |
| Bridge | `http://localhost:8054/health` | 8054 |
| Search | `http://localhost:8055/health` | 8055 |
| LangExtract | `http://localhost:8156/health` | 8156 |

**Expected Response** (Healthy):
```json
{
  "status": "healthy",
  "service": "archon-intelligence",
  "version": "1.0.0",
  "uptime_seconds": 158400,
  "dependencies": {
    "memgraph_connected": true,
    "qdrant_connected": true,
    "cache_connected": true
  },
  "timestamp": "2025-10-29T14:30:00Z"
}
```

**Status Values**:
- `healthy` - All systems operational
- `degraded` - Some dependencies unavailable (service continues operating)
- `unhealthy` - Critical dependencies failed (service unavailable)

**Usage**:
```bash
# Check single service
curl -s http://localhost:8053/health | jq

# Check all services in parallel
for port in 8053 8054 8055 8156; do
  curl -s http://localhost:$port/health | jq -r '"\(.service): \(.status)"' &
done
wait
```

### Subsystem Health Checks

Intelligence service provides granular health endpoints for each subsystem:

```bash
# Pattern learning health
curl http://localhost:8053/api/pattern-learning/health

# Pattern traceability health
curl http://localhost:8053/api/pattern-traceability/health

# Autonomous learning health
curl http://localhost:8053/api/autonomous/health

# Cache layer health
curl http://localhost:8053/cache/health
```

## Data Validation

### Qdrant Vector Database

**Health Check**:
```bash
# Get collection info
curl http://localhost:6333/collections/archon_vectors

# Expected response
{
  "result": {
    "status": "green",
    "vectors_count": 25249,
    "indexed_vectors_count": 25249,
    "points_count": 25249,
    "segments_count": 8
  }
}
```

**Key Metrics**:
- `vectors_count` > 0 (should match ingested documents)
- `status` = "green" (yellow = indexing, red = error)
- `indexed_vectors_count` = `vectors_count` (indexing complete)

**Troubleshooting**:
```bash
# Check if collection exists
curl http://localhost:6333/collections | jq '.result.collections[].name'

# Get detailed collection info
curl http://localhost:6333/collections/archon_vectors | jq

# Test vector search
curl -X POST http://localhost:6333/collections/archon_vectors/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3, ..., 1.0],
    "limit": 5
  }'
```

### Memgraph Knowledge Graph

**Health Check**:
```bash
# Via service endpoint
curl http://localhost:8053/health | jq '.dependencies.memgraph_connected'

# Direct Memgraph query
docker exec archon-memgraph mgconsole -h localhost -P 7687 \
  -c "MATCH (n:Document) RETURN count(n) as document_count;"
```

**Expected**:
- `memgraph_connected` = true
- `document_count` > 0 (matches Qdrant vector count)

### Search Service Validation

**Basic Search Test**:
```bash
# Test RAG search
curl -X POST http://localhost:8055/search/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ONEX architecture patterns",
    "limit": 5
  }' | jq

# Expected response
{
  "results": {
    "vector_search": {
      "results": [...],
      "count": 5
    },
    "knowledge_graph": {
      "results": [...]
    }
  },
  "metadata": {
    "query_time_ms": 125,
    "cache_hit": false
  }
}
```

**Metadata Filter Test**:
```bash
# Filter by language
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication",
    "filters": {
      "language": "python"
    },
    "limit": 10
  }' | jq '.results[] | {path, language}'

# Filter by project
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "API endpoints",
    "filters": {
      "project_name": "omniarchon"
    }
  }' | jq
```

**Cache Performance Test**:
```bash
# Cold cache query
time curl -s -X POST http://localhost:8055/search/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' > /dev/null

# Warm cache query (should be <100ms)
time curl -s -X POST http://localhost:8055/search/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' > /dev/null
```

## Kafka Pipeline Validation

### Event Bus Health

**Redpanda Cluster**:
```bash
# Check cluster health
docker exec omninode-bridge-redpanda rpk cluster health

# List topics
docker exec omninode-bridge-redpanda rpk topic list

# Get topic details
docker exec omninode-bridge-redpanda rpk topic describe \
  dev.archon-intelligence.tree.index-project-requested.v1
```

**Expected Topics**:
- `dev.archon-intelligence.tree.discover.v1` - Tree discovery events
- `dev.archon-intelligence.stamping.generate.v1` - Intelligence generation
- `dev.archon-intelligence.tree.index.v1` - Document indexing
- `dev.archon-intelligence.tree.index-project-requested.v1` - Project indexing requests
- `dev.archon-intelligence.tree.index-project-completed.v1` - Completed indexing
- `dev.archon-intelligence.tree.index-project-failed.v1` - Failed indexing

### Consumer Health

**Kafka Consumer Logs**:
```bash
# Check consumer is processing events
docker logs archon-kafka-consumer --tail 50 | grep "Processing"

# Monitor consumer in real-time
docker logs archon-kafka-consumer -f | grep -E "(Processing|Indexed|Error)"

# Check consumer lag (should be 0 or low)
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumers
```

**Expected Output**:
```
Processing event from topic: dev.archon-intelligence.tree.index.v1
Indexed document: /path/to/file.py (entity_id: abc123)
✅ Successfully processed event in 250ms
```

**Consumer Metrics**:
```bash
# Via service endpoint
curl http://localhost:8054/metrics | jq '.kafka.consumer'

# Expected
{
  "events_processed": 25249,
  "events_failed": 0,
  "average_processing_time_ms": 250,
  "consumer_lag": 0
}
```

### Event Flow Testing

**End-to-End Pipeline Test**:
```bash
# 1. Publish test event
curl -X POST http://localhost:8054/api/test/publish-event \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/test/sample.py",
    "content": "def hello(): pass",
    "metadata": {"language": "python"}
  }'

# 2. Wait for processing (2-5 seconds)
sleep 5

# 3. Verify in Qdrant
curl http://localhost:6333/collections/archon_vectors/points/search \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {"key": "file_path", "match": {"value": "/test/sample.py"}}
      ]
    },
    "limit": 1
  }' | jq

# 4. Verify in search
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "hello function",
    "filters": {"file_path": "/test/sample.py"}
  }' | jq
```

## Ingestion Pipeline Monitoring

### Real-Time Pipeline Monitor

**Purpose**: Continuous monitoring of the event-driven ingestion pipeline to verify end-to-end data flow.

**Script**: `scripts/monitor_ingestion_pipeline.py`

**Features**:
- **Kafka Topic Monitoring**: Message counts, consumer lag, throughput per topic
- **Qdrant Growth Tracking**: Vector count growth rate and indexing status
- **Processing Metrics**: Success rates, latency, throughput
- **Service Health**: Real-time health checks for archon-intelligence, archon-bridge, archon-search
- **Alert System**: Configurable thresholds with webhook notifications
- **Dashboard Mode**: Live console dashboard with real-time updates
- **JSON Export**: Machine-readable output for integration with monitoring tools

**Usage Examples**:

```bash
# Real-time dashboard (updates every 10 seconds)
python3 scripts/monitor_ingestion_pipeline.py --dashboard

# Monitor for 5 minutes and save JSON report
python3 scripts/monitor_ingestion_pipeline.py --duration 300 --json pipeline_metrics.json

# Custom check interval (5 seconds)
python3 scripts/monitor_ingestion_pipeline.py --dashboard --interval 5

# Monitor with Slack webhook alerts
python3 scripts/monitor_ingestion_pipeline.py --dashboard \
  --alert-webhook https://hooks.slack.com/services/YOUR/WEBHOOK

# Custom alert thresholds
python3 scripts/monitor_ingestion_pipeline.py --dashboard \
  --consumer-lag-warning 50 \
  --consumer-lag-critical 200
```

**Monitored Kafka Topics**:
- `dev.archon-intelligence.tree.discover.v1` - Tree discovery events
- `dev.archon-intelligence.tree.index-project-completed.v1` - Successful indexing
- `dev.archon-intelligence.tree.index-project-failed.v1` - Failed indexing
- `dev.archon-intelligence.stamping.generate.v1` - Intelligence generation

**Key Metrics**:

1. **Qdrant Metrics**:
   - Total vector count and growth rate
   - Indexed vectors vs total vectors
   - Collection status (green/yellow/red)
   - Segment count

2. **Processing Metrics**:
   - Total events processed
   - Success/failure counts
   - Success rate percentage
   - Average processing latency
   - Throughput (events per second)

3. **Service Health**:
   - Service status (healthy/degraded/unhealthy)
   - Response times
   - Dependency health

**Alert Thresholds** (default):

| Alert Type | Warning | Critical |
|------------|---------|----------|
| Consumer Lag | 100 messages | 500 messages |
| Success Rate | <80% | <50% |
| Service Response | >2s | >5s |
| Vector Growth | Stagnant 30min | Decreasing |

**Dashboard Output Example**:
```
================================================================================
📊 INGESTION PIPELINE DASHBOARD - 2025-10-29 18:15:30
================================================================================

🗄️  Qdrant Vector Database:
  Vectors: 25,249 (indexed: 25,249)
  Status: green
  Segments: 8
  Growth: +150 vectors

📨 Kafka Topics:
Topic                                              Messages     Lag      Rate (msg/s)
--------------------------------------------------------------------------------
tree.discover.v1                                   1,250        0        2.50
tree.index-project-completed.v1                    1,180        5        2.35
tree.index-project-failed.v1                       15           0        0.03
stamping.generate.v1                               980          2        1.95

⚙️  Processing Metrics:
  Total Processed: 1,195
  Success Rate: 98.7%
  Throughput: 2.38 events/s
  Avg Latency: 250ms

🏥 Service Health:
  archon-intelligence      healthy      Response: 125ms
  archon-bridge            healthy      Response: 95ms
  archon-search            healthy      Response: 180ms

✅ No active alerts

================================================================================
Press Ctrl+C to stop monitoring
```

**JSON Export Format**:
```json
{
  "monitoring_start": "2025-10-29T18:00:00Z",
  "monitoring_end": "2025-10-29T18:05:00Z",
  "duration_seconds": 300,
  "snapshot_count": 30,
  "snapshots": [...],
  "summary": {
    "vector_growth": 750,
    "total_events_processed": 1195,
    "final_success_rate": 0.987,
    "total_alerts": 2
  }
}
```

**When to Use**:
- During bulk repository ingestion operations
- Troubleshooting slow or failed indexing
- Verifying event pipeline end-to-end functionality
- Monitoring consumer lag and throughput
- Tracking vector database growth in real-time
- Production pipeline health monitoring

**Troubleshooting with Pipeline Monitor**:

```bash
# Problem: No vectors being indexed
# Solution: Monitor pipeline to identify bottleneck
python3 scripts/monitor_ingestion_pipeline.py --dashboard

# Check for:
# 1. High consumer lag → Consumer not processing events
# 2. Zero messages in completed topics → Ingestion not starting
# 3. High messages in failed topics → Processing errors
# 4. Stagnant vector growth → Indexing blocked

# Problem: Slow ingestion
# Solution: Monitor throughput and latency
python3 scripts/monitor_ingestion_pipeline.py --dashboard --interval 5

# Look for:
# - Low messages per second in topics
# - High average latency (>2000ms)
# - Service response times >1000ms
# - Consumer lag increasing over time
```

## Cache Management

### Valkey Distributed Cache

**Health Check**:
```bash
# Check cache is running
docker exec archon-valkey valkey-cli ping
# Expected: PONG

# Get cache info
docker exec archon-valkey valkey-cli INFO stats

# Get memory usage
docker exec archon-valkey valkey-cli INFO memory | grep used_memory_human
```

**Cache Metrics**:
```bash
# Via HTTP endpoint
curl http://localhost:8053/cache/metrics

# Expected response
{
  "status": "connected",
  "hit_rate": 0.67,
  "hits": 1250,
  "misses": 600,
  "memory_usage_mb": 128.5,
  "eviction_count": 45,
  "operations_per_sec": 150,
  "keys_count": 3450
}
```

**Cache Operations**:
```bash
# View all cache keys
docker exec archon-valkey valkey-cli KEYS "research:*"

# Get specific cache entry
docker exec archon-valkey valkey-cli GET "research:rag:abc123"

# Check TTL
docker exec archon-valkey valkey-cli TTL "research:rag:abc123"

# Manual invalidation
docker exec archon-valkey valkey-cli DEL "research:rag:abc123"

# Flush all cache (use with caution)
docker exec archon-valkey valkey-cli FLUSHDB
```

**HTTP Cache Management**:
```bash
# Invalidate specific key
curl -X POST http://localhost:8053/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"key": "research:rag:abc123"}'

# Invalidate all RAG cache
curl -X POST http://localhost:8053/cache/invalidate-pattern \
  -H "Content-Type: application/json" \
  -d '{"pattern": "research:rag:*"}'

# Clear entire cache
curl -X POST http://localhost:8053/cache/invalidate-all
```

**Cache Patterns**:
- `research:rag:*` - RAG search results (TTL: 5 minutes)
- `research:vector:*` - Vector search results (TTL: 5 minutes)
- `research:knowledge:*` - Knowledge graph results (TTL: 5 minutes)

## Troubleshooting

### No Vectors in Qdrant

**Symptoms**:
- `vectors_count: 0` in collection info
- Search returns no results
- `validate_data_integrity.py` reports unhealthy

**Resolution**:
```bash
# 1. Check Kafka consumer is running
docker ps | grep kafka-consumer
docker logs archon-kafka-consumer --tail 100

# 2. Verify topic subscription
docker exec omninode-bridge-redpanda rpk topic list | grep index

# 3. Check for consumer errors
docker logs archon-kafka-consumer | grep -i error

# 4. Re-index repository
poetry run python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name test-project \
  --kafka-servers 192.168.86.200:29092

# 5. Monitor ingestion
docker logs archon-kafka-consumer -f
```

### Search Returns 0 Results

**Symptoms**:
- API returns `{"results": [], "count": 0}`
- Qdrant has vectors but search fails

**Resolution**:
```bash
# 1. Verify Qdrant has vectors
curl http://localhost:6333/collections/archon_vectors | jq '.result.vectors_count'

# 2. Check search service logs
docker logs archon-search --tail 100

# 3. Validate collection name
curl http://localhost:6333/collections | jq '.result.collections[].name'

# 4. Test direct Qdrant search
curl -X POST http://localhost:6333/collections/archon_vectors/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}' | jq

# 5. Clear search cache
curl -X POST http://localhost:8053/cache/invalidate-pattern \
  -d '{"pattern": "research:*"}'
```

### Services Report Degraded

**Symptoms**:
- Health endpoint returns `"status": "degraded"`
- Some features work, others fail

**Resolution**:
```bash
# 1. Check which dependencies are down
curl http://localhost:8053/health | jq '.dependencies'

# 2. Memgraph connection (critical)
docker ps | grep memgraph
docker logs archon-memgraph --tail 50

# 3. Qdrant connection (critical)
curl http://localhost:6333/readiness

# 4. Cache connection (degrades performance only)
docker exec archon-valkey valkey-cli ping

# 5. Restart affected services
docker compose restart archon-intelligence
docker compose restart archon-search
```

### High Consumer Lag

**Symptoms**:
- Slow document indexing
- Events accumulating in topics
- Consumer lag > 100

**Resolution**:
```bash
# 1. Check consumer lag
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumers

# 2. Check consumer resource usage
docker stats archon-kafka-consumer --no-stream

# 3. Review consumer logs for slow operations
docker logs archon-kafka-consumer --tail 200 | grep -E "took.*ms"

# 4. Scale consumers (if supported)
docker compose up -d --scale archon-kafka-consumer=2

# 5. Monitor lag reduction
watch -n 5 'docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumers'
```

### Low Cache Hit Rate

**Symptoms**:
- Cache hit rate < 30%
- Slow query performance
- High backend service load

**Resolution**:
```bash
# 1. Check cache metrics
curl http://localhost:8053/cache/metrics | jq

# 2. Verify cache TTL configuration
docker exec archon-valkey valkey-cli CONFIG GET maxmemory*

# 3. Check eviction rate
docker exec archon-valkey valkey-cli INFO stats | grep evicted_keys

# 4. Increase cache memory (if needed)
# Edit docker-compose.yml: --maxmemory 1gb

# 5. Warm up cache with common queries
curl -X POST http://localhost:8055/search/rag -d '{"query": "common query 1"}'
curl -X POST http://localhost:8055/search/rag -d '{"query": "common query 2"}'
```

## CI/CD Integration

### GitHub Actions Example

**Basic Health Check**:
```yaml
name: Archon Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Start Archon services
        run: docker compose up -d

      - name: Wait for services
        run: sleep 30

      - name: Validate integrations
        run: |
          ./scripts/validate_integrations.sh
          if [ $? -ne 0 ]; then
            echo "❌ Integration validation failed"
            exit 1
          fi

      - name: Run data integrity check
        run: |
          poetry install
          poetry run python3 scripts/validate_data_integrity.py --json > results.json
          cat results.json | jq

      - name: Upload validation results
        uses: actions/upload-artifact@v3
        with:
          name: validation-results
          path: results.json
```

**Advanced Monitoring**:
```yaml
- name: Comprehensive validation
  run: |
    # Service health
    for port in 8053 8054 8055 8156; do
      STATUS=$(curl -s http://localhost:$port/health | jq -r '.status')
      if [ "$STATUS" != "healthy" ]; then
        echo "❌ Service on port $port is $STATUS"
        exit 1
      fi
    done

    # Data validation
    poetry run python3 scripts/validate_data_integrity.py --json > /tmp/validation.json
    EXIT_CODE=$?

    # Performance check
    RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" http://localhost:8055/search/rag \
      -X POST -d '{"query": "test"}')
    if (( $(echo "$RESPONSE_TIME > 1.0" | bc -l) )); then
      echo "⚠️  Slow response time: ${RESPONSE_TIME}s"
    fi

    exit $EXIT_CODE
```

### Kubernetes Health Probes

**Liveness Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8053
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Readiness Probe**:
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8053
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  successThreshold: 1
  failureThreshold: 3
```

## Monitoring Best Practices

### Continuous Monitoring Strategy

**Production Deployment**:
1. **Service Health**: Check every 5 minutes
2. **Data Integrity**: Validate every 30 minutes
3. **Cache Metrics**: Monitor hit rate every 15 minutes
4. **Consumer Lag**: Alert if lag > 100 for 5+ minutes
5. **Vector Count**: Track growth trends daily

**Alert Thresholds**:
| Metric | Warning | Critical |
|--------|---------|----------|
| Service Health | degraded | unhealthy |
| Vector Count | No growth 24h | Decreasing |
| Cache Hit Rate | <40% | <20% |
| Consumer Lag | >100 | >500 |
| Query Time | >2s | >5s |
| Memory Usage | >80% | >95% |

### Monitoring Script

**Automated Health Check** (`scripts/monitor_health.sh`):
```bash
#!/bin/bash

# Monitor Archon health continuously
while true; do
  echo "=== $(date) ==="

  # Service health
  for port in 8053 8054 8055; do
    STATUS=$(curl -s http://localhost:$port/health | jq -r '.status')
    echo "Port $port: $STATUS"
  done

  # Data integrity
  poetry run python3 scripts/validate_data_integrity.py --json | \
    jq -r '"Data: \(.overall_status) (\(.healthy_components)/\(.total_components))"'

  # Cache metrics
  curl -s http://localhost:8053/cache/metrics | \
    jq -r '"Cache: Hit rate \(.hit_rate), Memory \(.memory_usage_mb)MB"'

  # Consumer lag
  LAG=$(docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumers | \
    grep TOTAL-LAG | awk '{print $2}')
  echo "Kafka lag: $LAG"

  echo "---"
  sleep 300  # 5 minutes
done
```

### Grafana Dashboard (Future)

**Recommended Metrics**:
- Service uptime and response times
- Vector count growth over time
- Cache hit rate trends
- Consumer lag and throughput
- Query latency percentiles (p50, p95, p99)
- Error rates by service

**Prometheus Metrics** (to be implemented):
```
archon_service_health{service="intelligence"} 1
archon_vector_count 25249
archon_cache_hit_rate 0.67
archon_consumer_lag 0
archon_query_duration_seconds{quantile="0.95"} 0.125
```

## Summary

**Quick Reference**:
- **Health Checks**: `curl http://localhost:8053/health`
- **Data Validation**: `poetry run python3 scripts/validate_data_integrity.py`
- **Integration Tests**: `./scripts/validate_integrations.sh`
- **Ingestion Pipeline Monitor**: `python3 scripts/monitor_ingestion_pipeline.py --dashboard`
- **Cache Management**: `curl http://localhost:8053/cache/metrics`
- **Kafka Health**: `docker exec omninode-bridge-redpanda rpk cluster health`

**Emergency Response**:
1. Check service health endpoints
2. Review Docker logs for errors
3. Validate data layer (Qdrant, Memgraph)
4. Check Kafka consumer lag
5. Clear cache if needed
6. Restart affected services

**Support**:
- Documentation: `/docs/OBSERVABILITY.md`
- Validation Guide: `/docs/VALIDATION_SCRIPT.md`
- Architecture: `/docs/architecture/`
- Issues: Report via project issue tracker

---

**Archon Intelligence Platform** - Production observability and monitoring guide
