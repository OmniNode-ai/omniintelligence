# Correlation ID Tracing Enhancements (PR #18 - Priority 3)

## Overview

This document describes the correlation ID tracing enhancements implemented across the Archon Intelligence Service codebase. These improvements enable distributed tracing across service boundaries, making it easier to track requests through the entire system.

## Implemented Changes

### 1. Enhanced Logging with Correlation IDs

**Files Modified:**
- `services/intelligence/src/api/performance_analytics/routes.py`
- `services/intelligence/src/api/pattern_learning/routes.py`
- `services/intelligence/src/api/custom_rules/routes.py`

**Changes:**
- Added `correlation_id` parameter logging to all endpoint handlers
- Format: `logger.info(f"<METHOD> <ENDPOINT> | correlation_id={correlation_id}")`
- Enables request tracking across all API endpoints

**Example:**
```python
async def health_check(correlation_id: Optional[UUID] = None):
    logger.info(f"GET /api/performance-analytics/health | correlation_id={correlation_id}")
    # ... rest of implementation
```

### 2. Distributed Tracing in HTTP Clients

**Files Modified:**
- `services/intelligence/src/clients/metadata_stamping_client.py`

**Changes:**
- Added `correlation_id` parameter to all public methods:
  - `stamp_file()`
  - `batch_stamp()`
  - `validate_stamp()`
  - `get_stamp()`
- Propagated correlation_id through internal call chain:
  - `_execute_with_retry()`
  - `_execute_request()`
  - `_make_http_request()`
- Added `X-Correlation-ID` HTTP header to all outgoing requests
- Updated misleading comment from "correlation_id support enabled" to "Distributed tracing via X-Correlation-ID header"

**Example:**
```python
async def stamp_file(
    self,
    file_hash: str,
    metadata: Dict[str, Any],
    overwrite: bool = False,
    timeout_override: Optional[float] = None,
    correlation_id: Optional[UUID] = None
) -> StampResult:
    # ... implementation
    result = await self._execute_with_retry(
        "POST",
        "/api/v1/metadata-stamping/stamp",
        request,
        StampResult,
        timeout_override,
        correlation_id
    )
```

**Header Propagation:**
```python
async def _make_http_request(
    self,
    method: str,
    url: str,
    request: BaseModel,
    timeout: float,
    correlation_id: Optional[UUID] = None
) -> httpx.Response:
    # Build headers with optional correlation ID for distributed tracing
    headers = {}
    if correlation_id:
        headers["X-Correlation-ID"] = str(correlation_id)

    response = await self.client.post(
        url,
        json=request.model_dump(),
        timeout=timeout,
        headers=headers
    )
```

### 3. Correlation ID Context Manager

**Files Created:**
- `services/intelligence/src/utils/correlation_context.py`

**Features:**
- **Async Context Manager**: `correlation_context()` for async code
- **Sync Context Manager**: `correlation_context_sync()` for synchronous code
- **Automatic ID Generation**: Generates UUID if not provided
- **Context Variables**: Thread-safe storage using `contextvars`
- **Logging Filter**: Automatically adds correlation_id to all log records
- **Logging Formatter**: Custom formatter with correlation_id support
- **FastAPI Integration**: Dependency injection helper for route handlers

**Usage Examples:**

**Basic Usage:**
```python
from src.utils.correlation_context import correlation_context
from uuid import uuid4

# Automatic correlation ID generation
async with correlation_context():
    logger.info("This log includes correlation_id automatically")

# Explicit correlation ID (e.g., from HTTP header)
correlation_id = uuid4()
async with correlation_context(correlation_id):
    logger.info("This log includes the specified correlation_id")
```

**FastAPI Integration:**
```python
from fastapi import Depends
from src.utils.correlation_context import correlation_context, get_correlation_id_dependency

@router.get("/endpoint")
async def endpoint(
    correlation_id: UUID = Depends(get_correlation_id_dependency)
):
    async with correlation_context(correlation_id):
        logger.info("Processing request")
        # All logs in this scope include correlation_id
```

**Nested Contexts:**
```python
async with correlation_context() as outer_id:
    logger.info(f"Outer context: {outer_id}")

    async with correlation_context() as inner_id:
        logger.info(f"Inner context: {inner_id}")

    logger.info(f"Back to outer context: {get_correlation_id()}")
```

**Custom Logging Format:**
```python
import logging
from src.utils.correlation_context import CorrelationIdFilter

# Add filter to logger
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationIdFilter())

# Configure format
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | correlation_id=%(correlation_id)s | %(message)s'
)
```

## Benefits

### 1. **End-to-End Request Tracking**
- Track a single request across multiple services and components
- Correlate logs from different services using the same correlation_id
- Easier debugging of distributed system issues

### 2. **Observability Improvements**
- Logs now include correlation_id consistently across all endpoints
- HTTP headers propagate correlation_id to downstream services
- Context manager ensures correlation_id is available throughout request lifecycle

### 3. **Developer Experience**
- Simple API for adding correlation_id to any context
- Automatic logging integration (no manual correlation_id logging required)
- FastAPI dependency injection support for easy integration

### 4. **Production Readiness**
- Thread-safe implementation using contextvars
- Async-compatible context managers
- Minimal performance overhead (context variables are highly optimized)

## Implementation Details

