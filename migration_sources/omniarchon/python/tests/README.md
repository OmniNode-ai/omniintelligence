# Archon Test Suite Documentation

## Overview

Comprehensive test suite for Archon's Phase 1 search performance optimizations, including distributed caching, HTTP/2 connection pooling, and orchestrated intelligence.

**Status**: Production-ready with configurable timeouts for CI/CD environments

## ⚠️ IMPORTANT: Correct Test Execution

**Always use the virtual environment Python** to avoid dependency errors (crawl4ai, omnibase_core).

### ✅ Correct Way to Run Tests

```bash
# Recommended: Use helper script (easiest)
./run_tests.sh tests/ -v

# Alternative: Use venv Python directly
.venv/bin/python -m pytest tests/ -v

# Alternative: Activate venv first
source .venv/bin/activate
python -m pytest tests/ -v
```

### ❌ Wrong Way (Will Fail)

```bash
# Don't use system pytest - missing dependencies!
pytest tests/

# Don't use system python
python3 -m pytest tests/

# Don't use global pytest installation
/usr/local/bin/pytest tests/
```

**Why?** Tests require dependencies (crawl4ai, omnibase_core) that are only installed in the virtual environment.

**See**: [RUN_TESTS.md](RUN_TESTS.md) for complete dependency fix documentation.

## Quick Start

```bash
# Run all tests (CORRECT - using helper script)
./run_tests.sh tests/

# Run performance tests only
./run_tests.sh tests/test_search_performance.py -v -s

# Run full performance benchmark
./run_tests.sh tests/test_search_performance.py::TestPerformanceBenchmark::test_full_performance_benchmark -v -s

# Skip slow tests (for quick CI checks)
./run_tests.sh tests/ -m "not slow"

# Run only slow tests (comprehensive validation)
./run_tests.sh tests/ -m "slow"
```

## Test Configuration

### Environment Variables

All test timeouts are configurable via environment variables or `.env.test` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `COLD_CACHE_TIMEOUT_MS` | 9000 | Cold cache baseline (first query) |
| `WARM_CACHE_TIMEOUT_MS` | 1000 | Warm cache performance (cache hits) |
| `PARALLEL_QUERY_TIMEOUT_MS` | 5000 | Parallel queries with shared cache |
| `RETRY_TIMEOUT_MS` | 15000 | Service failure retry logic |
| `CONNECTION_POOL_TIMEOUT_MS` | 5000 | HTTP/2 connection pooling |
| `FULL_BENCHMARK_TIMEOUT_MS` | 30000 | Comprehensive benchmark suite |
| `CACHE_GET_TIMEOUT_MS` | 1000 | Cache get operations |
| `CACHE_SET_TIMEOUT_MS` | 1000 | Cache set operations |
| `CACHE_CLEAR_TIMEOUT_MS` | 5000 | Cache clear operations |
| `LARGE_RESULT_TIMEOUT_MS` | 10000 | Large result caching (>10MB) |
| `CONCURRENT_WRITE_TIMEOUT_MS` | 5000 | Concurrent write tests |
| `CACHE_EVICTION_TIMEOUT_MS` | 10000 | Cache eviction under pressure |
| `NETWORK_PARTITION_TIMEOUT_MS` | 5000 | Network partition handling |

### CI/CD Recommendations

**Shared CI/CD Runners** (resource contention):
```bash
export COLD_CACHE_TIMEOUT_MS=18000  # 2x default
export WARM_CACHE_TIMEOUT_MS=2000
export PARALLEL_QUERY_TIMEOUT_MS=10000
```

**Dedicated CI/CD Runners**:
```bash
export COLD_CACHE_TIMEOUT_MS=13500  # 1.5x default
export WARM_CACHE_TIMEOUT_MS=1500
export PARALLEL_QUERY_TIMEOUT_MS=7500
```

**Local Development**:
Use defaults from `.env.test` (no configuration needed)

## Test Suites

### 1. Cold Cache Performance (`TestColdCachePerformance`)

Tests first-time query performance without cache.

