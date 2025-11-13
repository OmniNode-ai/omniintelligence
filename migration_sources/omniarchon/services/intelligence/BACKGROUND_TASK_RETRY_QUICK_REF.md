# Background Task Retry - Quick Reference

## TL;DR

All background tasks in `app.py` now have **automatic retry with exponential backoff** and **Prometheus metrics tracking**.

## Usage

### Adding Retry to New Background Tasks

```python
from src.utils.background_task_utils import retry_background_task

@retry_background_task(
    max_retries=3,
    initial_delay=1.0,
    backoff_multiplier=2.0,
    operation_name="my_task",
    operation_type="custom_operation"
)
async def my_background_task(arg1, arg2):
    """Your background task with automatic retry."""
    # Task implementation
    await do_something(arg1, arg2)
```

### Quick Configuration Guide

| Operation Type | Recommended Config | Use Case |
|----------------|-------------------|----------|
| Lightweight (freshness, webhooks) | `initial_delay=0.5s`, `max_retries=3` | Fast operations, quick recovery |
| Standard (entity storage) | `initial_delay=1.0s`, `max_retries=3` | Database operations, API calls |
| Complex (document processing) | `initial_delay=2.0s`, `max_retries=3` | Multi-step pipelines, external services |
| Critical (payments, notifications) | `initial_delay=1.0s`, `max_retries=5` | High-importance operations |

### Error Classification

**Will retry** (transient errors):
- Timeout errors (`asyncio.TimeoutError`)
- Network errors (`ConnectionError`, `NetworkError`)
- Service unavailable (503)
- Unknown errors (safe default)

**Won't retry** (persistent errors):
- Validation errors (422, 400)
- Authentication errors (401, 403)
- Server errors (500)

### Monitoring

**Check metrics**:
```bash
# Total tasks and success rate
curl http://localhost:8053/metrics | grep background_tasks_total
curl http://localhost:8053/metrics | grep background_tasks_success

# Failed tasks by error type
curl http://localhost:8053/metrics | grep background_tasks_failed

# Retry attempts
curl http://localhost:8053/metrics | grep background_task_retries

# Execution time
curl http://localhost:8053/metrics | grep background_task_duration_seconds

# Currently active
curl http://localhost:8053/metrics | grep background_tasks_active
```

**Watch logs**:
```bash
docker logs -f archon-intelligence | grep "Background task"
```

### Structured Logging

All logs include:
- `correlation_id` - Unique ID for tracking
- `task_name` - Operation name
- `operation_type` - Task category
- `attempt` - Current retry attempt
- `error_type` - Classified error type
- `timestamp` - ISO 8601 timestamp

**Example log entry**:
```json
{
  "level": "WARNING",
  "message": "Background task attempt 1/4 failed: process_document. Retrying in 2.0s...",
  "extra": {
    "task_name": "process_document",
    "operation_type": "document_processing",
    "correlation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "attempt": 1,
    "max_retries": 4,
    "error_type": "timeout",
    "error_message": "Connection timeout",
    "retry_delay_seconds": 2.0
  }
}
```

### Debugging Failed Tasks

**Step 1: Check logs for correlation ID**
```bash
docker logs archon-intelligence | grep "correlation_id=f47ac10b"
```

**Step 2: Check metrics for failure patterns**
```bash
curl http://localhost:8053/metrics | grep background_tasks_failed
```

**Step 3: Review error type distribution**
```bash
curl http://localhost:8053/metrics | grep 'error_type="'
```

### Custom Retry Logic

**Override defaults**:
```python
@retry_background_task(
    max_retries=5,          # More retries for critical tasks
    initial_delay=0.5,      # Faster retry for lightweight tasks
    backoff_multiplier=3.0, # Aggressive backoff
    max_delay=120.0,        # Cap at 2 minutes
    operation_name="critical_payment",
    operation_type="payment_processing",
    track_metrics=True      # Enable Prometheus metrics (default: True)
)
async def process_payment(transaction_id):
    # Implementation
    pass
```

### Disable Retry for Specific Tasks

```python
# Option 1: Set max_retries=0
@retry_background_task(max_retries=0, operation_name="no_retry_task")
async def my_task():
    pass

# Option 2: Don't use decorator (no metrics tracking)
async def my_task_no_retry():
    pass
```

## Current Background Tasks

| Task | Operation Type | Max Retries | Initial Delay | Location |
|------|----------------|-------------|---------------|----------|
| `_process_document_background` | `document_processing` | 3 | 2.0s | app.py:1743 |
| `_store_entities_background` | `entity_storage` | 3 | 1.0s | app.py:720 |
| `_trigger_freshness_analysis_background` | `freshness_analysis` | 3 | 0.5s | app.py:780 |

## Metrics Cheat Sheet

```promql
# Success rate by task
sum(rate(background_tasks_success[5m])) by (task_name) /
sum(rate(background_tasks_total[5m])) by (task_name)

# P95 execution time
histogram_quantile(0.95, rate(background_task_duration_seconds_bucket[5m]))

# Failure rate by error type
sum(rate(background_tasks_failed[5m])) by (error_type)

# Retry rate
sum(rate(background_task_retries[5m]))

# Active tasks
background_tasks_active
```

## Troubleshooting

### High Retry Rate

**Symptoms**: Many retries, slow processing
**Diagnosis**: Check `background_task_retries` metric
**Fix**:
1. Check service health (Memgraph, Search service)
2. Increase timeouts if needed
3. Review error logs for patterns

### Silent Failures (Pre-Fix Behavior)

**Old**: Errors only logged, no retry
**New**: Automatic retry + metrics tracking

### Task Stuck in Retry Loop

**Check**: Are errors transient or persistent?
```bash
docker logs archon-intelligence | grep "error_type" | tail -20
```

**Fix**: If persistent errors (validation, auth), update task logic to handle correctly

### High Memory Usage

**Check**: Number of active tasks
```bash
curl http://localhost:8053/metrics | grep background_tasks_active
```

**Fix**: Adjust task execution rate or increase resources

## See Also

- [src/utils/background_task_utils.py](./src/utils/background_task_utils.py) - Source code
- [Prometheus docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) - Metrics querying
- [Circuit Breaker Implementation](./CIRCUIT_BREAKER_IMPLEMENTATION.md) - Related patterns
