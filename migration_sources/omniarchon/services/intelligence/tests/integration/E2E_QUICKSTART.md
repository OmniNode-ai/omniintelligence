# E2E Workflow Tests - Quick Start Guide

## Prerequisites

### 1. Start Required Services
```bash
# From project root
docker compose up -d archon-bridge archon-intelligence qdrant memgraph

# Verify services are running
curl http://localhost:8053/health
curl http://localhost:8054/health
```

### 2. Install Dependencies
```bash
cd services/intelligence
poetry install
```

## Running Tests

### Run All E2E Workflows
```bash
poetry run pytest tests/integration/test_e2e_workflows.py -v -s -m e2e
```

### Run Individual Workflows

**Pattern Learning**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_complete_pattern_learning_workflow -v -s
```

**Quality Intelligence**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_quality_intelligence_workflow -v -s
```

**Performance Optimization**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_performance_optimization_workflow -v -s
```

**Pattern Traceability**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_pattern_traceability_workflow -v -s
```

**Custom Rules**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_custom_rules_workflow -v -s
```

**Freshness Management**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_freshness_management_workflow -v -s
```

**Cross-Service Coordination**:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_cross_service_workflow -v -s
```

### Run Performance Tests
```bash
poetry run pytest tests/integration/test_e2e_workflows.py::TestWorkflowPerformance -v -s
```

## Test Options

### With Coverage
```bash
poetry run pytest tests/integration/test_e2e_workflows.py -v -s --cov=src --cov-report=html
```

### Fast Tests Only (Exclude Slow)
```bash
poetry run pytest tests/integration/test_e2e_workflows.py -v -s -m "e2e and not slow"
```

### With Detailed Output
```bash
poetry run pytest tests/integration/test_e2e_workflows.py -v -s --tb=long
```

### Stop on First Failure
```bash
poetry run pytest tests/integration/test_e2e_workflows.py -v -s -x
```

## Expected Output

```
[STEP 1] Ingesting pattern: e2e_pattern_abc123
✓ Pattern ingested successfully: e2e_pattern_abc123

[STEP 2] Matching pattern against execution
✓ Pattern matched with confidence: 0.87

[STEP 3] Recording pattern success
✓ Pattern success recorded

✅ Complete pattern learning workflow PASSED
```

## Troubleshooting

### Error: "Bridge service unavailable"
**Solution**: Ensure Docker services are running:
```bash
docker compose ps
docker compose logs archon-bridge
```

### Error: "Module not found"
**Solution**: Install dependencies:
```bash
poetry install
```

### Error: "Test collection failed"
**Solution**: Use poetry run:
```bash
poetry run pytest tests/integration/test_e2e_workflows.py
```

### Slow Test Execution
**Solution**: Run services locally for faster tests:
```bash
# Start services
docker compose up -d

# Run tests with increased timeout
poetry run pytest tests/integration/test_e2e_workflows.py --timeout=60
```

## Test Structure

Each E2E test follows this pattern:

1. **Setup**: Create test data and resources
2. **Execution**: Execute workflow steps sequentially
3. **Verification**: Validate results at each step
4. **Cleanup**: Clean up test resources (handled by fixtures)

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run E2E Workflow Tests
  run: |
    docker compose up -d
    poetry run pytest tests/integration/test_e2e_workflows.py -v -m e2e
```

### GitLab CI
```yaml
test:e2e:
  script:
    - docker compose up -d
    - poetry run pytest tests/integration/test_e2e_workflows.py -v -m e2e
```

## Test Duration

| Test | Expected Duration |
|------|------------------|
| Pattern Learning | ~5-10s |
| Quality Intelligence | ~5-10s |
| Performance Optimization | ~5-10s |
| Pattern Traceability | ~5-10s |
| Custom Rules | ~5-10s |
| Freshness Management | ~10-15s |
| Cross-Service | ~10-15s |
| Performance Tests | ~10-20s |
| **Total Suite** | **~60-90s** |

## Test Coverage

- **10 test functions** across 2 test classes
- **50+ API endpoint calls** across all tests
- **100+ assertions** validating workflow steps
- **1,217 lines** of comprehensive test code

## Support

For issues or questions:
1. Check service logs: `docker compose logs archon-intelligence`
2. Verify service health: `curl http://localhost:8053/health`
3. Review test output for detailed error messages
4. Check `E2E_WORKFLOW_TESTS_SUMMARY.md` for detailed documentation

## Quick Commands Reference

```bash
# Run everything
poetry run pytest tests/integration/test_e2e_workflows.py -v -s -m e2e

# Run fast tests only
poetry run pytest tests/integration/test_e2e_workflows.py -v -s -m "e2e and not slow"

# Run with coverage
poetry run pytest tests/integration/test_e2e_workflows.py -v -s --cov=src

# Run specific workflow
poetry run pytest tests/integration/test_e2e_workflows.py::TestEndToEndWorkflows::test_complete_pattern_learning_workflow -v -s

# Run performance tests
poetry run pytest tests/integration/test_e2e_workflows.py::TestWorkflowPerformance -v -s
```