**Purpose**: Establish performance baseline for uncached queries.

**Expected**: <9s (9000ms) default, configurable

**Example**:
```bash
pytest tests/test_search_performance.py::TestColdCachePerformance -v -s
```

### 2. Warm Cache Performance (`TestWarmCachePerformance`)

Tests repeated query performance with cache hits.

**Purpose**: Validate 95%+ performance improvement from caching.

**Expected**: <1s (1000ms) default, configurable

**Target Improvement**: 30-40% overall improvement (Phase 1 goal)

**Example**:
```bash
pytest tests/test_search_performance.py::TestWarmCachePerformance -v -s
```

### 3. Parallel Queries (`TestParallelQueriesWithCache`)

Tests multiple concurrent queries with shared cache.

**Purpose**: Verify cache efficiency across parallel operations.

**Expected**: <5s (5000ms) for 3 parallel queries

**Example**:
```bash
pytest tests/test_search_performance.py::TestParallelQueriesWithCache -v -s
```

### 4. Cache Key Context Handling (`TestCacheKeyContextHandling`)

Tests cache key generation with context parameters.

**Purpose**: Ensure different contexts don't collide, same contexts reuse cache.

**Edge Cases**:
- Different contexts generate different cache keys
- Same query + context reuses cached results
- No cache key collisions across parameters

**Example**:
```bash
pytest tests/test_search_performance.py::TestCacheKeyContextHandling -v -s
```

### 5. Cache Miss Handling (`TestCacheMissHandling`)

Tests graceful degradation when cache is disabled.

**Purpose**: Verify system works without cache.

**Example**:
```bash
pytest tests/test_search_performance.py::TestCacheMissHandling -v -s
```

### 6. Service Failure Handling (`TestServiceFailureHandling`)

Tests retry logic with exponential backoff.

**Purpose**: Validate resilience to service failures.

**Retry Strategy**: 3 attempts with 1s → 2s → 4s delays

**Example**:
```bash
pytest tests/test_search_performance.py::TestServiceFailureHandling -v -s
```

### 7. Connection Pooling (`TestConnectionPooling`)

Tests HTTP/2 connection reuse.

**Purpose**: Verify connection pooling reduces overhead.

**Example**:
```bash
pytest tests/test_search_performance.py::TestConnectionPooling -v -s
```

### 8. Performance Benchmark (`TestPerformanceBenchmark`)

Comprehensive benchmark suite with report generation.

**Purpose**: Full Phase 1 validation and performance reporting.

**Output**: `performance_benchmark_phase1.json`

**Example**:
```bash
pytest tests/test_search_performance.py::TestPerformanceBenchmark::test_full_performance_benchmark -v -s
```

### 9. Large Result Caching (`TestLargeResultCaching`)

Tests caching of large results (>10MB).

**Purpose**: Validate cache handles large data efficiently.

**Marker**: `@pytest.mark.slow`

**Example**:
```bash
pytest tests/test_search_performance.py::TestLargeResultCaching -v -s
```

### 10. Concurrent Writes (`TestConcurrentWrites`)

Tests race condition handling with concurrent cache writes.

**Purpose**: Verify cache consistency under concurrent writes.

**Marker**: `@pytest.mark.flaky(reruns=2)`

**Example**:
```bash
pytest tests/test_search_performance.py::TestConcurrentWrites -v -s
```

### 11. Network Partition (`TestNetworkPartition`)

Tests graceful degradation when Valkey becomes unavailable.

**Purpose**: Validate resilience to cache service failures.

**Marker**: `@pytest.mark.flaky(reruns=2)`

**Example**:
```bash
pytest tests/test_search_performance.py::TestNetworkPartition -v -s
```

### 12. Cache Eviction (`TestCacheEviction`)

Tests LRU eviction under memory pressure.

**Purpose**: Verify cache eviction works correctly.

**Marker**: `@pytest.mark.slow`

**Example**:
```bash
pytest tests/test_search_performance.py::TestCacheEviction -v -s
```

## Pytest Markers

