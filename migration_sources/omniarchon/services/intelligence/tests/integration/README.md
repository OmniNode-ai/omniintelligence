# Integration Tests - Intelligence Service

## Overview

Comprehensive end-to-end integration tests for Archon Intelligence Service Phase 5 features.

**Purpose**: Validate full request/response cycles, API contracts, and cross-service interactions for:
- Pattern Learning (4 phases)
- Quality Intelligence
- Performance Intelligence
- Pattern Traceability
- Autonomous Learning
- Pattern Analytics

## Test Coverage

### Test Suite: `test_hybrid_scoring_e2e.py`

#### ✅ Complete Hybrid Scoring Flow
Tests the full pipeline from task characteristics extraction through hybrid scoring:
1. Extract task characteristics
2. Generate embeddings (Ollama/mock)
3. Index vectors in Qdrant
4. Perform vector similarity search
5. Calculate pattern similarity scores
6. Combine into hybrid score (70% vector + 30% pattern)
7. Verify accuracy

**Target**: <5s for complete flow (cold cache)

#### ✅ Cache Effectiveness
Tests caching performance with repeated queries:
- First run (cold cache)
- Second run (warm cache)
- Verifies >2x speedup with warm cache

**Target**: >80% cache hit rate

#### ✅ Fallback to Vector-Only
Tests graceful degradation when pattern matching unavailable:
- Vector-only search
- Reasonable accuracy without pattern matching
- No errors when pattern matcher fails

**Target**: Seamless fallback, >50% accuracy

#### ✅ Performance Under Load
Tests concurrent request handling:
- 100 concurrent requests
- Batched processing (10 per batch)
- Measures avg and P99 latency

**Targets**:
- Complete within 10s total
- Avg latency <100ms
- P99 latency <3s

#### ✅ Hybrid Accuracy Improvement
Validates hybrid scoring provides better results than vector-only:
- Compare vector-only vs hybrid rankings
- Measure improvement percentage
- Verify similar tasks ranked higher

**Target**: >10% accuracy improvement over vector-only

## Running Tests

### Prerequisites

```bash
# Start required services
docker compose up -d archon-intelligence archon-valkey qdrant

# Verify services are healthy
curl http://localhost:8053/health

# Install test dependencies
cd /Volumes/PRO-G40/Code/omniarchon/services/intelligence
poetry install --with test
```

### Run All Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v -m integration

# Run with output
pytest tests/integration/ -v -s -m integration
```

### Run Specific Feature Tests

```bash
# Pattern Learning tests
pytest tests/integration/ -v -m pattern_learning

# Quality Intelligence tests
pytest tests/integration/ -v -m quality_intelligence

# Performance Intelligence tests
pytest tests/integration/ -v -m performance_intelligence

# Pattern Traceability tests
pytest tests/integration/ -v -m pattern_traceability

# Autonomous Learning tests
pytest tests/integration/ -v -m autonomous_learning
```

### Run Specific Test Files

```bash
# Run specific test file
pytest tests/integration/test_api_pattern_learning.py -v

# Run specific test class
pytest tests/integration/test_api_pattern_learning.py::TestPatternLearningAPI -v

# Run specific test method
pytest tests/integration/test_api_pattern_learning.py::TestPatternLearningAPI::test_pattern_matching_endpoint -v
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/integration/ --cov=src --cov-report=html --cov-report=term -m integration

# View HTML report
open htmlcov/index.html
```

### Run Slow Tests

```bash
# Run only slow tests (>5s execution)
pytest tests/integration/ -v -m slow

