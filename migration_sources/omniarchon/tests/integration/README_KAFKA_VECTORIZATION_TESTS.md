# Kafka Consumer Vectorization Pipeline Integration Tests

## Overview

Comprehensive end-to-end testing of the vectorization pipeline to prevent bugs like the one discovered where Kafka events were not being properly processed and vectorized.

**Test File**: `test_kafka_consumer_vectorization.py`

## Purpose

These tests validate the complete vectorization pipeline:

```
Kafka Event → Consumer → Handler → Intelligence Service → Qdrant + Memgraph
```

### What Was the Bug?

The vectorization bug occurred because:
1. Kafka consumer received file processing events
2. Consumer routed to DocumentProcessingHandler
3. Handler called `/process/document` endpoint on Intelligence service
4. **BUT**: No vectors were created in Qdrant, no nodes in Memgraph

This test suite prevents this by validating the **entire pipeline end-to-end**.

## Test Coverage

### 1. `test_consumer_creates_vector_and_node`
**Purpose**: Validate happy path - event → vector + node creation

**Flow**:
1. Publish `process-document-requested` event to Kafka
2. Wait for consumer to process event
3. Verify vector created in Qdrant with correct content
4. Verify FILE node created in Memgraph
5. Verify entities extracted and linked to file
6. Verify entity types (function, class) are correct

**Assertions**:
- ✅ Vector exists in Qdrant
- ✅ Vector contains expected content keywords
- ✅ FILE node exists in Memgraph
- ✅ At least 2 entities extracted
- ✅ Entity types are correct (function, class)

### 2. `test_consumer_handles_vectorization_failure`
**Purpose**: Verify error handling for invalid content

**Flow**:
1. Publish event with invalid/malformed content (1MB of garbage)
2. Consumer processes event
3. Intelligence service fails to process
4. Verify error is handled gracefully (no crash, DLQ routing)

**Assertions**:
- ✅ No vector created for invalid content
- ✅ Consumer continues running after error
- ✅ Error logged appropriately

### 3. `test_idempotency_same_event_twice`
**Purpose**: Verify idempotent processing (no duplicates)

**Flow**:
1. Publish event with correlation_id A
2. Wait for processing to complete
3. Publish SAME event with correlation_id A
4. Verify no duplicate vectors/nodes created
5. Verify existing data not corrupted

**Assertions**:
- ✅ Same number of vectors after second event
- ✅ Node data unchanged after second event
- ✅ No data corruption

### 4. `test_multiple_files_batch_processing`
**Purpose**: Verify batch processing under load

**Flow**:
1. Publish 5 events quickly in succession
2. Wait for all to process
3. Verify all vectors created
4. Verify all nodes created
5. Check for race conditions

**Assertions**:
- ✅ All 5 vectors created
- ✅ All 5 nodes created
- ✅ No data loss or corruption

### 5. `test_vector_dimensions_correctness`
**Purpose**: Verify vector quality and metadata

**Flow**:
1. Publish event
2. Retrieve vector with vector data
3. Verify dimensions match model config (1536)
4. Verify metadata is correct

**Assertions**:
- ✅ Vector dimensions = 1536 (or configured dimension)
- ✅ Metadata includes file_path, project_name
- ✅ Metadata values are correct

## Running the Tests

### Prerequisites

**Required Services**:
- Kafka/Redpanda (192.168.86.200:29092)
- Intelligence service (localhost:8053)
- Search service (localhost:8055)
- Qdrant (localhost:6333)
- Memgraph (localhost:7687)
- **Kafka Consumer** (must be running to process events)

**Start Kafka Consumer**:
```bash
# In the intelligence service directory
cd services/intelligence
python3 src/kafka_consumer.py
```

### Running Tests

**Run all vectorization tests**:
```bash
pytest tests/integration/test_kafka_consumer_vectorization.py -v
```

**Run specific test**:
```bash
pytest tests/integration/test_kafka_consumer_vectorization.py::test_consumer_creates_vector_and_node -v
```

**Run with detailed logging**:
```bash
pytest tests/integration/test_kafka_consumer_vectorization.py -v --log-cli-level=INFO
```

**Run in parallel** (requires pytest-xdist):
```bash
pytest tests/integration/test_kafka_consumer_vectorization.py -v -n 2
```

### Test Markers

Tests are marked with:
- `@pytest.mark.slow` - Tests take 30+ seconds
- `@pytest.mark.asyncio` - Async tests

**Skip slow tests**:
```bash
pytest tests/integration/test_kafka_consumer_vectorization.py -v -m "not slow"
```

