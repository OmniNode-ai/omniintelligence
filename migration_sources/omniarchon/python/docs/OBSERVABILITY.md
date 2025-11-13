# Archon Observability & Monitoring

**Comprehensive validation and monitoring tools for production deployment**

## Overview

Archon provides a complete observability suite for monitoring the event-driven intelligence pipeline. This includes real-time monitoring, health validation, performance tracking, and alerting capabilities.

## Quick Reference

| Tool | Purpose | Usage |
|------|---------|-------|
| **monitor_ingestion_pipeline.py** | Real-time pipeline monitoring | `python3 scripts/monitor_ingestion_pipeline.py --dashboard` |
| **validate_integrations.sh** | End-to-end integration testing | `./scripts/validate_integrations.sh` |
| **validate_data_integrity.py** | Data layer validation | `python3 scripts/validate_data_integrity.py` |
| **health_monitor.py** | Service health monitoring | `python3 scripts/health_monitor.py --dashboard` |
| **monitor_performance.py** | Performance metrics tracking | `python3 scripts/monitor_performance.py` |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   OBSERVABILITY LAYER                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Ingestion       │  │  Service Health  │               │
│  │  Pipeline        │  │  Monitoring      │               │
│  │  Monitor         │  │                  │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Data Integrity  │  │  Performance     │               │
│  │  Validation      │  │  Tracking        │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    ARCHON SERVICES                           │
│                                                              │
│  Event Bus → Intelligence → Bridge → Search → Storage       │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring Scripts

### 1. Ingestion Pipeline Monitor

**Purpose**: Real-time monitoring of the event-driven ingestion pipeline

**Location**: `scripts/monitor_ingestion_pipeline.py`

**Features**:
- ✅ Real-time Kafka/Redpanda topic monitoring
- ✅ Qdrant vector count growth tracking
- ✅ Service health checks (intelligence, bridge, search)
- ✅ Consumer lag monitoring with configurable thresholds
- ✅ Success/failure rate calculations
- ✅ Dashboard output with auto-refresh
- ✅ JSON export capability
- ✅ Webhook alerting (Slack, etc.)

**Basic Usage**:

```bash
# Real-time dashboard (continuous monitoring)
python3 scripts/monitor_ingestion_pipeline.py --dashboard

# Monitor for specific duration
python3 scripts/monitor_ingestion_pipeline.py --dashboard --duration 300

# Export metrics to JSON
python3 scripts/monitor_ingestion_pipeline.py --duration 120 --json metrics.json

# Custom check interval (default: 10 seconds)
python3 scripts/monitor_ingestion_pipeline.py --dashboard --interval 5
```

**Advanced Usage**:

```bash
# Custom alert thresholds
python3 scripts/monitor_ingestion_pipeline.py \
  --dashboard \
  --consumer-lag-warning 50 \
  --consumer-lag-critical 200

# With Slack alerting
python3 scripts/monitor_ingestion_pipeline.py \
  --dashboard \
  --alert-webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Monitor specific Redpanda instance
python3 scripts/monitor_ingestion_pipeline.py \
  --dashboard \
  --redpanda-host 192.168.86.200 \
  --redpanda-port 29092
```

**Dashboard Output**:

```
╔════════════════════════════════════════════════════════════════╗
║       Archon Ingestion Pipeline Monitor                       ║
╠════════════════════════════════════════════════════════════════╣
║  Timestamp: 2025-10-29T15:30:45.123456                        ║
╚════════════════════════════════════════════════════════════════╝

📊 SERVICE HEALTH
──────────────────────────────────────────────────────────────────
  archon-intelligence  ✅ HEALTHY      Response: 45.2ms
  archon-bridge        ✅ HEALTHY      Response: 32.1ms
  archon-search        ✅ HEALTHY      Response: 56.8ms

📨 KAFKA TOPIC METRICS
──────────────────────────────────────────────────────────────────
  tree.discover.v1
    Messages:     12,345
    Consumer Lag:      23
    Partitions:   3   Replicas:  1
  tree.index-project-completed.v1
    Messages:      8,901
    Consumer Lag:       5
    Partitions:   3   Replicas:  1
  tree.index-project-failed.v1
    Messages:         89
    Consumer Lag:       0
    Partitions:   3   Replicas:  1

🔢 QDRANT VECTOR METRICS
──────────────────────────────────────────────────────────────────
  Collection: archon
  Points Count: 145,678
  Indexed Vectors: 145,678

📈 PIPELINE PERFORMANCE
──────────────────────────────────────────────────────────────────
  Success Rate: 99.01%
  Vector Growth: +1,234 points

Last updated: 2025-10-29 15:30:45
Press Ctrl+C to stop monitoring
```