### Correlation ID Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Client Request                                          │
│     X-Correlation-ID: abc-123-def-456                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. API Endpoint Handler (FastAPI)                         │
│     - Extract correlation_id from header or generate new   │
│     - Log: "GET /api/endpoint | correlation_id=abc-123"    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Context Manager Scope                                   │
│     async with correlation_context(correlation_id):         │
│         # All logs automatically include correlation_id     │
│         logger.info("Processing...")                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  4. HTTP Client Call                                        │
│     await client.stamp_file(                                │
│         ...,                                                │
│         correlation_id=correlation_id                       │
│     )                                                       │
│     # Adds X-Correlation-ID header to outgoing request     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Downstream Service                                      │
│     - Receives X-Correlation-ID header                      │
│     - Uses same correlation_id for its logs                 │
│     - Continues propagation to further services             │
└─────────────────────────────────────────────────────────────┘
```

### Context Variable Storage

- Uses Python's `contextvars` module for async-safe storage
- Each async task has its own correlation_id context
- No cross-contamination between concurrent requests
- Automatic cleanup when context exits

### Logging Integration

- **Filter-based approach**: CorrelationIdFilter adds correlation_id to all log records
- **Formatter-based approach**: CorrelationIdFormatter includes correlation_id in output
- Both approaches can be combined for maximum flexibility
- Works with existing logging configuration

## Testing

### Manual Testing

```bash
# Test endpoint logging
curl -H "X-Correlation-ID: test-123" http://localhost:8053/api/performance-analytics/health

# Check logs for correlation_id
docker logs archon-intelligence 2>&1 | grep "correlation_id=test-123"

# Test context manager
python -m services.intelligence.src.utils.correlation_context
```

### Unit Tests

```python
import pytest
from uuid import uuid4
from src.utils.correlation_context import correlation_context, get_correlation_id

@pytest.mark.asyncio
async def test_correlation_context():
    """Test correlation context manager"""
    # Test auto-generation
    async with correlation_context() as corr_id:
        assert corr_id is not None
        assert get_correlation_id() == corr_id

    # Context cleaned up
    assert get_correlation_id() is None

    # Test explicit ID
    explicit_id = uuid4()
    async with correlation_context(explicit_id) as corr_id:
        assert corr_id == explicit_id
        assert get_correlation_id() == explicit_id

@pytest.mark.asyncio
async def test_nested_contexts():
    """Test nested correlation contexts"""
    async with correlation_context() as outer_id:
        assert get_correlation_id() == outer_id

        async with correlation_context() as inner_id:
            assert get_correlation_id() == inner_id
            assert inner_id != outer_id

        # Restored to outer context
        assert get_correlation_id() == outer_id
```

## Migration Guide

### For Existing Endpoints

**Before:**
```python
@router.get("/endpoint")
async def endpoint():
    logger.info("Processing request")
    # ... implementation
```

**After:**
```python
from uuid import UUID
from typing import Optional

@router.get("/endpoint")
async def endpoint(correlation_id: Optional[UUID] = None):
    logger.info(f"GET /endpoint | correlation_id={correlation_id}")
    # ... implementation
```

### For HTTP Clients

**Before:**
```python
async with MetadataStampingClient() as client:
    result = await client.stamp_file(
        file_hash="abc123",
        metadata={"key": "value"}
    )
```

**After:**
```python
from uuid import uuid4

correlation_id = uuid4()
async with MetadataStampingClient() as client:
    result = await client.stamp_file(
        file_hash="abc123",
        metadata={"key": "value"},
        correlation_id=correlation_id
    )
```

### For New Code

**Recommended Pattern:**
```python
from fastapi import Depends
from src.utils.correlation_context import correlation_context, get_correlation_id_dependency

@router.post("/process")
async def process_data(
    data: dict,
    correlation_id: UUID = Depends(get_correlation_id_dependency)
):
    async with correlation_context(correlation_id):
        logger.info("Starting data processing")

        # All logs in this scope automatically include correlation_id
        result = await process_step_1(data)
        logger.info("Step 1 complete")

        result = await process_step_2(result)
        logger.info("Step 2 complete")

        # HTTP client calls propagate correlation_id
        await external_service.update(
            result,
            correlation_id=correlation_id
        )

        return result
```

## Future Enhancements

### Phase 2 (Potential)
1. **OpenTelemetry Integration**: Add OpenTelemetry spans for APM tools
2. **Automatic Header Extraction**: FastAPI middleware to extract X-Correlation-ID
3. **Database Query Tracing**: Add correlation_id to database query comments
4. **Kafka Message Tracing**: Propagate correlation_id through Kafka headers
5. **Metrics Tags**: Add correlation_id as metric tag for correlation with logs

### Phase 3 (Potential)
1. **Distributed Tracing UI**: Visualization tool for request flows
2. **Correlation ID Search**: Search logs by correlation_id across services
3. **Performance Analytics**: Aggregate latency by correlation_id
4. **Alert Correlation**: Group alerts by correlation_id for root cause analysis

## Related Documentation

- **ONEX Architecture**: `/docs/onex/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md`
- **Performance Optimization**: `/docs/PERFORMANCE_PHASE1.md`
- **Intelligence APIs**: `/CLAUDE.md` (Intelligence APIs section)
- **Security Hardening**: `/IMPROVEMENTS.md` (Post-merge improvements)

## References

- **Python contextvars**: https://docs.python.org/3/library/contextvars.html
- **OpenTelemetry Context Propagation**: https://opentelemetry.io/docs/concepts/context-propagation/
- **W3C Trace Context**: https://www.w3.org/TR/trace-context/
- **HTTP Header Best Practices**: https://tools.ietf.org/html/rfc6648

---

**Status**: ✅ Implemented
**PR**: #18
**Priority**: 3 (Tracing Enhancements)
**Date**: January 2025
