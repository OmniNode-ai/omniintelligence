# HTTP Connection Pooling Implementation

**Status**: ✅ Implemented
**Date**: 2025-10-15
**Target Improvement**: 30-50% latency reduction for HTTP calls

## Overview

HTTP connection pooling has been implemented across all backend service HTTP clients to improve performance and reduce connection establishment overhead. This implementation provides:

- **Persistent connections** with configurable keep-alive
- **Connection reuse** across multiple requests
- **Configurable pool sizes** via environment variables
- **Proper lifecycle management** (startup/shutdown)
- **Performance monitoring** via metrics

## Architecture

### Connection Pool Configuration

All HTTP clients use httpx.AsyncClient with connection pooling:

```python
httpx.AsyncClient(
    timeout=httpx.Timeout(
        timeout=30.0,      # Overall timeout
        connect=10.0,      # Connection timeout
        read=30.0,         # Read timeout
        write=5.0          # Write timeout
    ),
    limits=httpx.Limits(
        max_connections=100,            # Total connection pool size
        max_keepalive_connections=20    # Keep-alive connection pool
    )
)
```

### Implementation Components

1. **HTTPClientConfig** (`src/config/http_client_config.py`)
   - Centralized configuration management
   - Environment variable integration
   - Pre-configured client creation functions

2. **Service-Level Clients**
   - `EnhancedEntityExtractor`: Ollama API calls (20 connections, 5 keepalive)
   - `ClientLangextractHttp`: LangExtract service (20 connections, 5 keepalive)
   - `FreshnessDatabase`: Bridge service (10 connections, 5 keepalive)
   - `WorkflowCoordinatorClient`: Workflow coordinator (20 connections, 5 keepalive)

3. **Shared HTTP Client** (`app.py`)
   - Application-level shared client for background tasks
   - Lifecycle-managed (created at startup, closed at shutdown)
   - Used by document indexing pipeline

## Configuration

### Environment Variables

Configure connection pooling via environment variables:

```bash
# Default HTTP client configuration
HTTP_CLIENT_MAX_CONNECTIONS=100
HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS=20
HTTP_CLIENT_DEFAULT_TIMEOUT=30.0
HTTP_CLIENT_CONNECT_TIMEOUT=10.0
HTTP_CLIENT_READ_TIMEOUT=30.0
HTTP_CLIENT_WRITE_TIMEOUT=5.0
HTTP_CLIENT_MAX_RETRIES=3
HTTP_CLIENT_RETRY_BACKOFF_MULTIPLIER=2.0

# Search service specific configuration
SEARCH_SERVICE_HTTP_CLIENT_MAX_CONNECTIONS=50
SEARCH_SERVICE_HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS=10
SEARCH_SERVICE_HTTP_CLIENT_DEFAULT_TIMEOUT=30.0
```

### Per-Service Configuration

| Service | Max Connections | Keepalive | Timeout | Use Case |
|---------|----------------|-----------|---------|----------|
| EnhancedEntityExtractor | 20 | 5 | 30s | Ollama embedding generation |
| ClientLangextractHttp | 20 | 5 | 5s | Semantic analysis |
| FreshnessDatabase | 10 | 5 | 30s | Bridge database queries |
| WorkflowCoordinatorClient | 20 | 5 | 30s | Workflow coordination |
| Shared Client (app.py) | 100* | 20* | 30s | Background tasks |

\* Configurable via environment variables

## Usage Examples

### Using Pre-configured Clients

```python
from src.config.http_client_config import create_default_client, create_search_service_client

# Create default client
async with create_default_client() as client:
    response = await client.get("http://service/api/endpoint")

# Create search service client with custom timeout
async with create_search_service_client(timeout_override=60.0) as client:
    response = await client.post("http://search/api/query")
```

### Using Custom Configuration

```python
from src.config.http_client_config import HTTPClientConfig

# Create custom configuration
config = HTTPClientConfig(
    max_connections=50,
    max_keepalive_connections=10,
    default_timeout=15.0,
    connect_timeout=5.0,
    read_timeout=10.0,
    write_timeout=3.0,
    max_retries=2,
    retry_backoff_multiplier=1.5,
)

# Create client from config
async with config.create_httpx_client() as client:
    response = await client.get("http://service/api/endpoint")
```

### Shared Client in Background Tasks

```python
# In app.py lifespan
global shared_http_client
from src.config.http_client_config import create_search_service_client

shared_http_client = create_search_service_client(timeout_override=30.0)

# In background task
async def _process_document_background(...):
    if shared_http_client:
        response = await shared_http_client.post(url, json=data)
    else:
        # Fallback to one-off client
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
```

## Performance Benefits

### Expected Improvements

| Scenario | Without Pooling | With Pooling | Improvement |
|----------|----------------|--------------|-------------|
| Sequential requests (50) | ~2.5s | ~1.5s | **40%** |
| Concurrent requests (20) | ~1.8s | ~0.9s | **50%** |
| Background indexing (100 docs) | ~15s | ~9s | **40%** |