# Skip slow tests
pytest tests/integration/ -v -m "not slow"
```

## Test Infrastructure

### Fixtures (`conftest.py`)

The integration test suite provides 17+ reusable fixtures:

**Event & Router Fixtures**:
- `mock_event_envelope` - Mock Kafka event envelopes
- `mock_router` - Mock HybridEventRouter for testing

**API Testing**:
- `test_client` - FastAPI TestClient (session-scoped)
- `auth_headers` - Authentication headers for protected endpoints

**Pattern Learning**:
- `sample_patterns` - 100 sample patterns for batch testing
- `sample_pattern_single` - Single pattern for focused tests

**Quality Intelligence**:
- `quality_history_fixture` - 30 days of quality trend data
- `quality_snapshot_fixture` - Single quality snapshot

**Performance Intelligence**:
- `baseline_fixture` - Performance baseline with statistics
- `performance_measurements_fixture` - 10 sample measurements

**Pattern Traceability**:
- `pattern_lineage_fixture` - Pattern evolution lineage
- `execution_logs_fixture` - Agent execution logs

**Utilities**:
- `clean_database` - Database cleanup after tests
- `correlation_id_fixture` - UUID correlation IDs
- `project_id_fixture` - Test project identifiers

### Test Helpers (`test_helpers.py`)

Comprehensive utility functions for integration testing:

**Response Validation**:
- `assert_response_schema(data, fields)` - Validate field presence
- `assert_response_types(data, types)` - Validate field types
- `assert_response_complete(data, fields, types)` - Combined validation

**Timestamp Utilities**:
- `assert_timestamp_format(timestamp)` - ISO 8601 validation
- `assert_timestamp_recent(timestamp, max_age)` - Recency checks

**Pagination**:
- `assert_pagination(data)` - Complete pagination structure validation
- `assert_pagination_bounds(data, page, size)` - Specific page validation

**Factory Functions**:
- `create_test_pattern(**overrides)` - Pattern data factory
- `create_test_quality_snapshot(**overrides)` - Quality data factory
- `create_test_performance_measurement(**overrides)` - Performance data factory
- `create_test_execution_log(**overrides)` - Execution log factory

**API Response**:
- `assert_success_response(data)` - Validate success responses
- `assert_error_response(data, substring)` - Validate error responses

**Score Validation**:
- `assert_score_in_range(score, min, max)` - Range validation
- `assert_scores_present(data, fields)` - Multiple score validation

**Correlation IDs**:
- `assert_correlation_id_valid(id)` - UUID validation
- `assert_correlation_id_preserved(req, resp)` - ID preservation

**Batch Operations**:
- `assert_batch_results(results, count, success, unique)` - Batch validation

### Base Test Classes (`utils/base.py`)

**HandlerTestBase**: Base class for handler integration tests with reusable methods:
- `verify_handler_success()` - Success verification
- `verify_handler_failure()` - Error handling verification
- `verify_concurrent_processing()` - Concurrent request testing
- `measure_performance()` - Single operation performance
- `measure_batch_throughput()` - Batch operation metrics
- `verify_response_structure()` - Common response validation
- `verify_router_initialization()` - Router lifecycle testing
- `verify_publish_failure_recovery()` - Publish error recovery

### Assertion Utilities (`utils/assertions.py`)

Specialized assertions for event-driven testing:
- `assert_response_structure()` - Payload structure validation
- `assert_topic_naming()` - Kafka topic naming conventions
- `assert_correlation_id_preserved()` - Event correlation tracking
- `assert_routing_context()` - Routing configuration validation
- `assert_error_response()` - Error response structure
- `assert_publish_called_with_key()` - Partition key verification
- `assert_unique_correlation_ids()` - Unique ID verification
- `assert_metrics_tracking()` - Handler metrics validation

## Test Data

Tests use realistic data samples:
- **Patterns**: 100 sample patterns with varying complexity and success rates
- **Quality Data**: 30-day trending quality snapshots with improving scores
- **Performance Data**: Baseline statistics with p50/p95/p99 percentiles
- **Execution Logs**: Agent execution traces with success/failure patterns
- **Lineage Data**: Pattern evolution with ancestor tracking

## Performance Metrics

Integration tests track and report:
- Extraction time
- Embedding generation time
- Vector indexing time
- Search time
- Hybrid score combination time
- Total pipeline time
- Cache hit rates
- Memory usage

## Assertions

All tests include comprehensive assertions for:
- ✅ Functional correctness
- ✅ Performance targets met
- ✅ Error handling works
- ✅ Fallback mechanisms activate
- ✅ Accuracy improvements verified

## Continuous Integration

These tests are designed to run in CI/CD:
- Docker-based Qdrant service
- Mock embedding generation (no Ollama dependency)
- Deterministic results
- Fast execution (<2 minutes total)

## Troubleshooting

### Qdrant Connection Issues

```bash
# Check Qdrant is running
curl http://localhost:6333/health

# Restart Qdrant
docker compose restart qdrant
```

### Test Failures

```bash
# Run with verbose output
pytest services/intelligence/tests/integration/ -v -s --tb=long

# Check test logs
tail -f services/intelligence/tests/integration/test.log
```

### Performance Degradation

```bash
# Run performance benchmark
python services/intelligence/tests/performance/benchmark_hybrid_scoring.py

# Profile slow tests
pytest services/intelligence/tests/integration/ --profile
```

## Writing Integration Tests

### Basic Test Structure

```python
import pytest
from tests.integration.test_helpers import (
    assert_response_schema,
    assert_success_response,
    create_test_pattern
)

