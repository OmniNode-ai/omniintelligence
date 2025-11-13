"""
Example Test File Demonstrating Phase 3 Validation Fixtures

This file shows practical examples of how to use the Phase 3 validation
fixtures in real tests.

Run this file:
    pytest tests/fixtures/phase3_validation/example_test.py -v
"""

import pytest

# ============================================================================
# Example 1: Testing ONEX Compliant Nodes
# ============================================================================


def test_compliant_effect_node_example(compliant_effect_node):
    """Example: Test a compliant Effect node."""
    # The fixture provides the class
    node_class = compliant_effect_node

    # Verify it's the correct class
    assert node_class.__name__ == "NodeDatabaseWriterEffect"

    # Verify it has the correct method
    assert hasattr(node_class, "execute_effect")

    # You could instantiate and test it
    # node = node_class(db_pool=mock_pool, transaction_manager=mock_tm)
    # result = await node.execute_effect(contract)
    # assert result.success is True


def test_all_compliant_nodes_example(all_compliant_nodes):
    """Example: Test all compliant node types."""
    # The fixture provides a dict of all node types
    assert "effect" in all_compliant_nodes
    assert "compute" in all_compliant_nodes
    assert "reducer" in all_compliant_nodes
    assert "orchestrator" in all_compliant_nodes

    # Verify each has correct naming
    assert all_compliant_nodes["effect"].__name__.endswith("Effect")
    assert all_compliant_nodes["compute"].__name__.endswith("Compute")
    assert all_compliant_nodes["reducer"].__name__.endswith("Reducer")
    assert all_compliant_nodes["orchestrator"].__name__.endswith("Orchestrator")


def test_compliant_code_string_example(compliant_effect_code):
    """Example: Test with code as string."""
    # The fixture provides the code as a string
    assert "class NodeDatabaseWriterEffect" in compliant_effect_code
    assert "async def execute_effect" in compliant_effect_code
    assert "ModelContractEffect" in compliant_effect_code

    # You could use this to test code parsing/validation
    # validator = ONEXValidator()
    # result = validator.validate_code(compliant_effect_code)
    # assert result.compliant is True


# ============================================================================
# Example 2: Testing ONEX Violations
# ============================================================================


def test_naming_violations_example(non_compliant_naming_violations):
    """Example: Test naming convention violations."""
    # The fixture provides a dict of all violation types
    assert "missing_suffix" in non_compliant_naming_violations
    assert "wrong_suffix" in non_compliant_naming_violations

    # Get specific violation details
    missing_suffix = non_compliant_naming_violations["missing_suffix"]
    assert missing_suffix["severity"] == "critical"
    assert missing_suffix["example"] == "NodeDatabaseWriter"
    assert missing_suffix["should_be"] == "NodeDatabaseWriterEffect"


def test_io_in_compute_violation_example(non_compliant_io_in_compute):
    """Example: Test I/O in Compute node violation."""
    # The fixture provides code with I/O in Compute node
    assert "NodeDataTransformerCompute" in non_compliant_io_in_compute
    assert "db_pool" in non_compliant_io_in_compute
    assert "fetchrow" in non_compliant_io_in_compute

    # This code should fail ONEX validation
    # validator = ONEXValidator()
    # result = validator.validate_code(non_compliant_io_in_compute)
    # assert result.compliant is False
    # assert "io_in_compute" in [v.type for v in result.violations]


def test_node_type_violations_example(non_compliant_node_type_violations):
    """Example: Test all node type violations."""
    # The fixture provides a dict of all node type violations
    violations = non_compliant_node_type_violations

    assert violations["io_in_compute"]["severity"] == "critical"
    assert "Database queries" in violations["io_in_compute"]["examples"]


# ============================================================================
# Example 3: Testing Quality Gates
# ============================================================================


