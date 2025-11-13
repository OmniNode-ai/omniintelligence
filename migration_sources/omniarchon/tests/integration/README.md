# Archon MCP Integration Test Suite

A comprehensive integration test suite for the MCP (Model Context Protocol) document indexing pipeline and file tree/graph implementation. This suite validates workflows from document creation through RAG queries and complete file-based repository indexing.

## 🎯 Overview

The integration test suite ensures that core Archon functionality works correctly across all services:

```
MCP Document Creation → Bridge Service → Memgraph (Knowledge Graph) → Qdrant (Vector DB) → RAG Query Retrieval
File Discovery → Indexing → Graph Building → Vector Embedding → Query/Visualization
```

### Test Categories

- **🟢 Happy Path Tests**: End-to-end validation of successful document processing workflows
- **🔴 Error Handling Tests**: Service failure scenarios, malformed content, and edge cases
- **⚡ Performance Tests**: Latency, throughput, and scalability benchmarks
- **🔄 Data Consistency Tests**: Cross-service synchronization and integrity validation
- **🌲 File Tree/Graph Tests**: Complete file indexing, import resolution, and orphan detection (NEW)
- **📊 Cross-Service Tests**: Service interaction, event-driven workflows, and API integration (NEW)
- **🏋️ Large Repository Tests**: Performance and scale testing with 1000+ files (NEW)

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ with Docker Compose
- 4GB+ available RAM
- 10GB+ free disk space
- Make (optional, for simplified commands)

### Running Tests

#### Option 1: Using Make (Recommended)

```bash
# Setup and run essential tests (5-10 minutes)
make test-integration-setup
make test-integration-fast

# Run complete test suite (15-30 minutes)
make test-integration-full

# Generate comprehensive report
make test-integration-report

# Cleanup when done
make test-integration-down
```

#### Option 2: Using the Test Runner Script

```bash
# Quick essential tests
./scripts/run-integration-tests.sh fast

# Complete test suite with verbose output
./scripts/run-integration-tests.sh -v full

# Performance benchmarks only
./scripts/run-integration-tests.sh performance

# View all options
./scripts/run-integration-tests.sh --help
```

#### Option 3: Manual Docker Commands

```bash
# Setup environment
docker compose -f deployment/docker-compose.integration-tests.yml up -d

# Wait for services to be ready (check health)
curl http://localhost:18181/health
curl http://localhost:18051/health
curl http://localhost:18053/health

# Run specific test category
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/test_happy_path.py -v

# Cleanup
docker compose -f deployment/docker-compose.integration-tests.yml down --volumes
```

## 🌲 NEW: File Tree/Graph Integration Tests

### Quick Start

Run file tree/graph tests (complete file-based repository indexing):

```bash
# Fast tests (~5 minutes)
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_cross_service.py -v -m "not slow"

# All tests including performance (~20 minutes)
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_large_repository.py \
       tests/integration/test_cross_service.py -v
```

### Documentation

- **📖 Full Documentation**: [`FILE_TREE_INTEGRATION_TESTS.md`](FILE_TREE_INTEGRATION_TESTS.md) - Complete guide (architecture, tests, troubleshooting)
- **⚡ Quick Reference**: [`RUN_FILE_TREE_TESTS.md`](RUN_FILE_TREE_TESTS.md) - Fast command reference and common options

### What's Tested

- ✅ **Complete File Indexing Pipeline** - Discovery through visualization
- ✅ **FILE Node Creation** - File metadata in Memgraph graph
- ✅ **IMPORTS Relationships** - Import resolution and dependency tracking
- ✅ **Directory Hierarchy** - PROJECT → DIR → FILE structure
- ✅ **Entity Linking** - FILE -[:DEFINES]-> ENTITY relationships
- ✅ **Orphan Detection** - Unused file identification
- ✅ **Tree Visualization API** - Graph query and rendering
- ✅ **Path-Enhanced Embeddings** - File path in vector search
- ✅ **Performance at Scale** - 1000+ file repositories
- ✅ **Cross-Service Integration** - Intelligence, Bridge, Search coordination
- ✅ **Event-Driven Workflow** - Kafka-based async processing

### Test Files

| File | Purpose | Duration | Tests |
|------|---------|----------|-------|
| `test_e2e_file_indexing.py` | Complete workflow validation | ~5 min | 6 tests |
| `test_large_repository.py` | Performance & scale testing | ~15 min | 5 tests |
| `test_cross_service.py` | Service interaction validation | ~10 min | 6 tests |

**Total**: 17 tests, 100% passing ✅

---

## 📊 Test Suite Structure

### Happy Path Tests (`test_happy_path.py`)

Tests the core success scenarios for document processing:

