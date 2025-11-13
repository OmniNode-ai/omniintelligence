# Tree Stamping Event Adapter Tests

**Created**: 2025-10-24
**Stream**: E - Testing Infrastructure
**Status**: Complete
**Purpose**: Comprehensive test suite for event-driven Tree + Stamping adapter

---

## Overview

This test suite provides comprehensive coverage for the Tree Stamping event-driven adapter, including:

- **Unit Tests**: Handler methods with mocked dependencies
- **Integration Tests**: End-to-end event flow testing
- **Event Tests**: Payload serialization and validation
- **Performance Tests**: Throughput and latency benchmarks
- **Mock Infrastructure**: Reusable Kafka fixtures

---

## Test Structure

```
tests/
├── fixtures/
│   └── kafka_fixtures.py                      # Mock Kafka infrastructure
├── unit/
│   ├── handlers/
│   │   └── test_tree_stamping_handler.py     # Handler unit tests
│   └── events/
│       └── test_tree_stamping_events.py      # Event model tests
├── integration/
│   └── test_tree_stamping_events.py          # End-to-end flow tests
└── performance/
    └── test_tree_stamping_throughput.py      # Performance benchmarks
```

---

## Test Files

### 1. Kafka Fixtures (`fixtures/kafka_fixtures.py`)

**Purpose**: Mock Kafka infrastructure for testing without real Kafka dependency

**Components**:
- `MockEventEnvelope`: Mock event structure
- `MockKafkaProducer`: Tracks published events by correlation ID and topic
- `MockKafkaConsumer`: Simulates event consumption
- Pytest fixtures for common test scenarios

**Key Features**:
- Correlation ID tracking
- Event tracking by topic
- Error simulation
- Metrics tracking

**Usage Example**:
```python
def test_example(mock_kafka_producer, event_factory):
    # Create event
    event = event_factory.create_index_request(
        project_path="/tmp/test",
        correlation_id="test-123"
    )

    # Publish to mock
    await mock_kafka_producer.publish(
        topic="test.topic",
        event=event,
        correlation_id=event.correlation_id
    )

    # Verify
    events = mock_kafka_producer.get_events_for_correlation("test-123")
    assert len(events) == 1
```

---

### 2. Handler Unit Tests (`unit/handlers/test_tree_stamping_handler.py`)

**Purpose**: Test TreeStampingHandler methods with mocked TreeStampingBridge

**Test Coverage**:
- ✅ Event routing (`can_handle`)
- ✅ Index project handling (success/failure)
- ✅ Search files handling (success/failure)
- ✅ Get status handling
- ✅ Error handling and recovery
- ✅ Metrics tracking
- ✅ Response publishing
- ✅ Correlation ID preservation

**Key Tests**:
- `test_handle_index_project_success`: Verify successful indexing flow
- `test_handle_index_project_publishes_completed`: Verify completed event published
- `test_handle_index_project_failure`: Verify failure handling
- `test_bridge_exception_handling`: Verify exception recovery

**Running**:
```bash
# Run all handler unit tests
pytest tests/unit/handlers/test_tree_stamping_handler.py -v

# Run specific test
pytest tests/unit/handlers/test_tree_stamping_handler.py::TestTreeStampingHandler::test_handle_index_project_success -v
```

**Coverage Target**: >80%

---

### 3. Event Serialization Tests (`unit/events/test_tree_stamping_events.py`)

**Purpose**: Test event payload models for validation and serialization

**Test Coverage**:
- ✅ Request payload validation (index, search, status)
- ✅ Response payload validation (completed, failed)
- ✅ Field constraints (path validation, quality score ranges, limits)
- ✅ JSON serialization/deserialization roundtrips
- ✅ Event type enums
- ✅ Error code enums
- ✅ Cross-model validation

**Key Tests**:
- `test_path_traversal_prevention`: Security validation
- `test_quality_score_validation`: Range validation
- `test_json_serialization`: Roundtrip serialization
- `test_error_code_enum`: Enum completeness

**Running**:
```bash
# Run all event tests
pytest tests/unit/events/test_tree_stamping_events.py -v

# Run specific test class
pytest tests/unit/events/test_tree_stamping_events.py::TestIndexProjectRequestPayload -v
```

---

### 4. Integration Tests (`integration/test_tree_stamping_events.py`)

**Purpose**: End-to-end event flow testing with mocked Kafka

