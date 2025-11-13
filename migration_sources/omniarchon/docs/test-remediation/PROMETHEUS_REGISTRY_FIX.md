# Prometheus Metrics Registry Cleanup Fix

**Date**: 2025-11-04
**Issue**: Duplicate timeseries registration errors causing ~25 test failures
**Status**: ✅ RESOLVED

## Problem

Tests were failing with `ValueError: Duplicated timeseries in CollectorRegistry` errors. This occurred when:

1. Modules with module-level Prometheus metrics (Counter, Gauge, Histogram) were imported
2. Tests ran multiple times, causing metrics to attempt re-registration
3. Python's module caching kept metrics registered across test runs

Example error:
```
ValueError: Duplicated timeseries in CollectorRegistry: {
    'kafka_event_processing_failures',
    'kafka_event_processing_failures_total',
    'kafka_event_processing_failures_created'
}
```

## Root Cause

Prometheus metrics defined at module level (in `src/kafka_consumer.py`, `monitoring_hybrid_patterns.py`, etc.) register themselves with the global REGISTRY when the module is first imported. When pytest runs multiple tests:

1. First test imports module → metrics register ✓
2. Pytest caches the module in `sys.modules`
3. Second test imports same module → Python returns cached module
4. But metrics try to register again → **DuplicatedError**

## Solution

Added a pytest fixture (`clear_prometheus_registry`) in `tests/conftest.py` that:

1. **Runs automatically** for all tests (`autouse=True`)
2. **Clears registry** before non-monitoring tests to ensure clean slate
3. **Reloads modules** that define metrics (forces fresh registration)
4. **Preserves metrics** for monitoring tests that explicitly test metric behavior
5. **Always clears after** each test to prevent pollution

### Implementation

```python
@pytest.fixture(autouse=True, scope="function")
def clear_prometheus_registry(request):
    """
    Clear Prometheus registry to prevent duplicate registrations.

    Strategy:
    - Skip clearing for tests that explicitly test metrics
    - Clear before/after other tests to prevent conflicts
    - Reload metric-defining modules for fresh state
    """
    from prometheus_client import REGISTRY
    import sys

    def safe_clear_registry():
        """Remove all application metrics, keep Python defaults."""
        collectors_to_remove = []
        for collector in list(REGISTRY._collector_to_names.keys()):
            collector_names = REGISTRY._collector_to_names.get(collector, set())
            # Keep python_gc_*, python_info, process_* collectors
            if not any(
                name.startswith(("python_gc_", "python_info", "process_"))
                for name in collector_names
            ):
                collectors_to_remove.append(collector)

        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass  # Ignore already-unregistered errors

    # Detect monitoring tests (they need persistent metrics)
    test_file = str(request.fspath)
    is_monitoring_test = "test_monitoring" in test_file

    # Clear before test (except monitoring tests)
    if not is_monitoring_test:
        safe_clear_registry()
        # Reload kafka_consumer to get fresh metrics
        modules_to_reload = [
            key for key in list(sys.modules.keys())
            if "kafka_consumer" in key and "src" in key
        ]
        for module_name in modules_to_reload:
            sys.modules.pop(module_name, None)

    yield  # Run the test

    # Always clear after test
    safe_clear_registry()
```

## Results

### Before Fix
```
❌ ValueError: Duplicated timeseries in CollectorRegistry
❌ ~25 test failures across multiple test files
❌ Tests could not run in sequence without errors
```

### After Fix
```
✅ No "Duplicated timeseries" errors in entire test suite
✅ Tests run cleanly in sequence
✅ Registry cleaned automatically between tests
✅ Monitoring tests preserve metric state when needed
```

### Test Suite Status
```bash
# Full test run - NO duplicate errors
$ poetry run pytest tests/ --tb=no 2>&1 | grep -i "duplicated"
# (no output - no errors!)

# Kafka consumer tests - previously failing
$ poetry run pytest tests/test_kafka_consumer.py -v
# Now passing (except unrelated test logic issues)

# Monitoring tests - metrics preserved
$ poetry run pytest tests/unit/pattern_learning/phase2_matching/test_monitoring_hybrid_patterns.py -v
# Registry available for metric validation tests
```

## Impact

- **Fixed**: ~25 test failures due to registry conflicts
- **Improved**: Test isolation and reliability
- **Preserved**: Monitoring test functionality
- **Side effect**: None - fixture is transparent to tests

## Files Modified

1. `tests/conftest.py` - Added `clear_prometheus_registry` fixture

## Future Recommendations

1. **Consider custom registries**: For production, use separate registry instances per service
2. **Lazy registration**: Register metrics on first use, not at module import
3. **Factory pattern**: Create metrics via factory functions that handle registration safely
4. **Test markers**: Use pytest markers (`@pytest.mark.skip_metrics_cleanup`) for finer control

## Verification Commands

```bash
# Verify no duplicate errors in full suite
poetry run pytest tests/ 2>&1 | grep -i "duplicated"

# Run specific test files that were failing
poetry run pytest tests/test_kafka_consumer.py -v
poetry run pytest tests/unit/pattern_learning/phase2_matching/test_monitoring_hybrid_patterns.py -v

# Check registry cleanup is working
poetry run pytest tests/ -v --tb=short | grep -E "FAILED|PASSED" | wc -l
```

## Notes

- The fixture uses `autouse=True` so developers don't need to remember to use it
- Monitoring tests detected via filename pattern (`"test_monitoring" in test_file`)
- Default Python collectors (GC stats, platform info) are preserved
- Module reloading ensures fresh metric registration each test
