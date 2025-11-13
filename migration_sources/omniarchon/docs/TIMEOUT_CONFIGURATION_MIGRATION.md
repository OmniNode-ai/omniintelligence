# Timeout Configuration Migration Guide

**Version**: 1.0.0
**Status**: Centralized timeout configuration implemented
**Module**: `config/timeout_config.py`

## Overview

This guide documents the migration from hardcoded timeout values to centralized configuration-driven timeouts using Pydantic Settings.

## What Changed

### Before (Hardcoded)
```python
# Scattered hardcoded values throughout codebase
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url, timeout=5.0)

await asyncio.wait_for(task, timeout=10.0)
conn = await asyncpg.connect(url, timeout=30)
```

### After (Configuration-Driven)
```python
from config import get_http_timeout, get_async_timeout, get_db_timeout

async with httpx.AsyncClient(timeout=get_http_timeout("default")) as client:
    response = await client.get(url, timeout=get_http_timeout("health"))

await asyncio.wait_for(task, timeout=get_async_timeout("standard"))
conn = await asyncpg.connect(url, timeout=get_db_timeout("connection"))
```

## Benefits

1. **Environment-Based Configuration**: Override any timeout via environment variables
2. **Type Safety**: Pydantic validation ensures values are within acceptable ranges
3. **Consistency**: Same timeout values across services for similar operations
4. **Flexibility**: Easy to adjust timeouts for different deployment environments (dev/staging/prod)
5. **Documentation**: Self-documenting with clear categories and validation ranges

## Configuration Categories

### 1. HTTP Timeouts (`get_http_timeout`)

**Service-Specific**:
- `default` - Default HTTP operations (30.0s)
- `intelligence` - Intelligence service calls (60.0s)
- `search` - Search service calls (45.0s)
- `bridge` - Bridge service calls (30.0s)
- `mcp` - MCP service calls (30.0s)
- `langextract` - Langextract operations (90.0s)
- `health` - Health check endpoints (5.0s)
- `optimization` - Optimization operations (120.0s)

**Connection-Level**:
- Use `httpx.Timeout()` for granular control:
  ```python
  from config import timeout_config

  timeout = httpx.Timeout(
      connect=timeout_config.http.connect,    # 10.0s
      read=timeout_config.http.read,          # 30.0s
      write=timeout_config.http.write,        # 5.0s
      pool=None
  )
  ```

### 2. Database Timeouts (`get_db_timeout`)

- `connection` - Database connection timeout (30.0s)
- `query` - Query execution timeout (60.0s)
- `socket` - Socket operation timeout (5.0s)
- `socket_connect` - Socket connection timeout (5.0s)
- `acquire` - Connection pool acquire timeout (2.0s)
- `memgraph_connection` - Memgraph connection timeout (30.0s)
- `memgraph_command` - Memgraph command execution timeout (60.0s)

### 3. Cache Timeouts (`get_cache_timeout`)

- `operation` - Cache operation timeout (2.0s)
- `socket` - Cache socket operation timeout (5.0s)
- `socket_connect` - Cache socket connection timeout (5.0s)

### 4. Async Operation Timeouts (`get_async_timeout`)

- `quick` - Quick async operations (2.0s)
- `standard` - Standard async operations (10.0s)
- `long` - Long-running async operations (30.0s)
- `consumer_shutdown` - Kafka consumer shutdown (10.0s)
- `event_consumption` - Event consumption task shutdown (30.0s)
- `git` - Git operations (5.0s)
- `git_log` - Git log operations (10.0s)

### 5. Retry Configuration (`get_retry_config`)

Returns dictionary with:
- `max_attempts` - Maximum retry attempts (3)
- `backoff_multiplier` - Exponential backoff multiplier (2.0)
- `max_delay` - Maximum retry delay (60.0s)

## Migration Steps

### Step 1: Add Import

For files in services subdirectories:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import get_http_timeout, get_db_timeout, get_cache_timeout, get_async_timeout
```

For files in root or python/:
```python
from config import get_http_timeout, get_db_timeout, get_cache_timeout, get_async_timeout
```

### Step 2: Identify Timeout Patterns

Search for common patterns:
```bash
grep -r "timeout\s*=\s*\d+" services/
grep -r "asyncio\.sleep\(\d+" services/
grep -r "time\.sleep\(\d+" services/
grep -r "asyncio\.wait_for.*timeout=" services/
```

### Step 3: Replace HTTP Timeouts

**httpx.AsyncClient**:
```python
# Before
self.http_client = httpx.AsyncClient(timeout=30.0)

# After
self.http_client = httpx.AsyncClient(timeout=get_http_timeout("search"))
```

**Individual requests**:
```python
# Before
response = await client.get(url, timeout=5.0)

