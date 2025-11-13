# Hybrid Pattern Scoring - Monitoring & Observability

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: 2025-10-02

## Overview

Comprehensive monitoring and observability infrastructure for the Archon Hybrid Pattern Scoring system. This system provides real-time metrics, alerting, and dashboards for:

- **Langextract Client Performance**: API request metrics, circuit breaker status, retry tracking
- **Semantic Cache Efficiency**: Hit rates, memory usage, eviction tracking
- **Hybrid Scoring Performance**: Latency percentiles, error rates, throughput
- **Pattern Quality Metrics**: Similarity score distributions, candidate evaluation counts
- **System Health**: Active sessions, database size, predictive analytics

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Monitoring Architecture                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Metrics Layer  │   Storage       │      Visualization          │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Prometheus    │ • Prometheus    │ • Grafana Dashboards        │
│   Client        │   TSDB          │ • Alert Manager UI          │
│ • Custom        │ • 30-day        │ • Real-time Graphs          │
│   Decorators    │   Retention     │ • Performance Trends        │
├─────────────────┼─────────────────┼─────────────────────────────┤
│  Alert Engine   │   Alerting      │      Intelligence           │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Alert Rules   │ • Email         │ • Predictive Alerts         │
│ • Thresholds    │ • Slack         │ • Anomaly Detection         │
│ • Severity      │ • PagerDuty     │ • Trend Analysis            │
│   Levels        │                 │                             │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Quick Start

### 1. Import Monitoring Module

```python
from services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (
    track_langextract_request,
    track_hybrid_scoring,
    record_cache_hit,
    record_cache_miss,
    initialize_system_info,
)

# Initialize system info on startup
initialize_system_info(
    version="1.0.0",
    config={
        "environment": "production",
        "langextract_url": "http://langextract:8000",
        "cache_enabled": True,
    }
)
```

### 2. Instrument Langextract Calls

```python
async def call_langextract_api(endpoint: str, payload: dict):
    """Example: Instrumenting langextract API calls"""
    with track_langextract_request(endpoint):
        response = await httpx.post(f"{LANGEXTRACT_URL}{endpoint}", json=payload)
        return response.json()
```

### 3. Instrument Hybrid Scoring

```python
def calculate_hybrid_score(semantic_score: float, structural_score: float):
    """Example: Instrumenting hybrid scoring calculation"""
    with track_hybrid_scoring(strategy='weighted_average'):
        # Your scoring logic here
        hybrid_score = (semantic_score * 0.6) + (structural_score * 0.4)

        # Record individual similarity scores
        record_pattern_similarity('semantic', semantic_score)
        record_pattern_similarity('structural', structural_score)
        record_pattern_similarity('hybrid', hybrid_score)

        return hybrid_score
```

### 4. Instrument Cache Operations

```python
async def get_from_cache(key: str):
    """Example: Instrumenting cache lookups"""
    with track_cache_lookup():
        result = await cache.get(key)

        if result:
            record_cache_hit()
        else:
            record_cache_miss()

        return result
```

## Metrics Reference

### Langextract Client Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `langextract_requests_total` | Counter | Total API requests | `endpoint`, `status` |
| `langextract_request_duration_seconds` | Histogram | Request duration | `endpoint` |
| `langextract_request_size_bytes` | Histogram | Request payload size | `endpoint` |
| `langextract_response_size_bytes` | Histogram | Response payload size | `endpoint` |
| `langextract_errors_total` | Counter | Total errors | `endpoint`, `error_type` |
| `langextract_circuit_breaker_state` | Gauge | Circuit breaker state (0/1/2) | `endpoint` |
| `langextract_circuit_breaker_failures_total` | Counter | Circuit breaker failures | `endpoint` |
| `langextract_retry_attempts_total` | Counter | Retry attempts | `endpoint`, `attempt` |

### Cache Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `semantic_cache_hits_total` | Counter | Total cache hits |
| `semantic_cache_misses_total` | Counter | Total cache misses |
| `semantic_cache_hit_rate` | Gauge | Current hit rate (0.0-1.0) |
| `semantic_cache_size_entries` | Gauge | Number of cache entries |
| `semantic_cache_evictions_total` | Counter | Total cache evictions |
| `semantic_cache_lookup_duration_seconds` | Histogram | Cache lookup duration |
| `semantic_cache_memory_usage_bytes` | Gauge | Estimated memory usage |

### Hybrid Scoring Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `hybrid_scoring_duration_seconds` | Histogram | Scoring calculation time | `scoring_strategy` |
| `hybrid_scoring_requests_total` | Counter | Total scoring requests | `scoring_strategy`, `status` |
| `pattern_similarity_score` | Histogram | Score distribution | `similarity_type` |
| `pattern_matching_candidates_count` | Histogram | Candidate evaluation count | - |
| `pattern_matching_duration_seconds` | Histogram | Total matching duration | - |