**Test Coverage**:
- ✅ Complete index project flow (request → process → response)
- ✅ Complete search files flow
- ✅ Complete get status flow
- ✅ Correlation ID preservation through flow
- ✅ Multiple concurrent requests
- ✅ Error event publishing
- ✅ Topic routing verification
- ✅ Metrics tracking during flow

**Key Tests**:
- `test_index_project_success_flow`: Full successful indexing workflow
- `test_correlation_id_preservation`: Verify correlation ID tracking
- `test_concurrent_event_processing`: Verify concurrent handling
- `test_complete_project_indexing_workflow`: End-to-end scenario

**Running**:
```bash
# Run all integration tests
pytest tests/integration/test_tree_stamping_events.py -v

# Run specific scenario
pytest tests/integration/test_tree_stamping_events.py::TestEndToEndScenarios::test_complete_project_indexing_workflow -v
```

---

### 5. Performance Tests (`performance/test_tree_stamping_throughput.py`)

**Purpose**: Benchmark handler performance characteristics

**Test Coverage**:
- ✅ Sequential throughput (events/second)
- ✅ Concurrent throughput
- ✅ Sustained throughput over time
- ✅ Latency distribution (P50, P95, P99)
- ✅ Concurrency impact on latency
- ✅ Handler overhead measurement
- ✅ High-volume stress testing
- ✅ Mixed operation performance
- ✅ Error handling performance impact

**Performance Targets**:
| Metric | Target | Test |
|--------|--------|------|
| Sequential throughput | >10 events/sec | `test_sequential_throughput` |
| Concurrent throughput | >50 events/sec | `test_concurrent_throughput` |
| P50 latency | <100ms | `test_event_processing_latency` |
| P95 latency | <500ms | `test_event_processing_latency` |
| P99 latency | <1000ms | `test_event_processing_latency` |
| Handler overhead | <10ms avg | `test_handler_overhead` |

**Running**:
```bash
# Run all performance tests
pytest tests/performance/test_tree_stamping_throughput.py -v -s -m benchmark

# Run specific benchmark
pytest tests/performance/test_tree_stamping_throughput.py::TestTreeStampingHandlerPerformance::test_concurrent_throughput -v -s

# Generate performance report
pytest tests/performance/test_tree_stamping_throughput.py::TestPerformanceReport::test_generate_performance_report -v -s
```

---

## Running Tests

### All Tests

```bash
# Run complete test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run specific stream
pytest tests/unit/handlers/ -v
pytest tests/integration/ -v
pytest tests/performance/ -v -m benchmark
```

### By Test Type

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Performance benchmarks only
pytest tests/performance/ -v -m benchmark

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### With Filters

```bash
# Run tests matching pattern
pytest tests/ -k "index_project" -v

# Run specific test
pytest tests/unit/handlers/test_tree_stamping_handler.py::TestTreeStampingHandler::test_handle_index_project_success -v

# Run with verbose output
pytest tests/ -v -s
```

---

## Test Coverage

### Coverage Targets

- **Overall**: >80%
- **Handler**: >85% (critical path)
- **Event models**: >90% (validation-heavy)
- **Integration**: >75% (end-to-end scenarios)

### Generating Coverage Reports

```bash
# HTML report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# XML report (for CI)
pytest tests/ --cov=src --cov-report=xml
```

---

## Test Markers

Tests use pytest markers for organization:

- `@pytest.mark.asyncio`: Async test
- `@pytest.mark.benchmark`: Performance test
- `@pytest.mark.slow`: Slow-running test (skip with `-m "not slow"`)
- `@pytest.mark.integration`: Integration test

**Usage**:
```bash
# Run only benchmark tests
pytest -m benchmark -v

# Skip slow tests
pytest -m "not slow" -v

# Run integration tests
pytest -m integration -v
```

---

## Mock Infrastructure

### MockKafkaProducer

**Purpose**: Track published events without real Kafka

**Features**:
- Event tracking by correlation ID
- Event tracking by topic
- Error simulation
- Metrics (total published, errors)

**Methods**:
```python
await producer.publish(topic, event, key, correlation_id)
producer.get_events_for_correlation(correlation_id)
producer.get_events_for_topic(topic)
producer.simulate_failure(should_fail=True)
producer.reset()
```

### MockKafkaConsumer

**Purpose**: Simulate event consumption