# After
response = await client.get(url, timeout=get_http_timeout("health"))
```

**httpx.Timeout objects**:
```python
# Before
timeout = httpx.Timeout(30.0)
timeout = httpx.Timeout(30.0, connect=10.0, read=30.0, write=5.0)

# After
from config import timeout_config
timeout = httpx.Timeout(timeout_config.http.default)
timeout = httpx.Timeout(
    timeout_config.http.default,
    connect=timeout_config.http.connect,
    read=timeout_config.http.read,
    write=timeout_config.http.write
)
```

### Step 4: Replace Database Timeouts

**asyncpg connections**:
```python
# Before
conn = await asyncpg.connect(url, timeout=30)

# After
conn = await asyncpg.connect(url, timeout=get_db_timeout("connection"))
```

**Connection pool**:
```python
# Before
pool = await asyncpg.create_pool(
    url,
    command_timeout=60,
    timeout=30
)

# After
pool = await asyncpg.create_pool(
    url,
    command_timeout=get_db_timeout("query"),
    timeout=get_db_timeout("connection")
)
```

**Memgraph connections**:
```python
# Before
driver = neo4j.AsyncGraphDatabase.driver(
    uri,
    connection_timeout=30.0
)

# After
driver = neo4j.AsyncGraphDatabase.driver(
    uri,
    connection_timeout=get_db_timeout("memgraph_connection")
)
```

### Step 5: Replace Cache Timeouts

**Redis/Valkey**:
```python
# Before
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    socket_timeout=5,
    socket_connect_timeout=5
)

# After
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    socket_timeout=get_cache_timeout("socket"),
    socket_connect_timeout=get_cache_timeout("socket_connect")
)
```

### Step 6: Replace Async Timeouts

**asyncio.wait_for**:
```python
# Before
result = await asyncio.wait_for(task, timeout=10.0)

# After
result = await asyncio.wait_for(task, timeout=get_async_timeout("standard"))
```

**asyncio.sleep** (for periodic tasks):
```python
# Before
await asyncio.sleep(30)  # Health check interval

# After
from config import timeout_config
await asyncio.sleep(timeout_config.background_task.health_check_interval)
```

### Step 7: Replace Retry Logic

**Before**:
```python
max_retries = 3
backoff = 2.0
for attempt in range(max_retries):
    try:
        result = await operation()
        break
    except Exception:
        if attempt < max_retries - 1:
            await asyncio.sleep(backoff ** attempt)
```

**After**:
```python
from config import get_retry_config

retry_config = get_retry_config()
for attempt in range(retry_config["max_attempts"]):
    try:
        result = await operation()
        break
    except Exception:
        if attempt < retry_config["max_attempts"] - 1:
            delay = min(
                retry_config["backoff_multiplier"] ** attempt,
                retry_config["max_delay"]
            )
            await asyncio.sleep(delay)
```

## Environment Variable Overrides

Override any timeout via environment variables:

```bash
# HTTP timeouts
HTTP_TIMEOUT_INTELLIGENCE=90.0
HTTP_TIMEOUT_SEARCH=60.0
HTTP_TIMEOUT_HEALTH_CHECK=10.0

# Database timeouts
DB_TIMEOUT_CONNECTION=45.0
DB_TIMEOUT_QUERY=120.0

# Cache timeouts
CACHE_TIMEOUT_OPERATION=5.0

# Async timeouts
ASYNC_TIMEOUT_STANDARD_OPERATION=20.0