## Test Data Cleanup

Tests automatically clean up after themselves:
- Memgraph: Deletes PROJECT and all child nodes
- Qdrant: Vectors remain (use separate test collection or manual cleanup)

**Manual cleanup if needed**:
```bash
# Clean up test projects from Memgraph
docker exec -it archon-memgraph mgconsole -e "MATCH (p:PROJECT) WHERE p.name STARTS WITH 'test_' DETACH DELETE p"

# Clean up test vectors from Qdrant (if using test collection)
curl -X DELETE http://localhost:6333/collections/test_vectors
```

## Debugging Test Failures

### Consumer Not Processing Events

**Symptoms**: Tests timeout waiting for vectors/nodes

**Debug Steps**:
1. Check if Kafka consumer is running:
   ```bash
   ps aux | grep kafka_consumer
   ```

2. Check consumer logs:
   ```bash
   docker logs archon-intelligence --tail 100 -f
   ```

3. Check Kafka topics:
   ```bash
   docker exec omninode-bridge-redpanda rpk topic list
   docker exec omninode-bridge-redpanda rpk topic consume dev.archon-intelligence.document.process-document-requested.v1
   ```

4. Check consumer health:
   ```bash
   curl http://localhost:8053/metrics/consumer
   ```

### Vector Not Created

**Symptoms**: `test_consumer_creates_vector_and_node` fails at vector assertion

**Debug Steps**:
1. Check if Intelligence service is healthy:
   ```bash
   curl http://localhost:8053/health
   ```

2. Check if embedding service is running:
   ```bash
   curl http://localhost:8051/health  # vLLM or embedding service
   ```

3. Check Qdrant collections:
   ```bash
   curl http://localhost:6333/collections
   ```

4. Check Qdrant points:
   ```bash
   curl http://localhost:6333/collections/archon_vectors/points/scroll
   ```

### Node Not Created

**Symptoms**: `test_consumer_creates_vector_and_node` fails at node assertion

**Debug Steps**:
1. Check Memgraph connection:
   ```bash
   docker exec -it archon-memgraph mgconsole -e "RETURN 1"
   ```

2. Query for test nodes:
   ```bash
   docker exec -it archon-memgraph mgconsole -e "MATCH (p:PROJECT) WHERE p.name STARTS WITH 'test_' RETURN p.name, count(*)"
   ```

3. Check for FILE nodes:
   ```bash
   docker exec -it archon-memgraph mgconsole -e "MATCH (f:FILE) WHERE f.path STARTS WITH '/test/' RETURN f.path LIMIT 10"
   ```

## Integration with CI/CD

### GitHub Actions

```yaml
- name: Run Kafka vectorization integration tests
  run: |
    # Start consumer in background
    docker exec -d archon-intelligence python3 src/kafka_consumer.py

    # Wait for consumer to be ready
    sleep 5

    # Run tests
    pytest tests/integration/test_kafka_consumer_vectorization.py -v --junit-xml=test-results/vectorization.xml

    # Stop consumer
    docker exec archon-intelligence pkill -f kafka_consumer
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:
```yaml
- id: kafka-vectorization-tests
  name: Kafka Vectorization Tests
  entry: pytest tests/integration/test_kafka_consumer_vectorization.py -v
  language: system
  pass_filenames: false
  stages: [push]
```

## Performance Benchmarks

Expected test durations:
- `test_consumer_creates_vector_and_node`: ~30-45s
- `test_consumer_handles_vectorization_failure`: ~15-20s
- `test_idempotency_same_event_twice`: ~45-60s
- `test_multiple_files_batch_processing`: ~30-45s
- `test_vector_dimensions_correctness`: ~20-30s

**Total suite**: ~2-3 minutes

## Contributing

When adding new vectorization features:
1. Add corresponding test to this suite
2. Verify test passes locally
3. Run full suite before committing
4. Update this README if new test patterns emerge

## References

- **Kafka Consumer**: `services/intelligence/src/kafka_consumer.py`
- **Document Processing Handler**: `services/intelligence/src/handlers/document_processing_handler.py`
- **Intelligence Service**: `services/intelligence/app.py` (POST `/process/document`)
- **Qdrant Client**: `qdrant_client` Python library
- **Memgraph Driver**: `neo4j` Python driver

## Support

For issues or questions:
1. Check service logs: `docker logs archon-intelligence`
2. Check Kafka consumer metrics: `curl http://localhost:8053/metrics/consumer`
3. Review existing test patterns in `tests/integration/`
4. Consult `CLAUDE.md` for architecture details
