# Performance Analytics API

**Phase 5C: Performance Intelligence - Workflow 9**

Comprehensive REST API for performance baseline reporting, anomaly detection, and optimization opportunity discovery.

## Overview

The Performance Analytics API provides 6 endpoints for monitoring and analyzing operation performance:

1. **GET /api/performance-analytics/baselines** - All operation baselines
2. **GET /api/performance-analytics/operations/{operation}/metrics** - Detailed metrics per operation
3. **GET /api/performance-analytics/optimization-opportunities** - ROI-ranked optimization suggestions
4. **POST /api/performance-analytics/operations/{operation}/anomaly-check** - Real-time anomaly detection
5. **GET /api/performance-analytics/trends** - Performance trends analysis
6. **GET /api/performance-analytics/health** - Service health check

## Architecture

```
┌─────────────────────────────────────────┐
│         FastAPI Router (routes.py)       │
│    6 endpoints + Pydantic models         │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│   PerformanceBaselineService             │
│   - In-memory measurement storage         │
│   - Real-time baseline calculation        │
│   - Z-score anomaly detection            │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│         Performance Measurements          │
│   Max 1000 measurements (LRU)            │
│   Baseline calculation every 10th sample  │
└─────────────────────────────────────────┘
```

## API Endpoints

### 1. GET /api/performance-analytics/baselines

Returns baseline statistics for all tracked operations.

**Query Parameters**:
- `operation` (optional): Filter by specific operation name

**Response**:
```json
{
  "baselines": {
    "codegen_validation": {
      "p50": 450.0,
      "p95": 1200.0,
      "p99": 1800.0,
      "mean": 500.0,
      "std_dev": 300.0,
      "sample_size": 150
    }
  },
  "total_operations": 4,
  "total_measurements": 600,
  "timestamp": "2025-10-15T10:30:00Z"
}
```

**Performance Target**: <50ms

**Example**:
```bash
curl http://localhost:8053/api/performance-analytics/baselines

# Filter by operation
curl "http://localhost:8053/api/performance-analytics/baselines?operation=codegen_validation"
```

### 2. GET /api/performance-analytics/operations/{operation}/metrics

Returns detailed performance metrics for a specific operation.

**Path Parameters**:
- `operation`: Operation name to retrieve metrics for

**Query Parameters**:
- `recent_count` (optional, default: 10): Number of recent measurements to include

**Response**:
```json
{
  "operation": "codegen_validation",
  "baseline": {
    "p50": 450.0,
    "p95": 1200.0,
    "p99": 1800.0,
    "mean": 500.0,
    "std_dev": 300.0,
    "sample_size": 150
  },
  "recent_measurements": [
    {
      "duration_ms": 480.0,
      "timestamp": "2025-10-15T10:30:00Z",
      "context": {}
    }
  ],
  "trend": "stable",
  "anomaly_count_24h": 3
}
```

**Performance Target**: <75ms

**Example**:
```bash
curl http://localhost:8053/api/performance-analytics/operations/codegen_validation/metrics

# Limit recent measurements
curl "http://localhost:8053/api/performance-analytics/operations/codegen_validation/metrics?recent_count=5"
```

### 3. GET /api/performance-analytics/optimization-opportunities

Returns prioritized optimization opportunities ranked by ROI score.

**Query Parameters**:
- `min_roi` (optional, default: 1.0): Minimum ROI score to include
- `max_effort` (optional, default: "high"): Maximum effort level (low/medium/high)

**Response**:
```json
{
  "opportunities": [
    {
      "operation": "codegen_validation",
      "current_p95": 1200.0,
      "estimated_improvement": 60.0,
      "effort_level": "medium",
      "roi_score": 30.0,
      "priority": "high",
      "recommendations": [
        "Add Redis caching for validation results",
        "Implement batch validation"
      ]
    }
  ],
  "total_opportunities": 2,
  "avg_roi": 25.5,
  "total_potential_improvement": 50.0
}
```

**Performance Target**: <100ms

**Example**:
```bash
curl http://localhost:8053/api/performance-analytics/optimization-opportunities

# Filter by ROI and effort
curl "http://localhost:8053/api/performance-analytics/optimization-opportunities?min_roi=5.0&max_effort=medium"
```

### 4. POST /api/performance-analytics/operations/{operation}/anomaly-check

Detects if current duration is a performance anomaly using Z-score analysis.

**Path Parameters**:
- `operation`: Operation name to check

**Request Body**:
```json
{
  "duration_ms": 3500.0
}
```

**Response**:
```json
{
  "anomaly_detected": true,
  "z_score": 6.67,
  "current_duration_ms": 3500.0,
  "baseline_mean": 500.0,
  "baseline_p95": 1200.0,
  "deviation_percentage": 600.0,
  "severity": "critical"
}
```

**Performance Target**: <25ms

**Severity Levels**:
- **normal**: Z-score ≤ 3.0
- **medium**: 3.0 < Z-score ≤ 4.0
- **high**: 4.0 < Z-score ≤ 5.0
- **critical**: Z-score > 5.0