### Connection Overhead Reduction

- **TCP handshake**: ~1-2ms per request → **0ms** (reused connections)
- **TLS negotiation**: ~10-50ms per request → **0ms** (reused connections)
- **Connection teardown**: ~1-2ms per request → **Deferred** (keepalive)

### Resource Utilization

- **Reduced file descriptors**: One connection per pool vs. one per request
- **Lower CPU usage**: Less connection establishment overhead
- **Better memory efficiency**: Connection pool management vs. continuous creation/destruction

## Testing

### Unit Tests

```bash
# Run unit tests
pytest services/intelligence/tests/unit/test_http_connection_pooling.py -v

# Expected output:
# ✅ Test default configuration from environment
# ✅ Test custom configuration from environment
# ✅ Test httpx client creation with pooling
# ✅ Test EnhancedEntityExtractor has connection pooling
# ✅ Test connection reuse
# ✅ Test pool limits configuration
```

### Performance Benchmarks

```bash
# Run performance benchmarks
pytest services/intelligence/tests/performance/test_connection_pooling_benchmark.py -v -s -m benchmark

# Expected output:
# ================================================================
# SEQUENTIAL REQUESTS PERFORMANCE BENCHMARK
# ================================================================
# Total requests: 50
#
# WITHOUT Connection Pooling:
#   Total time: 2.4532s
#   Average per request: 49.06ms
#   Requests/second: 20.38
#
# WITH Connection Pooling:
#   Total time: 1.5124s
#   Average per request: 30.25ms
#   Requests/second: 33.06
#
# ✅ Performance improvement: 38.4%
# ================================================================
```

## Monitoring

### Client Metrics

All HTTP clients expose metrics for monitoring:

```python
client.get_metrics()
# Returns:
# {
#     "total_requests": 150,
#     "successful_requests": 145,
#     "failed_requests": 5,
#     "timeout_errors": 2,
#     "circuit_breaker_opens": 1,
#     "retries_attempted": 8,
#     "total_duration_ms": 45000.0,
#     "success_rate": 0.967,
#     "avg_duration_ms": 310.34,
#     "circuit_breaker_state": "closed",
#     "is_healthy": true
# }
```

### Health Checks

```python
# Check client health
health = await client.check_health()
# Returns:
# {
#     "healthy": true,
#     "status_code": 200,
#     "response_time_ms": 45.23,
#     "last_check": "2025-10-15T10:30:00Z"
# }
```

## Troubleshooting

### Issue: Connection Pool Exhaustion

**Symptoms**: Requests hang or timeout when pool is full

**Solution**:
```bash
# Increase max connections
HTTP_CLIENT_MAX_CONNECTIONS=200
HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS=50
```

### Issue: Stale Connections

**Symptoms**: Intermittent connection failures

**Solution**:
```bash
# Reduce keepalive time
HTTP_CLIENT_CONNECT_TIMEOUT=5.0
# Connections are refreshed more frequently
```

### Issue: High Memory Usage

**Symptoms**: Memory increases with connection pool

**Solution**:
```bash
# Reduce pool size
HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS=10
# Fewer persistent connections
```

## Best Practices

1. **Reuse clients**: Always reuse HTTP clients across multiple requests
2. **Use context managers**: Ensure proper cleanup with `async with`
3. **Configure appropriately**: Tune pool sizes based on load patterns
4. **Monitor metrics**: Track connection pool utilization
5. **Handle failures gracefully**: Implement retry logic and circuit breakers
6. **Set timeouts**: Always configure reasonable timeouts
7. **Lifecycle management**: Create clients at startup, close at shutdown

## Implementation Checklist

- [x] Add connection pooling to EnhancedEntityExtractor
- [x] Create HTTPClientConfig for centralized configuration
- [x] Add shared HTTP client to app.py lifecycle
- [x] Update background tasks to use shared client
- [x] Add environment variable configuration
- [x] Write unit tests for connection pooling
- [x] Write performance benchmarks
- [x] Document configuration and usage
- [x] Verify connection reuse in tests

## Future Improvements

1. **Adaptive pool sizing**: Dynamically adjust pool size based on load
2. **Connection health monitoring**: Proactively detect and replace unhealthy connections
3. **Per-endpoint pooling**: Separate pools for different service endpoints
4. **Connection metrics dashboard**: Real-time visualization of pool utilization
5. **Automatic retry with backoff**: Built-in retry logic for all clients

## References

- [httpx Connection Pooling Documentation](https://www.python-httpx.org/advanced/#pool-limit-configuration)
- [HTTP/1.1 Persistent Connections](https://tools.ietf.org/html/rfc2616#section-8.1)
- [Connection Pooling Best Practices](https://www.python-httpx.org/advanced/#timeout-configuration)

---

**Last Updated**: 2025-10-15
**Maintained By**: Intelligence Service Team