```python
# Single document end-to-end pipeline
test_complete_pipeline_single_document()
  ├── Create MCP project and document
  ├── Wait for bridge synchronization (max 30s)
  ├── Verify entity extraction in Memgraph
  ├── Confirm vector indexing in Qdrant
  └── Validate RAG retrievability

# Multiple documents with sequential processing
test_multiple_documents_sequential()

# Large document handling
test_large_document_processing()

# Special character and encoding handling
test_special_characters_and_encoding()
```

**SLA Requirement**: All happy path tests must complete within 30 seconds to meet service level agreements.

### Error Handling Tests (`test_error_handling.py`)

Validates resilience and error recovery:

```python
# Service failure scenarios
TestServiceFailureScenarios:
  ├── test_intelligence_service_unavailable()
  ├── test_vector_database_unavailable()
  ├── test_knowledge_graph_unavailable()
  └── test_bridge_service_unavailable()

# Malformed content handling
TestMalformedContentHandling:
  ├── test_invalid_json_content()
  ├── test_oversized_document_content()
  └── test_malformed_mcp_requests()

# Concurrency and race conditions
TestConcurrencyAndRaceConditions:
  ├── test_concurrent_document_creation()
  ├── test_rapid_sequential_operations()
  └── test_simultaneous_bridge_processing()
```

### Performance Tests (`test_performance.py`)

Benchmarks system performance and scalability:

```python
# Latency benchmarks
TestLatencyBenchmarks:
  ├── test_document_creation_latency()      # Target: <2s
  ├── test_bridge_sync_latency()            # Target: <5s
  ├── test_rag_query_latency()              # Target: <1s
  └── test_end_to_end_pipeline_latency()    # Target: <30s

# Throughput benchmarks
TestThroughputBenchmarks:
  ├── test_document_creation_throughput()   # Target: >10 docs/min
  ├── test_concurrent_rag_queries()         # Target: >50 queries/min
  └── test_bulk_document_processing()       # Target: >100 docs/batch

# Resource utilization
TestResourceUtilization:
  ├── test_memory_usage_patterns()
  ├── test_cpu_utilization_under_load()
  └── test_storage_efficiency()
```

### Data Consistency Tests (`test_data_consistency.py`)

Ensures data integrity across all services:

```python
# Cross-service consistency
TestCrossServiceDataConsistency:
  ├── test_document_creation_consistency()   # MCP → Postgres → Memgraph → Qdrant
  ├── test_document_update_propagation()     # Updates sync across services
  └── test_document_deletion_cleanup()       # Cascading deletes work properly

# Eventual consistency validation
TestEventualConsistency:
  ├── test_bridge_sync_timing()              # Bridge processes within SLA
  ├── test_vector_indexing_completion()      # Qdrant indexing completes
  └── test_knowledge_graph_updates()         # Memgraph reflects changes

# Data integrity and corruption detection
TestDataIntegrityAndCorruption:
  ├── test_content_hash_validation()         # Content integrity preserved
  ├── test_encoding_preservation()           # UTF-8 handling correct
  └── test_metadata_consistency()            # Metadata matches across services
```

## 🔧 Configuration

### Environment Variables

The test suite uses these key environment variables:

```bash
# Service endpoints (automatically configured for Docker)
POSTGRES_HOST=postgres-test
QDRANT_URL=http://qdrant-test:6333
MEMGRAPH_URI=bolt://memgraph-test:7687

# Test-specific settings
TEST_TIMEOUT=1800                    # Maximum test execution time (30 min)
PYTEST_PARALLEL_WORKERS=2           # Number of parallel test workers
SLA_DOCUMENT_PROCESSING_SECONDS=30   # SLA requirement for processing
BENCHMARK_ITERATIONS=5               # Number of benchmark iterations

# Service ports (for health checks)
ARCHON_SERVER_TEST_PORT=18181
ARCHON_MCP_TEST_PORT=18051
INTELLIGENCE_SERVICE_TEST_PORT=18053
```

### Test Configuration

Key settings in `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests/integration
markers =
    slow: marks tests as slow (>30s execution time)
    smoke: minimal tests for deployment validation
    performance: performance and benchmark tests
    flaky: tests that may occasionally fail due to timing
timeout = 1800
```

### Performance Thresholds

Configurable performance expectations:

```python
PERFORMANCE_THRESHOLDS = {
    'document_creation': {'max_seconds': 2.0},
    'bridge_sync': {'max_seconds': 5.0},
    'rag_query': {'max_seconds': 1.0},
    'end_to_end_pipeline': {'max_seconds': 30.0},
    'throughput_docs_per_minute': {'min_value': 10},
    'concurrent_queries_per_minute': {'min_value': 50}
}
```