@pytest.mark.integration
@pytest.mark.pattern_learning
class TestPatternLearningAPI:
    """Integration tests for Pattern Learning API."""

    def test_pattern_matching_endpoint(self, test_client, auth_headers):
        """Test pattern matching endpoint returns valid results."""
        # Arrange
        pattern = create_test_pattern(pattern_type="code_generation")

        # Act
        response = test_client.post(
            "/api/pattern-learning/pattern/match",
            json=pattern,
            headers=auth_headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert_success_response(data)
        assert_response_schema(data, ["matches", "confidence", "timestamp"])
```

### Using Fixtures

```python
def test_with_sample_patterns(self, test_client, sample_patterns, auth_headers):
    """Test batch pattern processing."""
    # sample_patterns fixture provides 100 patterns
    response = test_client.post(
        "/api/patterns/batch",
        json={"patterns": sample_patterns[:10]},  # Use first 10
        headers=auth_headers
    )

    assert response.status_code == 200
```

### Using Test Helpers

```python
from tests.integration.test_helpers import (
    assert_pagination,
    assert_score_in_range,
    assert_timestamp_recent
)

def test_list_patterns(self, test_client, auth_headers):
    """Test pattern listing with pagination."""
    response = test_client.get(
        "/api/patterns?page=1&page_size=50",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Validate pagination structure
    assert_pagination(data)

    # Validate each result
    for pattern in data["results"]:
        assert_score_in_range(pattern["confidence_score"])
        assert_timestamp_recent(pattern["created_at"], max_age_seconds=3600)
```

### Testing Error Scenarios

```python
from tests.integration.test_helpers import assert_error_response

def test_invalid_pattern_data(self, test_client, auth_headers):
    """Test API handles invalid input gracefully."""
    invalid_pattern = {"invalid": "data"}

    response = test_client.post(
        "/api/pattern-learning/pattern/match",
        json=invalid_pattern,
        headers=auth_headers
    )

    assert response.status_code == 422  # Validation error
    assert_error_response(
        response.json(),
        expected_error_substring="Missing required field"
    )
```

## Best Practices

### DO ✅

1. **Use Markers**: Mark tests with appropriate markers (`@pytest.mark.integration`, `@pytest.mark.pattern_learning`)
2. **Use Fixtures**: Leverage shared fixtures for common test data
3. **Use Test Helpers**: Use helper functions for consistent assertions
4. **Clean Data**: Use `clean_database` fixture to ensure test isolation
5. **Test Both Success and Failure**: Test happy path AND error scenarios
6. **Validate Completely**: Check schema, types, ranges, and business logic
7. **Use Factory Functions**: Use `create_test_*` functions for flexible test data
8. **Document Tests**: Add docstrings explaining what each test validates

### DON'T ❌

1. **Don't Skip Cleanup**: Always use fixtures that clean up after tests
2. **Don't Hardcode Data**: Use fixtures and factory functions
3. **Don't Test Implementation**: Test behavior, not implementation details
4. **Don't Ignore Async**: Use `@pytest.mark.asyncio` for async tests
5. **Don't Create Test Pollution**: Ensure tests don't affect each other
6. **Don't Skip Negative Tests**: Error handling is as important as success cases
7. **Don't Forget Timeouts**: Mark slow tests with `@pytest.mark.slow`
8. **Don't Duplicate Code**: Extract common patterns to helpers/base classes

## Continuous Integration

Integration tests are designed for CI/CD:

**Requirements**:
- Docker Compose (services: archon-intelligence, archon-valkey, qdrant)
- Python 3.11+
- Poetry for dependency management

**CI Configuration** (example):

```yaml
test-integration:
  runs-on: ubuntu-latest
  services:
    redis:
      image: valkey/valkey:latest
      ports:
        - 6379:6379
    qdrant:
      image: qdrant/qdrant:latest
      ports:
        - 6333:6333
  steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        cd services/intelligence
        poetry install --with test
    - name: Run integration tests
      run: |
        cd services/intelligence
        poetry run pytest tests/integration/ -v -m integration --cov=src
```

## Troubleshooting

### Service Connection Issues

```bash
# Check service health
curl http://localhost:8053/health

# View service logs
docker compose logs archon-intelligence

# Restart services
docker compose restart archon-intelligence archon-valkey
```

### Test Failures

```bash
# Run with verbose output and logging
pytest tests/integration/ -v -s --log-cli-level=DEBUG

# Run specific failing test
pytest tests/integration/test_api_pattern_learning.py::TestPatternLearningAPI::test_pattern_matching_endpoint -vv

# Check traceback
pytest tests/integration/ --tb=long
```

### Database Issues

```bash
# Check database state
# (Add database inspection commands based on actual DB)

# Clean test data manually
# (Add cleanup commands)
```

### Performance Issues

```bash
# Run performance profiling
pytest tests/integration/ --profile

# Identify slow tests
pytest tests/integration/ --durations=10
```

## Test Organization

```
tests/integration/
├── conftest.py                          # Shared fixtures (17+ fixtures)
├── test_helpers.py                      # Test utilities (30+ functions)
├── README.md                            # This file
├── utils/
│   ├── assertions.py                    # Assertion utilities
│   └── base.py                          # Base test classes
├── test_api_pattern_learning.py         # Pattern Learning API tests
├── test_api_quality_intelligence.py     # Quality Intelligence API tests
├── test_api_performance_intelligence.py # Performance Intelligence API tests
├── test_api_pattern_traceability.py     # Pattern Traceability API tests
├── test_api_autonomous_learning.py      # Autonomous Learning API tests
└── test_api_pattern_analytics.py        # Pattern Analytics API tests
```

## Next Steps

After integration tests pass:
1. ✅ Run performance benchmarks
2. ✅ Run load tests
3. ✅ Validate in staging environment
4. ✅ Monitor production metrics
5. ✅ Track test coverage trends

---

**Part of**: Phase 5 - Intelligence Features Enhancement
**Status**: Infrastructure Complete, Tests In Progress
**Coverage Target**: >80% of intelligence APIs
**Last Updated**: 2025-10-16
