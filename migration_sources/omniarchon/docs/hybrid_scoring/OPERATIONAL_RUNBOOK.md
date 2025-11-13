# Hybrid Scoring Operational Runbook

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Audience**: DevOps, SRE, Platform Engineers

---

## Table of Contents

1. [Service Overview](#service-overview)
2. [Health Checks](#health-checks)
3. [Monitoring & Alerts](#monitoring--alerts)
4. [Common Issues](#common-issues)
5. [Incident Response](#incident-response)
6. [Performance Tuning](#performance-tuning)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Disaster Recovery](#disaster-recovery)

---

## Service Overview

### Service Dependencies

```
┌─────────────────────────────────────────────────────┐
│         Hybrid Scoring Service Architecture          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Intelligence Service (Port 8053)                    │
│  └── Pattern Learning Engine                         │
│       └── Hybrid Scoring Module                      │
│            ├── Langextract Client ──────┐           │
│            ├── Semantic Cache ────┐     │           │
│            ├── Pattern Scorer      │     │           │
│            └── Hybrid Combiner     │     │           │
│                                    │     │           │
│  External Dependencies:            │     │           │
│  • Langextract (8156) ────────────────┘ │           │
│  • Redis (6379) ───────────────────┘                 │
│  • Qdrant (6333) - Phase 1                           │
│  • PostgreSQL (5436) - Phase 1                       │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Service Ports

| Service | Port | Purpose | Protocol |
|---------|------|---------|----------|
| **Intelligence Service** | 8053 | Main API | HTTP |
| **Langextract** | 8156 | Semantic analysis | HTTP |
| **Redis** | 6379 | Distributed cache | TCP |
| **Prometheus** | 9090 | Metrics scraping | HTTP |
| **Grafana** | 3000 | Metrics visualization | HTTP |

### Service Ownership

| Component | Team | On-Call Contact | Escalation |
|-----------|------|----------------|------------|
| Hybrid Scoring Logic | ML Team | ml-oncall@company.com | ml-lead@company.com |
| Langextract Service | Infrastructure | infra-oncall@company.com | infra-lead@company.com |
| Redis Cache | Infrastructure | infra-oncall@company.com | infra-lead@company.com |
| Monitoring | DevOps | devops-oncall@company.com | devops-lead@company.com |

---

## Health Checks

### Service Health Endpoints

#### 1. Intelligence Service Health

```bash
curl -X GET http://localhost:8053/health | jq .
```

**Expected Response (Healthy)**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-02T12:00:00Z",
  "version": "2.0.0",
  "components": {
    "database": "healthy",
    "qdrant": "healthy",
    "langextract_client": "healthy",
    "semantic_cache": "healthy",
    "redis": "healthy"
  },
  "uptime_seconds": 3600.5,
  "memory_usage_mb": 512.3,
  "cpu_usage_percent": 25.4
}
```

**Degraded State**:
```json
{
  "status": "degraded",
  "timestamp": "2025-10-02T12:00:00Z",
  "components": {
    "database": "healthy",
    "qdrant": "healthy",
    "langextract_client": "unhealthy",  // ⚠️ Degraded
    "semantic_cache": "healthy",
    "redis": "unhealthy"  // ⚠️ Degraded
  },
  "warnings": [
    "Langextract service unavailable - using vector-only scoring",
    "Redis unavailable - using in-memory cache only"
  ]
}
```

#### 2. Langextract Health

```bash
curl -X GET http://localhost:8156/health | jq .
```

**Expected Response (Healthy)**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-02T12:00:00Z",
  "version": "1.0.0",
  "components": {
    "memgraph_adapter": "healthy",
    "intelligence_client": "healthy",
    "language_extractor": "healthy",
    "document_analyzer": "healthy"
  },
  "uptime_seconds": 7200.0
}
```

#### 3. Redis Health

```bash
redis-cli ping
```

**Expected**: `PONG`

**Check Redis info**:
```bash
redis-cli info | grep -E '(connected_clients|used_memory_human|uptime_in_seconds)'
```

**Expected Output**:
```
connected_clients:5
used_memory_human:128.45M
uptime_in_seconds:86400
```

### Automated Health Monitoring

```python
# File: monitoring/health_checker.py

import asyncio
import httpx
import redis
from typing import Dict, List

class HealthChecker:
    """Automated health monitoring for hybrid scoring system"""

    async def check_all_services(self) -> Dict[str, bool]:
        """Check health of all dependent services"""

        results = {}

        # Check Intelligence Service
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8053/health", timeout=5.0)
                data = response.json()
                results["intelligence"] = data["status"] == "healthy"
        except Exception as e:
            results["intelligence"] = False

        # Check Langextract
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8156/health", timeout=5.0)
                data = response.json()
                results["langextract"] = data["status"] == "healthy"
        except Exception as e:
            results["langextract"] = False

        # Check Redis
        try:
            r = redis.Redis(host='localhost', port=6379, socket_timeout=2)
            results["redis"] = r.ping()
        except Exception as e:
            results["redis"] = False

        return results

    def format_health_report(self, results: Dict[str, bool]) -> str:
        """Format health check results"""

        report = "=== System Health Report ===\n"

        for service, is_healthy in results.items():
            status = "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY"
            report += f"{service.upper()}: {status}\n"

        overall_healthy = all(results.values())
        overall_status = "✅ ALL SYSTEMS OPERATIONAL" if overall_healthy else "⚠️ DEGRADED"
        report += f"\nOVERALL: {overall_status}\n"

        return report


# Run health check
async def main():
    checker = HealthChecker()
    results = await checker.check_all_services()
    print(checker.format_health_report(results))

if __name__ == "__main__":
    asyncio.run(main())
```

**Automated Execution**:
```bash
# Run every 1 minute via cron
* * * * * cd /path/to/monitoring && python health_checker.py
```

---

## Monitoring & Alerts

### Prometheus Metrics

#### Key Metrics to Monitor

**Langextract Client Metrics**:
```yaml
langextract_requests_total{endpoint, status}
  - Total requests to langextract service
  - Labels: endpoint (analyze_semantic, health), status (success, error, timeout)

langextract_request_duration_seconds{endpoint}
  - Request duration histogram
  - Use for p50, p95, p99 latency tracking

langextract_circuit_breaker_state
  - Circuit breaker state (0=closed, 1=open, 2=half_open)

langextract_fallback_total{reason}
  - Total fallbacks to vector-only scoring
  - Labels: reason (timeout, unavailable, validation_error, circuit_breaker)
```

**Semantic Cache Metrics**:
```yaml
semantic_cache_hits_total
  - Total cache hits

semantic_cache_misses_total
  - Total cache misses

semantic_cache_hit_rate
  - Current cache hit rate (0.0-1.0)

semantic_cache_evictions_total
  - Total LRU evictions

semantic_cache_size
  - Current number of cached entries

semantic_cache_memory_bytes
  - Memory used by cache
```

**Hybrid Scoring Metrics**:
```yaml
hybrid_scoring_duration_seconds
  - Hybrid scoring calculation duration histogram

pattern_similarity_score
  - Pattern similarity scores histogram (0.0-1.0)

hybrid_score_confidence
  - Hybrid score confidence histogram (0.0-1.0)

hybrid_scoring_fallback_total{reason}
  - Total fallbacks to vector-only in hybrid scoring
```

### Grafana Dashboards

#### Dashboard: Hybrid Scoring Performance

**Panel 1: Request Rate**
```promql
# Langextract request rate (req/s)
rate(langextract_requests_total[5m])
```

**Panel 2: Latency Percentiles**
```promql
# p50 latency
histogram_quantile(0.50, langextract_request_duration_seconds)

# p95 latency
histogram_quantile(0.95, langextract_request_duration_seconds)

# p99 latency
histogram_quantile(0.99, langextract_request_duration_seconds)
```

**Panel 3: Cache Hit Rate**
```promql
# Cache hit rate over time
semantic_cache_hit_rate

# Rolling 5-minute average hit rate
avg_over_time(semantic_cache_hit_rate[5m])
```

**Panel 4: Error Rate**
```promql
# Langextract error rate (errors/s)
rate(langextract_requests_total{status="error"}[5m])

# Error percentage
(rate(langextract_requests_total{status="error"}[5m]) /
 rate(langextract_requests_total[5m])) * 100
```

**Panel 5: Fallback Rate**
```promql
# Fallback rate by reason
rate(langextract_fallback_total[5m])

# Total fallback percentage
(sum(rate(langextract_fallback_total[5m])) /
 rate(hybrid_scoring_duration_seconds_count[5m])) * 100
```

**Panel 6: Circuit Breaker State**
```promql
# Circuit breaker state (0=closed, 1=open, 2=half_open)
langextract_circuit_breaker_state
```

#### Import Dashboard

```bash
# Import pre-built Grafana dashboard
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @monitoring/grafana/dashboards/hybrid_scoring.json
```

### Alert Rules

#### Prometheus Alert Configuration

```yaml
# File: monitoring/prometheus/alerts/hybrid_scoring_alerts.yml

groups:
  - name: hybrid_scoring_alerts
    interval: 30s
    rules:

      # Alert: High error rate
      - alert: LangextractHighErrorRate
        expr: |
          (rate(langextract_requests_total{status="error"}[5m]) /
           rate(langextract_requests_total[5m])) > 0.05
        for: 2m
        labels:
          severity: warning
          component: langextract
        annotations:
          summary: "Langextract error rate above 5%"
          description: "Error rate: {{ $value | humanizePercentage }}"
          runbook: "https://docs.company.com/runbooks/langextract-high-errors"

      # Alert: High latency
      - alert: LangextractHighLatency
        expr: |
          histogram_quantile(0.95,
            rate(langextract_request_duration_seconds_bucket[5m])
          ) > 5.0
        for: 5m
        labels:
          severity: warning
          component: langextract
        annotations:
          summary: "Langextract p95 latency above 5s"
          description: "p95 latency: {{ $value | humanizeDuration }}"
          runbook: "https://docs.company.com/runbooks/langextract-high-latency"

      # Alert: Circuit breaker open
      - alert: LangextractCircuitBreakerOpen
        expr: langextract_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
          component: langextract
        annotations:
          summary: "Langextract circuit breaker is open"
          description: "Circuit breaker has been open for >1 minute"
          runbook: "https://docs.company.com/runbooks/circuit-breaker-open"

      # Alert: Low cache hit rate
      - alert: SemanticCacheLowHitRate
        expr: semantic_cache_hit_rate < 0.6
        for: 10m
        labels:
          severity: warning
          component: semantic_cache
        annotations:
          summary: "Semantic cache hit rate below 60%"
          description: "Current hit rate: {{ $value | humanizePercentage }}"
          runbook: "https://docs.company.com/runbooks/low-cache-hit-rate"

      # Alert: High fallback rate
      - alert: HybridScoringHighFallbackRate
        expr: |
          (sum(rate(langextract_fallback_total[5m])) /
           rate(hybrid_scoring_duration_seconds_count[5m])) > 0.15
        for: 5m
        labels:
          severity: warning
          component: hybrid_scoring
        annotations:
          summary: "Hybrid scoring fallback rate above 15%"
          description: "Fallback rate: {{ $value | humanizePercentage }}"
          runbook: "https://docs.company.com/runbooks/high-fallback-rate"

      # Alert: Redis unavailable
      - alert: RedisUnavailable
        expr: redis_up == 0
        for: 1m
        labels:
          severity: warning
          component: redis
        annotations:
          summary: "Redis is unavailable"
          description: "Redis has been down for >1 minute"
          runbook: "https://docs.company.com/runbooks/redis-unavailable"
```

#### Alert Notification Channels

```yaml
# Alertmanager configuration

route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    email_configs:
      - to: 'team@company.com'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<pagerduty-service-key>'

  - name: 'slack'
    slack_configs:
      - api_url: '<slack-webhook-url>'
        channel: '#alerts-hybrid-scoring'
        title: 'Hybrid Scoring Alert'
```

---

## Common Issues

### Issue 1: Langextract Service Degradation

**Symptoms**:
- High latency (>5s)
- Increased fallback rate
- Circuit breaker frequently opening

**Investigation Steps**:

1. **Check langextract health**:
```bash
curl http://localhost:8156/health | jq .
```

2. **Check resource usage**:
```bash
docker stats archon-langextract
```

3. **Check logs**:
```bash
docker logs --tail=100 archon-langextract
```

4. **Check dependencies**:
```bash
# Memgraph
curl http://localhost:7687
# Expected: Bolt protocol response

# Intelligence service
curl http://localhost:8053/health
```

**Resolution**:

**Option A**: Restart langextract service
```bash
docker compose restart langextract

# Verify health
sleep 10
curl http://localhost:8156/health | jq .status
```

**Option B**: Scale langextract horizontally
```bash
# Scale to 2 instances
docker compose up -d --scale langextract=2
```

**Option C**: Fallback mode (temporary)
```bash
# System automatically falls back to vector-only scoring
# Monitor fallback rate:
curl -s http://localhost:9090/api/v1/query?query=langextract_fallback_total
```

### Issue 2: Low Cache Hit Rate

**Symptoms**:
- Cache hit rate <60%
- High latency even for repeated queries
- Excessive langextract requests

**Investigation Steps**:

1. **Check cache metrics**:
```python
# Via Python API
metrics = cache.get_metrics()
print(f"Hit rate: {metrics['hit_rate']:.1%}")
print(f"Cache size: {metrics['current_size']}/{metrics['max_size']}")
print(f"TTL: {metrics['ttl_seconds']}s")
```

2. **Check cache configuration**:
```bash
# Environment variables
echo $SEMANTIC_CACHE_MAX_SIZE
echo $SEMANTIC_CACHE_TTL_SECONDS
```

3. **Analyze access patterns**:
```python
# Check if queries are unique or repeated
# Low hit rate normal for unique queries
# Low hit rate abnormal for repeated queries
```

**Resolution**:

**Option A**: Increase cache size
```bash
# Update docker-compose.yml
environment:
  - SEMANTIC_CACHE_MAX_SIZE=2000  # Increased from 1000

# Restart service
docker compose restart archon-intelligence
```

**Option B**: Increase TTL
```bash
environment:
  - SEMANTIC_CACHE_TTL_SECONDS=7200  # 2 hours instead of 1

docker compose restart archon-intelligence
```

**Option C**: Implement cache warming
```python
# warm_cache_startup.py
async def warm_cache_on_startup():
    """Warm cache with common patterns during startup"""

    # Load top 100 most frequent patterns
    patterns = await db.query("""
        SELECT description
        FROM pattern_templates
        ORDER BY usage_count DESC
        LIMIT 100
    """)

    # Warm cache
    count = await cache.warm_cache(
        content_samples=[p['description'] for p in patterns],
        langextract_client=client
    )

    print(f"Warmed cache with {count} patterns")

# Add to service startup
```

**Option D**: Enable Redis for persistent cache
```bash
# Deploy Redis if not already deployed
docker compose up -d redis

# Enable Redis cache
environment:
  - SEMANTIC_CACHE_ENABLE_REDIS=true
  - REDIS_HOST=redis
  - REDIS_PORT=6379

docker compose restart archon-intelligence
```

### Issue 3: Circuit Breaker Stuck Open

**Symptoms**:
- Circuit breaker permanently open
- All requests falling back to vector-only
- `langextract_circuit_breaker_state == 1`

**Investigation Steps**:

1. **Check circuit breaker state**:
```bash
# Via Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=langextract_circuit_breaker_state' | jq .
```

2. **Check failure count**:
```bash
# Check langextract error rate
curl -s 'http://localhost:9090/api/v1/query?query=rate(langextract_requests_total{status="error"}[5m])' | jq .
```

3. **Check langextract health**:
```bash
curl http://localhost:8156/health
```

**Resolution**:

**Option A**: Fix underlying langextract issue
```bash
# Restart langextract
docker compose restart langextract

# Wait for circuit breaker reset timeout (default: 60s)
sleep 65

# Verify circuit breaker closed
curl -s 'http://localhost:9090/api/v1/query?query=langextract_circuit_breaker_state'
```

**Option B**: Adjust circuit breaker thresholds
```bash
# Increase failure threshold
environment:
  - CIRCUIT_BREAKER_THRESHOLD=10  # Increased from 5

# Decrease reset timeout
environment:
  - CIRCUIT_BREAKER_TIMEOUT=30  # 30s instead of 60s

docker compose restart archon-intelligence
```

**Option C**: Manual circuit breaker reset (emergency)
```python
# Reset circuit breaker programmatically
from langextract_client import langextract_breaker

# Reset to closed state
langextract_breaker.reset()

# Verify
print(f"Circuit breaker state: {langextract_breaker.current_state}")
# Expected: closed
```

### Issue 4: Redis Connection Failures

**Symptoms**:
- Warnings about Redis unavailable
- Cache degraded to in-memory only
- `semantic_cache` component showing "degraded"

**Investigation Steps**:

1. **Check Redis health**:
```bash
redis-cli ping
# Expected: PONG
```

2. **Check Redis container**:
```bash
docker compose ps redis
# Should be "Up"

docker logs redis --tail=50
```

3. **Test connection from Intelligence service**:
```bash
docker exec -it archon-intelligence bash
redis-cli -h redis -p 6379 ping
```

**Resolution**:

**Option A**: Restart Redis
```bash
docker compose restart redis

# Verify
redis-cli ping
```

**Option B**: Check network connectivity
```bash
# Test network
docker network inspect archon-network | grep -A 5 redis

# Verify DNS resolution
docker exec -it archon-intelligence ping redis
```

**Option C**: Disable Redis (temporary fallback)
```bash
# Disable Redis, use in-memory cache only
environment:
  - SEMANTIC_CACHE_ENABLE_REDIS=false

docker compose restart archon-intelligence
```

### Issue 5: High Memory Usage

**Symptoms**:
- Service memory usage >2GB
- OOM (Out of Memory) errors
- Container restarts

**Investigation Steps**:

1. **Check memory usage**:
```bash
docker stats archon-intelligence --no-stream
```

2. **Check cache size**:
```python
metrics = cache.get_metrics()
print(f"Cache entries: {metrics['current_size']}")
print(f"Memory estimate: ~{metrics['current_size'] * 100}KB")
```

3. **Check for memory leaks**:
```bash
# Monitor over time
watch -n 5 'docker stats archon-intelligence --no-stream'
```

**Resolution**:

**Option A**: Reduce cache size
```bash
environment:
  - SEMANTIC_CACHE_MAX_SIZE=500  # Reduced from 1000

docker compose restart archon-intelligence
```

**Option B**: Adjust container memory limits
```yaml
# docker-compose.yml
services:
  archon-intelligence:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

**Option C**: Enable memory monitoring and alerts
```yaml
# Prometheus alert
- alert: HighMemoryUsage
  expr: container_memory_usage_bytes{name="archon-intelligence"} > 1.5e9  # 1.5GB
  for: 5m
```

---

## Incident Response

### Incident Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| **P0 - Critical** | Complete service outage | 15 min | Immediate page |
| **P1 - High** | Degraded performance, fallback active | 1 hour | Page if unresolved |
| **P2 - Medium** | Minor degradation, no user impact | 4 hours | Email escalation |
| **P3 - Low** | Monitoring alert, proactive fix | 24 hours | Ticket only |

### Incident Response Procedures

#### P0: Complete Service Outage

**Scenario**: Hybrid scoring completely unavailable

**Response Steps**:

1. **Immediate Assessment** (0-5 min)
```bash
# Check all services
curl http://localhost:8053/health
curl http://localhost:8156/health
redis-cli ping

# Check Docker containers
docker compose ps

# Check recent logs
docker compose logs --tail=100 archon-intelligence archon-langextract
```

2. **Emergency Mitigation** (5-15 min)
```bash
# Option 1: Restart services
docker compose restart archon-intelligence archon-langextract redis

# Option 2: Rollback to Phase 1 (vector-only)
docker compose down archon-intelligence
docker compose up -d archon-intelligence:phase1  # Previous stable version

# Option 3: Enable emergency fallback mode
# System automatically uses vector-only scoring
```

3. **Root Cause Analysis** (15-30 min)
- Check logs for errors
- Review recent deployments
- Check infrastructure changes
- Review metrics leading up to incident

4. **Resolution & Communication** (30-60 min)
- Implement fix
- Verify service recovery
- Update incident status
- Post-mortem document

#### P1: Degraded Performance

**Scenario**: High latency, circuit breaker open, high fallback rate

**Response Steps**:

1. **Assessment** (0-15 min)
```bash
# Check metrics
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,langextract_request_duration_seconds_bucket[5m])'

# Check circuit breaker
curl -s 'http://localhost:9090/api/v1/query?query=langextract_circuit_breaker_state'

# Check fallback rate
curl -s 'http://localhost:9090/api/v1/query?query=rate(langextract_fallback_total[5m])'
```

2. **Mitigation** (15-45 min)
```bash
# Option 1: Restart affected service
docker compose restart langextract

# Option 2: Scale horizontally
docker compose up -d --scale langextract=2

# Option 3: Adjust timeouts
# Temporarily increase timeout to prevent cascading failures
environment:
  - LANGEXTRACT_TIMEOUT=15.0  # Increased from 10s
```

3. **Monitoring** (45-60 min)
- Monitor metrics for improvement
- Check if circuit breaker closes
- Verify fallback rate decreases
- Document findings

### Post-Incident Review Template

```markdown
# Incident Post-Mortem: [Incident ID]

## Incident Summary
- **Date**: YYYY-MM-DD
- **Duration**: X hours
- **Severity**: P0/P1/P2/P3
- **Impact**: [Description of user impact]

## Timeline
- **HH:MM** - Alert triggered
- **HH:MM** - Investigation started
- **HH:MM** - Root cause identified
- **HH:MM** - Mitigation applied
- **HH:MM** - Service recovered
- **HH:MM** - Incident closed

## Root Cause
[Detailed description of what caused the incident]

## Resolution
[What was done to fix the issue]

## Preventive Measures
- [ ] Action item 1
- [ ] Action item 2
- [ ] Action item 3

## Lessons Learned
- [Key takeaway 1]
- [Key takeaway 2]
```

---

## Performance Tuning

### Optimization Checklist

#### Cache Optimization

**1. Cache Size Tuning**

```python
# Analyze cache effectiveness
metrics = cache.get_metrics()

if metrics['evictions'] > 1000:
    # Too many evictions - increase size
    recommended_size = metrics['max_size'] * 1.5
    print(f"Recommended cache size: {recommended_size}")
```

**Configuration**:
```bash
# Increase cache size
SEMANTIC_CACHE_MAX_SIZE=2000
```

**2. TTL Optimization**

```python
# Analyze cache age distribution
# If most entries expire before reuse, increase TTL
# If entries rarely reused, decrease TTL to save memory

recommended_ttl = analyze_cache_access_patterns()
print(f"Recommended TTL: {recommended_ttl}s")
```

**Configuration**:
```bash
# Optimize TTL based on access patterns
SEMANTIC_CACHE_TTL_SECONDS=7200  # 2 hours
```

**3. Cache Warming**

```python
# Implement startup cache warming
async def warm_cache_on_startup():
    # Load top N most frequently used patterns
    patterns = await load_top_patterns(limit=100)

    # Pre-populate cache
    count = await cache.warm_cache(patterns, client)

    logger.info(f"Warmed cache with {count} patterns")
```

#### Langextract Optimization

**1. Timeout Tuning**

```yaml
# Balance between latency and success rate

# Aggressive (lower latency, more failures)
LANGEXTRACT_TIMEOUT=5.0

# Balanced (recommended)
LANGEXTRACT_TIMEOUT=10.0

# Conservative (higher success, higher latency)
LANGEXTRACT_TIMEOUT=15.0
```

**2. Circuit Breaker Tuning**

```yaml
# Aggressive (fail fast)
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT=30

# Balanced (recommended)
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60

# Conservative (tolerate more failures)
CIRCUIT_BREAKER_THRESHOLD=10
CIRCUIT_BREAKER_TIMEOUT=120
```

**3. Connection Pooling**

```python
# Increase HTTP connection pool size for high throughput
client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=200,      # Increased from 100
        max_keepalive_connections=40  # Increased from 20
    )
)
```

#### Hybrid Scoring Weight Optimization

**1. A/B Testing Framework**

```python
# Test different weight configurations
weight_configs = [
    {"vector": 0.7, "pattern": 0.3},  # Default
    {"vector": 0.8, "pattern": 0.2},  # More vector emphasis
    {"vector": 0.6, "pattern": 0.4},  # More pattern emphasis
]

# Run A/B test
results = await run_ab_test(weight_configs, sample_size=1000)

# Select best performing configuration
best_config = max(results, key=lambda r: r['accuracy'])
```

**2. Adaptive Weight Analysis**

```python
# Analyze adaptive weight effectiveness
async def analyze_adaptive_weights():
    # Compare accuracy with/without adaptive weights

    accuracy_with_adaptive = measure_accuracy(adaptive=True)
    accuracy_without_adaptive = measure_accuracy(adaptive=False)

    improvement = accuracy_with_adaptive - accuracy_without_adaptive

    print(f"Adaptive weights improvement: {improvement:.1%}")
```

### Performance Benchmarking

```python
# File: benchmarks/performance_benchmark.py

import asyncio
import time
from typing import List, Dict

async def benchmark_hybrid_scoring():
    """Comprehensive performance benchmark"""

    # Initialize service
    scorer = HybridScoringService()

    # Test scenarios
    scenarios = [
        {"name": "Cold cache", "warm": False, "iterations": 100},
        {"name": "Warm cache", "warm": True, "iterations": 1000},
        {"name": "Concurrent", "warm": True, "concurrent": 10, "iterations": 100}
    ]

    results = []

    for scenario in scenarios:
        print(f"\n=== {scenario['name']} ===")

        if scenario.get("warm"):
            # Warm cache
            await scorer.cache.warm_cache(common_patterns, scorer.client)

        # Run benchmark
        start = time.time()

        if scenario.get("concurrent"):
            # Concurrent execution
            tasks = []
            for i in range(scenario["iterations"]):
                task = scorer.score(
                    task_description=f"Task {i}",
                    historical_pattern_text=f"Pattern {i % 10}",
                    vector_similarity=0.8
                )
                tasks.append(task)

            await asyncio.gather(*tasks)
        else:
            # Sequential execution
            for i in range(scenario["iterations"]):
                await scorer.score(
                    task_description=f"Task {i}",
                    historical_pattern_text=f"Pattern {i}",
                    vector_similarity=0.8
                )

        duration = time.time() - start
        throughput = scenario["iterations"] / duration

        results.append({
            "scenario": scenario["name"],
            "iterations": scenario["iterations"],
            "duration": duration,
            "throughput": throughput,
            "avg_latency": (duration / scenario["iterations"]) * 1000
        })

        print(f"Duration: {duration:.2f}s")
        print(f"Throughput: {throughput:.1f} req/s")
        print(f"Avg latency: {results[-1]['avg_latency']:.1f}ms")

    # Print summary
    print("\n=== Summary ===")
    for result in results:
        print(f"{result['scenario']}: {result['throughput']:.1f} req/s @ {result['avg_latency']:.1f}ms avg")

    await scorer.close()


if __name__ == "__main__":
    asyncio.run(benchmark_hybrid_scoring())
```

---

## Maintenance Procedures

### Routine Maintenance

#### Daily Tasks

**1. Health Check**
```bash
# Automated daily health check
0 9 * * * cd /path/to/monitoring && python health_checker.py | mail -s "Daily Health Report" team@company.com
```

**2. Metrics Review**
```bash
# Review key metrics
curl -s 'http://localhost:9090/api/v1/query?query=semantic_cache_hit_rate' | jq .
curl -s 'http://localhost:9090/api/v1/query?query=rate(langextract_fallback_total[24h])' | jq .
```

#### Weekly Tasks

**1. Cache Analysis**
```python
# Weekly cache performance analysis
async def weekly_cache_analysis():
    metrics = cache.get_metrics()

    report = f"""
    === Weekly Cache Report ===
    Hit rate: {metrics['hit_rate']:.1%}
    Total requests: {metrics['total_requests']}
    Cache size: {metrics['current_size']}/{metrics['max_size']}
    Evictions: {metrics['evictions']}

    Recommendations:
    {"✅ Cache performing well" if metrics['hit_rate'] > 0.8 else "⚠️ Consider increasing cache size"}
    """

    send_email(subject="Weekly Cache Report", body=report)
```

**2. Log Rotation**
```bash
# Rotate logs weekly
0 2 * * 0 docker compose logs archon-intelligence --tail=10000 > logs/intelligence_$(date +\%Y\%m\%d).log
0 2 * * 0 docker compose logs archon-langextract --tail=10000 > logs/langextract_$(date +\%Y\%m\%d).log
```

#### Monthly Tasks

**1. Performance Review**
```python
# Monthly performance analysis
async def monthly_performance_review():
    # Analyze trends
    cache_hit_rate_trend = analyze_metric_trend("semantic_cache_hit_rate", days=30)
    latency_trend = analyze_metric_trend("langextract_request_duration_seconds", days=30)
    fallback_trend = analyze_metric_trend("langextract_fallback_total", days=30)

    # Generate report
    report = generate_monthly_report(cache_hit_rate_trend, latency_trend, fallback_trend)

    send_email(subject="Monthly Performance Review", body=report)
```

**2. Capacity Planning**
```python
# Monthly capacity analysis
async def capacity_planning():
    # Project growth
    current_throughput = measure_throughput()
    projected_growth_rate = 0.20  # 20% monthly growth

    capacity_months = calculate_months_until_capacity(current_throughput, projected_growth_rate)

    if capacity_months < 6:
        alert("Capacity planning required: <6 months until capacity")
```

### Upgrade Procedures

#### Rolling Update Procedure

```bash
# Step 1: Build new image
cd /Volumes/PRO-G40/Code/Archon/services/intelligence
docker build -t archon-intelligence:v2.1.0 .

# Step 2: Update one instance (if using multiple instances)
docker compose up -d --scale archon-intelligence=2 archon-intelligence

# Step 3: Monitor for 30 minutes
watch -n 10 'curl -s http://localhost:8053/health | jq .status'

# Step 4: If stable, update remaining instances
docker compose up -d archon-intelligence

# Step 5: Verify all instances updated
docker ps | grep archon-intelligence

# Step 6: Run smoke tests
python tests/smoke_tests.py
```

#### Rollback Procedure

```bash
# Quick rollback to previous version
docker compose down archon-intelligence
docker compose up -d archon-intelligence:v2.0.0  # Previous stable version

# Verify rollback
curl http://localhost:8053/health | jq .version
# Expected: 2.0.0
```

---

## Disaster Recovery

### Backup Procedures

**1. Configuration Backup**
```bash
# Backup configuration files
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  docker-compose.yml \
  .env \
  config/ \
  monitoring/

# Upload to S3 (or other backup storage)
aws s3 cp config_backup_$(date +%Y%m%d).tar.gz s3://backups/hybrid-scoring/
```

**2. Redis Backup** (if using persistent cache)
```bash
# Create Redis snapshot
redis-cli BGSAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb backups/redis_dump_$(date +%Y%m%d).rdb

# Upload to S3
aws s3 cp backups/redis_dump_$(date +%Y%m%d).rdb s3://backups/redis/
```

### Recovery Procedures

**Complete Service Recovery**

```bash
# Step 1: Restore configuration
aws s3 cp s3://backups/hybrid-scoring/config_backup_20251002.tar.gz .
tar -xzf config_backup_20251002.tar.gz

# Step 2: Restore Redis (if applicable)
aws s3 cp s3://backups/redis/redis_dump_20251002.rdb /var/lib/redis/dump.rdb
docker compose restart redis

# Step 3: Start services
docker compose up -d

# Step 4: Verify recovery
curl http://localhost:8053/health
curl http://localhost:8156/health
redis-cli ping

# Step 5: Warm cache (if needed)
python scripts/warm_cache.py

# Step 6: Run smoke tests
python tests/smoke_tests.py
```

---

**Operational Runbook Complete**
**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Next**: See [Architecture Decision Records](adr/) for design rationale