**Monitored Topics**:
- `dev.archon-intelligence.tree.discover.v1` - Tree discovery events
- `dev.archon-intelligence.tree.index-project-completed.v1` - Successful indexing
- `dev.archon-intelligence.tree.index-project-failed.v1` - Failed indexing
- `dev.archon-intelligence.stamping.generate.v1` - Intelligence generation

**Alert Thresholds**:

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Consumer Lag | 100 msgs | 500 msgs | Check consumer health |
| Success Rate | <95% | <90% | Review failed events |
| Service Health | Degraded | Unhealthy | Restart service |
| Vector Growth | No growth 1h | Decreasing | Check indexing |

**JSON Export Format**:

```json
{
  "monitoring_session": {
    "start_time": "2025-10-29T15:30:00.000000",
    "end_time": "2025-10-29T15:35:00.000000",
    "duration_seconds": 300,
    "interval_seconds": 10,
    "snapshots_collected": 30
  },
  "metrics": [
    {
      "timestamp": "2025-10-29T15:30:00.000000",
      "services": [...],
      "topics": [...],
      "vectors": {...},
      "success_rate": 99.01,
      "alerts": [...]
    }
  ]
}
```

### 2. Service Health Monitor

**Purpose**: Real-time health monitoring with automatic recovery

**Location**: `scripts/health_monitor.py`

**Usage**:

```bash
# Basic health check
curl http://localhost:8053/health  # Intelligence service
curl http://localhost:8054/health  # Bridge service
curl http://localhost:8055/health  # Search service

# Real-time monitoring dashboard
python3 scripts/health_monitor.py --dashboard

# With auto-recovery
python3 scripts/health_monitor.py --dashboard --auto-recovery

# With alerting
python3 scripts/health_monitor.py --alert-webhook https://hooks.slack.com/services/YOUR/WEBHOOK
```

### 3. Data Integrity Validator

**Purpose**: Validate data layer components (Memgraph, Qdrant, Search)

**Location**: `scripts/validate_data_integrity.py`

**Usage**:

```bash
# Quick validation
poetry run python3 scripts/validate_data_integrity.py

# Detailed output
poetry run python3 scripts/validate_data_integrity.py --verbose

# JSON output for CI/CD
poetry run python3 scripts/validate_data_integrity.py --json
```

**Exit Codes**:
- `0` - Healthy (3-4 components working)
- `1` - Degraded (2 components working)
- `2` - Unhealthy (0-1 components working)

### 4. Integration Validator

**Purpose**: End-to-end integration testing

**Location**: `scripts/validate_integrations.sh`

**Usage**:

```bash
# Standard validation
./scripts/validate_integrations.sh

# Verbose mode
./scripts/validate_integrations.sh --verbose
```

### 5. Performance Monitor

**Purpose**: Track performance metrics and baselines

**Location**: `scripts/monitor_performance.py`

**Usage**:

```bash
# Basic performance check
python3 scripts/monitor_performance.py

# Extended monitoring with export
python3 scripts/monitor_performance.py --duration 300 --output metrics.json
```

## Event Bus Monitoring

### Redpanda/Kafka Health

**Check cluster health**:

```bash
# Cluster info
docker exec omninode-bridge-redpanda rpk cluster info

# Cluster health
docker exec omninode-bridge-redpanda rpk cluster health

# Topic list
docker exec omninode-bridge-redpanda rpk topic list

# Topic details
docker exec omninode-bridge-redpanda rpk topic describe dev.archon-intelligence.tree.discover.v1
```

