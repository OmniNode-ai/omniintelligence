# Real Integration Tests

**Status**: ✅ Implemented | **Version**: 1.0.0

Complete infrastructure for real integration tests against live services (Kafka, Qdrant, Memgraph).

## Overview

Real integration tests validate system behavior against actual service instances running in Docker, catching issues that mocked tests cannot detect:

- **Service Interaction**: Real network calls, connection pooling, timeouts
- **Data Consistency**: Cross-service transaction patterns, eventual consistency
- **Performance**: Real latency, throughput, resource usage
- **Edge Cases**: Connection failures, service restarts, data corruption

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               Test Framework                        │
│  pytest --real-integration                          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│            Test Infrastructure                      │
│  - pytest markers (real_integration)                │
│  - Test fixtures (connections, cleanup)             │
│  - Test data managers (setup/teardown)              │
│  - Health checks (service verification)             │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│          Real Services (Docker)                     │
│  - Kafka/Redpanda (9092)                           │
│  - Qdrant Vector DB (6334)                         │
│  - Memgraph Knowledge Graph (7688)                 │
│  - PostgreSQL (5433)                                │
│  - Valkey Cache (6380)                              │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Test Services

```bash
# Start all test services
docker compose -f deployment/docker-compose.test.yml up -d

# Verify services are healthy
docker compose -f deployment/docker-compose.test.yml ps

# Check service logs
docker logs archon-test-qdrant
docker logs archon-test-memgraph
docker logs archon-test-kafka  # If using separate Kafka container
```

### 2. Run Real Integration Tests

```bash
# Run all real integration tests
cd python
pytest --real-integration tests/real_integration/ -v

# Run specific test file
pytest --real-integration tests/real_integration/test_kafka_event_flow.py -v

# Run specific test
pytest --real-integration tests/real_integration/test_kafka_event_flow.py::test_kafka_produce_consume_single_event -v

# Run with detailed output
pytest --real-integration tests/real_integration/ -v -s

# Run excluding slow tests
pytest --real-integration tests/real_integration/ -v -m "not slow"
```

### 3. View Test Results

```bash
# Test reports generated in:
# - python/test-results/junit.xml
# - python/test-reports/report.html
# - python/test-reports/coverage/

# Open HTML report
open python/test-reports/report.html
```

## Test Organization

### Test Categories

**1. Kafka Event Flow** (`test_kafka_event_flow.py`)
- Single event produce/consume
- Multiple events with ordering
- Event envelope structure validation
- Consumer group isolation
- High-throughput stress testing

**2. Qdrant Vector Search** (`test_qdrant_vector_search.py`)
- Vector point insertion and retrieval
- Similarity search
- Filtered search with metadata
- Batch operations
- Quality-weighted search (ONEX-specific)
- Collection management

**3. Memgraph Knowledge Graph** (`test_memgraph_knowledge_graph.py`)
- Node creation and retrieval
- Relationship creation and traversal
- Graph pattern matching
- Multi-hop path finding
- Bulk operations
- Cleanup verification

**4. Multi-Service Orchestration** (`test_multi_service_orchestration.py`)
- End-to-end document indexing pipeline
- Cross-service data consistency
- Distributed transaction patterns (saga)
- Performance under load

## Test Fixtures

### Service Connection Fixtures

```python
@pytest.mark.real_integration
async def test_example(
    kafka_producer,          # AIOKafkaProducer
    kafka_consumer,          # AIOKafkaConsumer
    qdrant_client,           # AsyncQdrantClient
    memgraph_session,        # Neo4j AsyncSession
):
    # Test implementation
    pass
```

### Isolation Fixtures

```python
@pytest.mark.real_integration
async def test_isolated(
    kafka_test_topic,        # Unique topic name per test
    qdrant_test_collection,  # Unique collection per test
    memgraph_test_label,     # Unique label per test
    test_id,                 # Unique test session ID
):
    # Test runs in isolation
    pass
```

### Composite Fixtures

```python
@pytest.mark.real_integration
async def test_all_services(
    real_integration_services,  # Dict with all services
):
    kafka_producer = real_integration_services["kafka_producer"]
    qdrant = real_integration_services["qdrant"]
    memgraph = real_integration_services["memgraph"]
    # Use all services
```

## Test Data Management

### Using TestDataManager

