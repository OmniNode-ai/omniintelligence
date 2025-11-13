# Archon Security Guide

**Version**: 1.0.0 | **Phase**: Stream 4 - Security & Production Hardening

Comprehensive security configuration guide for production deployments of Archon MCP.

## Table of Contents

1. [Overview](#overview)
2. [Valkey Authentication](#valkey-authentication)
3. [Cache Stampede Protection](#cache-stampede-protection)
4. [Rate Limiting](#rate-limiting)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Production Checklist](#production-checklist)

---

## Overview

Archon MCP includes three production-grade security features:

| Feature | Purpose | Performance Impact |
|---------|---------|-------------------|
| **Valkey Authentication** | Prevent unauthorized cache access | <5ms overhead |
| **Cache Stampede Protection** | Prevent thundering herd on cache misses | <100ms additional latency |
| **Rate Limiting** | Prevent abuse and protect backend services | <10ms per check |

All features support **graceful degradation**:
- Authentication failure → Cache disabled (not crashed)
- Rate limiting failure → Fail-open (allow all requests)
- No crashes, only warnings in logs

---

## Valkey Authentication

### Overview

Password authentication for Valkey (Redis fork) distributed cache prevents unauthorized access and cache poisoning attacks.

### Configuration

#### 1. Set Password in Environment Variables

Edit `.env`:

```bash
# IMPORTANT: Change this in production!
VALKEY_PASSWORD=your_secure_password_here

# Connection URL with password
VALKEY_URL=redis://:your_secure_password_here@archon-valkey:6379/0
```

#### 2. Update Docker Compose

The docker-compose.yml already includes auth configuration:

```yaml
archon-valkey:
  environment:
    - VALKEY_PASSWORD=${VALKEY_PASSWORD:-archon_cache_2025}
  command: >
    valkey-server
    --requirepass ${VALKEY_PASSWORD:-archon_cache_2025}
    # ... other flags
```

#### 3. Update MCP Service Environment

The archon-mcp service already includes auth:

```yaml
archon-mcp:
  environment:
    - VALKEY_URL=redis://:${VALKEY_PASSWORD:-archon_cache_2025}@archon-valkey:6379/0
    - VALKEY_PASSWORD=${VALKEY_PASSWORD:-archon_cache_2025}
```

### Testing Authentication

```bash
# Test with correct password
docker exec archon-valkey valkey-cli -a archon_cache_2025 ping
# Expected: PONG

# Test with wrong password (should fail)
docker exec archon-valkey valkey-cli -a wrong_password ping
# Expected: (error) WRONGPASS invalid username-password pair
```

### Disabling Authentication (Dev Only)

For development environments where authentication is not needed:

```bash
# In .env
VALKEY_PASSWORD=

# Or set to empty in docker-compose.yml
VALKEY_PASSWORD=
```

**WARNING**: Never disable authentication in production!

### Security Best Practices

1. **Strong Passwords**: Use 32+ character passwords in production
2. **Rotate Regularly**: Change passwords every 90 days
3. **Secure Storage**: Store passwords in secrets management (AWS Secrets Manager, HashiCorp Vault)
4. **Monitor Access**: Check `connected_clients` in cache stats for unauthorized connections

---

## Cache Stampede Protection

### Overview

Prevents "thundering herd" problem where multiple concurrent requests for the same uncached key all hit the backend simultaneously.

**Without Protection**:
```
100 concurrent requests for uncached key
→ 100 backend calls
→ System overload
```

**With Protection**:
```
100 concurrent requests for uncached key
→ 1 backend call (first request)
→ 99 requests wait for result
→ All get same cached result
```

### How It Works

Request coalescing using async locks:

1. **Cache Hit**: Return immediately (no coalescing needed)
2. **Cache Miss**:
   - First request: Acquires lock, computes value, caches result
   - Concurrent requests: Wait for lock, get result from first request
3. **Result**: 1 backend call for N concurrent requests

### Usage

#### Automatic (Recommended)

The ResearchOrchestrator already uses cache stampede protection for all queries:

```python
# In orchestration/research_orchestrator.py
# Cache stampede protection is built-in
cache_key = cache_manager.generate_cache_key(query, service)
result = await cache_manager.get_or_compute(
    key=cache_key,
    compute_fn=lambda: backend_query(query),
    ttl=300
)
```

#### Manual Integration

For custom code needing stampede protection:

```python
from src.mcp_server.orchestration.cache import get_cache

async def your_expensive_operation(param):
    cache = await get_cache()
    cache_key = cache.generate_cache_key(param, "your_service")

    async def compute():
        # Your expensive backend call
        result = await expensive_backend_call(param)
        return result

    # get_or_compute handles stampede protection
    return await cache.get_or_compute(cache_key, compute, ttl=300)
```

### Performance

| Scenario | Without Protection | With Protection | Improvement |
|----------|-------------------|----------------|-------------|
| 100 concurrent requests (cold cache) | 10,000ms (100 × 100ms) | 100ms | 99% faster |
| 100 concurrent requests (warm cache) | <100ms | <100ms | Same |
| Single request | 100ms | 100ms | Same |

**Overhead**: <100ms additional latency for cache misses (acceptable tradeoff)

### Monitoring

Check logs for stampede protection activity:

```bash
docker logs archon-mcp 2>&1 | grep "Cache COALESCE"
```

Log messages:
- `🔒 Cache COMPUTE`: First request acquired lock
- `🔄 Cache COALESCE`: Waiting for in-flight request
- `✅ Cache COMPUTED`: Value computed and cached
- `✅ Cache COALESCED`: Got result from first request

---

## Rate Limiting

### Overview

Distributed rate limiting using Redis sliding window algorithm protects backend services from abuse and prevents single clients from monopolizing resources.

### Configuration

#### 1. Default Limits (Production Settings)

```python
# In src/mcp_server/middleware/rate_limiter.py
RateLimiter(
    cache=cache_manager,
    client_max_requests=100,      # 100 requests per client per window
    client_window_seconds=60,     # 60 second window (per-minute)
    global_max_requests=1000,     # 1000 total requests per window
    global_window_seconds=60      # 60 second window (global)
)
```

#### 2. Custom Limits

Create rate limiter with custom limits:

```python
from src.mcp_server.middleware.rate_limiter import RateLimiter
from src.mcp_server.orchestration.cache import get_cache

async def create_rate_limiter():
    cache = await get_cache()
    return RateLimiter(
        cache=cache,
        client_max_requests=200,    # More lenient
        client_window_seconds=60,
        global_max_requests=2000,
        global_window_seconds=60
    )
```

#### 3. Environment-Based Configuration (Recommended)

Add to `.env`:

```bash
# Rate Limiting Configuration
RATE_LIMIT_CLIENT_MAX=100
RATE_LIMIT_CLIENT_WINDOW=60
RATE_LIMIT_GLOBAL_MAX=1000
RATE_LIMIT_GLOBAL_WINDOW=60
```

Then in code:

```python
import os

rate_limiter = RateLimiter(
    cache=cache,
    client_max_requests=int(os.getenv("RATE_LIMIT_CLIENT_MAX", "100")),
    client_window_seconds=int(os.getenv("RATE_LIMIT_CLIENT_WINDOW", "60")),
    global_max_requests=int(os.getenv("RATE_LIMIT_GLOBAL_MAX", "1000")),
    global_window_seconds=int(os.getenv("RATE_LIMIT_GLOBAL_WINDOW", "60")),
)
```

### Integration with FastMCP (Future Work)

**Current Status**: Rate limiter middleware is implemented but not yet integrated with FastMCP server.

**Planned Integration**: FastMCP pre-execution hooks for rate limiting

**Manual Integration** (for custom FastAPI endpoints):

```python
from fastapi import Request, HTTPException
from src.mcp_server.middleware.rate_limiter import RateLimiter

rate_limiter = RateLimiter(cache=cache_manager)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = request.client.host

    allowed, info = await rate_limiter.check_rate_limit(client_id)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "limit": info["limit"],
                "remaining": info["remaining"],
                "reset": info["reset"],
                "retry_after": info["retry_after"]
            },
            headers={
                "Retry-After": str(info["retry_after"]),
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset"])
            }
        )

    response = await call_next(request)
    return response
```

### 429 Response Format

When rate limit is exceeded:

```json
{
  "error": "Rate limit exceeded",
  "limit": 100,
  "remaining": 0,
  "reset": 1696723456,
  "retry_after": 45,
  "global_limit_hit": false
}
```

HTTP Headers:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1696723456
```

### Sliding Window Algorithm

More accurate than fixed window:

**Fixed Window** (inaccurate):
```
Window 1: 100 requests at 0:59
Window 2: 100 requests at 1:01
→ 200 requests in 2 seconds (should be limited!)
```

**Sliding Window** (accurate):
```
At 1:01, count requests in [0:01 to 1:01]
→ Only requests within last 60s count
→ Accurately enforces rate limit
```

### Admin Operations

#### Check Client Status

```python
status = await rate_limiter.get_client_status("client_ip")
# Returns:
# {
#   "requests_made": 45,
#   "limit": 100,
#   "remaining": 55,
#   "window_seconds": 60,
#   "reset": 1696723456
# }
```

#### Reset Client Limit

```python
success = await rate_limiter.reset_client_limit("client_ip")
# Client can make requests again immediately
```

### Graceful Degradation

If Redis is unavailable:

1. **In-Memory Fallback**: Uses local fallback (less accurate but works)
2. **Fail-Open Mode**: Allows all requests (for availability)
3. **No Crashes**: Only warnings in logs

Check logs:
```bash
docker logs archon-mcp 2>&1 | grep "Rate limit check failed"
```

---

## Configuration

### Production Environment Variables

Complete `.env` for production:

```bash
# =====================================================
# VALKEY CACHE SECURITY
# =====================================================
VALKEY_PASSWORD=<STRONG_PASSWORD_32_CHARS_MINIMUM>
VALKEY_URL=redis://:${VALKEY_PASSWORD}@archon-valkey:6379/0
ENABLE_CACHE=true

# =====================================================
# RATE LIMITING
# =====================================================
RATE_LIMIT_CLIENT_MAX=100
RATE_LIMIT_CLIENT_WINDOW=60
RATE_LIMIT_GLOBAL_MAX=1000
RATE_LIMIT_GLOBAL_WINDOW=60

# =====================================================
# CACHE PERFORMANCE
# =====================================================
VALKEY_MAXMEMORY=512mb
VALKEY_MAXMEMORY_POLICY=allkeys-lru
```

### Docker Compose Checklist

Verify docker-compose.yml includes:

- [x] `VALKEY_PASSWORD` environment variable
- [x] `--requirepass` flag in Valkey command
- [x] Password in MCP service `VALKEY_URL`
- [x] Cache enabled by default (`ENABLE_CACHE=true`)

### Health Checks

Monitor security features:

```bash
# Check cache authentication
docker exec archon-valkey valkey-cli -a $VALKEY_PASSWORD ping

# Check cache stats
curl http://localhost:8053/performance/report

# Check rate limit status (custom endpoint needed)
# Rate limiter status available via Python API
```

---

## Testing

### Run Security Tests

```bash
# All security tests
pytest python/tests/test_security.py -v

# Specific test categories
pytest python/tests/test_security.py -v -k "test_valkey_auth"
pytest python/tests/test_security.py -v -k "test_cache_stampede"
pytest python/tests/test_security.py -v -k "test_rate_limit"
```

### Manual Testing

#### 1. Test Valkey Authentication

```bash
# Correct password (should work)
docker exec archon-valkey valkey-cli -a archon_cache_2025 SET test_key "test_value"
docker exec archon-valkey valkey-cli -a archon_cache_2025 GET test_key

# Wrong password (should fail)
docker exec archon-valkey valkey-cli -a wrong_password GET test_key
# Expected: (error) WRONGPASS
```

#### 2. Test Cache Stampede Protection

```python
# In Python shell or notebook
import asyncio
from src.mcp_server.orchestration.cache import get_cache

async def test_stampede():
    cache = await get_cache()
    call_count = 0

    async def expensive():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return {"data": "result"}

    # 100 concurrent requests
    key = cache.generate_cache_key("test", "stampede")
    tasks = [cache.get_or_compute(key, expensive) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    print(f"Backend calls: {call_count}")  # Should be 1
    print(f"Results: {len(results)}")      # Should be 100

# Run test
asyncio.run(test_stampede())
```

#### 3. Test Rate Limiting

```python
# In Python shell or notebook
from src.mcp_server.middleware.rate_limiter import RateLimiter
from src.mcp_server.orchestration.cache import get_cache

async def test_rate_limit():
    cache = await get_cache()
    rate_limiter = RateLimiter(
        cache=cache,
        client_max_requests=5,
        client_window_seconds=10
    )

    client_id = "test_client"

    # First 5 should work
    for i in range(5):
        allowed, info = await rate_limiter.check_rate_limit(client_id)
        print(f"Request {i+1}: {'✅ Allowed' if allowed else '❌ Denied'} (remaining: {info['remaining']})")

    # 6th should be denied
    allowed, info = await rate_limiter.check_rate_limit(client_id)
    print(f"Request 6: {'✅ Allowed' if allowed else '❌ Denied'} (retry_after: {info.get('retry_after')}s)")

# Run test
asyncio.run(test_rate_limit())
```

---

## Troubleshooting

### Issue: Cache Operations Failing

**Symptoms**:
```
⚠️  Valkey authentication failed: WRONGPASS invalid username-password pair
⚠️  Cache is disabled via ENABLE_CACHE=false
```

**Solutions**:

1. **Check password is correct**:
   ```bash
   # In .env
   echo $VALKEY_PASSWORD

   # In docker-compose
   docker compose config | grep VALKEY_PASSWORD
   ```

2. **Verify environment variables loaded**:
   ```bash
   docker exec archon-mcp env | grep VALKEY
   ```

3. **Test connection manually**:
   ```bash
   docker exec archon-valkey valkey-cli -a $VALKEY_PASSWORD ping
   ```

4. **Check logs**:
   ```bash
   docker logs archon-mcp 2>&1 | grep "Valkey"
   ```

### Issue: Cache Stampede Not Working

**Symptoms**:
```
Multiple backend calls for same query
Logs show "Cache COMPUTE" multiple times for same key
```

**Solutions**:

1. **Verify cache is enabled**:
   ```bash
   curl http://localhost:8053/health | jq '.cache'
   ```

2. **Check for lock contention**:
   ```bash
   docker logs archon-mcp 2>&1 | grep "COALESCE"
   ```

3. **Ensure using `get_or_compute`**:
   ```python
   # Correct (with stampede protection)
   result = await cache.get_or_compute(key, compute_fn)

   # Wrong (no stampede protection)
   result = await cache.get(key)
   if not result:
       result = await compute_fn()
       await cache.set(key, result)
   ```

### Issue: Rate Limiting Too Strict/Lenient

**Symptoms**:
```
Legitimate users getting 429 errors
Abusive clients not being rate limited
```

**Solutions**:

1. **Adjust limits in environment**:
   ```bash
   # In .env
   RATE_LIMIT_CLIENT_MAX=200  # Increase for legitimate users
   RATE_LIMIT_GLOBAL_MAX=2000  # Increase for higher traffic
   ```

2. **Check client identification**:
   ```python
   # Ensure client_id is correct (IP, user ID, etc.)
   client_id = request.client.host  # FastAPI
   ```

3. **Monitor rate limit status**:
   ```python
   status = await rate_limiter.get_client_status(client_id)
   print(status)
   ```

4. **Reset specific client**:
   ```python
   await rate_limiter.reset_client_limit(client_id)
   ```

### Issue: Performance Degradation

**Symptoms**:
```
High latency on cache operations
Rate limit checks taking >10ms
```

**Solutions**:

1. **Check cache health**:
   ```python
   health = await cache.get_cache_health()
   print(health["latency_ms"])  # Should be <10ms
   ```

2. **Check cache memory**:
   ```bash
   docker exec archon-valkey valkey-cli -a $VALKEY_PASSWORD INFO memory
   ```

3. **Monitor eviction rate**:
   ```bash
   docker exec archon-valkey valkey-cli -a $VALKEY_PASSWORD INFO stats | grep evicted_keys
   ```

4. **Increase cache memory if needed**:
   ```yaml
   # In docker-compose.yml
   VALKEY_MAXMEMORY=1024mb  # Increase from 512mb
   ```

---

## Production Checklist

Use this checklist before deploying to production:

### Security Configuration

- [ ] Strong Valkey password (32+ characters, alphanumeric + symbols)
- [ ] Password stored in secrets management (not in .env file)
- [ ] Rate limits configured for production traffic patterns
- [ ] Cache stampede protection enabled (default)
- [ ] Authentication tested and working

### Monitoring

- [ ] Cache health monitoring enabled
- [ ] Rate limit metrics being collected
- [ ] Alerts configured for:
  - Cache authentication failures
  - Rate limit violations
  - Cache memory >80%
  - Cache latency >50ms

### Performance

- [ ] Cache hit rate >60% after warmup period
- [ ] Cache stampede protection reducing backend calls
- [ ] Rate limit checks <10ms
- [ ] No performance degradation from security features

### Testing

- [ ] All security tests passing
- [ ] Load testing with rate limits
- [ ] Chaos testing (Redis down, auth failure)
- [ ] Performance benchmarks meet SLAs

### Documentation

- [ ] `.env.example` updated with security settings
- [ ] Team trained on security features
- [ ] Runbooks created for common issues
- [ ] Incident response plan includes security scenarios

### Deployment

- [ ] Secrets rotation process documented
- [ ] Backup password access established
- [ ] Rollback plan tested
- [ ] Zero-downtime deployment verified

---

## Additional Resources

- [Valkey Documentation](https://valkey.io/docs/)
- [Redis Security Best Practices](https://redis.io/docs/management/security/)
- [Rate Limiting Algorithms](https://en.wikipedia.org/wiki/Rate_limiting)
- [Cache Stampede Problem](https://en.wikipedia.org/wiki/Cache_stampede)
- [Archon Performance Benchmarks](../../python/performance_benchmark_phase1.json)

---

**Archon Security Guide** | Version 1.0.0 | Stream 4 Complete