def test_low_coverage_example(low_coverage_stats):
    """Example: Test with low coverage statistics."""
    # The fixture provides coverage stats
    assert low_coverage_stats["UserValidator"]["coverage_percent"] == 40.0
    assert low_coverage_stats["UserValidator"]["tested_methods"] == 2
    assert low_coverage_stats["UserValidator"]["total_methods"] == 5

    # You could test quality gate logic
    # gate = QualityGate("test_coverage", threshold=0.90)
    # result = gate.evaluate(low_coverage_stats["UserValidator"])
    # assert result.passed is False


def test_quality_metrics_example(quality_metrics):
    """Example: Test with code quality metrics."""
    # The fixture provides quality metrics
    order_processor = quality_metrics["OrderProcessor.process_order"]

    assert order_processor["cyclomatic_complexity"] == 15
    assert order_processor["nesting_depth"] == 5
    assert "complexity" in order_processor["threshold_violations"]

    # You could test quality validation
    # validator = QualityValidator(max_complexity=10)
    # result = validator.validate(order_processor)
    # assert result.passed is False


def test_performance_metrics_example(performance_metrics):
    """Example: Test with performance metrics."""
    # The fixture provides performance metrics
    list_processor = performance_metrics["ListProcessor.find_duplicates"]

    assert list_processor["time_complexity"] == "O(n²)"
    assert list_processor["should_be"] == "O(n)"
    assert list_processor["execution_time_ms"] == 1500
    assert list_processor["sla_ms"] == 100

    # This should fail performance SLA
    # gate = PerformanceGate(sla_ms=100)
    # result = gate.evaluate(list_processor)
    # assert result.passed is False


# ============================================================================
# Example 4: Testing Consensus
# ============================================================================


def test_architectural_scenarios_example(architectural_decision_scenarios):
    """Example: Test architectural decision scenarios."""
    # The fixture provides decision scenarios
    node_type_scenario = architectural_decision_scenarios[0]

    assert node_type_scenario["scenario_id"] == "node_type_001"
    assert "email notification" in node_type_scenario["title"].lower()
    assert len(node_type_scenario["consensus_options"]) == 4

    # You could test consensus resolution
    # resolver = ConsensusResolver()
    # result = resolver.resolve_scenario(node_type_scenario)
    # assert result.scenario_id == "node_type_001"


def test_consensus_edge_cases_example(consensus_edge_cases):
    """Example: Test consensus edge cases."""
    # The fixture provides edge cases
    split_case = consensus_edge_cases[0]  # Split decision

    assert split_case["case_id"] == "split_001"
    assert split_case["consensus_reached"] is False
    assert split_case["tie_breaking_needed"] is True

    # You could test edge case handling
    # resolver = ConsensusResolver()
    # result = resolver.resolve(split_case["model_responses"])
    # assert result.consensus_reached is False


# ============================================================================
# Example 5: Testing with Configurations
# ============================================================================


def test_quality_gate_configs_example(quality_gate_configs):
    """Example: Test with different quality gate configs."""
    # The fixture provides all configurations
    assert "default" in quality_gate_configs
    assert "strict" in quality_gate_configs
    assert "lenient" in quality_gate_configs

    # Compare configurations
    default = quality_gate_configs["default"]
    strict = quality_gate_configs["strict"]

    # Strict should have higher thresholds
    assert (
        strict["gates"]["test_coverage"]["thresholds"]["line_coverage"]
        > default["gates"]["test_coverage"]["thresholds"]["line_coverage"]
    )


def test_default_config_example(default_quality_gate_config):
    """Example: Test with default config."""
    # The fixture provides default configuration
    assert default_quality_gate_config["config_id"] == "default"
    assert default_quality_gate_config["overall_threshold"] == 0.80

    coverage_threshold = default_quality_gate_config["gates"]["test_coverage"][
        "thresholds"
    ]["line_coverage"]
    assert coverage_threshold == 0.90


