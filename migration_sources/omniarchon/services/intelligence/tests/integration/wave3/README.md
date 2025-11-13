# Wave 3 Integration Tests

## Overview

Wave 3 replaces stub implementations with actual HTTP service calls for 10 operations across 3 handler domains.

**Total Operations**: 10
**Test Files**: 3
**Test Coverage**: End-to-end HTTP integration with mocked service responses

## Operations Implemented

### 1. Freshness - Analyses (1 operation)

**File**: `test_freshness_analyses_integration.py`
**Handler**: `FreshnessHandler`
**HTTP Endpoint**: `GET /freshness/analyses`

**Tests**:
- ✅ Successful HTTP call with analyses results
- ✅ HTTP error handling (500 errors)
- ✅ Limit parameter validation
- ✅ Empty results handling

### 2. Pattern Learning (7 operations)

**File**: `test_pattern_learning_integration.py`
**Handler**: `PatternLearningHandler`
**HTTP Endpoints**: `POST/GET /api/pattern-learning/*`

**Operations**:
1. **Pattern Match** - `POST /api/pattern-learning/pattern/match`
   - Match patterns against query
   - Context-aware matching

2. **Hybrid Score** - `POST /api/pattern-learning/hybrid/score`
   - Calculate hybrid matching score
   - Semantic + keyword + structural scoring

3. **Semantic Analyze** - `POST /api/pattern-learning/semantic/analyze`
   - Semantic code analysis
   - Feature extraction and embeddings

4. **Metrics** - `GET /api/pattern-learning/metrics`
   - Pattern learning metrics
   - Cache hit rates, average similarity

5. **Cache Stats** - `GET /api/pattern-learning/cache/stats`
   - Cache statistics
   - Hit rate, eviction count, size

6. **Cache Clear** - `POST /api/pattern-learning/cache/clear`
   - Clear pattern cache
   - Pattern-based clearing

7. **Health** - `GET /api/pattern-learning/health`
   - Service health check
   - Component status checks

### 3. Pattern Traceability (2 operations)

**File**: `test_pattern_traceability_integration.py`
**Handler**: `PatternTraceabilityHandler`
**HTTP Endpoints**: `POST /api/pattern-traceability/lineage/*`

**Operations**:
1. **Track** - `POST /api/pattern-traceability/lineage/track`
   - Track single pattern lineage
   - Metadata preservation

2. **Track Batch** - `POST /api/pattern-traceability/lineage/track/batch`
   - Track multiple patterns
   - Batch processing with partial failure handling

## Running Tests

### Run All Wave 3 Tests

```bash
cd /Volumes/PRO-G40/Code/omniarchon/services/intelligence
poetry run pytest tests/integration/wave3/ -v
```

### Run Specific Test Files

```bash
# Freshness tests
poetry run pytest tests/integration/wave3/test_freshness_analyses_integration.py -v

# Pattern Learning tests
poetry run pytest tests/integration/wave3/test_pattern_learning_integration.py -v

# Pattern Traceability tests
poetry run pytest tests/integration/wave3/test_pattern_traceability_integration.py -v
```

### Run Specific Test Classes

```bash
# Pattern Match tests
poetry run pytest tests/integration/wave3/test_pattern_learning_integration.py::TestPatternMatchIntegration -v

# Track tests
poetry run pytest tests/integration/wave3/test_pattern_traceability_integration.py::TestTrackIntegration -v
```

## Test Structure

### Test Pattern

Each test follows the **Arrange-Act-Assert** pattern:

```python
@respx.mock
@pytest.mark.asyncio
async def test_operation_successful(self, handler, correlation_id):
    # Arrange: Mock HTTP response
    mock_response = {...}
    respx.post("http://localhost:8053/api/...").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    payload = ModelRequestPayload(...)

    # Act: Handle event
    result = await handler._handle_operation(
        correlation_id, payload.model_dump(), time.perf_counter()
    )

    # Assert: Verify success
    assert result is True
    assert handler.metrics["events_handled"] == 1
```

