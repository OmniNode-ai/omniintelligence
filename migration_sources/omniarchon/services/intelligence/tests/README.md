# Intelligence Service Test Suite

## Running Tests

### Quick Start
```bash
# Run all Phase 5 tests (recommended)
./run_phase5_tests.sh

# Run all tests
pytest -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run with HTML coverage report
pytest --cov=src --cov-report=html
```

### Test Markers

Tests are organized with markers for selective execution:

| Marker | Description | Example |
|--------|-------------|---------|
| `unit` | Unit tests | `pytest -m unit` |
| `integration` | Integration tests | `pytest -m integration` |
| `phase5` | Phase 5 intelligence features | `pytest -m phase5` |
| `pattern_learning` | Pattern learning tests | `pytest -m pattern_learning` |
| `quality_intelligence` | Quality intelligence tests | `pytest -m quality_intelligence` |
| `performance_intelligence` | Performance tests | `pytest -m performance_intelligence` |
| `slow` | Slow running tests (>5s) | `pytest -m "not slow"` |

### Common Test Commands

```bash
# Fast test suite (exclude slow tests)
pytest -m "not slow" -v

# Pattern learning only
pytest -m pattern_learning -v

# All Phase 5 except slow tests
pytest -m "phase5 and not slow" -v

# Integration tests for quality intelligence
pytest -m "integration and quality_intelligence" -v

# Specific test file
pytest tests/unit/pattern_learning/phase4_traceability/test_feedback_loop_orchestrator.py -v

# Specific test function
pytest tests/unit/pattern_learning/phase4_traceability/test_feedback_loop_orchestrator.py::TestFeedbackLoopOrchestrator::test_full_feedback_cycle -v

# Run with stdout output (see print statements)
pytest -v -s

# Run failed tests only
pytest --lf -v

# Run last failed, then all
pytest --lf --ff -v
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── unit/                    # Unit tests (isolated, fast)
│   └── pattern_learning/    # Pattern learning unit tests
│       ├── phase2_pattern_matching/
│       ├── phase3_validation/
│       └── phase4_traceability/
├── services/                # Service layer tests
│   ├── performance/         # Performance service tests
│   └── quality/             # Quality service tests
├── api/                     # API endpoint tests
└── integration/             # Integration tests (cross-service)
```

## Coverage Targets

- **Overall**: ≥70% (Current: 72%)
- **Critical paths**: ≥90%
- **New code**: ≥80%

### View Coverage Report

```bash
# Terminal report
pytest --cov=src --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Writing Tests

### Test Structure

```python
import pytest
from src.services.pattern_learning.phase4_traceability.feedback_loop_orchestrator import FeedbackLoopOrchestrator

@pytest.mark.unit
@pytest.mark.pattern_learning
@pytest.mark.phase5
async def test_example_functionality():
    """Test description following AAA pattern."""
    # Arrange: Set up test data and dependencies
    orchestrator = FeedbackLoopOrchestrator()

    # Act: Execute the functionality being tested
    result = await orchestrator.process_feedback(...)

    # Assert: Verify expected outcomes
    assert result.success is True
    assert result.data["pattern_id"] is not None
```

### Marker Guidelines

Apply markers based on test characteristics:

```python
# Unit test: Tests single function/class in isolation
@pytest.mark.unit

# Integration test: Tests multiple services working together
@pytest.mark.integration

# Phase 5 feature: Part of Phase 5 intelligence features
@pytest.mark.phase5

# Slow test: Takes >5 seconds to complete
@pytest.mark.slow

# Feature-specific: Pattern learning, quality, or performance
@pytest.mark.pattern_learning
@pytest.mark.quality_intelligence
@pytest.mark.performance_intelligence
```

### Using Fixtures

```python
@pytest.fixture
async def feedback_orchestrator():
    """Provide configured FeedbackLoopOrchestrator instance."""
    orchestrator = FeedbackLoopOrchestrator()
    await orchestrator.initialize()
    yield orchestrator
    await orchestrator.cleanup()

@pytest.mark.unit
async def test_with_fixture(feedback_orchestrator):
    """Example using fixture."""
    result = await feedback_orchestrator.process_feedback(...)
    assert result.success is True
```

## Continuous Integration

Tests run automatically on:
- Pull request creation
- Push to feature branches
- Pre-merge validation

CI pipeline runs:
```bash
pytest -m "not slow" --cov=src --cov-report=xml
```

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Ensure you're in the correct directory
cd services/intelligence

# Install dependencies
poetry install
```

**Async test errors:**
```bash
# Ensure pytest-asyncio is installed
poetry add --dev pytest-asyncio

# Check pytest.ini has asyncio_mode = auto
```

**Coverage missing:**
```bash
# Ensure coverage plugin is installed
poetry add --dev pytest-cov
```

**Database connection errors:**
```bash
# Ensure test environment variables are set
export SUPABASE_URL="test_url"
export SUPABASE_SERVICE_KEY="test_key"

# Or use pytest fixtures with mocked connections
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- Project-specific: `/services/intelligence/run_phase5_tests.sh`