def test_strict_config_example(strict_quality_gate_config):
    """Example: Test with strict config."""
    # The fixture provides strict configuration
    assert strict_quality_gate_config["config_id"] == "strict"
    assert strict_quality_gate_config["overall_threshold"] == 0.90
    assert strict_quality_gate_config["require_all_gates"] is True

    # Strict has tighter thresholds
    coverage_threshold = strict_quality_gate_config["gates"]["test_coverage"][
        "thresholds"
    ]["line_coverage"]
    assert coverage_threshold == 0.95


# ============================================================================
# Example 6: Testing with Expected Results
# ============================================================================


def test_expected_results_example(expected_validation_results):
    """Example: Test with expected validation results."""
    # The fixture provides expected results
    compliant_result = expected_validation_results["onex_compliant"]

    assert compliant_result["result"]["compliant"] is True
    assert compliant_result["result"]["compliance_score"] == 1.0
    assert compliant_result["result"]["violations"] == []

    non_compliant_result = expected_validation_results["onex_non_compliant"]

    assert non_compliant_result["result"]["compliant"] is False
    assert non_compliant_result["result"]["compliance_score"] == 0.4
    assert len(non_compliant_result["result"]["violations"]) > 0


# ============================================================================
# Example 7: Parameterized Testing
# ============================================================================


@pytest.mark.parametrize("node_type", ["effect", "compute", "reducer", "orchestrator"])
def test_parameterized_example(all_compliant_nodes, node_type):
    """Example: Parameterized test with fixtures."""
    # Test each node type
    node_class = all_compliant_nodes[node_type]

    # All should have correct suffix
    assert node_class.__name__.endswith(node_type.capitalize())

    # All should have correct method
    expected_method = (
        f"execute_{node_type if node_type != 'orchestrator' else 'orchestration'}"
    )
    if node_type == "reducer":
        expected_method = "execute_reduction"
    assert hasattr(node_class, expected_method)


# ============================================================================
# Example 8: Combined Fixtures
# ============================================================================


def test_combined_fixtures_example(
    compliant_effect_node,
    compliant_contracts,
    default_quality_gate_config,
):
    """Example: Using multiple fixtures together."""
    # Get effect node

    # Get effect contract
    compliant_contracts["effect"]()

    # Get quality config

    # You could test complete validation
    # validator = ValidationPipeline(config=config)
    # node = node_class()
    # result = validator.validate_node_with_contract(node, effect_contract)
    # assert result.passed is True


# ============================================================================
# Example 9: Testing Contract Factory
# ============================================================================


def test_contract_factory_example(compliant_contracts):
    """Example: Using contract factory functions."""
    # The fixture provides factory functions for each contract type
    effect_contract = compliant_contracts["effect"]()
    compute_contract = compliant_contracts["compute"]()

    # Verify contracts are created correctly
    assert effect_contract.node_type == "effect"
    assert effect_contract.name == "DatabaseWriter"
    assert effect_contract.version == "1.0.0"

    assert compute_contract.node_type == "compute"
    assert compute_contract.name == "DataTransformer"


# ============================================================================
# Example 10: Real-World Validation Example
# ============================================================================


def test_real_world_validation_example(
    compliant_effect_code,
    default_quality_gate_config,
    expected_validation_results,
):
    """Example: Real-world validation test."""
    # This is how you might test actual validation logic

    # Simulated validation (you would use real validator)
    simulated_result = {
        "compliant": True,
        "compliance_score": 1.0,
        "violations": [],
        "checks": {
            "naming_convention": {"passed": True},
            "method_signature": {"passed": True},
            "contract_type": {"passed": True},
        },
    }

    # Compare with expected
    expected = expected_validation_results["onex_compliant"]["result"]

    assert simulated_result["compliant"] == expected["compliant"]
    assert simulated_result["compliance_score"] == expected["compliance_score"]
    assert len(simulated_result["violations"]) == len(expected["violations"])


# ============================================================================
# Run Examples
# ============================================================================

if __name__ == "__main__":
    # Run with: python -m pytest tests/fixtures/phase3_validation/example_test.py -v
    pytest.main([__file__, "-v"])