### Component Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `semantic_similarity_computation_seconds` | Histogram | Semantic similarity time | `method` |
| `structural_similarity_computation_seconds` | Histogram | Structural similarity time | `method` |
| `weight_calculation_duration_seconds` | Histogram | Weight calculation time | - |

## Alert Rules

### Critical Alerts (Immediate Action Required)

1. **LangextractCriticalErrorRate**: Error rate > 25% for 2 minutes
2. **LangextractCriticalLatency**: P95 latency > 10 seconds for 2 minutes
3. **CacheCriticalHitRate**: Hit rate < 40% for 5 minutes
4. **HybridScoringCriticalLatency**: P99 latency > 5 seconds for 2 minutes

### Warning Alerts (Attention Needed)

1. **LangextractHighErrorRate**: Error rate > 10% for 5 minutes
2. **CacheLowHitRate**: Hit rate < 60% for 10 minutes
3. **HybridScoringHighLatency**: P99 latency > 3 seconds for 5 minutes
4. **PatternMatchingHighCandidates**: P95 candidates > 250 for 10 minutes

### Predictive Alerts (Trend-based)

1. **CacheHitRateTrendingDown**: Predicted to drop below 50% in 2 hours
2. **HybridScoringLatencyTrendingUp**: P95 predicted to exceed 5s in 2 hours
3. **CacheMemoryUsageTrendingUp**: Predicted to exceed 2GB in 4 hours

## Grafana Dashboard

### Dashboard URL
```
http://localhost:3000/d/archon-hybrid-scoring
```

### Dashboard Panels

1. **Langextract Request Rate (5m)**: Real-time request throughput by endpoint and status
2. **Semantic Cache Hit Rate**: Gauge showing current hit rate (target: >80%)
3. **Cache Size (Entries)**: Current number of cached entries
4. **Hybrid Scoring Latency (P50, P95, P99)**: Latency percentiles by strategy
5. **Pattern Similarity Score Distribution**: Histogram of similarity scores
6. **Circuit Breaker Status**: Current state of circuit breakers
7. **Langextract Error Rate Trend**: Error rate percentage over time
8. **Retry Attempts Rate**: Retry frequency by endpoint
9. **Similarity Computation Time (P95)**: Semantic vs structural comparison
10. **Pattern Matching Candidate Count**: Number of candidates evaluated
11. **Cache Memory Usage**: Current memory consumption
12. **Cache Operations Rate**: Hits, misses, and evictions per second

### Dashboard Refresh
- **Default**: 10 seconds
- **Options**: 5s, 10s, 30s, 1m, 5m, 15m, 30m, 1h, 2h, 1d

## Usage Examples

### Example 1: Full Instrumentation

```python
from services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (
    track_langextract_request,
    track_hybrid_scoring,
    record_pattern_similarity,
    record_circuit_breaker_state,
    record_retry_attempt,
)

class LangextractClient:
    async def extract_patterns(self, content: str) -> dict:
        """Extract patterns with full monitoring"""
        endpoint = '/extract'

        # Track the request
        with track_langextract_request(endpoint):
            try:
                response = await self._make_request(endpoint, {'content': content})
                return response
            except CircuitBreakerOpen:
                record_circuit_breaker_state(endpoint, 'open')
                raise
            except Exception as e:
                # Retry with tracking
                for attempt in range(1, 4):
                    record_retry_attempt(endpoint, attempt)
                    try:
                        response = await self._make_request(endpoint, {'content': content})
                        return response
                    except Exception:
                        if attempt == 3:
                            raise

class HybridScorer:
    def score_pattern(self, pattern: dict, reference: dict) -> float:
        """Calculate hybrid score with monitoring"""
        with track_hybrid_scoring(strategy='adaptive_weights'):
            # Calculate semantic similarity
            semantic_score = self.semantic_similarity(pattern, reference)
            record_pattern_similarity('semantic', semantic_score)

            # Calculate structural similarity
            structural_score = self.structural_similarity(pattern, reference)
            record_pattern_similarity('structural', structural_score)

            # Calculate hybrid score
            hybrid_score = self.combine_scores(semantic_score, structural_score)
            record_pattern_similarity('hybrid', hybrid_score)

            return hybrid_score
```

### Example 2: Async Function Decoration

```python
from services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (
    instrument_async_function,
)

@instrument_async_function('semantic_similarity', {'type': 'batch'})
async def batch_semantic_similarity(patterns: list[dict]) -> list[float]:
    """Automatically instrumented async function"""
    results = []
    for pattern in patterns:
        score = await compute_similarity(pattern)
        results.append(score)
    return results
```