# Retry configuration
RETRY_MAX_ATTEMPTS=5
RETRY_BACKOFF_MULTIPLIER=1.5
```

## Migration Status

### Completed (✅)
- **Bridge Service**:
  - `services/bridge/app.py` - 2 timeouts migrated
  - `services/bridge/mapping/entity_mapper.py` - 2 timeouts migrated

- **Search Service** (Sample):
  - `services/search/orchestration/hybrid_search.py` - 3 timeouts migrated
  - `services/search/engines/vector_search.py` - 3 timeouts migrated

### Pending (⏳)

**High Priority**:
- `services/search/engines/qdrant_adapter.py` - 3 timeouts
- `services/search/engines/graph_search.py` - 1 timeout
- `services/search/engines/search_cache.py` - 2 timeouts
- `python/src/mcp_server/gateway/unified_gateway.py` - timeouts
- `python/src/mcp_server/orchestration/service_client.py` - timeouts
- `python/src/mcp_server/features/intelligence/*.py` - multiple timeouts
- `services/intelligence/src/handlers/*.py` - multiple timeouts
- `services/intelligence/src/services/*.py` - multiple timeouts

**Medium Priority**:
- `services/langextract/events/extraction_event_emitter.py` - 1 timeout
- `services/langextract/integration/event_subscriber.py` - 3 asyncio.sleep
- `python/src/omninode_bridge/clients/client_intelligence_service.py` - timeouts
- Test files with hardcoded timeouts

**Low Priority** (Scripts/Tests):
- `scripts/*.py` - Various test and utility scripts
- `tests/**/*.py` - Test files with hardcoded timeouts

## Testing After Migration

1. **Unit Tests**: Verify configuration loading
   ```bash
   python -c "from config import timeout_config; print(timeout_config.http.intelligence)"
   ```

2. **Integration Tests**: Test with overridden values
   ```bash
   HTTP_TIMEOUT_INTELLIGENCE=90.0 pytest tests/integration/
   ```

3. **Service Health Checks**: Verify services start correctly
   ```bash
   docker compose up -d
   curl http://localhost:8053/health
   curl http://localhost:8055/health
   curl http://localhost:8054/health
   ```

4. **Performance Testing**: Ensure timeouts work as expected
   ```bash
   # Test short timeout triggers correctly
   HTTP_TIMEOUT_HEALTH_CHECK=0.001 docker compose up archon-search
   # Should see timeout errors in logs
   ```

## Validation Ranges

All timeout configurations have validation ranges to prevent misconfiguration:

| Configuration | Min | Max | Default | Unit |
|---------------|-----|-----|---------|------|
| HTTP Default | 1.0 | 300.0 | 30.0 | seconds |
| HTTP Health Check | 1.0 | 30.0 | 5.0 | seconds |
| HTTP Intelligence | 10.0 | 300.0 | 60.0 | seconds |
| HTTP Search | 10.0 | 300.0 | 45.0 | seconds |
| HTTP Langextract | 10.0 | 300.0 | 90.0 | seconds |
| HTTP Optimization | 30.0 | 600.0 | 120.0 | seconds |
| DB Connection | 5.0 | 120.0 | 30.0 | seconds |
| DB Query | 5.0 | 300.0 | 60.0 | seconds |
| Cache Operation | 0.5 | 30.0 | 2.0 | seconds |
| Async Quick | 0.5 | 30.0 | 2.0 | seconds |
| Async Standard | 1.0 | 300.0 | 10.0 | seconds |
| Async Long | 5.0 | 600.0 | 30.0 | seconds |
| Retry Max Attempts | 1 | 10 | 3 | count |
| Retry Backoff | 1.0 | 5.0 | 2.0 | multiplier |

## Common Issues

### Issue 1: Import Error
```
ModuleNotFoundError: No module named 'config'
```

**Solution**: Add correct path adjustment:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import get_http_timeout
```

### Issue 2: Validation Error
```
ValidationError: HTTP_TIMEOUT_INTELLIGENCE must be between 10.0 and 300.0
```

**Solution**: Check environment variable value is within valid range.

### Issue 3: Timeout Still Hardcoded
```
# service.py still uses hardcoded value
timeout=30.0
```

**Solution**: Ensure you're importing from the correct module and using the helper functions.

## Best Practices

1. **Use Appropriate Timeout Category**: Match timeout to operation type
   - Health checks → `get_http_timeout("health")` (5s)
   - Long operations → `get_http_timeout("intelligence")` (60s)
   - Quick operations → `get_async_timeout("quick")` (2s)

2. **Environment-Specific Overrides**: Set different timeouts per environment
   - Development: Longer timeouts for debugging
   - Production: Optimized timeouts for performance
   - Testing: Shorter timeouts to catch issues faster

3. **Document Timeout Choices**: When using timeouts, document why
   ```python
   # Use intelligence timeout for ML model operations (can be slow)
   timeout = get_http_timeout("intelligence")
   ```

4. **Test Timeout Scenarios**: Verify timeout behavior
   - Test timeout triggers correctly
   - Test retry logic with exponential backoff
   - Test graceful degradation on timeout

## Next Steps

1. **Complete High Priority Migrations**: Focus on service core files
2. **Update Tests**: Ensure tests use configuration instead of hardcoded values
3. **Monitor Performance**: Track if timeout changes affect performance
4. **Document Service-Specific Needs**: Add environment overrides for edge cases
5. **Gradual Rollout**: Deploy changes service by service, monitor impact

## Support

For questions or issues:
- Review `config/timeout_config.py` for implementation details
- Check `.env.example` for all available configuration options
- See `CLAUDE.md` for usage examples and integration guide

---

**Last Updated**: 2025-10-23
**Migration Progress**: 10% (Bridge & Sample Search Files)
**Target Completion**: 100% migration across all services