### Available Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `slow` | Slow running tests (>5s) | `pytest -m "slow"` to run only slow tests |
| `flaky` | Potentially flaky tests (auto-retry) | `pytest -m "flaky"` to run only flaky tests |
| `performance` | Performance-critical tests | `pytest -m "performance"` |
| `asyncio` | Async tests | Automatically detected |

### Marker Examples

**Skip slow tests** (fast CI pipeline):
```bash
pytest tests/ -m "not slow"
```

**Run only slow tests** (comprehensive validation):
```bash
pytest tests/ -m "slow"
```

**Run performance tests**:
```bash
pytest tests/ -m "performance"
```

## Custom Timeout Configuration

### Option 1: Environment Variables

```bash
# Override specific timeouts
export COLD_CACHE_TIMEOUT_MS=15000
export WARM_CACHE_TIMEOUT_MS=2000

pytest tests/test_search_performance.py -v -s
```

### Option 2: Create Custom `.env.test`

Create `python/.env.test`:
```bash
# Custom timeouts for CI/CD
COLD_CACHE_TIMEOUT_MS=18000
WARM_CACHE_TIMEOUT_MS=2000
PARALLEL_QUERY_TIMEOUT_MS=10000
```

Then run tests normally:
```bash
pytest tests/ -v -s
```

### Option 3: Inline Override

```bash
COLD_CACHE_TIMEOUT_MS=20000 pytest tests/test_search_performance.py::TestColdCachePerformance -v -s
```

## CI/CD Integration

### Docker Compose Test Infrastructure

Archon provides dedicated test infrastructure via `docker-compose.test.yml` for CI/CD pipelines.

**Services Included**:
- `test-postgres`: PostgreSQL 15 (port 5433)
- `test-qdrant`: Qdrant vector DB (ports 6334/6335)
- `test-memgraph`: Memgraph graph DB (ports 7688/7445)
- `test-valkey`: Valkey cache (port 6380)

**Quick Start**:
```bash
# Start test infrastructure
cd deployment
docker compose -f docker-compose.test.yml --env-file .env.test up -d

# Wait for services to be healthy
docker compose -f docker-compose.test.yml ps

# Run tests
cd ../python
pytest tests/ -v

# Cleanup
cd ../deployment
docker compose -f docker-compose.test.yml down -v
```

**Service Health Checks**:
```bash
# Check all services are healthy
docker compose -f docker-compose.test.yml ps

# Check specific service
docker compose -f docker-compose.test.yml logs test-valkey
docker compose -f docker-compose.test.yml exec test-valkey valkey-cli ping

# Manual healthcheck
curl http://localhost:6334/readyz  # Qdrant
curl http://localhost:7445/        # Memgraph
pg_isready -h localhost -p 5433    # PostgreSQL
```

**Environment Variables**:

All test configuration is managed via `/deployment/.env.test`:

| Service | Port (Dev) | Port (Test) | Connection String |
|---------|------------|-------------|-------------------|
| PostgreSQL | 5432 | 5433 | `postgresql://archon_test:archon_test_password_2025@localhost:5433/archon_test` |
| Qdrant REST | 6333 | 6334 | `http://localhost:6334` |
| Qdrant gRPC | 6334 | 6335 | `http://localhost:6335` |
| Memgraph Bolt | 7687 | 7688 | `bolt://localhost:7688` |
| Memgraph HTTP | 7444 | 7445 | `http://localhost:7445` |
| Valkey | 6379 | 6380 | `redis://:archon_test_cache_2025@localhost:6380/0` |

### GitHub Actions Example

#### Simple (Valkey only)

```yaml
name: Fast Tests (Cache Only)

on: [push, pull_request]

jobs:
  fast-tests:
    runs-on: ubuntu-latest

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

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-rerunfailures

      - name: Run fast tests
        env:
          TEST_VALKEY_URL: redis://localhost:6380/0
          COLD_CACHE_TIMEOUT_MS: 18000
          WARM_CACHE_TIMEOUT_MS: 2000
        run: |
          pytest tests/ -m "not slow" -v

      - name: Upload benchmark report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: performance-report
          path: python/performance_benchmark_phase1.json
```