**Consumer Group Monitoring**:

```bash
# List consumer groups
docker exec omninode-bridge-redpanda rpk group list

# Consumer group details
docker exec omninode-bridge-redpanda rpk group describe archon-kafka-consumer

# Consumer lag
docker exec omninode-bridge-redpanda rpk group describe archon-kafka-consumer --format json | \
  jq '.members[].partitions[] | {topic: .topic, partition: .partition, lag: .lag}'
```

## Cache Management

### Valkey/Redis Cache

**Check cache health**:

```bash
# Ping test
docker exec archon-valkey valkey-cli ping

# Cache stats
docker exec archon-valkey valkey-cli INFO stats

# Memory usage
docker exec archon-valkey valkey-cli INFO memory
```

**Cache key patterns**:

```bash
# List research cache keys
docker exec archon-valkey valkey-cli KEYS "research:*"

# List RAG cache keys
docker exec archon-valkey valkey-cli KEYS "research:rag:*"

# Get cache value
docker exec archon-valkey valkey-cli GET "research:rag:some-key"

# Clear specific pattern
docker exec archon-valkey valkey-cli --scan --pattern "research:*" | xargs docker exec -i archon-valkey valkey-cli DEL
```

**HTTP Cache API**:

```bash
# Cache health
curl http://localhost:8053/cache/health

# Cache metrics
curl http://localhost:8053/cache/metrics

# Invalidate pattern
curl -X POST http://localhost:8053/cache/invalidate-pattern \
  -H "Content-Type: application/json" \
  -d '{"pattern": "research:rag:*"}'
```

## Vector Database Monitoring

### Qdrant

**Collection info**:

```bash
# Collection details
curl http://localhost:6333/collections/archon

# Point count
curl http://localhost:6333/collections/archon/points/count

# Cluster info
curl http://localhost:6333/cluster
```

## Knowledge Graph Monitoring

### Memgraph

**Query node counts**:

```bash
# Connect to Memgraph
docker exec -it memgraph mgconsole

# Count documents
MATCH (n:Document) RETURN count(n);

# Count relationships
MATCH ()-[r]->() RETURN count(r);

# Check node labels
MATCH (n) RETURN DISTINCT labels(n);
```

## Alert Configuration

### Alert Thresholds

**Service Health**:
- Warning: Service responds but slow (>1s)
- Critical: Service unhealthy or unresponsive

**Consumer Lag**:
- Warning: >100 messages (default)
- Critical: >500 messages (default)

**Success Rate**:
- Warning: <95%
- Critical: <90%

**Vector Growth**:
- Warning: No growth for 1 hour
- Critical: Decreasing count

**Query Performance**:
- Warning: >2s response time
- Critical: >5s response time

### Webhook Alerting

**Slack Integration**:

```bash
# Set webhook URL
export ALERT_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Run with alerting
python3 scripts/monitor_ingestion_pipeline.py \
  --dashboard \
  --alert-webhook "$ALERT_WEBHOOK"
```

**Alert Payload Format**:

```json
{
  "text": "🚨 Archon Ingestion Pipeline Alerts",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "⚠️  Topic dev.archon-intelligence.tree.discover.v1 has lag of 150 (threshold: 100)\n🚨 CRITICAL: Service archon-bridge unhealthy"
      }
    }
  ]
}
```

## Production Monitoring Best Practices

### Continuous Monitoring

**Run in tmux/screen**:

```bash
# Start tmux session
tmux new -s archon-monitor

# Run dashboard
python3 scripts/monitor_ingestion_pipeline.py --dashboard

# Detach: Ctrl+B, D
# Reattach: tmux attach -t archon-monitor
```

### Scheduled Validation

**Add to crontab**:

