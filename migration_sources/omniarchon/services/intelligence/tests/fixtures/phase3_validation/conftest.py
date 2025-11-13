"""
Phase 3 Validation Test Fixtures - Conftest

This module provides pytest fixtures for Phase 3 validation testing.
All fixtures are automatically discovered and made available to tests.

Fixture Categories:
- ONEX Compliant Code
- ONEX Non-Compliant Code
- Quality Gate Scenarios
- Multi-Model Consensus
- Expected Validation Results
- Quality Gate Configurations
"""

import pytest

from .compliant.compliant_contracts import (
    create_compliant_compute_contract,
    create_compliant_effect_contract,
    create_compliant_orchestrator_contract,
    create_compliant_reducer_contract,
)
from .compliant.compliant_node_compute import (
    COMPLIANT_COMPUTE_NODE_CODE,
    NodeDataTransformerCompute,
)

# Import compliant fixtures
from .compliant.compliant_node_effect import (
    COMPLIANT_EFFECT_NODE_CODE,
    NodeDatabaseWriterEffect,
)
from .compliant.compliant_node_orchestrator import (
    COMPLIANT_ORCHESTRATOR_NODE_CODE,
    NodeWorkflowCoordinatorOrchestrator,
)
from .compliant.compliant_node_reducer import (
    COMPLIANT_REDUCER_NODE_CODE,
    NodeEventAggregatorReducer,
)

# Import consensus fixtures
from .consensus.architectural_decision_scenarios import ALL_SCENARIOS
from .consensus.consensus_edge_cases import (
    ALL_EDGE_CASES,
    RESOLUTION_STRATEGIES,
)
from .non_compliant.non_compliant_contracts import (
    CONTRACT_VIOLATIONS,
)

# Import non-compliant fixtures
from .non_compliant.non_compliant_naming import (
    NAMING_VIOLATIONS,
    NON_COMPLIANT_MISSING_SUFFIX_CODE,
    NON_COMPLIANT_WRONG_CASE_CODE,
    NON_COMPLIANT_WRONG_METHOD_CODE,
    NON_COMPLIANT_WRONG_SUFFIX_CODE,
)
from .non_compliant.non_compliant_node_types import (
    NODE_TYPE_VIOLATIONS,
    NON_COMPLIANT_IO_IN_COMPUTE_CODE,
    NON_COMPLIANT_NO_TRANSACTION_CODE,
    NON_COMPLIANT_PURE_IN_EFFECT_CODE,
    NON_COMPLIANT_STATE_IN_COMPUTE_CODE,
)

# Import quality gate fixtures
from .quality_gates.low_coverage_module import (
    COVERAGE_REPORT,
    LOW_COVERAGE_STATS,
    MISSING_TESTS,
)
from .quality_gates.poor_quality_code import QUALITY_METRICS
from .quality_gates.slow_performance_code import (
    PERFORMANCE_METRICS,
    SLA_VIOLATIONS,
)
from .test_data.quality_gate_configs import (
    ALL_QUALITY_GATE_CONFIGS,
    get_gate_config,
)

# Import test data fixtures
from .test_data.validation_results import ALL_EXPECTED_RESULTS

# ============================================================================
# ONEX Compliant Code Fixtures
# ============================================================================


@pytest.fixture
def compliant_effect_node():
    """Fully compliant Effect node class."""
    return NodeDatabaseWriterEffect


@pytest.fixture
def compliant_effect_code():
    """Compliant Effect node as code string."""
    return COMPLIANT_EFFECT_NODE_CODE


@pytest.fixture
def compliant_compute_node():
    """Fully compliant Compute node class."""
    return NodeDataTransformerCompute


@pytest.fixture
def compliant_compute_code():
    """Compliant Compute node as code string."""
    return COMPLIANT_COMPUTE_NODE_CODE


@pytest.fixture
def compliant_reducer_node():
    """Fully compliant Reducer node class."""
    return NodeEventAggregatorReducer


@pytest.fixture
def compliant_reducer_code():
    """Compliant Reducer node as code string."""
    return COMPLIANT_REDUCER_NODE_CODE


@pytest.fixture
def compliant_orchestrator_node():
    """Fully compliant Orchestrator node class."""
    return NodeWorkflowCoordinatorOrchestrator


@pytest.fixture
def compliant_orchestrator_code():
    """Compliant Orchestrator node as code string."""
    return COMPLIANT_ORCHESTRATOR_NODE_CODE


@pytest.fixture
def compliant_contracts():
    """All compliant contract factory functions."""
    return {
        "effect": create_compliant_effect_contract,
        "compute": create_compliant_compute_contract,
        "reducer": create_compliant_reducer_contract,
        "orchestrator": create_compliant_orchestrator_contract,
    }


# ============================================================================
# ONEX Non-Compliant Code Fixtures
# ============================================================================