#### Comprehensive (Full Test Infrastructure)

```yaml
name: Comprehensive Tests (Full Stack)

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

jobs:
  comprehensive-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-rerunfailures pytest-xdist

      - name: Start test infrastructure
        run: |
          cd deployment
          docker compose -f docker-compose.test.yml --env-file .env.test up -d

      - name: Wait for services to be healthy
        run: |
          cd deployment
          timeout 120 bash -c 'until docker compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 5; done'

      - name: Verify service health
        run: |
          docker compose -f deployment/docker-compose.test.yml ps
          curl -f http://localhost:6334/readyz || exit 1  # Qdrant
          curl -f http://localhost:7445/ || exit 1        # Memgraph
          docker exec archon-test-valkey valkey-cli --no-auth-warning -a archon_test_cache_2025 ping || exit 1

      - name: Run comprehensive tests
        env:
          TEST_DATABASE_URL: postgresql://archon_test:archon_test_password_2025@localhost:5433/archon_test
          TEST_QDRANT_URL: http://localhost:6334
          TEST_MEMGRAPH_URI: bolt://localhost:7688
          TEST_VALKEY_URL: redis://:archon_test_cache_2025@localhost:6380/0
          COLD_CACHE_TIMEOUT_MS: 18000
          WARM_CACHE_TIMEOUT_MS: 2000
          PARALLEL_QUERY_TIMEOUT_MS: 10000
        run: |
          cd python
          pytest tests/ -v -s --maxfail=5 -n auto

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: |
            python/performance_benchmark_phase1.json
            python/htmlcov/

      - name: Cleanup test infrastructure
        if: always()
        run: |
          cd deployment
          docker compose -f docker-compose.test.yml down -v
```

### GitLab CI Example

#### Simple (Valkey only)

```yaml
fast-tests:
  image: python:3.11

  services:
    - name: valkey/valkey:8.0-alpine
      alias: test-valkey
      command: ["valkey-server", "--requirepass", "archon_test_cache_2025"]

  variables:
    TEST_VALKEY_URL: "redis://:archon_test_cache_2025@test-valkey:6379/0"
    COLD_CACHE_TIMEOUT_MS: "18000"
    WARM_CACHE_TIMEOUT_MS: "2000"

  before_script:
    - pip install -r requirements.txt
    - pip install pytest-rerunfailures

  script:
    - pytest tests/ -m "not slow" -v

  artifacts:
    when: always
    paths:
      - python/performance_benchmark_phase1.json
    expire_in: 30 days
```

#### Comprehensive (Full Test Infrastructure)

```yaml
comprehensive-tests:
  image: python:3.11

  services:
    - name: postgres:15-alpine
      alias: test-postgres
      variables:
        POSTGRES_USER: archon_test
        POSTGRES_PASSWORD: archon_test_password_2025
        POSTGRES_DB: archon_test

    - name: qdrant/qdrant:v1.7.4
      alias: test-qdrant

    - name: memgraph/memgraph:latest
      alias: test-memgraph

    - name: valkey/valkey:8.0-alpine
      alias: test-valkey
      command: ["valkey-server", "--requirepass", "archon_test_cache_2025"]

  variables:
    TEST_DATABASE_URL: "postgresql://archon_test:archon_test_password_2025@test-postgres:5432/archon_test"
    TEST_QDRANT_URL: "http://test-qdrant:6333"
    TEST_MEMGRAPH_URI: "bolt://test-memgraph:7687"
    TEST_VALKEY_URL: "redis://:archon_test_cache_2025@test-valkey:6379/0"
    COLD_CACHE_TIMEOUT_MS: "18000"
    WARM_CACHE_TIMEOUT_MS: "2000"
    PARALLEL_QUERY_TIMEOUT_MS: "10000"

  before_script:
    - pip install -r requirements.txt
    - pip install pytest-rerunfailures pytest-xdist

  script:
    # Fast tests for every commit
    - pytest tests/ -m "not slow" -v -n auto

    # Comprehensive tests for main branch only
    - |
      if [ "$CI_COMMIT_BRANCH" == "main" ] || [ "$CI_COMMIT_BRANCH" == "develop" ]; then
        pytest tests/ -v -s --maxfail=5
      fi

  artifacts:
    when: always
    paths:
      - python/performance_benchmark_phase1.json
      - python/htmlcov/
    expire_in: 30 days
```

