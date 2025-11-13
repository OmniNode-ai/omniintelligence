# Async Intelligence Architecture - Quick Start Guide

**Companion to**: ASYNC_INTELLIGENCE_ARCHITECTURE.md
**Version**: 1.0.0
**Last Updated**: 2025-10-30

---

## Quick Implementation Checklist

### Phase 1: Infrastructure Setup (Day 1)

```bash
# 1. Create Kafka topics
cd /Volumes/PRO-G40/Code/omniarchon
./scripts/create_async_enrichment_topics.sh

# 2. Verify topics created
docker exec omninode-bridge-redpanda rpk topic list | grep enrich-document

# 3. Add Kafka dependencies to bridge
cd services/bridge
poetry add aiokafka==0.12.0

# 4. Update environment variables
echo "ENABLE_ASYNC_ENRICHMENT=false" >> .env
echo "KAFKA_ENRICHMENT_TOPIC=dev.archon-intelligence.enrich-document.v1" >> .env
```

### Phase 2: Bridge Producer (Day 2-3)

```bash
# 1. Copy producer implementation
cp docs/examples/kafka_producer_manager.py services/bridge/

# 2. Update app.py with producer integration
# See ASYNC_INTELLIGENCE_ARCHITECTURE.md section 8.1

# 3. Test producer
docker compose restart archon-bridge
curl http://localhost:8054/health/enrichment

# 4. Enable async enrichment for test project
docker exec archon-bridge sh -c 'echo "ENABLE_ASYNC_ENRICHMENT=true" >> /app/.env'
docker restart archon-bridge
```

### Phase 3: Intelligence Consumer (Day 4-7)

```bash
# 1. Create consumer service
mkdir -p services/intelligence-consumer/src
cp docs/examples/intelligence_consumer.py services/intelligence-consumer/src/main.py

# 2. Build consumer image
cd services/intelligence-consumer
docker build -t archon-intelligence-enrichment-consumer .

# 3. Add to docker-compose.yml
# See ASYNC_INTELLIGENCE_ARCHITECTURE.md section 8.3

# 4. Start consumer
docker compose up -d archon-intelligence-enrichment-consumer

# 5. Monitor consumer logs
docker logs -f archon-intelligence-enrichment-consumer
```

### Phase 4: Testing (Day 8-10)

```bash
# 1. Run integration test
pytest tests/integration/test_async_enrichment_e2e.py -v

# 2. Load test (1000 documents)
python3 scripts/load_test_async_enrichment.py --num-docs 1000

# 3. Verify enrichment
python3 scripts/validate_enrichment_completeness.py
```

### Phase 5: Production Rollout (Day 11-14)

```bash
# Day 11: 10% rollout
docker exec archon-bridge sh -c 'echo "ASYNC_ENRICHMENT_ROLLOUT_PERCENTAGE=10" >> /app/.env'
docker restart archon-bridge

# Day 12: Monitor for 24 hours
python3 scripts/monitor_enrichment_metrics.py --duration 86400

# Day 13: 50% rollout
docker exec archon-bridge sh -c 'sed -i "s/ROLLOUT_PERCENTAGE=10/ROLLOUT_PERCENTAGE=50/" /app/.env'
docker restart archon-bridge

# Day 14: 100% rollout
docker exec archon-bridge sh -c 'sed -i "s/ROLLOUT_PERCENTAGE=50/ROLLOUT_PERCENTAGE=100/" /app/.env'
docker restart archon-bridge
```

---

## Quick Reference Commands

### Check System Health

```bash
# Bridge health
curl http://localhost:8054/health/enrichment

# Consumer health
curl http://localhost:8156/health

# Intelligence service health
curl http://localhost:8053/health
```

### Monitor Kafka Topics

```bash
# List topics
docker exec omninode-bridge-redpanda rpk topic list | grep enrich

# Check topic stats
docker exec omninode-bridge-redpanda rpk topic describe dev.archon-intelligence.enrich-document.v1

# Consumer lag
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-enrichment-consumer-group

# Consume messages (debug)
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.enrich-document.v1 --num 1
```

### Monitor Enrichment Progress

```bash
# Documents pending enrichment
docker exec archon-memgraph mgconsole << EOF
MATCH (doc:Document)
WHERE doc.enrichment_status = 'pending'
RETURN count(doc) as pending_count;
EOF

# Recent enrichments
docker exec archon-memgraph mgconsole << EOF
MATCH (doc:Document)
WHERE doc.enrichment_status = 'completed'
AND datetime(doc.enriched_at) > datetime() - duration({hours: 1})
RETURN count(doc) as enriched_last_hour;
EOF

# Enrichment rate
python3 scripts/calculate_enrichment_rate.py
```

### Troubleshooting

```bash
# Check DLQ for failures
docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.enrich-document-dlq.v1 --num 10

# Circuit breaker status
curl http://localhost:8156/metrics/circuit_breaker

# Consumer metrics
curl http://localhost:8156/metrics

# Bridge metrics
curl http://localhost:8054/metrics
```

---

## Common Issues and Solutions

