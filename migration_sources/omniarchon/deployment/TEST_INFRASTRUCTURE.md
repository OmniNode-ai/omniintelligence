# Test Infrastructure Guide

## Overview

Archon provides dedicated test infrastructure via `docker-compose.test.yml` for CI/CD pipelines and local testing. All test services use non-conflicting ports to run alongside development infrastructure.

**Status**: ✅ Production-ready | **Updated**: 2025-10-20

---

## Quick Start

### Local Testing

```bash
# 1. Start test infrastructure
cd deployment
docker compose -f docker-compose.test.yml --env-file .env.test up -d

# 2. Wait for services to be healthy
docker compose -f docker-compose.test.yml ps

# 3. Run tests
cd ../python
pytest tests/ -v

# 4. Cleanup
cd ../deployment
docker compose -f docker-compose.test.yml down -v
```

### CI/CD Testing

See `.github/workflows/test-suite.yml` for complete GitHub Actions example.

**Quick CI/CD setup**:
```yaml
# GitHub Actions
- name: Start test infrastructure
  run: docker compose -f deployment/docker-compose.test.yml up -d

- name: Run tests
  env:
    TEST_VALKEY_URL: redis://:archon_test_cache_2025@localhost:6380/0
  run: pytest tests/ -v
```

---

## Test Services

All services use dedicated test ports to avoid conflicts with development environment.

| Service | Image | Dev Port | Test Port | Purpose |
|---------|-------|----------|-----------|---------|
| **test-postgres** | `postgres:15-alpine` | 5432 | 5433 | PostgreSQL test database |
| **test-qdrant** | `qdrant/qdrant:v1.7.4` | 6333 | 6334 | Vector search (REST API) |
| **test-qdrant-grpc** | `qdrant/qdrant:v1.7.4` | 6334 | 6335 | Vector search (gRPC) |
| **test-memgraph** | `memgraph/memgraph:latest` | 7687 | 7688 | Graph DB (Bolt) |
| **test-memgraph-http** | `memgraph/memgraph:latest` | 7444 | 7445 | Graph DB (HTTP) |
| **test-valkey** | `valkey/valkey:8.0-alpine` | 6379 | 6380 | Distributed cache |

---

## Connection Strings

### Environment Variables (from `.env.test`)

```bash
# PostgreSQL
TEST_DATABASE_URL=postgresql://archon_test:archon_test_password_2025@localhost:5433/archon_test

# Qdrant
TEST_QDRANT_URL=http://localhost:6334
TEST_QDRANT_GRPC_URL=http://localhost:6335

# Memgraph
TEST_MEMGRAPH_URI=bolt://localhost:7688

# Valkey
TEST_VALKEY_URL=redis://:archon_test_cache_2025@localhost:6380/0
```

### Python Test Configuration

```python
import os

# In conftest.py or test setup
DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://archon_test:archon_test_password_2025@localhost:5433/archon_test")
QDRANT_URL = os.getenv("TEST_QDRANT_URL", "http://localhost:6334")
MEMGRAPH_URI = os.getenv("TEST_MEMGRAPH_URI", "bolt://localhost:7688")
VALKEY_URL = os.getenv("TEST_VALKEY_URL", "redis://:archon_test_cache_2025@localhost:6380/0")
```

---

## Service Configuration

### PostgreSQL (`test-postgres`)

**Features**:
- PostgreSQL 15 (Alpine)
- 512MB memory limit
- Test-optimized performance settings
- Optional schema initialization via volume mount

**Configuration**:
```yaml
environment:
  POSTGRES_USER: archon_test
  POSTGRES_PASSWORD: archon_test_password_2025
  POSTGRES_DB: archon_test
  POSTGRES_MAX_CONNECTIONS: 100
  POSTGRES_SHARED_BUFFERS: 128MB
```

**Healthcheck**:
```bash
docker exec archon-test-postgres pg_isready -U archon_test
```

### Qdrant (`test-qdrant`)

**Features**:
- Qdrant v1.7.4 (pinned for stability)
- 1GB memory limit
- In-memory storage for test speed
- WARN log level (reduced noise)

**Configuration**:
```yaml
environment:
  QDRANT__STORAGE__ON_DISK_PAYLOAD: false  # In-memory
  QDRANT__SERVICE__MAX_WORKERS: 2
  QDRANT__LOG_LEVEL: WARN
```

**Healthcheck**:
```bash
curl -f http://localhost:6334/readyz
```

### Memgraph (`test-memgraph`)

**Features**:
- Latest Memgraph (graph database)
- 512MB memory limit
- In-memory transactional mode
- WARNING log level

**Configuration**:
```yaml
environment:
  MEMGRAPH_MEMORY_LIMIT: 512
  MEMGRAPH_STORAGE_MODE: IN_MEMORY_TRANSACTIONAL
  MEMGRAPH_LOG_LEVEL: WARNING
```

**Healthcheck**:
```bash
curl -f http://localhost:7445/
```

### Valkey (`test-valkey`)

**Features**:
- Valkey 8.0 (Redis fork)
- 256MB memory limit
- LRU eviction policy
- No persistence (speed optimized)