## Troubleshooting

### Tests Timing Out

**Problem**: Tests fail with timeout errors in CI/CD.

**Solution**: Increase timeouts for your environment:
```bash
# For shared runners (high resource contention)
export COLD_CACHE_TIMEOUT_MS=18000  # 2x default
export WARM_CACHE_TIMEOUT_MS=2000
export PARALLEL_QUERY_TIMEOUT_MS=10000
```

### Flaky Tests Failing

**Problem**: Network-dependent tests fail intermittently.

**Solution**: Tests marked with `@pytest.mark.flaky(reruns=2)` automatically retry. Ensure `pytest-rerunfailures` is installed:
```bash
pip install pytest-rerunfailures
```

### Cache Service Unavailable

**Problem**: Tests fail because Valkey is not running.

**Solution**:
```bash
# Start Valkey service
docker run -d -p 6379:6379 valkey/valkey:latest

# Or use Docker Compose
docker compose up -d archon-valkey
```

### Connection Refused Errors

**Problem**: Tests can't connect to localhost services.

**Solution**: Ensure services are running:
```bash
# Check Valkey
docker ps | grep valkey

# Check if port is open
nc -zv localhost 6379

# Restart services
docker compose restart archon-valkey
```

### Slow Test Execution

**Problem**: Tests take too long in CI/CD.

**Solution**: Skip slow tests for fast pipelines:
```bash
pytest tests/ -m "not slow" -v
```

### Memory Issues with Large Tests

**Problem**: Large result caching tests fail with memory errors.

**Solution**: Increase Docker memory or skip slow tests:
```bash
# Skip slow tests
pytest tests/ -m "not slow"

# Or increase Docker memory limit
docker compose down
docker compose up -d --build
```

## Test Coverage Report

### Quick Start

**Using the run_tests.sh script** (recommended - coverage enabled by default):
```bash
# Run all tests with coverage (default)
./run_tests.sh

# Run specific tests with coverage
./run_tests.sh tests/test_my_module.py

# Run without coverage (faster)
./run_tests.sh --no-cov

# View HTML coverage report
open htmlcov/index.html
```

**Direct pytest command**:
```bash
# With coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term --cov-report=xml

# Without coverage
pytest tests/
```

### Coverage Reports

**Terminal Output** (generated automatically):
- Shows line coverage for each module
- Highlights missing lines with line numbers
- Displays total coverage percentage

**HTML Report** (`htmlcov/index.html`):
- Interactive browsable coverage report
- View exactly which lines are covered/missing
- Branch coverage visualization
- Sort by coverage percentage
- Filter by module/package

**XML Report** (`coverage.xml`):
- Machine-readable format for CI/CD
- Used by Codecov and other coverage services
- Includes detailed line and branch coverage data

### Coverage Configuration

**Configuration File**: `.coveragerc`

**Key Settings**:
- **Minimum Coverage Threshold**: 80% (build fails if below)
- **Branch Coverage**: Enabled (measures if/else branches)
- **Exclusions**: tests/, migrations/, __init__.py
- **Exclude Lines**: pragma: no cover, TYPE_CHECKING blocks, abstract methods

**Example excluded code**:
```python
def debug_function():  # pragma: no cover
    # Excluded from coverage
    print("Debug info")

if TYPE_CHECKING:
    # Type-only imports excluded
    from typing import Protocol
```

### Coverage Targets

| Category | Target | Current | Notes |
|----------|--------|---------|-------|
| Overall | 80%+ | ~80%+ | Enforced by .coveragerc |
| Core Services | 85%+ | ~85%+ | Intelligence, Search, Bridge |
| API Endpoints | 90%+ | ~90%+ | All FastAPI routes |
| Utilities | 75%+ | ~75%+ | Helper functions |
| Branch Coverage | 75%+ | ~75%+ | if/else paths |