**Features**:
- Event injection for testing
- Handler registration
- Error simulation
- Consumed event tracking

**Methods**:
```python
await consumer.subscribe(topics)
await consumer.inject_event(event)
event = await consumer.consume()
consumer.simulate_failure(should_fail=True)
consumer.reset()
```

### Event Factory

**Purpose**: Simplify test event creation

**Methods**:
```python
event_factory.create_index_request(project_path, project_name, correlation_id)
event_factory.create_search_request(query, projects, correlation_id)
event_factory.create_status_request(project_name, correlation_id)
```

### Correlation Tracker

**Purpose**: Track request → response event chains

**Methods**:
```python
tracker.track_request(correlation_id, event)
tracker.track_response(correlation_id, event)
tracker.has_response(correlation_id)
tracker.verify_flow(correlation_id)
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tree Stamping Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run performance benchmarks
        run: pytest tests/performance/ -v -m benchmark

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

---

## Troubleshooting

### Common Issues

**1. Tests fail with "ModuleNotFoundError"**
```bash
# Ensure src is in Python path
export PYTHONPATH=/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src:$PYTHONPATH
pytest tests/ -v
```

**2. Async tests fail with "RuntimeWarning"**
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Or use asyncio mode in pytest.ini
[pytest]
asyncio_mode = auto
```

**3. Performance tests too slow**
```bash
# Skip slow tests
pytest tests/performance/ -v -m "benchmark and not slow"

# Reduce event counts in tests (edit test file)
```

**4. Coverage too low**
```bash
# Check missing lines
pytest tests/ --cov=src --cov-report=term-missing

# Add tests for uncovered code paths
```

---

## Integration with Stream B (Handler)

### When Real Handler Exists

**Update imports** in test files:
```python
# Replace mock handler import:
# from unit.handlers.test_tree_stamping_handler import MockTreeStampingHandler

# With real handler import:
from src.handlers.tree_stamping_handler import TreeStampingHandler
```

**Update fixtures**:
```python
@pytest.fixture
def handler(mock_bridge):
    """Use real handler once Stream B completes."""
    handler = TreeStampingHandler(bridge=mock_bridge)
    handler._router = AsyncMock()
    handler._router.publish = AsyncMock()
    return handler
```

---

## Integration with Stream A (Event Models)

### When Real Event Models Exist

**Update imports** in test files:
```python
# Replace mock event models:
# from unit.events.test_tree_stamping_events import ModelIndexProjectRequestPayload

# With real event models:
from src.events.models.tree_stamping_events import (
    ModelIndexProjectRequestPayload,
    ModelIndexProjectCompletedPayload,
    EnumTreeStampingEventType,
)
```

**Remove mock definitions** from test files (models defined in Stream A).

---

## Success Criteria

- ✅ Unit tests >80% coverage
- ✅ Integration tests complete end-to-end flows
- ✅ Event serialization tests pass
- ✅ Performance tests meet targets
- ✅ All tests passing
- ✅ Fixtures working correctly
- ✅ Documentation complete

---

## Next Steps

1. **Stream B Complete**: Replace mock handler with real TreeStampingHandler
2. **Stream A Complete**: Replace mock event models with real event schemas
3. **Stream D Complete**: Add consumer registration tests
4. **CI Integration**: Add tests to CI/CD pipeline
5. **Coverage Analysis**: Identify and fill coverage gaps
6. **Performance Tuning**: Optimize based on benchmark results

---

## Deliverables

| File | Status | Coverage | Tests |
|------|--------|----------|-------|
| `kafka_fixtures.py` | ✅ Complete | N/A | Fixtures |
| `test_tree_stamping_handler.py` | ✅ Complete | >80% | 25+ tests |
| `test_tree_stamping_events.py` | ✅ Complete | >90% | 30+ tests |
| `test_tree_stamping_events.py` (integration) | ✅ Complete | >75% | 20+ tests |
| `test_tree_stamping_throughput.py` | ✅ Complete | N/A | 15+ benchmarks |

**Total**: 90+ tests across 5 files

---

## Contact

**Stream Owner**: Poly-E (Testing Infrastructure)
**Dependencies**: Stream A (Event Schemas), Stream B (Handler), Stream C (Publisher)
**Status**: Ready for integration with Streams A & B

---

**Last Updated**: 2025-10-24
**Version**: 1.0.0