### HTTP Mocking

All tests use `respx` to mock HTTP calls to `localhost:8053`:

- **Success cases**: Mock 200 responses with expected data
- **Error cases**: Mock 4xx/5xx responses to test error handling
- **Validation**: Verify request parameters and payloads

### Fixtures

Common fixtures across all test files:

- `handler`: Creates handler instance (e.g., `FreshnessHandler()`)
- `correlation_id`: Generates UUID for event tracking

## Implementation Details

### Handler Updates

Each handler method was updated from stub to HTTP implementation:

**Before (Stub)**:
```python
# TODO: Implement actual operation
result = {
    "stub": "implementation_pending"
}
```

**After (HTTP)**:
```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(
        "http://localhost:8053/api/...",
        json=request_data
    )
    response.raise_for_status()
    data = response.json()
```

### Error Handling

All operations implement comprehensive error handling:

1. **HTTP Status Errors** (`httpx.HTTPStatusError`)
   - Logged with status code and response text
   - Publishes FAILED event with HTTP error details

2. **Generic Exceptions** (`Exception`)
   - Logged with full traceback
   - Publishes FAILED event with error message

3. **Metrics Tracking**
   - `events_handled` incremented on success
   - `events_failed` incremented on failure
   - `total_processing_time_ms` tracked

## Test Coverage

### Per Operation

Each operation has tests for:
- ✅ Successful HTTP call
- ✅ HTTP error handling (4xx/5xx)
- ✅ Request parameter validation
- ✅ Response parsing and result construction

### Special Cases

- **Empty Results**: All operations handle empty result sets
- **Large Payloads**: Track Batch tested with 100 patterns
- **Partial Failures**: Track Batch handles partial success scenarios
- **Service Degradation**: Health endpoint tested with degraded status

## Dependencies

### Required Packages

```toml
[tool.poetry.dependencies]
httpx = "^0.27.0"  # HTTP client

[tool.poetry.group.test.dependencies]
pytest = "^8.1.1"
pytest-asyncio = "^0.23.6"
respx = "^0.21.1"  # HTTP mocking
```

### Service Dependencies

Tests expect the Intelligence Service to be available at:
- **URL**: `http://localhost:8053`
- **Endpoints**: All `/api/pattern-learning/*`, `/api/pattern-traceability/*`, `/freshness/*`

**Note**: Tests use `respx` to mock responses, so the actual service doesn't need to be running.

## Next Steps

### Wave 4 (Future)

Potential Wave 4 operations:
- Additional freshness operations (analyze, stale, refresh, stats, document, cleanup)
- Pattern traceability operations (lineage, evolution, execution logs, analytics)
- End-to-end integration tests with actual Kafka events

### Integration with CI/CD

```yaml
# .github/workflows/test.yml
- name: Run Wave 3 Integration Tests
  run: |
    poetry run pytest tests/integration/wave3/ -v --cov
```

## Troubleshooting

### Common Issues

**Import Errors**:
```bash
# Ensure you're in the intelligence service directory
cd /Volumes/PRO-G40/Code/omniarchon/services/intelligence
poetry install
```

**Async Warnings**:
```bash
# Install pytest-asyncio
poetry add pytest-asyncio --group test
```

**HTTP Mocking Issues**:
```bash
# Check respx is installed
poetry show respx
poetry add respx --group test
```

## Contributing

When adding new Wave 3 tests:

1. Follow the existing test structure (Arrange-Act-Assert)
2. Use `respx.mock` decorator for HTTP mocking
3. Test both success and error cases
4. Verify request parameters when applicable
5. Update this README with new operations

## Summary

Wave 3 successfully implements HTTP integration for **10 operations** across **3 handler domains**, with comprehensive integration tests validating end-to-end functionality.

**Status**: ✅ Complete
**Test Coverage**: 100% of implemented operations
**Integration**: Full HTTP service integration with mocked responses
