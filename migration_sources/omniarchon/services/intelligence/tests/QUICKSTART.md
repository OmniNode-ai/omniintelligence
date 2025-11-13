# Quick Start - Hybrid Scoring Tests

## Installation

```bash
# Navigate to intelligence service
cd /Volumes/PRO-G40/Code/Archon/services/intelligence

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov psutil

# Ensure Qdrant is running
docker compose up -d qdrant
```

## Run All Tests

```bash
./tests/run_tests.sh
```

This runs:
1. Unit tests
2. Pattern learning tests
3. Integration tests (hybrid scoring)
4. Performance benchmarks

## Run Specific Test Suites

```bash
# Integration tests only
./tests/run_tests.sh integration

# Performance benchmarks only
./tests/run_tests.sh performance

# With verbose output
./tests/run_tests.sh integration -v

# With coverage report
./tests/run_tests.sh coverage
```

## Run Individual Tests

```bash
# Specific integration test
pytest tests/integration/test_hybrid_scoring_e2e.py::TestHybridScoringE2E::test_complete_hybrid_scoring_flow -v -s

# All integration tests
pytest tests/integration/ -v

# Specific benchmark
python tests/performance/benchmark_hybrid_scoring.py
```

## Expected Results

### Integration Tests

```
✓ Complete Hybrid Scoring Flow: ~2-4s
✓ Cache Effectiveness: 2-6x speedup
✓ Fallback to Vector-only: No errors
✓ Performance Under Load: 100 requests in <10s
✓ Hybrid Accuracy: >10% improvement
```

### Performance Benchmarks

```
✓ Cold cache: <5s
✓ Warm cache: <1s
✓ Throughput: ≥10 req/s
✓ Vector search: <100ms
✓ P99 latency: <3s
✓ Pipeline E2E: <2s
```

## Troubleshooting

### Qdrant not running

```bash
# Check status
curl http://localhost:6333/health

# Start Qdrant
docker compose up -d qdrant

# Check logs
docker compose logs qdrant
```

### Test failures

```bash
# Run with full traceback
pytest tests/integration/ -v -s --tb=long

# Run with debugging
pytest tests/integration/ -v -s --pdb
```

### Performance issues

```bash
# Profile tests
python -m cProfile -o profile.stats tests/performance/benchmark_hybrid_scoring.py

# View profile
python -m pstats profile.stats
```

## Next Steps

1. Review test output and metrics
2. Check coverage report: `htmlcov/index.html` (if ran with coverage)
3. Compare benchmarks with baseline
4. Investigate any failures or performance regressions

## Documentation

- Integration Tests: `tests/integration/README.md`
- Performance Benchmarks: `tests/performance/README.md`
- Completion Report: `/docs/TRACK_3_2_AGENT_6_COMPLETION.md`