```python
from tests.utils.test_data_manager import TestDataManager, KafkaTestDataGenerator

@pytest.mark.real_integration
async def test_with_data_manager(
    kafka_producer,
    qdrant_client,
    memgraph_session,
    test_id,
):
    # Create data manager
    manager = TestDataManager(test_id)

    # Track resources for cleanup
    manager.track_resource("kafka_topic", "test-topic", {"purpose": "integration"})
    manager.track_resource("qdrant_collection", "test-collection")
    manager.track_resource("memgraph_node", "TestNode")

    # Generate test data
    event = KafkaTestDataGenerator.generate_routing_decision_event(
        agent_name="test-agent",
        confidence=0.95,
        user_request="Test request"
    )

    # ... perform test operations ...

    # Cleanup all tracked resources
    stats = await manager.cleanup_all(
        kafka_producer=kafka_producer,
        qdrant_client=qdrant_client,
        memgraph_session=memgraph_session,
    )

    print(f"Cleaned up {stats.total_resources} resources in {stats.cleanup_duration_ms}ms")
```

### Test Data Generators

```python
from tests.utils.test_data_manager import (
    KafkaTestDataGenerator,
    QdrantTestDataGenerator,
    MemgraphTestDataGenerator,
)

# Kafka events
event = KafkaTestDataGenerator.generate_routing_decision_event(...)
event = KafkaTestDataGenerator.generate_transformation_event(...)

# Qdrant points
points = QdrantTestDataGenerator.generate_points(count=10)
quality_point = QdrantTestDataGenerator.generate_quality_point(...)

# Memgraph queries
query = MemgraphTestDataGenerator.generate_create_node_query(...)
rel_query = MemgraphTestDataGenerator.generate_create_relationship_query(...)
```

## Configuration

### Environment Variables

```bash
# Test service URLs (override defaults)
export TEST_KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export TEST_QDRANT_URL="http://localhost:6334"
export TEST_MEMGRAPH_URI="bolt://localhost:7688"
export TEST_MEMGRAPH_USER=""
export TEST_MEMGRAPH_PASSWORD=""

# Enable real integration tests
export REAL_INTEGRATION_TESTS="true"
```

### Docker Compose Test Services

Test services use different ports to avoid conflicts with development:

| Service | Dev Port | Test Port | Container Name |
|---------|----------|-----------|----------------|
| Kafka/Redpanda | 9092 | 9092 | archon-test-kafka |
| Qdrant | 6333 | 6334 | archon-test-qdrant |
| Memgraph | 7687 | 7688 | archon-test-memgraph |
| PostgreSQL | 5432 | 5433 | archon-test-postgres |
| Valkey | 6379 | 6380 | archon-test-valkey |

## Troubleshooting

### Services Not Healthy

```bash
# Check service status
docker compose -f deployment/docker-compose.test.yml ps

# Check specific service logs
docker logs archon-test-qdrant
docker logs archon-test-memgraph

# Restart services
docker compose -f deployment/docker-compose.test.yml restart

# Full restart (clean slate)
docker compose -f deployment/docker-compose.test.yml down -v
docker compose -f deployment/docker-compose.test.yml up -d
```

### Connection Timeouts

```bash
# Verify ports are accessible
nc -zv localhost 6334  # Qdrant
nc -zv localhost 7688  # Memgraph
nc -zv localhost 9092  # Kafka

# Check firewall rules
# Ensure Docker network allows connections

# Increase timeout in conftest.py
# Edit real_integration_config fixture
```

### Test Data Not Cleaned Up

```bash
# Manual cleanup
docker exec archon-test-qdrant curl -X DELETE http://localhost:6333/collections/test_collection_*
docker exec archon-test-memgraph mgconsole -e "MATCH (n:TestNode_*) DETACH DELETE n"

# Or restart services (clean slate)
docker compose -f deployment/docker-compose.test.yml down -v
docker compose -f deployment/docker-compose.test.yml up -d
```

### Kafka Topic Issues

```bash
# Note: Kafka running via omninode-bridge-redpanda (external network)
# Check Redpanda status
docker logs omninode-bridge-redpanda

# List topics
docker exec omninode-bridge-redpanda rpk topic list

# Delete test topics
docker exec omninode-bridge-redpanda rpk topic delete test-topic-*
```

### Tests Skipped

If tests are skipped with "requires --real-integration flag":