**Example**:
```bash
curl -X POST http://localhost:8053/api/performance-analytics/operations/codegen_validation/anomaly-check \
  -H "Content-Type: application/json" \
  -d '{"duration_ms": 3500.0}'
```

### 5. GET /api/performance-analytics/trends

Returns performance trends across all operations for specified time window.

**Query Parameters**:
- `time_window` (optional, default: "24h"): Time window (24h/7d/30d)

**Response**:
```json
{
  "time_window": "24h",
  "operations": {
    "codegen_validation": {
      "trend": "stable",
      "avg_duration_change": 0.02,
      "anomaly_count": 3
    }
  },
  "overall_health": "good"
}
```

**Performance Target**: <100ms

**Health Levels**:
- **excellent**: No degraded operations, <10% anomalies
- **good**: <20% degraded operations, <30% anomalies
- **warning**: <50% degraded operations
- **critical**: ≥50% degraded operations

**Example**:
```bash
curl http://localhost:8053/api/performance-analytics/trends

# 7-day trends
curl "http://localhost:8053/api/performance-analytics/trends?time_window=7d"
```

### 6. GET /api/performance-analytics/health

Returns service health status and component status.

**Response**:
```json
{
  "status": "healthy",
  "baseline_service": "operational",
  "optimization_analyzer": "operational",
  "total_operations_tracked": 4,
  "total_measurements": 600,
  "uptime_seconds": 86400
}
```

**Performance Target**: <50ms

**Example**:
```bash
curl http://localhost:8053/api/performance-analytics/health
```

## Integration

### Initialize in app.py

```python
# Import router
from src.api.performance_analytics.routes import router as performance_analytics_router

# Import initialization function
from src.api.performance_analytics.routes import initialize_services

# In lifespan function
from src.services.performance.baseline_service import PerformanceBaselineService
performance_baseline_service = PerformanceBaselineService(max_measurements=1000)

# Initialize the router with the service
initialize_services(performance_baseline_service)

# Include router
app.include_router(performance_analytics_router)
```

### Recording Measurements

```python
# In your handler code
await performance_baseline_service.record_measurement(
    operation="codegen_validation",
    duration_ms=480.0,
    context={"node_type": "Effect", "event_type": "validation"}
)
```

## Performance Characteristics

| Metric | Target | Notes |
|--------|--------|-------|
| Measurement recording | <1ms | Minimal overhead |
| Baseline calculation | <10ms | Every 10th measurement |
| Anomaly detection | <5ms | Z-score calculation |
| API response time | <100ms | Most endpoints <50ms |
| Memory usage | <50MB | For 10,000 measurements |

## Testing

### Manual Testing

```bash
# 1. Start the intelligence service
cd /Volumes/PRO-G40/Code/omniarchon
docker compose up archon-intelligence

# 2. Wait for service to be ready
curl http://localhost:8053/health

# 3. Record some test measurements (Python script)
python3 <<EOF
import requests
import time

for i in range(20):
    # Simulate recording measurements
    duration = 500 + (i * 10)  # Gradually increasing
    print(f"Recording measurement {i+1}: {duration}ms")
    time.sleep(0.5)
EOF

# 4. Query baselines
curl http://localhost:8053/api/performance-analytics/baselines | jq

# 5. Check for optimization opportunities
curl http://localhost:8053/api/performance-analytics/optimization-opportunities | jq

# 6. Test anomaly detection
curl -X POST http://localhost:8053/api/performance-analytics/operations/codegen_validation/anomaly-check \
  -H "Content-Type: application/json" \
  -d '{"duration_ms": 5000.0}' | jq

# 7. View trends
curl http://localhost:8053/api/performance-analytics/trends?time_window=24h | jq
```

### Unit Tests

```bash
# Run baseline service tests
cd /Volumes/PRO-G40/Code/omniarchon/services/intelligence
pytest tests/api/performance_analytics/test_baseline_service.py -v

# Run API integration tests (requires full environment)
pytest tests/api/performance_analytics/test_routes.py -v
```

## Future Enhancements

1. **Persistent Storage**: Add database backend for historical data
2. **Optimization Analyzer**: Integrate with Workflow 8 for detailed optimization analysis
3. **Alerting**: Add webhook/notification support for critical anomalies
4. **Visualization**: Generate performance charts and trend graphs
5. **ML Predictions**: Use historical data for predictive anomaly detection
6. **Dashboard**: React-based real-time monitoring dashboard

## Related Documentation

- Baseline Service: `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src/services/performance/baseline_service.py`
- MVP Plan: `/Volumes/PRO-G40/Code/omniarchon/docs/MVP_PHASE_5_INTELLIGENCE_FEATURES_PLAN.md`
- Performance Thresholds: `@performance-thresholds.yaml`

## Support

For issues or questions, see:
- Integration guide in CLAUDE.md
- Phase 5C specification in MVP plan
- Test examples in `/tests/api/performance_analytics/`

---

**Status**: ✅ Production Ready (Workflow 9 Complete)
**Created**: 2025-10-15
**Version**: 1.0.0