### Improving Coverage

**1. Find Missing Coverage**:
```bash
# Run tests and view terminal report
./run_tests.sh

# Look for modules with low coverage
# Example output:
# src/my_module.py     156    42    73%   45-52, 89-102
```

**2. View Detailed HTML Report**:
```bash
open htmlcov/index.html
# Click on files with low coverage
# Red = not covered, green = covered
```

**3. Add Tests for Missing Lines**:
```python
# Example: covering error handling
def test_error_handling():
    with pytest.raises(ValueError):
        my_function(invalid_input)  # Now covers error branch
```

**4. Use Coverage Comments**:
```python
# For truly untestable code (rare!)
def platform_specific():
    if sys.platform == "win32":  # pragma: no cover
        # Windows-only code, CI runs on Linux
        return windows_implementation()
```

### CI/CD Integration

**GitHub Actions** (already configured in `.github/workflows/ci.yml`):
```yaml
- name: Run tests with coverage
  run: |
    uv run pytest tests/ --cov=src --cov-report=xml --cov-report=html

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./python/coverage.xml
    flags: backend
```

**Codecov Badge** (in main README.md):
```markdown
[![codecov](https://codecov.io/gh/OmniNode-ai/omniarchon/branch/main/graph/badge.svg)](https://codecov.io/gh/OmniNode-ai/omniarchon)
```

### Coverage Best Practices

**1. Write Tests First** (TDD):
- Write failing test
- Implement feature to pass test
- Coverage increases naturally

**2. Test Edge Cases**:
```python
def test_edge_cases():
    # Empty input
    assert process([]) == []
    # Single item
    assert process([1]) == [1]
    # Large input
    assert process(range(1000)) is not None
```

**3. Test Error Paths**:
```python
def test_error_scenarios():
    # Invalid input
    with pytest.raises(ValueError):
        process(None)
    # Network failure
    with pytest.raises(ConnectionError):
        api_call(unreachable_url)
```

**4. Use Fixtures to Reduce Duplication**:
```python
@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    result = process(sample_data)
    assert result is not None
```

**5. Don't Chase 100% Coverage**:
- 80%+ is excellent for most projects
- Focus on critical business logic
- Some defensive code may never execute
- Use `pragma: no cover` judiciously

### Troubleshooting Coverage Issues

**Issue: Coverage report missing files**
- Solution: Ensure `.coveragerc` source paths are correct
- Check that files are in `src/` directory

**Issue: Coverage too low**
- Solution: Run `./run_tests.sh` and review `htmlcov/index.html`
- Focus on files with <80% coverage
- Add tests for missing branches and error paths

**Issue: Coverage report not generated**
- Solution: Ensure `pytest-cov` is installed (`uv sync --group dev`)
- Check that `--cov=src` flag is present in pytest command

**Issue: CI failing on coverage threshold**
- Solution: Coverage must be ≥80% (configured in `.coveragerc`)
- Fix locally: `./run_tests.sh` and add missing tests
- Temporary: Lower `fail_under` in `.coveragerc` (not recommended)

### Coverage Metrics Explained

**Line Coverage**:
- Percentage of executable lines executed by tests
- Example: 80% = 80 out of 100 lines executed

**Branch Coverage**:
- Percentage of conditional branches executed
- Example: `if x > 5: ...` needs tests for both True and False cases

**Statement Coverage**:
- Similar to line coverage
- More granular for multi-statement lines

**Missing Lines**:
- Line numbers not executed by any test
- Listed in terminal report (e.g., `45-52, 89-102`)

### Example Coverage Workflow

**1. Initial Run**:
```bash
$ ./run_tests.sh
...
src/my_module.py     100    60    60%   45-52, 89-102
TOTAL                5000   4200  84%
```

**2. Identify Gaps**:
```bash
# Open HTML report
$ open htmlcov/index.html
# Click on my_module.py
# See red highlighting on lines 45-52, 89-102
```

