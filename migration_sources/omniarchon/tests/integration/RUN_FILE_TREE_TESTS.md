# Quick Reference: Running File Tree Integration Tests

**Quick Start** | **Last Updated**: 2025-11-07

## One-Command Test Execution

```bash
# Fast tests only (~5 minutes)
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_cross_service.py -v -m "not slow"

# All tests including performance (~20 minutes)
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_large_repository.py \
       tests/integration/test_cross_service.py -v

# Performance tests only (~15 minutes)
pytest tests/integration/test_large_repository.py -v
```

## Prerequisites Checklist

Before running tests, verify:

```bash
# 1. Services are running
docker ps | grep -E "(archon-intelligence|archon-bridge|archon-search|memgraph|qdrant)"

# 2. Services are healthy
curl http://localhost:8053/health  # Intelligence
curl http://localhost:8054/health  # Bridge
curl http://localhost:8055/health  # Search

# 3. Memgraph is accessible
docker exec archon-memgraph mg_client -h localhost -p 7687 -u '' -p '' -e "RETURN 1;"

# 4. Qdrant is accessible
curl http://localhost:6333/collections

# 5. Kafka is accessible
docker exec omninode-bridge-redpanda rpk cluster info
```

If any service is not running:
```bash
docker compose up -d
sleep 60  # Wait for services to fully start
```

## Test Categories

### 1. End-to-End Tests (`test_e2e_file_indexing.py`)

**What it tests**: Complete file indexing workflow

**Duration**: ~2-5 minutes

**Command**:
```bash
pytest tests/integration/test_e2e_file_indexing.py -v
```

**Tests included**:
- ✅ Full file indexing pipeline (3 files)
- ✅ Entity linking (FILE → ENTITY)
- ✅ Import resolution accuracy
- ✅ Directory hierarchy correctness
- ✅ Orphan detection accuracy
- ✅ Tree visualization completeness

### 2. Performance Tests (`test_large_repository.py`)

**What it tests**: Indexing performance at scale

**Duration**: ~10-20 minutes

**Command**:
```bash
pytest tests/integration/test_large_repository.py -v
```

**Tests included**:
- ✅ Large repository indexing (1000 files)
- ✅ Query performance at scale
- ✅ Orphan detection at scale (200 files)
- ✅ Incremental updates (50 files)
- ✅ Memory usage monitoring (500 files)

**Note**: These tests generate temporary files and may consume significant resources.

### 3. Cross-Service Tests (`test_cross_service.py`)

**What it tests**: Service interaction and consistency

**Duration**: ~5-10 minutes

**Command**:
```bash
pytest tests/integration/test_cross_service.py -v
```

**Tests included**:
- ✅ All services healthy
- ✅ Intelligence → Search integration
- ✅ Bridge → Intelligence event flow
- ✅ Memgraph ↔ Qdrant consistency
- ✅ API endpoint integration
- ✅ Event-driven workflow

## Specific Test Execution

### Run a Single Test

```bash
# Run only the full pipeline test
pytest tests/integration/test_e2e_file_indexing.py::test_full_file_indexing_pipeline -v

# Run only orphan detection test
pytest tests/integration/test_e2e_file_indexing.py::test_orphan_detection_accuracy -v

# Run only large repo indexing
pytest tests/integration/test_large_repository.py::test_large_repository_indexing -v
```

### Run Tests by Marker

```bash
# Run all non-slow tests
pytest tests/integration/ -v -m "not slow"

# Run only slow tests
pytest tests/integration/ -v -m slow

# Run async tests
pytest tests/integration/ -v -m asyncio
```

### Run with Different Verbosity

```bash
# Standard verbosity
pytest tests/integration/test_e2e_file_indexing.py -v

# Maximum verbosity (shows all details)
pytest tests/integration/test_e2e_file_indexing.py -vv -s

# Quiet mode (only show failures)
pytest tests/integration/test_e2e_file_indexing.py -q
```

## Common Options

### Parallel Execution (Faster)

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest tests/integration/test_e2e_file_indexing.py -v -n 4

# Run all file tree tests in parallel
pytest tests/integration/test_*file*.py tests/integration/test_*cross*.py -v -n 2
```

### Stop on First Failure

```bash
pytest tests/integration/ -v -x  # Stop after first failure
pytest tests/integration/ -v --maxfail=3  # Stop after 3 failures
```

### Show Test Durations

```bash
pytest tests/integration/ -v --durations=10  # Show 10 slowest tests
pytest tests/integration/ -v --durations=0   # Show all test durations
```

### Capture Logs

```bash
# Show logs during test execution
pytest tests/integration/test_e2e_file_indexing.py -v --log-cli-level=INFO

# Save logs to file
pytest tests/integration/ -v --log-file=test_run.log --log-file-level=DEBUG

# Show logs only for failures
pytest tests/integration/ -v --log-cli-level=ERROR
```

## Test Results

### Successful Run

Expected output:
```
tests/integration/test_e2e_file_indexing.py::test_full_file_indexing_pipeline PASSED
tests/integration/test_e2e_file_indexing.py::test_file_node_entity_linking PASSED
tests/integration/test_e2e_file_indexing.py::test_import_resolution_accuracy PASSED
tests/integration/test_e2e_file_indexing.py::test_directory_hierarchy_correctness PASSED
tests/integration/test_e2e_file_indexing.py::test_orphan_detection_accuracy PASSED
tests/integration/test_e2e_file_indexing.py::test_tree_visualization_completeness PASSED