**Configuration**:
```yaml
environment:
  VALKEY_PASSWORD: archon_test_cache_2025
  VALKEY_MAXMEMORY: 256mb
  VALKEY_MAXMEMORY_POLICY: allkeys-lru
```

**Healthcheck**:
```bash
docker exec archon-test-valkey valkey-cli --no-auth-warning -a archon_test_cache_2025 ping
```

---

## Usage Examples

### Local Development

```bash
# Start only Valkey for cache tests
docker compose -f deployment/docker-compose.test.yml up -d test-valkey

# Start all services
docker compose -f deployment/docker-compose.test.yml --env-file deployment/.env.test up -d

# Check service health
docker compose -f deployment/docker-compose.test.yml ps

# View logs
docker compose -f deployment/docker-compose.test.yml logs -f test-valkey

# Stop services
docker compose -f deployment/docker-compose.test.yml down

# Stop and remove volumes (clean slate)
docker compose -f deployment/docker-compose.test.yml down -v
```

### CI/CD Pipeline

#### Minimal (Valkey only)

```yaml
services:
  valkey:
    image: valkey/valkey:8.0-alpine
    ports:
      - 6380:6379
    options: >-
      --health-cmd "valkey-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

#### Full Stack

```yaml
steps:
  - name: Start test infrastructure
    run: docker compose -f deployment/docker-compose.test.yml up -d

  - name: Wait for health
    run: |
      timeout 180 bash -c 'until docker compose -f deployment/docker-compose.test.yml ps | grep -q "healthy"; do sleep 5; done'

  - name: Run tests
    env:
      TEST_DATABASE_URL: postgresql://archon_test:archon_test_password_2025@localhost:5433/archon_test
      TEST_QDRANT_URL: http://localhost:6334
      TEST_MEMGRAPH_URI: bolt://localhost:7688
      TEST_VALKEY_URL: redis://:archon_test_cache_2025@localhost:6380/0
    run: pytest tests/ -v

  - name: Cleanup
    if: always()
    run: docker compose -f deployment/docker-compose.test.yml down -v
```

---

## Troubleshooting

### Services Not Starting

**Problem**: Services fail to start or stay unhealthy.

**Solution**:
```bash
# Check logs
docker compose -f deployment/docker-compose.test.yml logs

# Check specific service
docker compose -f deployment/docker-compose.test.yml logs test-valkey

# Restart service
docker compose -f deployment/docker-compose.test.yml restart test-valkey

# Clean restart (removes data)
docker compose -f deployment/docker-compose.test.yml down -v
docker compose -f deployment/docker-compose.test.yml up -d
```

### Port Conflicts

**Problem**: Port already in use.

**Solution**: Update test ports in `.env.test`:
```bash
# Change ports to avoid conflicts
TEST_VALKEY_PORT=6381  # Instead of 6380
TEST_POSTGRES_PORT=5434  # Instead of 5433
```

### Connection Refused

**Problem**: Tests can't connect to services.

**Solution**:
```bash
# 1. Verify services are running
docker compose -f deployment/docker-compose.test.yml ps

# 2. Check healthchecks
docker inspect archon-test-valkey | jq '.[0].State.Health'

# 3. Test connectivity manually
telnet localhost 6380  # Valkey
curl http://localhost:6334/readyz  # Qdrant
pg_isready -h localhost -p 5433 -U archon_test  # PostgreSQL

# 4. Check network
docker network inspect archon-test-network
```

### Slow Service Startup

**Problem**: Services take too long to become healthy.

**Solution**: Increase healthcheck timeouts in `docker-compose.test.yml`:
```yaml
healthcheck:
  start_period: 60s  # Increase from 30s
  interval: 15s      # Increase from 10s
  retries: 10        # Increase from 5
```

### Memory Issues

**Problem**: Services crashing due to memory limits.

**Solution**: Increase resource limits in `docker-compose.test.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 1G      # Increase from 512M
```

Or reduce parallel test execution:
```bash
# Run tests sequentially
pytest tests/ -v  # No -n flag

# Or limit workers
pytest tests/ -v -n 2  # Instead of -n auto
```

### Volume Permission Errors

**Problem**: Permission denied errors for mounted volumes.

**Solution**:
```bash
# Fix volume permissions
sudo chown -R $(id -u):$(id -g) deployment/config/

# Or use named volumes only (no bind mounts)
```

---

## Performance Tuning

### Faster Test Execution

```yaml
# In docker-compose.test.yml
environment:
  # Use in-memory storage
  QDRANT__STORAGE__ON_DISK_PAYLOAD: false
  MEMGRAPH_STORAGE_MODE: IN_MEMORY_TRANSACTIONAL

  # Disable persistence
  VALKEY_SAVE: ""
  VALKEY_APPENDONLY: no

  # Reduce log levels
  QDRANT__LOG_LEVEL: WARN
  MEMGRAPH_LOG_LEVEL: WARNING
  VALKEY_LOG_LEVEL: warning
```

### Resource Optimization

**For CI/CD runners with limited resources**:
```yaml
deploy:
  resources:
    limits:
      memory: 256M    # Reduce from defaults
      cpus: '0.5'     # Limit CPU usage