## 📈 Monitoring and Reporting

### Test Reports

The test suite generates comprehensive reports:

- **HTML Report**: `test-results/reports/report.html` - Detailed test results with logs
- **JUnit XML**: `test-results/reports/junit.xml` - CI/CD compatible results
- **Coverage Report**: `test-results/coverage/html/index.html` - Test coverage analysis
- **Performance Benchmarks**: `test-results/benchmarks/benchmark.json` - Performance metrics

### Dashboard

Launch the real-time test dashboard:

```bash
# Install dashboard dependencies
poetry add fastapi uvicorn aiofiles click

# Start the dashboard
poetry run python scripts/test-dashboard.py --scan --port 8080

# Access at http://localhost:8080
```

Dashboard features:
- 📊 Real-time test metrics and trends
- 📈 Performance graphs and analysis
- 🔍 Detailed test run inspection
- 📋 Historical test data and patterns
- 🚨 Failure notifications and alerts

### Continuous Monitoring

For production monitoring:

```bash
# Set up automated daily runs
echo "0 2 * * * cd /path/to/archon && make workflow-integration-ci" | crontab -

# Monitor with the dashboard
poetry run python scripts/test-dashboard.py --watch --scan
```

## 🎛️ Advanced Usage

### Custom Test Scenarios

Create custom test scenarios by extending the base test classes:

```python
from tests.integration.conftest import IntegrationTestClient

class TestCustomScenario:
    async def test_my_custom_workflow(self, test_client: IntegrationTestClient):
        # Create test project
        project = await test_client.create_test_project("Custom Test Project")

        # Create custom document
        document = await test_client.create_test_document(
            project=project,
            title="Custom Document",
            content={"my_field": "custom_data"}
        )

        # Wait for processing
        assert await test_client.wait_for_indexing(document, max_wait_seconds=30)

        # Verify custom RAG behavior
        assert await test_client.test_rag_retrievability(document)
```

### Performance Profiling

Enable detailed performance profiling:

```bash
# Run with profiling enabled
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/ \
  --profile \
  --profile-svg \
  -v

# Profile specific performance bottlenecks
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/test_performance.py::TestLatencyBenchmarks \
  --benchmark-histogram \
  --benchmark-save=detailed_profile
```

### Debugging Failed Tests

When tests fail, use these debugging approaches:

```bash
# Run with maximum verbosity and no capture
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/ -v -s --tb=long --no-header

# Debug specific test with PDB
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/test_happy_path.py::test_complete_pipeline_single_document \
  --pdb --capture=no

# Check service logs
docker compose -f deployment/docker-compose.integration-tests.yml logs archon-server-test
docker compose -f deployment/docker-compose.integration-tests.yml logs archon-mcp-test

# Inspect database state
docker compose -f deployment/docker-compose.integration-tests.yml exec postgres-test \
  psql -U test_user -d archon_test -c "SELECT * FROM projects ORDER BY created_at DESC LIMIT 5;"
```

### Load Testing

Run load tests to validate system limits:

```bash
# Stress test with high concurrency
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/test_performance.py::TestScalabilityAndStress \
  --stress-mode \
  --workers=10 \
  --duration=300

# Memory leak detection
docker compose -f deployment/docker-compose.integration-tests.yml run --rm test-runner \
  pytest tests/integration/test_performance.py::TestResourceUtilization::test_memory_usage_patterns \
  --memory-profiler \
  --iterations=100
```

## 🔄 CI/CD Integration

### GitHub Actions

The test suite integrates with GitHub Actions for automated testing:

```yaml
# .github/workflows/integration-tests.yml
name: MCP Integration Tests
on: [push, pull_request]
jobs:
  integration_tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Integration Tests
        run: make workflow-integration-ci
```

Features:
- 🔄 Automatic test execution on PR and push
- 📊 Test result reporting and artifact collection
- 🔧 Configurable test suite selection (fast/full/custom)
- 📅 Scheduled daily test runs for environment drift detection
- 🚨 Automatic issue creation for scheduled test failures

### Local CI Simulation

Test the CI workflow locally:

```bash
# Simulate GitHub Actions workflow
make workflow-integration-ci

# Test specific scenarios
./scripts/run-integration-tests.sh --ci full

# Generate CI-style reports
./scripts/run-integration-tests.sh --ci --no-cleanup full
```

## 🐛 Troubleshooting

### Common Issues

#### Services Not Ready

```bash
# Symptoms: Health check failures, connection errors
# Solution: Increase startup wait time
docker compose -f deployment/docker-compose.integration-tests.yml up -d
sleep 60  # Wait longer for services
make test-integration-health
```

#### Port Conflicts