**3. Add Tests**:
```python
# tests/test_my_module.py
def test_missing_branch():
    # Cover lines 45-52
    result = my_module.special_case(edge_case_input)
    assert result == expected_output

def test_error_handler():
    # Cover lines 89-102
    with pytest.raises(CustomError):
        my_module.process(invalid_input)
```

**4. Verify Improvement**:
```bash
$ ./run_tests.sh
...
src/my_module.py     100    85    85%   95-98
TOTAL                5000   4350  87%
```

## Performance Benchmark Report

After running the full benchmark, view the detailed report:

```bash
# Run benchmark
pytest tests/test_search_performance.py::TestPerformanceBenchmark::test_full_performance_benchmark -v -s

# View report
cat python/performance_benchmark_phase1.json | jq
```

**Report Structure**:
```json
{
  "timestamp": "2025-10-07T...",
  "phase": "Phase 1 - Quick Wins",
  "configured_timeouts": {
    "cold_cache_ms": 9000,
    "warm_cache_ms": 1000
  },
  "tests": [
    {
      "name": "cold_cache_baseline",
      "duration_ms": 7234,
      "target_ms": 9000,
      "passed": true
    },
    {
      "name": "warm_cache_performance",
      "duration_ms": 187,
      "improvement_pct": 97.4,
      "target_ms": 1000,
      "passed": true
    }
  ],
  "cache_stats": {
    "total_keys": 27,
    "hits": 342,
    "misses": 187,
    "hit_rate": 64.7
  },
  "summary": {
    "cold_cache_ms": 7234,
    "warm_cache_ms": 187,
    "improvement_pct": 97.4,
    "phase1_target_met": true
  }
}
```

## Best Practices

### 1. Always Use Fixtures

**Good**:
```python
async def test_something(test_timeouts):
    timeout = test_timeouts["cold_cache"]
    assert duration < timeout
```

**Bad**:
```python
async def test_something():
    timeout = 9000  # Hardcoded
    assert duration < timeout
```

### 2. Mark Slow Tests

**Good**:
```python
@pytest.mark.slow
async def test_large_operation():
    # Long-running test
    pass
```

### 3. Mark Flaky Tests

**Good**:
```python
@pytest.mark.flaky(reruns=2)
async def test_network_dependent():
    # Network-dependent test
    pass
```

### 4. Clean Up Resources

**Good**:
```python
async def test_cache_operation(cache_client):
    try:
        # Test code
        await cache_client.set("key", "value")
    finally:
        # Always cleanup
        await cache_client.delete("key")
```

### 5. Use Descriptive Assertions

**Good**:
```python
assert duration < timeout, f"Query took {duration}ms, expected < {timeout}ms"
```

**Bad**:
```python
assert duration < timeout  # No context
```

## Contributing

### Adding New Tests

1. **Create test class**:
```python
class TestNewFeature:
    """Test description."""

    @pytest.mark.asyncio
    async def test_new_feature(self, test_timeouts):
        """Test new feature with configurable timeout."""
        timeout = test_timeouts["new_feature"]  # Add to .env.test
        # Test implementation
```

2. **Update `.env.test`**:
```bash
# New feature timeout
NEW_FEATURE_TIMEOUT_MS=5000
```

3. **Update `conftest.py`** (if new timeout):
```python
@pytest.fixture(scope="session")
def test_timeouts() -> Dict[str, int]:
    return {
        # ... existing timeouts
        "new_feature": int(os.getenv("NEW_FEATURE_TIMEOUT_MS", "5000")),
    }
```

4. **Add marker** (if appropriate):
```python
@pytest.mark.slow  # Or @pytest.mark.flaky
async def test_new_feature():
    pass
```

5. **Update this README** with new test documentation.

## Support

For issues or questions:
- Check troubleshooting section above
- Review test output with `-v -s` flags
- Check service logs: `docker compose logs archon-valkey`
- Review performance report: `performance_benchmark_phase1.json`

---

**Archon Test Suite** | Version 1.0.0 | Phase 1 Optimizations