```

**For local development with ample resources**:
```yaml
deploy:
  resources:
    limits:
      memory: 2G      # Increase for better performance
      cpus: '2.0'     # Allow more CPU usage
```

---

## CI/CD Integration Examples

### GitHub Actions (Complete)

See `.github/workflows/test-suite.yml` for full example.

**Key features**:
- Fast tests on every push (cache-only)
- Comprehensive tests on PRs to main/develop
- Performance benchmarks on main branch merges
- Artifact uploads for test reports

### GitLab CI (Complete)

```yaml
comprehensive-tests:
  image: python:3.11

  services:
    - name: postgres:15-alpine
      alias: test-postgres
    - name: qdrant/qdrant:v1.7.4
      alias: test-qdrant
    - name: memgraph/memgraph:latest
      alias: test-memgraph
    - name: valkey/valkey:8.0-alpine
      alias: test-valkey

  variables:
    TEST_DATABASE_URL: "postgresql://archon_test:archon_test_password_2025@test-postgres:5432/archon_test"
    TEST_QDRANT_URL: "http://test-qdrant:6333"
    TEST_MEMGRAPH_URI: "bolt://test-memgraph:7687"
    TEST_VALKEY_URL: "redis://:archon_test_cache_2025@test-valkey:6379/0"

  script:
    - pip install -r requirements.txt pytest-rerunfailures
    - pytest tests/ -v -n auto
```

### CircleCI

```yaml
version: 2.1

jobs:
  test:
    docker:
      - image: cimg/python:3.11
      - image: postgres:15-alpine
        environment:
          POSTGRES_USER: archon_test
          POSTGRES_PASSWORD: archon_test_password_2025
      - image: qdrant/qdrant:v1.7.4
      - image: memgraph/memgraph:latest
      - image: valkey/valkey:8.0-alpine

    environment:
      TEST_DATABASE_URL: postgresql://archon_test:archon_test_password_2025@localhost:5432/archon_test
      TEST_QDRANT_URL: http://localhost:6333
      TEST_MEMGRAPH_URI: bolt://localhost:7687
      TEST_VALKEY_URL: redis://localhost:6379/0

    steps:
      - checkout
      - run: pip install -r requirements.txt pytest-rerunfailures
      - run: pytest tests/ -v
```

---

## Best Practices

### 1. Always Use Healthchecks

Wait for services to be healthy before running tests:
```bash
timeout 180 bash -c 'until docker compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 5; done'
```

### 2. Clean Up After Tests

Always clean up volumes to ensure fresh state:
```bash
docker compose -f docker-compose.test.yml down -v
```

### 3. Use CI-Specific Timeouts

Set higher timeouts for CI/CD environments:
```bash
export COLD_CACHE_TIMEOUT_MS=18000  # 2x default
export WARM_CACHE_TIMEOUT_MS=2000
```

### 4. Parallel Test Execution

Use pytest-xdist for faster tests:
```bash
pytest tests/ -n auto  # Auto-detect cores
pytest tests/ -n 4     # Explicitly use 4 workers
```

### 5. Selective Service Startup

Only start services you need:
```bash
# Just cache
docker compose -f docker-compose.test.yml up -d test-valkey

# Cache + vector DB
docker compose -f docker-compose.test.yml up -d test-valkey test-qdrant
```

### 6. Use Test Markers

Skip slow tests in fast CI pipelines:
```bash
pytest tests/ -m "not slow" -v
```

### 7. Capture Logs on Failure

Always capture logs when tests fail:
```bash
if ! pytest tests/ -v; then
  docker compose -f deployment/docker-compose.test.yml logs --tail=100
  exit 1
fi
```

---

## Maintenance

### Update Service Versions

```bash
# Edit docker-compose.test.yml
# Update image tags
test-postgres:
  image: postgres:16-alpine  # Was 15-alpine

test-qdrant:
  image: qdrant/qdrant:v1.8.0  # Was v1.7.4
```

### Clean Up Old Data

```bash
# Remove test volumes
docker volume ls | grep archon-test | awk '{print $2}' | xargs docker volume rm

# Or use docker compose
docker compose -f deployment/docker-compose.test.yml down -v --remove-orphans
```

### Monitor Resource Usage

```bash
# Check resource usage
docker stats $(docker compose -f deployment/docker-compose.test.yml ps -q)

# Check disk usage
docker system df
```

---

## Support

**Documentation**:
- Test suite README: `python/tests/README.md`
- Performance testing: `python/tests/README.md#performance-benchmark`
- CI/CD workflows: `.github/workflows/test-suite.yml`

**Troubleshooting**:
- Check service logs: `docker compose -f deployment/docker-compose.test.yml logs`
- Verify connectivity: Use healthcheck commands above
- Reset state: `docker compose -f deployment/docker-compose.test.yml down -v`

**Environment Configuration**:
- Test ports: `deployment/.env.test`
- Test timeouts: `python/.env.test`
- Service settings: `deployment/docker-compose.test.yml`

---

**Archon Test Infrastructure** | Version 1.0.0 | Updated 2025-10-20