```bash
# Symptoms: "Port already in use" errors
# Solution: Check for conflicting services
netstat -tuln | grep -E "18(051|053|181)"

# Stop conflicting services or change ports in deployment/docker-compose.integration-tests.yml
```

#### Disk Space Issues

```bash
# Symptoms: "No space left on device"
# Solution: Clean up Docker resources
docker system prune -f --volumes
docker volume prune -f

# Monitor disk usage during tests
df -h
```

#### Memory Issues

```bash
# Symptoms: Tests killed by OOM, container crashes
# Solution: Reduce parallel workers or increase Docker memory
export PYTEST_PARALLEL_WORKERS=1
./scripts/run-integration-tests.sh --parallel-jobs 1 fast
```

#### Network Issues

```bash
# Symptoms: Service discovery failures, DNS resolution issues
# Solution: Restart Docker network
docker compose -f deployment/docker-compose.integration-tests.yml down
docker network prune -f
docker compose -f deployment/docker-compose.integration-tests.yml up -d
```

### Debug Mode

Enable comprehensive debugging:

```bash
# Full debug mode with detailed logging
./scripts/run-integration-tests.sh --verbose --no-cleanup full 2>&1 | tee debug.log

# Inspect service states
docker compose -f deployment/docker-compose.integration-tests.yml ps
docker compose -f deployment/docker-compose.integration-tests.yml top

# Check resource utilization
docker stats
```

### Log Analysis

Analyze service logs for issues:

```bash
# Check specific service logs
docker compose -f deployment/docker-compose.integration-tests.yml logs archon-server-test | grep ERROR
docker compose -f deployment/docker-compose.integration-tests.yml logs archon-mcp-test | grep -i exception

# Monitor logs in real-time during test execution
docker compose -f deployment/docker-compose.integration-tests.yml logs -f &
./scripts/run-integration-tests.sh fast
```

## 📚 Reference

### Test Fixtures

Key test fixtures available in all tests:

- `test_client: IntegrationTestClient` - High-level test operations
- `test_project: TestProject` - Pre-created test project
- `performance_thresholds: Dict` - Performance expectations
- `service_health: ServiceHealthChecker` - Service monitoring utilities

### Utility Functions

Helper functions for custom tests:

```python
# Test data creation
async def create_test_document(project, title, content)
async def create_large_test_document(project, size_mb)
async def create_test_documents_bulk(project, count)

# Validation utilities
async def wait_for_indexing(document, max_wait_seconds)
async def verify_cross_service_consistency(document)
async def check_service_health(services)

# Performance measurement
@measure_execution_time
@benchmark_memory_usage
@track_resource_utilization
```

### Performance Targets

Expected performance benchmarks:

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Document Creation | <2s | 95th percentile |
| Bridge Synchronization | <5s | Average |
| RAG Query Response | <1s | 95th percentile |
| End-to-End Pipeline | <30s | Maximum (SLA) |
| Document Throughput | >10/min | Sustained rate |
| Concurrent Queries | >50/min | Peak capacity |

### Service Dependencies

Understanding the service dependency chain:

```
Test Suite
    ├── Archon Server (18181) - Project/document management
    ├── Archon MCP (18051) - MCP protocol handling
    ├── Intelligence Service (18053) - Document processing
    ├── Bridge Service (18054) - Cross-service synchronization
    ├── Search Service (18055) - Enhanced search capabilities
    ├── PostgreSQL (15432) - Primary data storage
    ├── Qdrant (16333) - Vector search database
    └── Memgraph (17687) - Knowledge graph database
```

Each service must be healthy for tests to pass. Use `make test-integration-health` to verify all services are operational.

---

## 🤝 Contributing

### Adding New Tests

1. **Choose the appropriate test category** based on what you're testing
2. **Follow existing patterns** for consistency
3. **Use provided fixtures** for common operations
4. **Add appropriate markers** for test categorization
5. **Include performance assertions** where relevant
6. **Update documentation** for new test scenarios

### Test Development Guidelines

- ✅ **Write descriptive test names** that explain the scenario
- ✅ **Use async/await** for all test operations
- ✅ **Include timeout assertions** for SLA compliance
- ✅ **Clean up test data** using provided utilities
- ✅ **Add appropriate error handling** for flaky operations
- ✅ **Document complex test logic** with inline comments

### Performance Test Guidelines

- ⚡ **Set realistic thresholds** based on actual system capabilities
- ⚡ **Use statistical measurements** (median, 95th percentile)
- ⚡ **Account for system variance** in assertions
- ⚡ **Measure resource utilization** alongside timing
- ⚡ **Test under realistic load** conditions

For detailed contribution guidelines, see the main project CONTRIBUTING.md.

---

**Built with ❤️ for reliable MCP document indexing pipeline validation**