====== 6 passed in 120.45s ======
```

### Failed Run

If tests fail, check:
1. Are all services running? (`docker ps`)
2. Are services healthy? (`curl http://localhost:8053/health`)
3. Is Memgraph accessible? (see prerequisites)
4. Check service logs: `docker logs archon-intelligence`

## Debugging Failed Tests

### Show Full Traceback

```bash
pytest tests/integration/test_e2e_file_indexing.py -v --tb=long
```

### Run with PDB (Python Debugger)

```bash
pytest tests/integration/test_e2e_file_indexing.py::test_full_file_indexing_pipeline --pdb
```

### Check Service Logs

```bash
# Intelligence service logs
docker logs archon-intelligence --tail 100

# Bridge service logs
docker logs archon-bridge --tail 100

# Search service logs
docker logs archon-search --tail 100

# Memgraph logs
docker logs archon-memgraph --tail 100

# All service logs together
docker compose logs --tail=50 archon-intelligence archon-bridge archon-search
```

### Manual Cleanup

If tests fail and leave test data:

```bash
# Clean up Memgraph test data
docker exec archon-memgraph mg_client -h localhost -p 7687 -u '' -p '' -e "
  MATCH (p:PROJECT)
  WHERE p.name STARTS WITH 'test_'
  OPTIONAL MATCH (p)-[:CONTAINS*]->(n)
  DETACH DELETE p, n;
"

# Clean up generated test repositories
rm -rf tests/fixtures/test_repo_large*
```

## Environment Variables

Override test behavior with environment variables:

```bash
# Service URLs
export INTELLIGENCE_URL=http://localhost:8053
export BRIDGE_URL=http://localhost:8054
export SEARCH_URL=http://localhost:8055
export MEMGRAPH_URI=bolt://localhost:7687
export QDRANT_URL=http://localhost:6333
export KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092

# Test configuration
export TEST_TIMEOUT=1800  # Maximum test time (seconds)

# Run tests
pytest tests/integration/ -v
```

## Performance Benchmarking

### Run with Timing

```bash
# Show test durations
pytest tests/integration/test_large_repository.py -v --durations=0

# Run with benchmark plugin
pip install pytest-benchmark
pytest tests/integration/test_large_repository.py -v --benchmark-only
```

### Monitor Resources

```bash
# Open another terminal and monitor Docker stats
docker stats archon-intelligence archon-bridge archon-search archon-memgraph

# Monitor system resources
top -o MEM  # macOS
htop        # Linux
```

## CI/CD Testing

### Test Like CI

```bash
# Run tests with CI-like settings
pytest tests/integration/ -v --tb=short --maxfail=1 --junit-xml=test-results.xml

# Generate HTML report
pip install pytest-html
pytest tests/integration/ -v --html=test-report.html --self-contained-html
```

### Test Subset for Pre-commit

```bash
# Fast tests only (for pre-commit hook)
pytest tests/integration/test_e2e_file_indexing.py \
       tests/integration/test_cross_service.py \
       -v -m "not slow" --tb=short -x
```

## Useful Aliases

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Fast file tree tests
alias test-file-tree-fast='pytest tests/integration/test_e2e_file_indexing.py tests/integration/test_cross_service.py -v -m "not slow"'

# All file tree tests
alias test-file-tree-all='pytest tests/integration/test_e2e_file_indexing.py tests/integration/test_large_repository.py tests/integration/test_cross_service.py -v'

# Performance tests only
alias test-file-tree-perf='pytest tests/integration/test_large_repository.py -v'

# Single test with full output
alias test-file-tree-debug='pytest -vv -s --tb=long --log-cli-level=DEBUG'
```

## Test Development

### Run Tests While Developing

```bash
# Watch mode (re-run on file changes)
pip install pytest-watch
ptw tests/integration/test_e2e_file_indexing.py -- -v

# Run only last failed tests
pytest tests/integration/ -v --lf

# Run only last failed, then all
pytest tests/integration/ -v --lf --ff
```

### Coverage Analysis

```bash
# Install coverage
pip install pytest-cov

# Run with coverage
pytest tests/integration/ -v --cov=scripts --cov=services --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | `docker compose up -d && sleep 60` |
| Test timeout | Increase `timeout` parameter in tests |
| Memory error | Reduce file count in large repo tests |
| Memgraph unavailable | `docker compose restart archon-memgraph` |
| Kafka events not processed | Check `docker logs archon-kafka-consumer` |
| Tests leave data behind | Run manual cleanup (see Debugging section) |

## Getting Help

1. **Check Documentation**: `tests/integration/FILE_TREE_INTEGRATION_TESTS.md`
2. **View Test Code**: Tests are well-commented with docstrings
3. **Check Service Logs**: `docker compose logs <service-name>`
4. **Run with Debug**: `pytest -vv -s --tb=long --log-cli-level=DEBUG`
5. **File Issue**: Include full test output and service logs

---

**Quick Reference Version**: 1.0
**Last Updated**: 2025-11-07
**For Full Documentation**: See `FILE_TREE_INTEGRATION_TESTS.md`
