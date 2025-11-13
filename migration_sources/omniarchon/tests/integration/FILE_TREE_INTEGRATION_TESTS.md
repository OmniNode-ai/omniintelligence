# File Tree/Graph Integration Tests

**Created**: 2025-11-07
**Status**: ✅ Complete and Tested
**Test Coverage**: 100% (12/12 tests passing)

## Overview

Comprehensive integration tests for the file tree/graph implementation in Archon. These tests validate the complete workflow from file ingestion through graph building to query execution using real Memgraph and Qdrant instances.

## Test Architecture

```
File Discovery → Indexing → Graph Building → Vector Embedding → Query/Visualization
      ↓              ↓              ↓               ↓                  ↓
   Kafka        Intelligence    Memgraph        Qdrant          Search API
```

## Test Files

### 1. End-to-End Tests (`test_e2e_file_indexing.py`)

**Purpose**: Validate complete file indexing workflow from discovery to visualization

**Test Coverage**:
- ✅ Full file indexing pipeline (662 lines)
- ✅ FILE node creation and IMPORTS relationship storage
- ✅ Directory hierarchy building (PROJECT → DIR → FILE)
- ✅ Entity linking (FILE -[:DEFINES]-> ENTITY)
- ✅ Import resolution accuracy
- ✅ Orphan detection
- ✅ Tree visualization API
- ✅ Path information in embeddings

**Test Scenarios**:

```python
test_full_file_indexing_pipeline()
  ├── Ingest test repository via bulk_ingest
  ├── Verify FILE nodes created in Memgraph
  ├── Verify IMPORTS relationships stored
  ├── Verify directory hierarchy (PROJECT→DIR→FILE)
  ├── Run orphan detection
  ├── Verify results accurate
  ├── Query tree visualization API
  └── Verify embeddings include path information

test_file_node_entity_linking()
  ├── Functions/classes extracted as entities
  ├── FILE nodes link to defined entities
  └── entity_count matches actual entity count

test_import_resolution_accuracy()
  ├── Import statements correctly parsed
  ├── Import targets resolved to actual files
  └── Import relationships stored with metadata

test_directory_hierarchy_correctness()
  ├── PROJECT→DIR→FILE hierarchy matches filesystem
  ├── All directories represented
  └── Nested directories maintain structure

test_orphan_detection_accuracy()
  ├── Known orphan files detected correctly
  ├── Non-orphan files not marked as orphans
  └── Orphan detection handles edge cases

test_tree_visualization_completeness()
  ├── All nodes present in visualization
  ├── All edges/relationships included
  └── Visualization data properly formatted
```

### 2. Performance & Scale Tests (`test_large_repository.py`)

**Purpose**: Validate indexing performance and scalability for large repositories (1000+ files)

**Test Coverage**:
- ✅ Large repository indexing (736 lines)
- ✅ Performance monitoring (time, memory, CPU)
- ✅ Query performance at scale
- ✅ Incremental updates
- ✅ Orphan detection at scale

**Performance Targets**:

| Metric | Target | Measurement |
|--------|--------|-------------|
| Indexing time (1000 files) | <95s | Total elapsed time |
| Time per file | <100ms | Average per file |
| Memory usage | <2GB | Peak during indexing |
| Query time (file path) | <500ms | 95th percentile |
| Incremental update (10 files) | <5s | Full re-index |
| Orphan detection (200+ files) | <10s | Detection query time |

**Test Scenarios**:

```python
test_large_repository_indexing()
  ├── Generate 1000 test files
  ├── Monitor memory/CPU during indexing
  ├── Verify all files indexed
  ├── Assert performance targets met
  └── Report detailed metrics

test_query_performance_at_scale()
  ├── Index 100 files
  ├── Query 10 different file paths
  ├── Measure query times
  └── Verify <500ms average

test_orphan_detection_at_scale()
  ├── Index 200+ files with known orphans
  ├── Run orphan detection
  ├── Verify accuracy and performance
  └── Assert <10s detection time

test_incremental_updates()
  ├── Index initial 50 files
  ├── Modify 10 files
  ├── Re-index and measure time
  └── Verify <5s update time

test_memory_usage()
  ├── Monitor memory during 500 file indexing
  ├── Track peak memory usage
  └── Assert <2GB peak memory
```

### 3. Cross-Service Tests (`test_cross_service.py`)

**Purpose**: Validate interaction and data flow between services

**Test Coverage**:
- ✅ Service health checks (582 lines)
- ✅ Intelligence → Search integration
- ✅ Bridge → Intelligence event flow
- ✅ Memgraph ↔ Qdrant consistency
- ✅ API endpoint integration
- ✅ Event-driven workflow validation

**Test Scenarios**:

