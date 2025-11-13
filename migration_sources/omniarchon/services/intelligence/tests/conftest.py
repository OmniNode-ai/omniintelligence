"""
Shared test fixtures for Phase 5 Intelligence Features
"""

# CRITICAL: Manipulate sys.path BEFORE any imports to override parent monorepo paths
# The parent omniarchon directory (/Volumes/PRO-G40/Code/omniarchon) has its own
# services/ directory that conflicts with our src/services/ directory.
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
src_path = str(repo_root / "src")
root_path = str(repo_root)
models_path = str(repo_root / "models")
parent_omniarchon_path = str(repo_root.parent.parent)

# Remove parent omniarchon path if present
while parent_omniarchon_path in sys.path:
    sys.path.remove(parent_omniarchon_path)

# Ensure paths are in correct order: src first, then root
# This prioritizes new src/ structure over legacy root-level modules
# while still allowing root-level imports (extractors, models) to work
# Remove both absolute and relative versions of these paths
import os

paths_to_remove = [src_path, root_path]
# Also check for relative path versions
for path_str in paths_to_remove[:]:
    for sys_path in sys.path[:]:
        if os.path.abspath(sys_path) == os.path.abspath(path_str):
            sys.path.remove(sys_path)

# Add src first (position 0), then root (position 1)
# This way src/models/external_api is found before root/models/
sys.path.insert(0, src_path)
sys.path.insert(1, root_path)

# DEBUG: Print sys.path to verify
import os

if os.getenv("DEBUG_SYSPATH"):
    print(f"\n[conftest.py] sys.path after manipulation:")
    for i, p in enumerate(sys.path[:5]):
        print(f"  [{i}] {p}")

    # Also check which config module would be imported
    try:
        import config

        print(f"\n[conftest.py] config module loaded from: {config.__file__}")
        print(f"[conftest.py] config.__path__: {config.__path__}")
        print(
            f"[conftest.py] Has http_client_config: {hasattr(config, 'http_client_config')}"
        )
    except Exception as e:
        print(f"\n[conftest.py] Could not import config: {e}")

# Now import other modules
from datetime import datetime, timezone

import pytest

# ============================================================================
# Prometheus Metrics Registry Cleanup
# ============================================================================


@pytest.fixture(autouse=True, scope="function")
def clear_prometheus_registry(request):
    """
    Clear Prometheus registry after each test to prevent metric re-registration conflicts.

    This prevents "Duplicated timeseries in CollectorRegistry" errors
    that occur when modules with module-level metrics are imported
    multiple times across different tests.

    Strategy:
    - Skip registry clearing for tests that explicitly test metrics (they need persistent state)
    - For all other tests, clear metrics AFTER the test completes
    - This prevents duplicate registration errors on next test

    autouse=True ensures this runs for ALL tests automatically.
    """
    import sys

    from prometheus_client import REGISTRY

    # Helper function to safely unregister collectors
    def safe_clear_registry():
        """Clear all application metrics, keeping only Python default collectors."""
        collectors_to_remove = []
        for collector in list(REGISTRY._collector_to_names.keys()):
            # Keep the default Python GC and info collectors
            collector_names = REGISTRY._collector_to_names.get(collector, set())
            # Only remove if it's an application metric (not a Python default metric)
            if not any(
                name.startswith(("python_gc_", "python_info", "process_"))
                for name in collector_names
            ):
                collectors_to_remove.append(collector)

        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                # Ignore errors during cleanup
                pass

    # Check if this is a monitoring metrics test (skip clearing for these)
    test_file = str(request.fspath)
    is_monitoring_test = "test_monitoring" in test_file

    # For non-monitoring tests, clear BEFORE to ensure clean state
    if not is_monitoring_test:
        safe_clear_registry()
        # Also reload kafka_consumer module to get fresh metrics
        modules_to_reload = [
            key
            for key in list(sys.modules.keys())
            if "kafka_consumer" in key and "src" in key
        ]
        for module_name in modules_to_reload:
            sys.modules.pop(module_name, None)

    yield  # Run the test

    # For non-monitoring tests, clear AFTER test
    # For monitoring tests, skip cleanup to preserve metrics between tests
    if not is_monitoring_test:
        safe_clear_registry()


# ============================================================================
# Pattern Learning Fixtures
# ============================================================================


@pytest.fixture
def sample_onex_code():
    """Sample ONEX-compliant code for pattern extraction"""
    return '''
class NodeValidationEffect(NodeBase, CachingMixin):
    """Effect node for code validation."""

    def __init__(self, container: Container[DB]):
        self.db = container.resolve(DB)

    async def execute_effect(self, contract: Contract) -> Dict[str, Any]:
        """Execute validation effect."""
        if not contract or not contract.payload:
            raise ValueError("Invalid contract")

        try:
            logger.info("Executing validation",
                extra={"correlation_id": contract.id})
            result = await self._validate(contract.payload)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise
'''


@pytest.fixture
def validation_result_success():
    """Sample successful validation result"""
    return {
        "is_valid": True,
        "quality_score": 0.92,
        "onex_compliance_score": 0.95,
        "violations": [],
        "warnings": [],
        "node_type": "effect",
    }


@pytest.fixture
def validation_result_failure():
    """Sample failed validation result"""
    return {
        "is_valid": False,
        "quality_score": 0.45,
        "onex_compliance_score": 0.50,
        "violations": ["Missing error handling", "No type hints"],
        "warnings": ["Missing docstring"],
        "node_type": "compute",
    }


# ============================================================================
# Quality Intelligence Fixtures
# ============================================================================


@pytest.fixture
def quality_snapshot():
    """Sample quality snapshot"""
    return {
        "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        "project_id": "test_project",
        "file_path": "src/test.py",
        "quality_score": 0.85,
        "compliance_score": 0.90,
        "violations": [],
        "warnings": ["Missing docstring"],
        "correlation_id": "test_correlation_123",
    }


@pytest.fixture
def quality_rule_config():
    """Sample custom quality rule configuration"""
    return {
        "rule_id": "test_rule_001",
        "description": "Test rule for validation",
        "rule_type": "pattern",
        "severity": "warning",
        "pattern": r"def\s+\w+\s*\(",
        "weight": 0.1,
        "enabled": True,
    }


# ============================================================================
# Performance Intelligence Fixtures
# ============================================================================


@pytest.fixture
def performance_measurements():
    """Sample performance measurements with fixed, deterministic timestamps"""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        {"operation": "test_op", "duration_ms": 100.0, "timestamp": base_time},
        {
            "operation": "test_op",
            "duration_ms": 110.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 1, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 105.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 2, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 95.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 3, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 100.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 4, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 115.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 5, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 90.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 6, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 105.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 7, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 100.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 8, tzinfo=timezone.utc),
        },
        {
            "operation": "test_op",
            "duration_ms": 110.0,
            "timestamp": datetime(2025, 1, 15, 12, 0, 9, tzinfo=timezone.utc),
        },
    ]


@pytest.fixture
def baseline_stats():
    """Sample baseline statistics"""
    return {
        "p50": 105.0,
        "p95": 115.0,
        "p99": 115.0,
        "mean": 103.0,
        "std_dev": 7.5,
        "sample_size": 10,
    }


# ============================================================================
# Common Utilities
# ============================================================================


@pytest.fixture
def correlation_id():
    """Generate test correlation ID"""
    return "test_correlation_abc123"


@pytest.fixture
def project_id():
    """Test project ID"""
    return "test_project"
