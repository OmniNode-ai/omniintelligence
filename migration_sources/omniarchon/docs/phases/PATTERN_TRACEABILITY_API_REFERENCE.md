# Phase 4 API Reference
# Track 3: Pattern Learning Engine - Pattern Traceability & Feedback Loop

**Version**: 1.0.0
**Last Updated**: 2025-10-03
**Base URL**: `http://localhost:8053`

---

## Table of Contents

1. [REST API Endpoints](#rest-api-endpoints)
2. [Python API](#python-api)
3. [Request/Response Schemas](#requestresponse-schemas)
4. [Error Codes](#error-codes)
5. [Rate Limits](#rate-limits)
6. [Authentication](#authentication)

---

## REST API Endpoints

### Analytics APIs

#### GET /api/analytics/pattern/{pattern_id}

Get comprehensive usage analytics for a pattern.

**Parameters**:
- `pattern_id` (path, required): UUID of the pattern
- `time_window` (query, optional): Time window - `hourly`, `daily`, `weekly` (default), `monthly`, `quarterly`, `yearly`, `all_time`
- `granularity` (query, optional): Detail level - `summary`, `detailed` (default), `comprehensive`
- `include_trends` (query, optional): Include trend analysis (default: `true`)
- `include_performance` (query, optional): Include performance metrics (default: `true`)
- `include_distribution` (query, optional): Include context distribution (default: `true`)

**Example Request**:
```bash
curl -X GET "http://localhost:8053/api/analytics/pattern/550e8400-e29b-41d4-a716-446655440000?time_window=weekly&granularity=comprehensive"
```

**Response** (200 OK):
```json
{
  "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
  "time_window_start": "2025-09-26T00:00:00Z",
  "time_window_end": "2025-10-03T00:00:00Z",
  "time_window_type": "weekly",

  "usage_metrics": {
    "total_executions": 150,
    "executions_per_day": 21.4,
    "executions_per_week": 150.0,
    "executions_per_month": 642.9,
    "unique_contexts": 4,
    "unique_users": 5,
    "peak_daily_usage": 28,
    "time_since_last_use": 0.5
  },

  "success_metrics": {
    "success_count": 128,
    "failure_count": 22,
    "success_rate": 0.853,
    "error_rate": 0.147,
    "timeout_count": 0,
    "quality_gate_failures": 3,
    "avg_quality_score": 0.82
  },

  "performance_metrics": {
    "avg_execution_time_ms": 203.5,
    "p50_execution_time_ms": 165.0,
    "p95_execution_time_ms": 425.7,
    "p99_execution_time_ms": 478.1,
    "min_execution_time_ms": 45.2,
    "max_execution_time_ms": 520.4,
    "std_dev_ms": 125.3,
    "total_execution_time_ms": 30525.0
  },

  "trend_analysis": {
    "trend_type": "growing",
    "velocity": 2.35,
    "acceleration": 0.45,
    "adoption_rate": 0.85,
    "retention_rate": 0.923,
    "churn_rate": 0.077,
    "growth_percentage": 0.185,
    "confidence_score": 0.875
  },

  "context_distribution": {
    "by_context_type": {
      "development": 68,
      "debugging": 42,
      "testing": 26,
      "production": 14
    },
    "by_agent": {
      "agent-1": 48,
      "agent-2": 42,
      "user-direct": 35,
      "agent-3": 25
    },
    "by_project": {
      "project-a": 57,
      "project-b": 52,
      "project-c": 41
    },
    "by_time_of_day": {
      "14": 18,
      "10": 16,
      "16": 15
    }
  },

  "total_data_points": 150,
  "analytics_quality_score": 0.92,
  "computation_time_ms": 245.3
}
```

---

#### GET /api/analytics/trends

Get trend summary across all patterns.

**Parameters**:
- `time_window` (query, optional): Time window (default: `weekly`)
- `min_executions` (query, optional): Minimum executions to include (default: `10`)

**Response** (200 OK):
```json
{
  "timestamp": "2025-10-03T10:30:00Z",
  "time_window": "weekly",
  "total_patterns_analyzed": 25,

  "trends_summary": {
    "growing": 8,
    "stable": 12,
    "declining": 3,
    "emerging": 1,
    "abandoned": 1
  },

  "top_growing_patterns": [
    {
      "pattern_id": "...",
      "pattern_name": "DatabaseQueryPattern",
      "velocity": 3.5,
      "growth_percentage": 0.28
    }
  ],

  "patterns_needing_attention": [
    {
      "pattern_id": "...",
      "pattern_name": "AuthPattern",
      "issue": "declining_usage",
      "velocity": -1.2
    }
  ]
}
```

---

### Lineage APIs

#### GET /api/lineage/{pattern_id}

Get complete lineage graph for a pattern.

**Parameters**:
- `pattern_id` (path, required): UUID of the pattern
- `include_edges` (query, optional): Include edge details (default: `true`)
- `max_depth` (query, optional): Maximum traversal depth (default: `unlimited`)

**Response** (200 OK):
```json
{
  "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_versions": 4,
  "total_edges": 3,

  "nodes": [
    {
      "node_id": "550e8400-e29b-41d4-a716-446655440001",
      "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
      "version_number": 1,
      "pattern_name": "DatabaseQueryPattern",
      "performance_baseline": {
        "p50": 450.0,
        "p95": 850.0,
        "p99": 1200.0
      },
      "created_at": "2025-10-03T08:00:00Z",
      "status": "active"
    }
  ],

  "edges": [
    {
      "edge_id": "...",
      "source_node_id": "...",
      "target_node_id": "...",
      "edge_type": "IMPROVED_VERSION",
      "weight": 1.0,
      "metadata": {
        "improvement_type": "performance",
        "performance_delta": 0.62,
        "p_value": 0.003,
        "confidence": 0.997
      },
      "created_at": "2025-10-03T09:00:00Z"
    }
  ]
}
```

---

#### GET /api/lineage/{pattern_id}/path/{node_id}

Get lineage path from root to specific node.

**Response** (200 OK):
```json
{
  "pattern_id": "...",
  "node_id": "...",
  "path_length": 4,

  "lineage_path": [
    {
      "version_number": 1,
      "node_id": "...",
      "performance_baseline": {"p95": 850.0},
      "created_at": "2025-10-03T08:00:00Z"
    },
    {
      "version_number": 2,
      "node_id": "...",
      "performance_baseline": {"p95": 320.0},
      "improvement_from_parent": 0.624,
      "created_at": "2025-10-03T09:00:00Z"
    }
  ]
}
```

---

#### GET /api/lineage/{pattern_id}/ancestors/{node_id}

Get all ancestor versions of a node.

**Response** (200 OK):
```json
{
  "node_id": "...",
  "ancestor_count": 3,

  "ancestors": [
    {
      "version_number": 1,
      "node_id": "...",
      "depth": 3,
      "created_at": "2025-10-03T08:00:00Z"
    }
  ]
}
```

---

#### GET /api/lineage/{pattern_id}/descendants/{node_id}

Get all descendant versions (improvements) of a node.

**Response** (200 OK):
```json
{
  "node_id": "...",
  "descendant_count": 2,

  "descendants": [
    {
      "version_number": 3,
      "node_id": "...",
      "depth": 1,
      "improvement_delta": 0.53,
      "created_at": "2025-10-03T10:00:00Z"
    }
  ]
}
```

---

### Feedback APIs

#### POST /api/feedback

Submit user feedback for a pattern.

**Request Body**:
```json
{
  "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
  "execution_id": "550e8400-e29b-41d4-a716-446655440010",
  "feedback_type": "performance",
  "rating": 2.0,
  "sentiment": "negative",
  "comments": "Query taking too long on large datasets",
  "metadata": {
    "expected_duration_ms": 200.0,
    "actual_duration_ms": 850.0,
    "severity": "high"
  },
  "user_id": "user@example.com"
}
```

**Response** (201 Created):
```json
{
  "feedback_id": "...",
  "pattern_id": "...",
  "execution_id": "...",
  "feedback_type": "performance",
  "submitted_at": "2025-10-03T10:30:00Z",
  "status": "received"
}
```

---

#### GET /api/feedback/pattern/{pattern_id}

Get all feedback for a pattern.

**Parameters**:
- `pattern_id` (path, required): UUID of the pattern
- `feedback_type` (query, optional): Filter by type - `performance`, `quality`, `usage`
- `limit` (query, optional): Max results (default: `50`, max: `500`)
- `offset` (query, optional): Pagination offset (default: `0`)

**Response** (200 OK):
```json
{
  "pattern_id": "...",
  "total_feedback": 45,
  "limit": 50,
  "offset": 0,
  "has_more": false,

  "feedback_items": [
    {
      "feedback_id": "...",
      "feedback_type": "performance",
      "rating": 2.0,
      "sentiment": "negative",
      "sentiment_score": -0.75,
      "comments": "Too slow",
      "submitted_at": "2025-10-03T10:00:00Z",
      "user_id": "user@example.com"
    }
  ],

  "aggregated_stats": {
    "avg_rating": 3.2,
    "total_positive": 20,
    "total_negative": 15,
    "total_neutral": 10
  }
}
```

---

### Feedback Loop APIs

#### POST /api/feedback-loop/trigger

Trigger feedback loop workflow for a pattern.

**Request Body**:
```json
{
  "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
  "feedback_type": "performance",
  "time_window_days": 7,
  "auto_apply_threshold": 0.95,
  "min_sample_size": 30,
  "significance_level": 0.05,
  "enable_ab_testing": true
}
```

**Response** (202 Accepted):
```json
{
  "workflow_id": "...",
  "pattern_id": "...",
  "status": "started",
  "estimated_duration_seconds": 60,
  "started_at": "2025-10-03T10:35:00Z",

  "configuration": {
    "feedback_type": "performance",
    "time_window_days": 7,
    "auto_apply_threshold": 0.95
  }
}
```

---

#### GET /api/feedback-loop/status/{workflow_id}

Get status of a running feedback loop workflow.

**Response** (200 OK):
```json
{
  "workflow_id": "...",
  "pattern_id": "...",
  "status": "completed",

  "current_stage": "apply",
  "completed_stages": ["collect", "analyze", "validate", "apply"],

  "results": {
    "feedback_collected": 150,
    "improvements_identified": 3,
    "improvements_validated": 2,
    "improvements_applied": 1,
    "performance_delta": 0.60,
    "confidence_score": 0.997,
    "p_value": 0.003,
    "statistically_significant": true
  },

  "started_at": "2025-10-03T10:35:00Z",
  "completed_at": "2025-10-03T10:36:15Z",
  "duration_seconds": 75
}
```

---

## Python API

### NodePatternLineageTrackerEffect

**ONEX Effect Node** for lineage I/O operations.

```python
from pattern_learning.phase4_traceability import (
    NodePatternLineageTrackerEffect,
    ModelContractEffect,
)

# Initialize
tracker = NodePatternLineageTrackerEffect()

# Insert lineage node
contract = ModelContractEffect(
    operation="insert_node",
    data={
        "pattern_id": uuid4(),
        "version_number": 1,
        "pattern_name": "MyPattern",
        "template_code": "...",
        "performance_baseline": {"p95": 850.0}
    }
)
result = await tracker.execute_effect(contract)
node_id = result.data["node_id"]

# Create lineage edge
edge_contract = ModelContractEffect(
    operation="create_edge",
    data={
        "source_node_id": parent_node_id,
        "target_node_id": node_id,
        "edge_type": "IMPROVED_VERSION",
        "metadata": {"performance_delta": 0.62}
    }
)
await tracker.execute_effect(edge_contract)

# Query lineage path
path_contract = ModelContractEffect(
    operation="get_lineage_path",
    data={"node_id": node_id}
)
path_result = await tracker.execute_effect(path_contract)
lineage_path = path_result.data["lineage_path"]

# Get ancestors
ancestors_contract = ModelContractEffect(
    operation="get_ancestors",
    data={"node_id": node_id}
)
ancestors_result = await tracker.execute_effect(ancestors_contract)
ancestors = ancestors_result.data["ancestors"]

# Get descendants
descendants_contract = ModelContractEffect(
    operation="get_descendants",
    data={"node_id": node_id}
)
descendants_result = await tracker.execute_effect(descendants_contract)
descendants = descendants_result.data["descendants"]
```

---

### NodeUsageAnalyticsReducer

**ONEX Reducer Node** for usage analytics computation.

```python
from pattern_learning.phase4_traceability import (
    NodeUsageAnalyticsReducer,
    ModelUsageAnalyticsInput,
    TimeWindowType,
    AnalyticsGranularity,
)
from datetime import datetime, timedelta, timezone

# Initialize
reducer = NodeUsageAnalyticsReducer()

# Create input contract
contract = ModelUsageAnalyticsInput(
    pattern_id=pattern_id,
    time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
    time_window_end=datetime.now(timezone.utc),
    time_window_type=TimeWindowType.WEEKLY,
    granularity=AnalyticsGranularity.COMPREHENSIVE,

    # Feature flags
    include_trends=True,
    include_performance=True,
    include_distribution=True,

    # Execution data (from database)
    execution_data=execution_data,

    correlation_id=uuid4()
)

# Compute analytics
result = await reducer.execute_reduction(contract)

# Access metrics
print(f"Total Executions: {result.usage_metrics.total_executions}")
print(f"Success Rate: {result.success_metrics.success_rate:.1%}")
print(f"P95 Latency: {result.performance_metrics.p95_execution_time_ms:.2f}ms")
print(f"Trend: {result.trend_analysis.trend_type.value}")
```

---

### NodeFeedbackLoopOrchestrator

**ONEX Orchestrator Node** for feedback loop workflow.

```python
from pattern_learning.phase4_traceability import (
    NodeFeedbackLoopOrchestrator,
    ModelFeedbackLoopInput,
)

# Initialize
orchestrator = NodeFeedbackLoopOrchestrator()

# Configure feedback loop
contract = ModelFeedbackLoopInput(
    pattern_id="pattern_api_debug_v1",
    feedback_type="performance",
    time_window_days=7,
    auto_apply_threshold=0.95,
    min_sample_size=30,
    significance_level=0.05,
    enable_ab_testing=True,
    correlation_id=uuid4()
)

# Execute feedback loop
result = await orchestrator.execute_orchestration(contract)

if result.success:
    print(f"Improvements Applied: {result.data['improvements_applied']}")
    print(f"Performance Delta: {result.data['performance_delta']:+.1%}")
    print(f"Confidence: {result.data['confidence_score']:.1%}")
    print(f"p-value: {result.data['p_value']}")
else:
    print(f"Error: {result.error}")
```

---

## Request/Response Schemas

### ModelContractEffect

Base contract for Effect node operations.

```python
{
  "operation": str,           # Operation type
  "data": Dict[str, Any],     # Operation-specific data
  "correlation_id": UUID,     # Tracing ID
  "timestamp": datetime       # Request timestamp
}
```

### ModelUsageAnalyticsInput

Input contract for analytics computation.

```python
{
  "pattern_id": UUID,
  "time_window_start": datetime,
  "time_window_end": datetime,
  "time_window_type": TimeWindowType,
  "granularity": AnalyticsGranularity,
  "include_trends": bool,
  "include_performance": bool,
  "include_distribution": bool,
  "include_predictions": bool,
  "execution_data": List[Dict[str, Any]],
  "correlation_id": UUID
}
```

### ModelFeedbackLoopInput

Input contract for feedback loop orchestration.

```python
{
  "pattern_id": str,
  "feedback_type": str,
  "time_window_days": int,
  "auto_apply_threshold": float,
  "min_sample_size": int,
  "significance_level": float,
  "enable_ab_testing": bool,
  "correlation_id": UUID
}
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Async operation started |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable Entity | Validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Response Format

```json
{
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Not enough feedback data to generate improvements",
    "details": {
      "required_sample_size": 30,
      "actual_sample_size": 15,
      "pattern_id": "..."
    },
    "timestamp": "2025-10-03T10:45:00Z",
    "correlation_id": "..."
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INSUFFICIENT_DATA` | Not enough data for operation |
| `INVALID_PATTERN_ID` | Pattern ID not found |
| `INVALID_NODE_ID` | Lineage node not found |
| `LOW_CONFIDENCE` | Improvements below confidence threshold |
| `VALIDATION_FAILED` | Input validation failed |
| `DATABASE_ERROR` | Database operation failed |
| `WORKFLOW_TIMEOUT` | Feedback loop timeout |
| `CIRCULAR_DEPENDENCY` | Circular lineage detected |

---

## Rate Limits

### Default Limits

| Endpoint Pattern | Limit | Window |
|------------------|-------|--------|
| `/api/analytics/*` | 100 requests | 1 minute |
| `/api/lineage/*` | 200 requests | 1 minute |
| `/api/feedback` | 50 requests | 1 minute |
| `/api/feedback-loop/trigger` | 10 requests | 1 minute |

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1696329600
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after_seconds": 60,
    "timestamp": "2025-10-03T10:50:00Z"
  }
}
```

---

## Authentication

### Current Implementation

Phase 4 currently uses **no authentication** for development. All endpoints are open.

### Planned Authentication (Phase 5)

Future authentication will use:
- **API Keys** for service-to-service
- **JWT Tokens** for user requests
- **OAuth2** for external integrations

**Example with API Key** (Phase 5):
```bash
curl -X GET "http://localhost:8053/api/analytics/pattern/{id}" \
  -H "X-API-Key: your-api-key"
```

---

## WebSocket API (Future)

Real-time feedback loop status updates (planned for Phase 5).

```javascript
const ws = new WebSocket('ws://localhost:8053/ws/feedback-loop/{workflow_id}');

ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log(`Stage: ${status.current_stage}, Progress: ${status.progress}%`);
};
```

---

## Support & Resources

**Documentation**:
- User Guide: [PATTERN_TRACEABILITY_USER_GUIDE.md](PATTERN_TRACEABILITY_USER_GUIDE.md)
- Operations: [PATTERN_TRACEABILITY_OPERATIONS.md](PATTERN_TRACEABILITY_OPERATIONS.md)

**Example Code**:
- `/services/intelligence/src/services/pattern_learning/phase4_traceability/analytics_examples.py`
- `/services/intelligence/src/services/pattern_learning/phase4_traceability/feedback_workflow_examples.py`

**API Client Libraries**:
- Python: `from pattern_learning.phase4_traceability import *`
- TypeScript: Coming in Phase 5
- REST: Standard HTTP/JSON

---

**Version**: 1.0.0
**Last Updated**: 2025-10-03
**Maintainer**: Archon Intelligence Team