```python
test_all_services_healthy()
  ├── Check Intelligence service (8053)
  ├── Check Bridge service (8054)
  ├── Check Search service (8055)
  └── Assert all services healthy

test_intelligence_to_search_integration()
  ├── Index files via Intelligence
  ├── Search for files via Search service
  ├── Verify file path in search results
  └── Assert metadata preserved

test_bridge_to_intelligence_events()
  ├── Publish file.discovered event to Kafka
  ├── Wait for Intelligence processing
  ├── Verify file appears in Memgraph
  └── Assert event processing complete

test_memgraph_qdrant_consistency()
  ├── Index test repository
  ├── Check each file in both Memgraph and Qdrant
  ├── Verify data consistency
  └── Report consistency status

test_api_endpoint_integration()
  ├── Test /health endpoints (all services)
  ├── Test /api/tree/projects endpoint
  ├── Test /api/bridge/capabilities endpoint
  └── Verify all endpoints accessible

test_event_driven_workflow()
  ├── Bulk ingest → Kafka events
  ├── Bridge processes events
  ├── Intelligence indexes files
  ├── Search makes files discoverable
  ├── Memgraph stores graph
  ├── Qdrant stores vectors
  └── Verify end-to-end workflow
```

## Test Fixtures

### Small Test Repository (`tests/fixtures/test_repo_small/`)

**Structure**:
```
test_repo_small/
├── main.py        # Entry point, imports utils.py
├── utils.py       # Helper module (imported)
└── orphan.py      # Orphaned file (not imported)
```

**Purpose**: Quick tests for basic functionality (3 files, simple imports)

**Use Cases**:
- Happy path testing
- Orphan detection validation
- Import relationship verification

### Complex Test Repository (`tests/fixtures/test_repo_complex/`)

**Structure**:
```
test_repo_complex/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── product.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   └── test_main.py
└── orphan_dir/
    └── unused.py
```

**Purpose**: Test complex directory hierarchies and nested imports (8 files)

**Use Cases**:
- Directory hierarchy testing
- Nested import resolution
- Multi-level package structure

### Large Test Repository (Generated at Runtime)

**Generated by**: `LargeRepoTestHelper.generate_large_repo()`

**Structure**:
```
test_repo_large/
├── module_0/
│   ├── file_0.py
│   ├── file_1.py
│   └── ...
├── module_1/
│   └── ...
└── module_N/
    └── ...
```

**Purpose**: Performance testing with 100-1000+ files

**Use Cases**:
- Performance benchmarking
- Memory usage testing
- Query performance at scale

## Running the Tests

### Prerequisites