```bash
# Ensure you're using the flag
pytest tests/real_integration/ -v  # ❌ WRONG - tests will be skipped
pytest --real-integration tests/real_integration/ -v  # ✅ CORRECT
```

If tests are skipped with "Unhealthy services detected":

```bash
# Services not running - start them
docker compose -f deployment/docker-compose.test.yml up -d

# Services not healthy - check logs
docker compose -f deployment/docker-compose.test.yml ps
docker logs archon-test-qdrant
```

## Performance Benchmarks

Expected performance on typical development machine:

| Operation | Expected Time | Note |
|-----------|---------------|------|
| Kafka produce single event | <100ms | Network + serialization |
| Kafka consume single event | <500ms | Polling interval |
| Qdrant insert 10 points | <500ms | Includes indexing |
| Qdrant similarity search | <100ms | Top-K search |
| Memgraph create node | <50ms | Single transaction |
| Memgraph traversal (3 hops) | <200ms | Graph query |
| Full pipeline (all services) | <2s | End-to-end |

Performance marked tests (`@pytest.mark.slow`):
- High-throughput Kafka: 100 events in <10s
- Qdrant batch operations: 50 points in <5s
- Memgraph bulk operations: 20 nodes in <5s
- Multi-service orchestration: 20 entities in <15s

## CI/CD Integration

### GitHub Actions Workflow (Optional)

```yaml
name: Real Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  real-integration-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    services:
      qdrant:
        image: qdrant/qdrant:v1.7.4
        ports:
          - 6334:6333
        options: >-
          --health-cmd "curl -f http://localhost:6333/readyz"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      memgraph:
        image: memgraph/memgraph:latest
        ports:
          - 7688:7687
        options: >-
          --health-cmd "curl -f http://localhost:7444/"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 3

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd python
          pip install poetry
          poetry install

      - name: Start Kafka (Redpanda)
        run: |
          docker run -d --name redpanda \
            -p 9092:9092 \
            docker.redpanda.com/redpandadata/redpanda:latest \
            redpanda start --overprovisioned --smp 1 --memory 1G

      - name: Run real integration tests
        run: |
          cd python
          poetry run pytest --real-integration tests/real_integration/ -v

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: python/test-reports/
```

## Best Practices

### Test Isolation

✅ **DO**:
- Use unique test IDs for all test data
- Use fixture-provided test collections/topics/labels
- Clean up test data in fixture teardown
- Use separate consumer groups per test

❌ **DON'T**:
- Hardcode topic/collection names
- Reuse test data between tests
- Assume specific execution order
- Share resources between parallel tests

### Test Performance

✅ **DO**:
- Mark slow tests with `@pytest.mark.slow`
- Use appropriate timeouts (not too short, not too long)
- Batch operations when possible
- Include performance assertions

❌ **DON'T**:
- Wait unnecessarily (use events/polling)
- Create excessive test data
- Run performance tests in parallel
- Skip performance validation

### Test Reliability

✅ **DO**:
- Check service health before tests
- Use retries for transient failures
- Validate test data was created
- Verify cleanup completed

❌ **DON'T**:
- Assume services are always available
- Ignore cleanup failures
- Use fixed delays (use polling instead)
- Assume instant consistency

## Maintenance

### Updating Service Versions

When updating service versions in docker-compose.test.yml:

1. Test locally first
2. Check for API changes
3. Update test expectations if needed
4. Run full test suite
5. Update documentation

### Adding New Tests

1. Create test in appropriate file
2. Use `@pytest.mark.real_integration`
3. Use existing fixtures
4. Add test data generators if needed
5. Include cleanup verification
6. Document expected behavior
7. Run test suite to verify

### Debugging Failures

1. Check service logs first
2. Verify test data was created
3. Check for timeout issues
4. Verify cleanup completed
5. Try manual operation
6. Check for concurrency issues
7. Validate test assumptions

## Reference

### Test Markers

- `@pytest.mark.real_integration` - Requires real services
- `@pytest.mark.slow` - Takes >10 seconds
- `@pytest.mark.asyncio` - Async test

### Fixture Reference

See `tests/fixtures/real_integration.py` for complete fixture documentation.

### Test Data Reference

See `tests/utils/test_data_manager.py` for complete data generator documentation.

---

**For questions or issues**: See troubleshooting section or check test logs in `python/test-reports/`.