### Example 3: Metrics Summary

```python
from services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (
    get_metrics_summary,
)

# Get current metrics summary
summary = get_metrics_summary()
print(f"Cache hit rate: {summary['cache']['hit_rate']:.2%}")
print(f"Total langextract requests: {summary['langextract']['total_requests']}")
print(f"Circuit breaker failures: {summary['langextract']['circuit_breaker_failures']}")
```

## Prometheus Configuration

### Add Job to prometheus.yml

```yaml
scrape_configs:
  - job_name: 'archon-intelligence'
    scrape_interval: 15s
    static_configs:
      - targets: ['intelligence:8053']
    metrics_path: '/metrics'
```

### Load Alert Rules

```yaml
rule_files:
  - '/etc/prometheus/rules/archon_alerts.yml'
  - '/etc/prometheus/rules/hybrid_scoring_alerts.yml'
```

## Performance Targets

| Metric | Target | Warning Threshold | Critical Threshold |
|--------|--------|-------------------|-------------------|
| Langextract P95 Latency | < 2s | > 5s | > 10s |
| Cache Hit Rate | > 80% | < 60% | < 40% |
| Hybrid Scoring P99 | < 2s | > 3s | > 5s |
| Error Rate | < 1% | > 5% | > 10% |
| Cache Lookup P95 | < 10ms | > 100ms | > 500ms |

## Troubleshooting

### High Error Rate

1. Check Grafana dashboard for error distribution
2. Review logs for specific error types
3. Verify langextract service health
4. Check circuit breaker states

### Low Cache Hit Rate

1. Review cache size and memory usage
2. Check eviction rate (high evictions = undersized cache)
3. Verify cache key generation logic
4. Consider cache warming strategies

### High Latency

1. Check P95/P99 latency breakdown by component
2. Review candidate count (high count = slow matching)
3. Verify langextract service performance
4. Consider horizontal scaling

### Missing Metrics

1. Verify Prometheus scraping: `curl http://intelligence:8053/metrics`
2. Check Prometheus targets: `http://prometheus:9090/targets`
3. Review service logs for errors
4. Verify network connectivity

## Best Practices

### 1. Metric Naming
- Use descriptive names with units (e.g., `_seconds`, `_bytes`, `_total`)
- Follow Prometheus naming conventions
- Include relevant labels for filtering

### 2. Alert Tuning
- Start with conservative thresholds
- Adjust based on baseline performance
- Use `for:` duration to avoid flapping
- Implement predictive alerts for trends

### 3. Dashboard Design
- Group related metrics
- Use appropriate visualization types
- Include context (targets, baselines)
- Add annotations for deployments

### 4. Performance
- Use labels sparingly (high cardinality = high cost)
- Sample high-frequency metrics if needed
- Use histograms for latency tracking
- Clean up old metrics regularly

## Integration Testing

### Test Metrics Endpoint

```bash
# Test metrics export
curl http://localhost:8053/metrics | grep hybrid_scoring

# Expected output:
# hybrid_scoring_duration_seconds_bucket{le="0.01",scoring_strategy="default"} 0
# hybrid_scoring_duration_seconds_bucket{le="0.05",scoring_strategy="default"} 5
# ...
```

### Test Alert Rules

```bash
# Validate alert rules
promtool check rules /monitoring/prometheus/rules/hybrid_scoring_alerts.yml

# Test specific alert
promtool test rules /monitoring/prometheus/rules/hybrid_scoring_alerts_test.yml
```

### Test Grafana Dashboard

```bash
# Import dashboard via API
curl -X POST http://admin:admin123@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @/monitoring/grafana/dashboards/hybrid_scoring_dashboard.json
```

## Maintenance

### Regular Tasks

- **Daily**: Review alert trends, check dashboard health
- **Weekly**: Analyze performance trends, tune alert thresholds
- **Monthly**: Review metric retention, optimize queries
- **Quarterly**: Dashboard refresh, alert rule audit

### Metric Retention

- **Raw metrics**: 15 days (high resolution)
- **Downsampled**: 30 days (standard resolution)
- **Long-term**: 1 year (via recording rules)

## Support & Documentation

### Resources

- **Prometheus Docs**: https://prometheus.io/docs/
- **Grafana Docs**: https://grafana.com/docs/
- **AlertManager Docs**: https://prometheus.io/docs/alerting/latest/alertmanager/
- **Best Practices**: https://prometheus.io/docs/practices/

### Contact

For issues or questions:
1. Check troubleshooting section above
2. Review service logs
3. Consult Grafana dashboards
4. Contact platform team

---

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Maintained by**: Archon Intelligence Team