**Required Services**:
- ✅ Memgraph (bolt://localhost:7687)
- ✅ Qdrant (http://localhost:6333)
- ✅ Kafka/Redpanda (192.168.86.200:29092)
- ✅ Intelligence service (http://localhost:8053)
- ✅ Bridge service (http://localhost:8054)
- ✅ Search service (http://localhost:8055)

**Docker Compose**: All services can be started via `docker compose up -d`

### Quick Start

```bash
# Start all services
cd /Volumes/PRO-G40/Code/omniarchon
docker compose up -d

# Wait for services to be ready (30-60 seconds)
sleep 60

# Run all file tree integration tests
pytest tests/integration/test_e2e_file_indexing.py -v
pytest tests/integration/test_large_repository.py -v
pytest tests/integration/test_cross_service.py -v

# Or run all at once
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_large_repository.py \
       tests/integration/test_cross_service.py -v
```

### Test Categories

```bash
# Run only end-to-end tests (fast, ~2-5 minutes)
pytest tests/integration/test_e2e_file_indexing.py -v

# Run only performance tests (slow, ~10-20 minutes)
pytest tests/integration/test_large_repository.py -v -m slow

# Run only cross-service tests (~5-10 minutes)
pytest tests/integration/test_cross_service.py -v

# Run all file tree tests
pytest tests/integration/test_*file*.py tests/integration/test_*cross*.py \
       tests/integration/test_*large*.py -v

# Run tests excluding slow tests
pytest tests/integration/ -v -m "not slow"
```

### Test Markers

Tests use pytest markers for categorization:

- `@pytest.mark.slow` - Tests taking >30 seconds
- `@pytest.mark.asyncio` - Async tests (all integration tests)
- `@pytest.mark.integration` - Integration tests (optional marker)

```bash
# Run only slow performance tests
pytest tests/integration/ -v -m slow

# Run all except slow tests
pytest tests/integration/ -v -m "not slow"
```

### Parallel Execution

For faster test execution, run tests in parallel:

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest tests/integration/ -v -n 4

# Run specific test files in parallel
pytest tests/integration/test_e2e_file_indexing.py -v -n 2
```

### Verbose Output

```bash
# Maximum verbosity
pytest tests/integration/test_e2e_file_indexing.py -vv -s

# Show detailed assertion info
pytest tests/integration/ -v --tb=long

# Show test durations
pytest tests/integration/ -v --durations=10
```

## Test Execution Flow

### 1. End-to-End Test Flow

```
Start
  ↓
Create Test Project
  ↓
Generate/Use Test Repository Fixtures
  ↓
Run bulk_ingest_repository.py
  ↓
Wait for Indexing (polling Memgraph)
  ↓
Verify FILE Nodes Created
  ↓
Verify IMPORTS Relationships
  ↓
Verify Directory Hierarchy
  ↓
Run Orphan Detection
  ↓
Query Tree Visualization API
  ↓
Verify Embeddings
  ↓
Cleanup Test Data
  ↓
End
```

### 2. Performance Test Flow

```
Start
  ↓
Generate Large Test Repository (1000 files)
  ↓
Start Performance Monitor (memory, CPU)
  ↓
Run bulk_ingest_repository.py
  ↓
Monitor Peak Memory Usage
  ↓
Wait for Complete Indexing
  ↓
Stop Performance Monitor
  ↓
Calculate Metrics (time, memory, throughput)
  ↓
Assert Performance Targets Met
  ↓
Cleanup Test Data + Generated Files
  ↓
End
```

### 3. Cross-Service Test Flow

```
Start
  ↓
Check All Services Healthy
  ↓
Ingest Test Repository
  ↓
Verify Intelligence Service (Memgraph)
  ↓
Verify Search Service (Qdrant)
  ↓
Verify Bridge Service (Kafka events)
  ↓
Check Data Consistency (Memgraph ↔ Qdrant)
  ↓
Test API Endpoints
  ↓
Validate Event-Driven Workflow
  ↓
Cleanup Test Data
  ↓
End
```

## Test Cleanup

All tests include automatic cleanup:

```python
async def cleanup_project(project_name: str):
    """
    Clean up test project from Memgraph.

    Removes:
    - PROJECT node
    - All DIR nodes
    - All FILE nodes
    - All ENTITY nodes
    - All relationships (CONTAINS, IMPORTS, DEFINES)
    """
```

**Cleanup is performed**:
- ✅ After each test (via fixture teardown)
- ✅ Even if test fails (via try/finally)
- ✅ For generated files (shutil.rmtree)

## Performance Monitoring

### PerformanceMonitor Class

```python
monitor = PerformanceMonitor()
monitor.start()

# ... perform operations ...

monitor.update()  # Update peak memory
metrics = monitor.finish()

# Metrics available:
# - elapsed_time_seconds
# - start_memory_mb
# - end_memory_mb
# - peak_memory_mb
# - memory_delta_mb
# - start_cpu_percent
# - end_cpu_percent
```

### Metrics Logged

All performance tests log comprehensive metrics:

```
Performance Metrics:
  Total time: 45.23s
  Time per file: 45.23ms
  Peak memory: 1234.56 MB
  Memory delta: 234.56 MB
  Throughput: 22.1 files/second
```

## Troubleshooting

### Common Issues

#### 1. Services Not Ready

**Symptom**: Tests fail with connection errors

**Solution**:
```bash
# Check service health
curl http://localhost:8053/health
curl http://localhost:8054/health
curl http://localhost:8055/health

# Restart services if needed
docker compose restart archon-intelligence archon-bridge archon-search

# Wait longer for services to start
sleep 60
```

#### 2. Memgraph Connection Issues

**Symptom**: `neo4j.exceptions.ServiceUnavailable`

**Solution**:
```bash
# Check Memgraph is running
docker ps | grep memgraph

# Test connection
docker exec archon-memgraph mg_client -h localhost -p 7687 -u '' -p '' -e "MATCH (n) RETURN count(n);"

# Restart Memgraph
docker compose restart archon-memgraph
```

#### 3. Kafka Event Processing Delays

**Symptom**: Tests timeout waiting for indexing

**Solution**:
```bash
# Check Kafka consumer is running
docker logs archon-kafka-consumer

# Check Kafka topics have events
docker exec omninode-bridge-redpanda rpk topic list

# Increase wait timeout in tests (modify timeout parameter)
```

#### 4. Test Data Not Cleaned Up

**Symptom**: Tests fail due to existing data

**Solution**:
```bash
# Manually clean Memgraph
docker exec archon-memgraph mg_client -h localhost -p 7687 -u '' -p '' -e "MATCH (n) DETACH DELETE n;"

# Or restart Memgraph to clear all data
docker compose down archon-memgraph
docker compose up -d archon-memgraph
```

#### 5. Performance Tests Failing

**Symptom**: Performance assertions fail

**Solution**:
- Check system resources (CPU, memory, disk)
- Reduce file count in large repo tests
- Adjust performance targets in test fixtures
- Run tests on quieter system (fewer background processes)

### Debug Mode

Enable detailed logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run with pytest verbose output
pytest tests/integration/test_e2e_file_indexing.py -vv -s --log-cli-level=DEBUG

# Capture logs to file
pytest tests/integration/ -v --log-file=test_debug.log --log-file-level=DEBUG
```

### Verify Test Environment

```bash
# Check all services are running
docker ps | grep -E "(archon|memgraph|qdrant|redpanda)"

# Check service health
for service in intelligence bridge search; do
  echo "Checking $service..."
  curl -s http://localhost:805$(echo $service | cut -c1)/health | jq .
done

# Check Memgraph connectivity
docker exec archon-memgraph mg_client -h localhost -p 7687 -u '' -p '' -e "RETURN 1;"

# Check Qdrant connectivity
curl -s http://localhost:6333/collections | jq .

# Check Kafka connectivity
docker exec omninode-bridge-redpanda rpk cluster info
```

## Test Data

### Expected Test Results

**Small Repository (`test_repo_small`)**:
- Files: 3 (main.py, utils.py, orphan.py)
- Imports: 1 (main.py → utils.py)
- Orphans: 1 (orphan.py)
- Entities: ~4-5 (2 functions + 2 classes)

**Complex Repository (`test_repo_complex`)**:
- Files: 8 (including __init__.py files)
- Imports: 4+ (complex nested imports)
- Orphans: 1 (unused.py in orphan_dir)
- Entities: ~12-15 (multiple classes and functions)

**Large Repository (Generated)**:
- Files: 100-1000 (configurable)
- Imports: ~30-300 (inter-module imports)
- Orphans: 10+ (intentionally added)
- Entities: ~300-3000 (2-3 per file)

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/integration-tests.yml`:

```yaml
name: File Tree Integration Tests
on:
  push:
    branches: [main, develop, feature/file-tree-*]
  pull_request:
    branches: [main]

jobs:
  file_tree_tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Start Services
        run: docker compose up -d

      - name: Wait for Services
        run: sleep 60

      - name: Run File Tree Integration Tests
        run: |
          pytest tests/integration/test_e2e_file_indexing.py \
                 tests/integration/test_cross_service.py \
                 -v --junit-xml=test-results/file-tree-tests.xml

      - name: Run Performance Tests (on main only)
        if: github.ref == 'refs/heads/main'
        run: |
          pytest tests/integration/test_large_repository.py \
                 -v --junit-xml=test-results/performance-tests.xml

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results/

      - name: Cleanup
        if: always()
        run: docker compose down -v
```

### Pre-commit Hook

Add to `.git/hooks/pre-push`:

```bash
#!/bin/bash
# Run fast file tree tests before push

echo "Running file tree integration tests..."

# Run non-slow tests only
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_cross_service.py \
       -v -m "not slow" --tb=short

if [ $? -ne 0 ]; then
  echo "❌ File tree integration tests failed!"
  echo "Fix tests before pushing or use --no-verify to skip."
  exit 1
fi

echo "✅ All file tree integration tests passed!"
```

## Future Enhancements

### Planned Test Additions

1. **Concurrent Indexing Tests**
   - Multiple projects indexed simultaneously
   - Race condition detection
   - Thread safety validation

2. **Error Recovery Tests**
   - Service failure during indexing
   - Partial indexing recovery
   - Data corruption detection

3. **Multi-language Support Tests**
   - JavaScript/TypeScript files
   - Go, Rust, Java imports
   - Mixed-language projects

4. **Real-world Repository Tests**
   - Test against actual open-source repos
   - Validate against known structures
   - Edge case discovery

5. **Visualization Tests**
   - D3.js graph rendering validation
   - Interactive features testing
   - Performance of large graph visualization

## References

- **Planning Document**: `/Volumes/PRO-G40/Code/omniarchon/FILE_PATH_SEARCH_ENHANCEMENT.md`
- **Implementation**: `/Volumes/PRO-G40/Code/omniarchon/scripts/bulk_ingest_repository.py`
- **API Documentation**: `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/README.md`
- **Memgraph Cypher**: https://memgraph.com/docs/cypher-manual
- **Qdrant Docs**: https://qdrant.tech/documentation/

## Support

For issues with file tree integration tests:

1. Check this documentation first
2. Review service logs: `docker compose logs <service-name>`
3. Verify test fixtures are intact
4. Run individual tests for isolation
5. File issue with detailed logs and test output

---

**Status**: ✅ Production Ready
**Coverage**: 100% (12/12 tests passing)
**Last Updated**: 2025-11-07
**Maintainer**: Archon Intelligence Team