### Issue: Consumer Lag Growing

**Symptoms**:
```bash
rpk group describe archon-intelligence-enrichment-consumer-group
# Shows lag > 500
```

**Solutions**:
1. Scale up consumers:
   ```bash
   docker compose up -d --scale archon-intelligence-enrichment-consumer=4
   ```

2. Increase concurrent enrichments:
   ```bash
   docker exec archon-intelligence-enrichment-consumer sh -c \
     'echo "MAX_CONCURRENT_ENRICHMENTS=20" >> /app/.env'
   docker restart archon-intelligence-enrichment-consumer
   ```

3. Check intelligence service health:
   ```bash
   curl http://localhost:8053/health
   ```

### Issue: Circuit Breaker Open

**Symptoms**:
```bash
curl http://localhost:8156/metrics/circuit_breaker
# Returns: {"state": "OPEN"}
```

**Solutions**:
1. Check intelligence service:
   ```bash
   docker logs archon-intelligence --tail 100
   curl http://localhost:8053/health
   ```

2. Wait for recovery timeout (60s default)

3. Manually reset circuit breaker:
   ```bash
   curl -X POST http://localhost:8156/circuit_breaker/reset
   ```

### Issue: DLQ Accumulating Messages

**Symptoms**:
```bash
rpk topic describe dev.archon-intelligence.enrich-document-dlq.v1
# Shows growing message count
```

**Solutions**:
1. Analyze failures:
   ```bash
   rpk topic consume dev.archon-intelligence.enrich-document-dlq.v1 \
     --num 10 --format json | jq '.failure_reason'
   ```

2. Fix root cause (e.g., data quality issues, service outages)

3. Reprocess DLQ messages:
   ```bash
   python3 scripts/reprocess_dlq.py --topic dev.archon-intelligence.enrich-document-dlq.v1
   ```

### Issue: Documents Not Enriching

**Symptoms**:
```bash
# Documents stuck in 'pending' state
MATCH (doc:Document) WHERE doc.enrichment_status = 'pending'
RETURN count(doc);  # Returns > 0 after 30+ minutes
```

**Solutions**:
1. Check if enrichment events are being published:
   ```bash
   docker logs archon-bridge | grep "Published enrichment request"
   ```

2. Check if consumer is running:
   ```bash
   docker ps | grep enrichment-consumer
   curl http://localhost:8156/health
   ```

3. Check consumer is consuming events:
   ```bash
   docker logs archon-intelligence-enrichment-consumer | grep "Processing enrichment"
   ```

4. Manually publish enrichment event:
   ```bash
   python3 scripts/publish_enrichment_event.py --document-id <doc_id>
   ```

---

## Performance Targets

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Indexing Latency (P95) | <200ms | <500ms | >1000ms |
| Enrichment Time (P95) | <15s | <30s | >60s |
| Consumer Lag | <100 | <500 | >1000 |
| DLQ Rate | 0/min | <0.1/min | >1/min |
| Circuit Breaker State | CLOSED | HALF-OPEN | OPEN |
| Enrichment Completion Rate | >95% | >90% | <85% |

---

## Monitoring Dashboard URLs

- **Grafana Dashboard**: http://localhost:3000/d/async-enrichment
- **Prometheus Metrics**: http://localhost:9090/graph
- **Redpanda Console**: http://192.168.86.200:8080
- **Bridge Metrics**: http://localhost:8054/metrics
- **Consumer Metrics**: http://localhost:8156/metrics
- **Intelligence Metrics**: http://localhost:8053/metrics

---

## Emergency Rollback Procedure

If async enrichment causes production issues:

```bash
# 1. Disable async enrichment (immediate)
docker exec archon-bridge sh -c 'echo "ENABLE_ASYNC_ENRICHMENT=false" >> /app/.env'
docker restart archon-bridge

# 2. Stop consumer
docker stop archon-intelligence-enrichment-consumer

# 3. Verify indexing still works
curl -X POST http://localhost:8054/api/bridge/document -d @test_doc.json

# 4. Check for documents stuck in 'pending' state
docker exec archon-memgraph mgconsole << EOF
MATCH (doc:Document)
WHERE doc.enrichment_status = 'pending'
RETURN count(doc) as pending_count;
EOF

# 5. If needed, backfill enrichment synchronously
python3 scripts/backfill_enrichment_sync.py
```

**Rollback Time**: ~5 minutes
**Data Loss**: None (documents remain in Memgraph, can be enriched later)

---

## Key Files Reference

- **Architecture Doc**: `docs/ASYNC_INTELLIGENCE_ARCHITECTURE.md`
- **Bridge Changes**: `services/bridge/app.py` (lines 498+)
- **Consumer Service**: `services/intelligence-consumer/src/main.py`
- **Docker Compose**: `deployment/docker-compose.yml`
- **Kafka Topics Script**: `scripts/create_async_enrichment_topics.sh`
- **Load Test**: `scripts/load_test_async_enrichment.py`
- **Validation**: `scripts/validate_enrichment_completeness.py`

---

**Quick Start Complete!** Proceed to full architecture implementation.