```bash
# Every 30 minutes: integration validation
*/30 * * * * cd /path/to/archon && ./scripts/validate_integrations.sh >> /var/log/archon/validation.log 2>&1

# Every hour: data integrity check
0 * * * * cd /path/to/archon && poetry run python3 scripts/validate_data_integrity.py --json /var/log/archon/integrity-$(date +\%Y\%m\%d-\%H).json

# Daily: performance baseline
0 0 * * * cd /path/to/archon && python3 scripts/monitor_performance.py --duration 3600 --output /var/log/archon/perf-$(date +\%Y\%m\%d).json
```

### Retention Policy

**Log Rotation**:

```bash
# /etc/logrotate.d/archon
/var/log/archon/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}

/var/log/archon/*.json {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

## Troubleshooting

### Common Issues

**Issue**: Consumer lag growing

**Diagnosis**:
```bash
# Check consumer health
docker logs archon-kafka-consumer --tail 100

# Check consumer group
docker exec omninode-bridge-redpanda rpk group describe archon-kafka-consumer
```

**Solution**:
- Restart consumer: `docker restart archon-kafka-consumer`
- Check for errors in consumer logs
- Verify Redpanda connectivity

---

**Issue**: Service unhealthy

**Diagnosis**:
```bash
# Check service logs
docker logs archon-intelligence --tail 100
docker logs archon-bridge --tail 100
docker logs archon-search --tail 100

# Check dependencies
curl http://localhost:6333/collections/archon  # Qdrant
docker exec memgraph mgconsole -e "MATCH (n) RETURN count(n) LIMIT 1;"  # Memgraph
```

**Solution**:
- Restart service: `docker restart <service-name>`
- Check .env configuration
- Verify network connectivity

---

**Issue**: No vector growth

**Diagnosis**:
```bash
# Check indexing events
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.tree.index-project-completed.v1 --num 10

# Check failed events
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.tree.index-project-failed.v1 --num 10

# Check Qdrant logs
docker logs qdrant --tail 100
```

**Solution**:
- Review failed event messages
- Check Qdrant connectivity
- Verify intelligence service health

---

**Issue**: High query latency

**Diagnosis**:
```bash
# Check cache hit rate
curl http://localhost:8053/cache/metrics

# Check Qdrant performance
curl http://localhost:6333/collections/archon/points/count

# Check Valkey stats
docker exec archon-valkey valkey-cli INFO stats
```

**Solution**:
- Warm up cache: Run common queries
- Optimize Qdrant index
- Increase Valkey memory limit

## Metrics Reference

### Pipeline Metrics

| Metric | Description | Target | Critical |
|--------|-------------|--------|----------|
| Message Count | Total messages in topic | Growing | Decreasing |
| Consumer Lag | Messages waiting to process | <100 | >500 |
| Success Rate | % successful indexing | >95% | <90% |
| Vector Count | Total vectors in Qdrant | Growing | Stale |
| Response Time | Service response time | <1s | >5s |

### Service Metrics

| Service | Port | Health Endpoint | Target Response |
|---------|------|-----------------|-----------------|
| archon-intelligence | 8053 | /health | <100ms |
| archon-bridge | 8054 | /health | <50ms |
| archon-search | 8055 | /health | <100ms |
| Qdrant | 6333 | /collections/archon | <50ms |
| Memgraph | 7687 | (Cypher query) | <100ms |

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Archon Health Check

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Validate data integrity
        run: |
          cd python
          poetry install
          poetry run python3 scripts/validate_data_integrity.py --json

      - name: Monitor pipeline
        run: |
          cd python
          python3 scripts/monitor_ingestion_pipeline.py --duration 60 --json metrics.json

      - name: Upload metrics
        uses: actions/upload-artifact@v3
        with:
          name: health-metrics
          path: python/metrics.json
```

## Related Documentation

- [SLACK_ALERTING.md](SLACK_ALERTING.md) - Container health monitoring with Slack
- [TESTING.md](TESTING.md) - Testing strategy and validation
- [EVENT_DRIVEN_ARCHITECTURE.md](intelligence/EVENT_DRIVEN_ARCHITECTURE.md) - Event bus architecture
- [ALERT_RUNBOOK.md](ALERT_RUNBOOK.md) - Alert handling runbook

---

**Archon Observability**: Production-ready monitoring for intelligence-driven development.
