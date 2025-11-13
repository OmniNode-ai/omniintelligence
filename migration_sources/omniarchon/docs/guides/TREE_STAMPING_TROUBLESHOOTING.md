# Tree Stamping Troubleshooting Guide

**Version**: 1.0.0
**Status**: Operational Guide
**Created**: 2025-10-27
**Audience**: DevOps, SRE, Support Engineers

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Common Issues](#common-issues)
3. [Event Flow Debugging](#event-flow-debugging)
4. [Performance Issues](#performance-issues)
5. [DLQ Management](#dlq-management)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Recovery Procedures](#recovery-procedures)
8. [CLI Tools Reference](#cli-tools-reference)

---

## Quick Diagnostics

### Health Check Workflow

```bash
# 1. Check all service health
curl http://localhost:8053/health  # Intelligence service
curl http://localhost:8054/health  # Bridge service
curl http://localhost:8058/health  # OnexTree service
curl http://localhost:8057/health  # Metadata stamping

# 2. Check Kafka/Redpanda health
docker exec omninode-bridge-redpanda rpk cluster health
docker exec omninode-bridge-redpanda rpk cluster info

# 3. Check consumer groups
docker exec omninode-bridge-redpanda rpk group list
docker exec omninode-bridge-redpanda rpk group describe tree-discovery-group
docker exec omninode-bridge-redpanda rpk group describe stamping-generator-group
docker exec omninode-bridge-redpanda rpk group describe indexing-processor-group

# 4. Check topic lag
docker exec omninode-bridge-redpanda rpk group describe tree-discovery-group --state

# 5. Check DLQ topics for errors
docker exec omninode-bridge-redpanda rpk topic list | grep dlq
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.tree.discover.v1.dlq --num 10
```

### Quick Status Dashboard

```bash
#!/bin/bash
# tree-stamping-status.sh - Quick status check

echo "=== Tree Stamping System Status ==="
echo ""

# Service health
echo "Services:"
echo "  Intelligence: $(curl -s http://localhost:8053/health | jq -r .status)"
echo "  Bridge: $(curl -s http://localhost:8054/health | jq -r .status)"
echo "  OnexTree: $(curl -s http://localhost:8058/health | jq -r .status)"
echo "  Metadata Stamping: $(curl -s http://localhost:8057/health | jq -r .status)"
echo ""

# Kafka health
echo "Kafka/Redpanda:"
KAFKA_HEALTH=$(docker exec omninode-bridge-redpanda rpk cluster health --format json 2>/dev/null | jq -r '.healthy')
echo "  Cluster: ${KAFKA_HEALTH:-UNKNOWN}"
echo ""

# Consumer lag
echo "Consumer Lag:"
for group in tree-discovery-group stamping-generator-group indexing-processor-group; do
    LAG=$(docker exec omninode-bridge-redpanda rpk group describe $group --format json 2>/dev/null | jq -r '.members[0].lag // "N/A"')
    echo "  $group: $LAG"
done
echo ""

# DLQ counts
echo "Dead Letter Queue:"
for topic in tree.discover stamping.generate tree.index; do
    COUNT=$(docker exec omninode-bridge-redpanda rpk topic consume "dev.archon-intelligence.$topic.v1.dlq" --num 1000 --format json 2>/dev/null | wc -l)
    if [ $COUNT -gt 0 ]; then
        echo "  $topic: $COUNT events (WARNING)"
    else
        echo "  $topic: 0 events (OK)"
    fi
done
```

---

## Common Issues

### Issue 1: High Consumer Lag

**Symptoms**:
- Consumer lag > 10,000 messages
- Events not processed in reasonable time
- Dashboard shows increasing backlog

**Diagnosis**:
```bash
# Check consumer lag
docker exec omninode-bridge-redpanda rpk group describe stamping-generator-group

# Check consumer logs for errors
docker logs archon-intelligence | grep -i "stamping.*error" | tail -50

# Check partition assignment
docker exec omninode-bridge-redpanda rpk group describe stamping-generator-group --format json | jq '.members[].assigned_partitions'
```

**Root Causes**:
1. **Slow Consumer Processing**
   - Downstream services (OnexTree, Metadata Stamping) slow/down
   - Network latency to Qdrant/Memgraph
   - CPU/memory resource constraints

2. **Consumer Crash/Restart**
   - Consumer repeatedly crashing
   - Pod eviction in Kubernetes
   - OOM (Out of Memory) errors

3. **Event Spike**
   - Large project ingestion (10k+ files)
   - Multiple concurrent ingestion requests
   - No backpressure/throttling

**Solutions**:

```bash
# 1. Scale consumer horizontally (add more consumers)
# Edit docker-compose.yml or Kubernetes deployment
# Increase replicas for stamping-generator-consumer from 1 to 3

# 2. Check downstream service health
curl http://localhost:8057/health
# If degraded, restart service:
docker restart metadata-stamping

# 3. Increase consumer parallelism (if not OOM)
# Edit consumer configuration:
# max_poll_records: 100 → 200
# semaphore: 10 → 20

# 4. Temporarily pause producer if lag critical
# Manually stop producer:
docker stop tree-discovery-producer

# Wait for lag to decrease, then resume:
docker start tree-discovery-producer
```

---

### Issue 2: Events Stuck in DLQ

**Symptoms**:
- DLQ topic has > 10 events
- Alert: "DLQ overflow detected"
- Files not indexed despite discovery

**Diagnosis**:
```bash
# View DLQ events
docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.stamping.generate.v1.dlq \
  --num 20 --format json | jq -r '.value | fromjson'

# Group by error type
docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.stamping.generate.v1.dlq \
  --num 100 --format json | \
  jq -r '.value | fromjson | .error_type' | sort | uniq -c
```

**Common Error Patterns**:

1. **FILE_NOT_FOUND (Error Code: FILE_NOT_FOUND)**
   ```
   Error: File '/project/src/deleted.py' not found
   ```
   **Cause**: File deleted between discovery and stamping
   **Solution**: Skip file, do not reprocess

2. **SERVICE_UNAVAILABLE (Error Code: INTELLIGENCE_SERVICE_ERROR)**
   ```
   Error: Intelligence service timeout after 30s
   ```
   **Cause**: Intelligence service overloaded/down
   **Solution**: Restart service, reprocess events after recovery

3. **INVALID_CONTENT (Error Code: ENCODING_ERROR)**
   ```
   Error: Cannot decode file with UTF-8 encoding
   ```
   **Cause**: Binary file or non-UTF-8 encoding
   **Solution**: Update exclude patterns to skip binary files

**Reprocessing DLQ Events**:

```bash
# Reprocess specific correlation_id
python3 /tools/reprocess_dlq.py \
  --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq \
  --correlation-id abc-123-def-456 \
  --republish

# Reprocess all DLQ events (use with caution!)
python3 /tools/reprocess_dlq.py \
  --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq \
  --limit 1000 \
  --republish \
  --confirm

# Preview DLQ events without reprocessing
python3 /tools/reprocess_dlq.py \
  --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq \
  --dry-run
```

---

### Issue 3: Missing Files in Search Results

**Symptoms**:
- File discovered but not searchable
- Search returns 0 results for known files
- Qdrant/Memgraph missing entries

**Diagnosis**:
```bash
# 1. Trace event flow by correlation_id
CORRELATION_ID="abc-123-def-456"

# Check discovery event
docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.tree.discover-completed.v1 \
  --format json | jq "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\")"

# Check stamping events
docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.stamping.generate-completed.v1 \
  --format json | jq "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\")" | wc -l

# Check indexing events
docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.tree.index-completed.v1 \
  --format json | jq "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\")" | wc -l

# 2. Check Qdrant directly
curl -X POST http://localhost:6333/collections/file_locations/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"filter": {"must": [{"key": "project_name", "match": {"value": "omniarchon"}}]}, "limit": 10}'

# 3. Check Memgraph directly
docker exec archon-memgraph mgconsole --username "" --password "" \
  --execute "MATCH (f:File {project_name: 'omniarchon'}) RETURN count(f);"
```

**Root Causes**:
1. **Indexing Consumer Down**
   - Consumer crashed/restarted
   - Not processing `tree.index.v1` events

2. **Qdrant/Memgraph Unavailable**
   - Services down during indexing
   - Network connectivity issues

3. **Event Lost in Transit**
   - Kafka partition failure
   - Consumer committed offset before processing

**Solutions**:

```bash
# 1. Check indexing consumer status
docker logs archon-intelligence | grep -i "indexing.*processor" | tail -50

# If consumer down, restart:
docker restart archon-intelligence

# 2. Verify Qdrant/Memgraph connectivity
docker exec archon-intelligence curl http://qdrant:6333/health
docker exec archon-intelligence curl http://memgraph:7687

# 3. Reprocess stamping-completed events (re-trigger indexing)
python3 /tools/replay_events.py \
  --topic dev.archon-intelligence.stamping.generate-completed.v1 \
  --correlation-id "$CORRELATION_ID" \
  --target-topic dev.archon-intelligence.tree.index.v1
```

---

### Issue 4: Slow Project Ingestion

**Symptoms**:
- Project ingestion takes > 5 minutes for 1000 files
- Throughput < 1000 files/minute
- High CPU/memory usage on consumers

**Diagnosis**:
```bash
# 1. Check processing time metrics
curl http://localhost:8053/metrics | grep tree_event_processing_seconds

# 2. Check cache hit rate
curl http://localhost:8053/cache/metrics | jq '.hit_rate'

# 3. Profile consumer performance
docker stats archon-intelligence --no-stream

# 4. Check downstream service latency
curl http://localhost:8057/metrics | grep stamping_latency_ms_p95
```

**Optimization Steps**:

```bash
# 1. Warm cache before ingestion
python3 /tools/warm_cache.py --project omniarchon

# 2. Increase consumer parallelism
# Edit consumer config:
# max_concurrent_events: 10 → 20
# max_poll_records: 100 → 200

# 3. Enable batch processing
# Edit stamping consumer:
# batch_size: 50  # Process 50 files at once

# 4. Scale consumers horizontally
docker-compose up -d --scale stamping-generator-consumer=3

# 5. Optimize Qdrant batch upsert
# Edit indexing consumer:
# qdrant_batch_size: 50 → 100
```

---

## Event Flow Debugging

### Trace Complete Event Flow

**Python Script**: `trace_event_flow.py`

```python
#!/usr/bin/env python3
"""
Trace event flow by correlation_id across all topics.

Usage:
    python3 trace_event_flow.py --correlation-id abc-123-def-456
"""

import argparse
import json
import subprocess
from datetime import datetime


def consume_topic(topic: str, correlation_id: str) -> list[dict]:
    """Consume events from topic matching correlation_id."""
    cmd = [
        "docker", "exec", "omninode-bridge-redpanda", "rpk", "topic", "consume",
        topic, "--num", "10000", "--format", "json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    events = []

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue

        try:
            msg = json.loads(line)
            payload = json.loads(msg['value'])

            if payload.get('payload', {}).get('correlation_id') == correlation_id:
                events.append({
                    'topic': topic,
                    'partition': msg['partition'],
                    'offset': msg['offset'],
                    'timestamp': msg['timestamp'],
                    'payload': payload
                })
        except Exception as e:
            continue

    return events


def main():
    parser = argparse.ArgumentParser(description='Trace event flow by correlation_id')
    parser.add_argument('--correlation-id', required=True, help='Correlation ID to trace')
    args = parser.parse_args()

    correlation_id = args.correlation_id

    # Topics to check
    topics = [
        'dev.archon-intelligence.tree.discover.v1',
        'dev.archon-intelligence.tree.discover-completed.v1',
        'dev.archon-intelligence.tree.discover-failed.v1',
        'dev.archon-intelligence.stamping.generate.v1',
        'dev.archon-intelligence.stamping.generate-completed.v1',
        'dev.archon-intelligence.stamping.generate-failed.v1',
        'dev.archon-intelligence.tree.index.v1',
        'dev.archon-intelligence.tree.index-completed.v1',
        'dev.archon-intelligence.tree.index-failed.v1',
    ]

    print(f"Tracing correlation_id: {correlation_id}\n")

    all_events = []
    for topic in topics:
        events = consume_topic(topic, correlation_id)
        all_events.extend(events)

    # Sort by timestamp
    all_events.sort(key=lambda e: e['timestamp'])

    # Display results
    if not all_events:
        print(f"No events found with correlation_id: {correlation_id}")
        return

    print(f"Found {len(all_events)} events:\n")

    for i, event in enumerate(all_events, 1):
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        print(f"{i}. [{timestamp.strftime('%H:%M:%S.%f')[:-3]}] {event['topic']}")
        print(f"   Partition: {event['partition']}, Offset: {event['offset']}")
        print(f"   Payload: {json.dumps(event['payload']['payload'], indent=2)[:200]}...")
        print()

    # Check for gaps
    discovery_complete = any('discover-completed' in e['topic'] for e in all_events)
    stamping_complete = any('stamping.*completed' in e['topic'] for e in all_events)
    indexing_complete = any('index-completed' in e['topic'] for e in all_events)

    print("Status Summary:")
    print(f"  Discovery: {'✓' if discovery_complete else '✗'}")
    print(f"  Stamping: {'✓' if stamping_complete else '✗'}")
    print(f"  Indexing: {'✓' if indexing_complete else '✗'}")


if __name__ == '__main__':
    main()
```

---

## Performance Issues

### Performance Benchmarking

```bash
#!/bin/bash
# benchmark_tree_stamping.sh - Performance benchmark

PROJECT_PATH="/test/large-project"  # 10,000 files
PROJECT_NAME="benchmark-test"

echo "Starting benchmark: $PROJECT_NAME"
echo "Project path: $PROJECT_PATH"
echo "Expected files: 10,000"
echo ""

# Start timer
START_TIME=$(date +%s)

# Trigger ingestion
CORRELATION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
echo "Correlation ID: $CORRELATION_ID"

# Publish discovery request
python3 /tools/publish_event.py \
  --topic dev.archon-intelligence.tree.discover.v1 \
  --payload "{\"project_path\": \"$PROJECT_PATH\", \"project_name\": \"$PROJECT_NAME\", \"correlation_id\": \"$CORRELATION_ID\"}"

echo "Discovery request published, waiting for completion..."

# Wait for completion (poll every 5 seconds)
COMPLETED=false
TIMEOUT=600  # 10 minutes
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))

    # Check indexing completion
    INDEX_COUNT=$(docker exec omninode-bridge-redpanda rpk topic consume \
      dev.archon-intelligence.tree.index-completed.v1 \
      --format json --num 100000 | \
      jq -r "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\")" | \
      wc -l)

    if [ $INDEX_COUNT -ge 10000 ]; then
        COMPLETED=true
        break
    fi

    echo "  Indexed: $INDEX_COUNT / 10,000 files ($ELAPSED seconds elapsed)"
done

# End timer
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Calculate metrics
THROUGHPUT=$((10000 / DURATION))  # files per second

echo ""
echo "=== Benchmark Results ==="
echo "Duration: ${DURATION}s"
echo "Throughput: ${THROUGHPUT} files/second"
echo "Status: $([ $COMPLETED == true ] && echo 'COMPLETED' || echo 'TIMEOUT')"

# Check for errors in DLQ
DLQ_COUNT=$(docker exec omninode-bridge-redpanda rpk topic consume \
  dev.archon-intelligence.stamping.generate.v1.dlq \
  --format json --num 10000 | \
  jq -r "select(.value | fromjson | .correlation_id == \"$CORRELATION_ID\")" | \
  wc -l)

echo "DLQ Events: $DLQ_COUNT"

# Performance targets
echo ""
echo "=== Performance Targets ==="
echo "  Throughput: $([ $THROUGHPUT -ge 166 ] && echo '✓ PASS' || echo '✗ FAIL') (target: ≥166 files/sec)"
echo "  Duration: $([ $DURATION -le 60 ] && echo '✓ PASS' || echo '✗ FAIL') (target: ≤60s for 10k files)"
echo "  DLQ Rate: $([ $DLQ_COUNT -le 10 ] && echo '✓ PASS' || echo '✗ FAIL') (target: ≤0.1%)"
```

---

## DLQ Management

### DLQ Reprocessing Tool

**Python Script**: `reprocess_dlq.py`

```python
#!/usr/bin/env python3
"""
Reprocess events from Dead Letter Queue.

Usage:
    # Dry run (preview only)
    python3 reprocess_dlq.py --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq --dry-run

    # Reprocess specific correlation_id
    python3 reprocess_dlq.py --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq --correlation-id abc-123

    # Reprocess all events (requires confirmation)
    python3 reprocess_dlq.py --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq --limit 100 --republish --confirm
"""

import argparse
import json
import subprocess
from typing import Optional


def consume_dlq(dlq_topic: str, correlation_id: Optional[str] = None, limit: int = 1000) -> list[dict]:
    """Consume events from DLQ topic."""
    cmd = [
        "docker", "exec", "omninode-bridge-redpanda", "rpk", "topic", "consume",
        dlq_topic, "--num", str(limit), "--format", "json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    events = []

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue

        try:
            msg = json.loads(line)
            dlq_event = json.loads(msg['value'])

            if correlation_id is None or dlq_event.get('correlation_id') == correlation_id:
                events.append(dlq_event)
        except Exception as e:
            continue

    return events


def republish_events(original_topic: str, events: list[dict]):
    """Republish events to original topic."""
    from aiokafka import AIOKafkaProducer
    import asyncio

    async def publish():
        producer = AIOKafkaProducer(bootstrap_servers='redpanda:9092')
        await producer.start()

        try:
            for event in events:
                original_payload = event['original_payload']
                await producer.send(
                    original_topic,
                    value=json.dumps(original_payload).encode()
                )
                print(f"  Republished: {original_payload.get('file_path', 'N/A')}")
        finally:
            await producer.stop()

    asyncio.run(publish())


def main():
    parser = argparse.ArgumentParser(description='Reprocess DLQ events')
    parser.add_argument('--dlq-topic', required=True, help='DLQ topic name')
    parser.add_argument('--correlation-id', help='Filter by correlation_id')
    parser.add_argument('--limit', type=int, default=1000, help='Max events to process')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not republish')
    parser.add_argument('--republish', action='store_true', help='Republish events to original topic')
    parser.add_argument('--confirm', action='store_true', help='Confirm reprocessing (required for --republish)')
    args = parser.parse_args()

    print(f"Consuming DLQ: {args.dlq_topic}")
    events = consume_dlq(args.dlq_topic, args.correlation_id, args.limit)

    if not events:
        print("No events found in DLQ")
        return

    print(f"\nFound {len(events)} events in DLQ:")

    # Group by error type
    error_types = {}
    for event in events:
        error_type = event.get('error_type', 'UNKNOWN')
        error_types[error_type] = error_types.get(error_type, 0) + 1

    for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {error_type}: {count}")

    if args.dry_run:
        print("\nDry run - no events republished")
        return

    if args.republish:
        if not args.confirm:
            print("\nERROR: --confirm required for republishing")
            print("This will republish all events to the original topic.")
            print("Add --confirm flag to proceed.")
            return

        # Extract original topic
        original_topic = events[0]['original_topic']
        print(f"\nRepublishing {len(events)} events to {original_topic}...")

        republish_events(original_topic, events)
        print(f"\n✓ Republished {len(events)} events")


if __name__ == '__main__':
    main()
```

---

## Monitoring & Alerts

### Grafana Dashboard Queries

**Consumer Lag**:
```promql
# Consumer lag by group
kafka_consumer_group_lag{group=~"tree-.*-group"}

# Alert on high lag
kafka_consumer_group_lag > 10000
```

**Throughput**:
```promql
# Events processed per second
rate(tree_events_processed_total[1m])

# Alert on low throughput
rate(tree_events_processed_total[5m]) < 16.67  # < 1000 files/min
```

**Error Rate**:
```promql
# Error rate
rate(tree_events_processed_total{status="failed"}[1m]) / rate(tree_events_processed_total[1m])

# Alert on high error rate
(rate(tree_events_processed_total{status="failed"}[5m]) / rate(tree_events_processed_total[5m])) > 0.05  # > 5%
```

**DLQ Events**:
```promql
# DLQ message count
kafka_topic_partition_current_offset{topic=~".*\\.dlq"}

# Alert on DLQ overflow
increase(kafka_topic_partition_current_offset{topic=~".*\\.dlq"}[5m]) > 10
```

### Alert Rules (Prometheus)

```yaml
groups:
  - name: tree_stamping_alerts
    interval: 30s
    rules:
      - alert: HighConsumerLag
        expr: kafka_consumer_group_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High consumer lag detected"
          description: "Consumer group {{ $labels.group }} has lag of {{ $value }}"

      - alert: DLQOverflow
        expr: increase(kafka_topic_partition_current_offset{topic=~".*\\.dlq"}[5m]) > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dead Letter Queue overflow"
          description: "DLQ topic {{ $labels.topic }} has {{ $value }} new failures"

      - alert: LowThroughput
        expr: rate(tree_events_processed_total[5m]) < 16.67
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low event processing throughput"
          description: "Throughput is {{ $value }} events/sec (target: ≥16.67 events/sec)"

      - alert: HighErrorRate
        expr: (rate(tree_events_processed_total{status="failed"}[5m]) / rate(tree_events_processed_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High event processing error rate"
          description: "Error rate is {{ $value | humanizePercentage }} (target: <5%)"
```

---

## Recovery Procedures

### Procedure 1: Reindex Entire Project

**Scenario**: Project index corrupted or incomplete

```bash
#!/bin/bash
# reindex_project.sh - Reindex entire project

PROJECT_PATH="/path/to/project"
PROJECT_NAME="my-project"

echo "Reindexing project: $PROJECT_NAME"
echo "Path: $PROJECT_PATH"
echo ""

# 1. Clear existing index
echo "Step 1: Clearing existing index..."
curl -X DELETE http://localhost:6333/collections/file_locations/points/delete \
  -H "Content-Type: application/json" \
  -d "{\"filter\": {\"must\": [{\"key\": \"project_name\", \"match\": {\"value\": \"$PROJECT_NAME\"}}]}}"

docker exec archon-memgraph mgconsole --username "" --password "" \
  --execute "MATCH (f:File {project_name: '$PROJECT_NAME'}) DETACH DELETE f;"

echo "  ✓ Existing index cleared"

# 2. Trigger new discovery
echo "Step 2: Triggering tree discovery..."
CORRELATION_ID=$(uuidgen)

python3 /tools/publish_event.py \
  --topic dev.archon-intelligence.tree.discover.v1 \
  --payload "{\"project_path\": \"$PROJECT_PATH\", \"project_name\": \"$PROJECT_NAME\", \"correlation_id\": \"$CORRELATION_ID\", \"force_regenerate\": true}"

echo "  ✓ Discovery request published: $CORRELATION_ID"

# 3. Monitor progress
echo "Step 3: Monitoring progress (Ctrl+C to exit)..."
while true; do
    sleep 10

    INDEX_COUNT=$(docker exec omninode-bridge-redpanda rpk topic consume \
      dev.archon-intelligence.tree.index-completed.v1 \
      --format json --num 100000 | \
      jq -r "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\")" | \
      wc -l)

    DISCOVERY_COMPLETE=$(docker exec omninode-bridge-redpanda rpk topic consume \
      dev.archon-intelligence.tree.discover-completed.v1 \
      --format json --num 1000 | \
      jq -r "select(.value | fromjson | .payload.correlation_id == \"$CORRELATION_ID\") | .payload.files_discovered" | \
      head -1)

    if [ -n "$DISCOVERY_COMPLETE" ]; then
        PERCENT=$((INDEX_COUNT * 100 / DISCOVERY_COMPLETE))
        echo "  Progress: $INDEX_COUNT / $DISCOVERY_COMPLETE files indexed ($PERCENT%)"

        if [ $INDEX_COUNT -ge $DISCOVERY_COMPLETE ]; then
            echo ""
            echo "✓ Reindexing complete!"
            break
        fi
    else
        echo "  Discovery in progress..."
    fi
done
```

---

### Procedure 2: Consumer Group Reset

**Scenario**: Consumer stuck, need to reset offsets

```bash
#!/bin/bash
# reset_consumer_group.sh - Reset consumer group to specific offset

CONSUMER_GROUP="stamping-generator-group"
TOPIC="dev.archon-intelligence.stamping.generate.v1"
RESET_TO="earliest"  # or "latest" or specific offset

echo "Resetting consumer group: $CONSUMER_GROUP"
echo "Topic: $TOPIC"
echo "Reset to: $RESET_TO"
echo ""

# 1. Stop consumer
echo "Step 1: Stopping consumer..."
docker stop archon-intelligence
echo "  ✓ Consumer stopped"

# 2. Reset offsets
echo "Step 2: Resetting offsets..."
docker exec omninode-bridge-redpanda rpk group seek $CONSUMER_GROUP \
  --to $RESET_TO \
  --topics $TOPIC

echo "  ✓ Offsets reset"

# 3. Restart consumer
echo "Step 3: Restarting consumer..."
docker start archon-intelligence
echo "  ✓ Consumer restarted"

# 4. Verify
echo "Step 4: Verifying offset reset..."
sleep 5
docker exec omninode-bridge-redpanda rpk group describe $CONSUMER_GROUP

echo ""
echo "✓ Consumer group reset complete"
```

---

## CLI Tools Reference

### Kafka/Redpanda Commands

```bash
# List all topics
docker exec omninode-bridge-redpanda rpk topic list

# Describe topic (partitions, replicas, config)
docker exec omninode-bridge-redpanda rpk topic describe dev.archon-intelligence.tree.discover.v1

# Consume events (tail)
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.tree.discover.v1 --num 10

# Consume events (from beginning)
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.tree.discover.v1 --offset start --num 100

# Produce event (testing)
echo '{"project_path": "/test", "project_name": "test", "correlation_id": "abc"}' | \
  docker exec -i omninode-bridge-redpanda rpk topic produce dev.archon-intelligence.tree.discover.v1

# List consumer groups
docker exec omninode-bridge-redpanda rpk group list

# Describe consumer group
docker exec omninode-bridge-redpanda rpk group describe tree-discovery-group

# Reset consumer group offset
docker exec omninode-bridge-redpanda rpk group seek tree-discovery-group --to earliest

# Delete topic (DANGEROUS)
docker exec omninode-bridge-redpanda rpk topic delete dev.archon-intelligence.tree.discover.v1.dlq
```

### Python Tools

```bash
# Trace event flow
python3 /tools/trace_event_flow.py --correlation-id abc-123-def-456

# Reprocess DLQ (dry run)
python3 /tools/reprocess_dlq.py --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq --dry-run

# Reprocess DLQ (republish)
python3 /tools/reprocess_dlq.py --dlq-topic dev.archon-intelligence.stamping.generate.v1.dlq --limit 100 --republish --confirm

# Benchmark performance
bash /tools/benchmark_tree_stamping.sh

# Reindex project
bash /tools/reindex_project.sh /path/to/project my-project

# Reset consumer group
bash /tools/reset_consumer_group.sh stamping-generator-group
```

---

## Emergency Contacts

**On-Call Rotation**:
- Primary: DevOps Team (Slack: #tree-stamping-oncall)
- Escalation: Platform Engineering Lead

**Service Owners**:
- Tree Discovery: @tree-team
- Metadata Stamping: @intelligence-team
- Indexing: @search-team

**Slack Channels**:
- #tree-stamping-alerts - Automated alerts
- #tree-stamping-support - User support
- #tree-stamping-oncall - On-call escalations

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-27
**Maintained By**: DevOps Team
**Review Cycle**: Monthly