@pytest.fixture
def non_compliant_naming_violations():
    """Non-compliant naming convention examples."""
    return NAMING_VIOLATIONS


@pytest.fixture
def non_compliant_io_in_compute():
    """Non-compliant Compute node with I/O operations."""
    return NON_COMPLIANT_IO_IN_COMPUTE_CODE


@pytest.fixture
def non_compliant_state_in_compute():
    """Non-compliant Compute node with state mutations."""
    return NON_COMPLIANT_STATE_IN_COMPUTE_CODE


@pytest.fixture
def non_compliant_pure_in_effect():
    """Non-compliant Effect node with only pure computation."""
    return NON_COMPLIANT_PURE_IN_EFFECT_CODE


@pytest.fixture
def non_compliant_node_type_violations():
    """All node type violations summary."""
    return NODE_TYPE_VIOLATIONS


@pytest.fixture
def non_compliant_contract_violations():
    """All contract violations summary."""
    return CONTRACT_VIOLATIONS


# ============================================================================
# Quality Gate Fixtures
# ============================================================================


@pytest.fixture
def low_coverage_stats():
    """Low test coverage statistics."""
    return LOW_COVERAGE_STATS


@pytest.fixture
def coverage_report():
    """Simulated coverage report text."""
    return COVERAGE_REPORT


@pytest.fixture
def missing_tests():
    """List of missing test cases."""
    return MISSING_TESTS


@pytest.fixture
def quality_metrics():
    """Code quality metrics."""
    return QUALITY_METRICS


@pytest.fixture
def performance_metrics():
    """Performance metrics for slow code."""
    return PERFORMANCE_METRICS


@pytest.fixture
def sla_violations():
    """Performance SLA violations."""
    return SLA_VIOLATIONS


# ============================================================================
# Consensus Fixtures
# ============================================================================


@pytest.fixture
def architectural_decision_scenarios():
    """Architectural decision scenarios for consensus."""
    return ALL_SCENARIOS


@pytest.fixture
def consensus_edge_cases():
    """Consensus edge cases."""
    return ALL_EDGE_CASES


@pytest.fixture
def consensus_resolution_strategies():
    """Consensus resolution strategies."""
    return RESOLUTION_STRATEGIES


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def expected_validation_results():
    """Expected validation results for all scenarios."""
    return ALL_EXPECTED_RESULTS


@pytest.fixture
def quality_gate_configs():
    """All quality gate configurations."""
    return ALL_QUALITY_GATE_CONFIGS


@pytest.fixture
def default_quality_gate_config():
    """Default quality gate configuration."""
    return get_gate_config("default")


@pytest.fixture
def strict_quality_gate_config():
    """Strict quality gate configuration."""
    return get_gate_config("strict")


@pytest.fixture
def lenient_quality_gate_config():
    """Lenient quality gate configuration."""
    return get_gate_config("lenient")


@pytest.fixture
def onex_quality_gate_config():
    """ONEX-specific quality gate configuration."""
    return get_gate_config("onex")


# ============================================================================
# Helper Fixtures
# ============================================================================


@pytest.fixture
def all_compliant_nodes():
    """All compliant node types."""
    return {
        "effect": NodeDatabaseWriterEffect,
        "compute": NodeDataTransformerCompute,
        "reducer": NodeEventAggregatorReducer,
        "orchestrator": NodeWorkflowCoordinatorOrchestrator,
    }


@pytest.fixture
def all_compliant_code_strings():
    """All compliant code as strings."""
    return {
        "effect": COMPLIANT_EFFECT_NODE_CODE,
        "compute": COMPLIANT_COMPUTE_NODE_CODE,
        "reducer": COMPLIANT_REDUCER_NODE_CODE,
        "orchestrator": COMPLIANT_ORCHESTRATOR_NODE_CODE,
    }


@pytest.fixture
def all_non_compliant_code_strings():
    """All non-compliant code examples."""
    return {
        "io_in_compute": NON_COMPLIANT_IO_IN_COMPUTE_CODE,
        "state_in_compute": NON_COMPLIANT_STATE_IN_COMPUTE_CODE,
        "pure_in_effect": NON_COMPLIANT_PURE_IN_EFFECT_CODE,
        "no_transaction": NON_COMPLIANT_NO_TRANSACTION_CODE,
        "missing_suffix": NON_COMPLIANT_MISSING_SUFFIX_CODE,
        "wrong_suffix": NON_COMPLIANT_WRONG_SUFFIX_CODE,
        "wrong_case": NON_COMPLIANT_WRONG_CASE_CODE,
        "wrong_method": NON_COMPLIANT_WRONG_METHOD_CODE,
    }


@pytest.fixture
def sample_validation_request():
    """Sample validation request for testing."""
    return {
        "code": COMPLIANT_EFFECT_NODE_CODE,
        "language": "python",
        "validation_type": "onex_compliance",
        "config": get_gate_config("default"),
    }
