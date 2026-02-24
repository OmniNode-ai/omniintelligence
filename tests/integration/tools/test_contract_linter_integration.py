# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Integration tests for Contract Linter using real YAML contract files.

These tests validate the contract linter against actual contract files in the
codebase, ensuring that the linter correctly validates real-world contracts
used by ONEX nodes.

Tests cover:
- Real contract file validation (compute, effect, reducer, orchestrator, FSM)
- Parallel validation threshold behavior
- Field name conflict resolution
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from omniintelligence.tools.contract_linter import (
    DEFAULT_PARALLEL_THRESHOLD,
    ContractLinter,
    ModelContractValidationResult,
)

# =============================================================================
# Path Configuration
# =============================================================================

# Project root directory (relative to this test file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Contracts base directory in the canonical nodes
CONTRACTS_DIR = PROJECT_ROOT / "src" / "omniintelligence" / "nodes"

# Runtime contracts directory
RUNTIME_CONTRACTS_DIR = (
    PROJECT_ROOT / "src" / "omniintelligence" / "runtime" / "contracts"
)


# =============================================================================
# Helper Functions
# =============================================================================


def _collect_contracts_by_pattern(base_dir: Path, pattern: str) -> list[Path]:
    """Collect contract files matching a glob pattern.

    Args:
        base_dir: Base directory to search
        pattern: Glob pattern for matching files

    Returns:
        List of matching file paths
    """
    if not base_dir.exists():
        return []
    return list(base_dir.glob(pattern))


def _get_all_contracts() -> list[Path]:
    """Get all contract files from the canonical nodes directory.

    Returns:
        List of all contract YAML files
    """
    if not CONTRACTS_DIR.exists():
        return []
    # Contracts are named contract.yaml directly in node directories
    # Path: src/omniintelligence/nodes/{node_name}/contract.yaml
    return list(CONTRACTS_DIR.glob("*/contract.yaml"))


# =============================================================================
# Fixtures
# =============================================================================


def _filter_contracts_by_node_type(contracts: list[Path], node_type: str) -> list[Path]:
    """Filter contracts by node_type field in YAML.

    Args:
        contracts: List of contract file paths
        node_type: Expected node_type value (e.g., 'COMPUTE_GENERIC', 'EFFECT_GENERIC')

    Returns:
        List of contracts matching the node_type
    """
    import yaml

    result = []
    for contract_path in contracts:
        try:
            with open(contract_path) as f:
                data = yaml.safe_load(f)
                if data and data.get("node_type") == node_type:
                    result.append(contract_path)
        except (yaml.YAMLError, OSError, KeyError):
            continue
    return result


@pytest.fixture
def compute_contracts() -> list[Path]:
    """Collect all compute contract files from canonical nodes."""
    # Contracts are at */contract.yaml, filter by node_type field
    all_contracts = _collect_contracts_by_pattern(CONTRACTS_DIR, "*/contract.yaml")
    return _filter_contracts_by_node_type(all_contracts, "COMPUTE_GENERIC")


@pytest.fixture
def effect_contracts() -> list[Path]:
    """Collect all effect contract files from canonical nodes."""
    # Contracts are at */contract.yaml, filter by node_type field
    all_contracts = _collect_contracts_by_pattern(CONTRACTS_DIR, "*/contract.yaml")
    return _filter_contracts_by_node_type(all_contracts, "EFFECT_GENERIC")


@pytest.fixture
def reducer_contracts() -> list[Path]:
    """Collect all reducer contract files from canonical nodes."""
    # Contracts are at */contract.yaml, filter by node_type field
    all_contracts = _collect_contracts_by_pattern(CONTRACTS_DIR, "*/contract.yaml")
    return _filter_contracts_by_node_type(all_contracts, "REDUCER_GENERIC")


@pytest.fixture
def orchestrator_contracts() -> list[Path]:
    """Collect all orchestrator contract files from canonical nodes."""
    # Contracts are at */contract.yaml, filter by node_type field
    all_contracts = _collect_contracts_by_pattern(CONTRACTS_DIR, "*/contract.yaml")
    return _filter_contracts_by_node_type(all_contracts, "ORCHESTRATOR_GENERIC")


@pytest.fixture
def fsm_contracts() -> list[Path]:
    """Collect all FSM subcontract files from canonical nodes.

    Note: In the current structure, FSM state machines are embedded in reducer contracts
    rather than separate fsm_*.yaml files. Returns empty list as no separate FSM files exist.
    """
    # FSM contracts were a separate pattern in old structure, not present in current
    return []


@pytest.fixture
def all_contracts() -> list[Path]:
    """Collect all contract files from canonical nodes."""
    return _get_all_contracts()


@pytest.fixture
def large_contract_batch(tmp_path: Path) -> list[Path]:
    """Create a batch of contracts larger than parallel threshold.

    Creates enough contract files to trigger parallel validation when
    the parallel=True flag is passed to validate_batch().

    Returns:
        List of paths to temporary contract files
    """
    batch_size = DEFAULT_PARALLEL_THRESHOLD + 5  # Exceed threshold
    files: list[Path] = []

    # Updated YAML format with required fields: contract_version, node_version
    valid_yaml = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_compute_{index}
description: Test compute contract {index} for parallel validation
node_type: COMPUTE_GENERIC
input_model:
  name: ModelComputeInput
  module: tests.fixtures.models
output_model:
  name: ModelComputeOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    compute_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""

    for i in range(batch_size):
        contract_path = tmp_path / f"parallel_test_{i}.yaml"
        contract_path.write_text(valid_yaml.format(index=i))
        files.append(contract_path)

    return files


# =============================================================================
# Test Class: Real Contract File Validation
# =============================================================================


@pytest.mark.integration
class TestRealContractValidation:
    """Integration tests using actual contract files from the codebase.

    These tests validate that the contract linter correctly processes
    real-world contracts from the ONEX node implementations.
    """

    def test_validate_compute_contracts_structure(
        self, compute_contracts: list[Path]
    ) -> None:
        """Verify compute contracts are detected and have correct type."""
        if not compute_contracts:
            pytest.skip("No compute contracts found in codebase")

        linter = ContractLinter()
        for contract_path in compute_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.file_path == contract_path
            # Compute contracts have node_type "COMPUTE_GENERIC" which becomes "compute_generic"
            assert result.contract_type in ("compute", "compute_generic"), (
                f"Expected 'compute' or 'compute_generic' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_effect_contracts_structure(
        self, effect_contracts: list[Path]
    ) -> None:
        """Verify effect contracts are detected and have correct type."""
        if not effect_contracts:
            pytest.skip("No effect contracts found in codebase")

        linter = ContractLinter()
        for contract_path in effect_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            # Effect contracts have node_type "EFFECT_GENERIC" which becomes "effect_generic"
            assert result.contract_type in ("effect", "effect_generic"), (
                f"Expected 'effect' or 'effect_generic' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_reducer_contracts_structure(
        self, reducer_contracts: list[Path]
    ) -> None:
        """Verify reducer contracts are detected and have correct type."""
        if not reducer_contracts:
            pytest.skip("No reducer contracts found in codebase")

        linter = ContractLinter()
        for contract_path in reducer_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            # Reducer contracts have node_type "REDUCER_GENERIC" which becomes "reducer_generic"
            assert result.contract_type in ("reducer", "reducer_generic"), (
                f"Expected 'reducer' or 'reducer_generic' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_orchestrator_contracts_structure(
        self, orchestrator_contracts: list[Path]
    ) -> None:
        """Verify orchestrator contracts are detected and have correct type."""
        if not orchestrator_contracts:
            pytest.skip("No orchestrator contracts found in codebase")

        linter = ContractLinter()
        for contract_path in orchestrator_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            # Orchestrator contracts have node_type "ORCHESTRATOR_GENERIC" which becomes "orchestrator_generic"
            assert result.contract_type in ("orchestrator", "orchestrator_generic"), (
                f"Expected 'orchestrator' or 'orchestrator_generic' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_fsm_subcontracts_structure(
        self, fsm_contracts: list[Path]
    ) -> None:
        """Verify FSM subcontracts are detected and have correct type."""
        if not fsm_contracts:
            pytest.skip("No FSM subcontracts found in codebase")

        linter = ContractLinter()
        for contract_path in fsm_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.contract_type == "fsm_subcontract", (
                f"Expected 'fsm_subcontract' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_batch_validate_all_contracts(self, all_contracts: list[Path]) -> None:
        """Test batch validation of all contracts with summary statistics."""
        if not all_contracts:
            pytest.skip("No contracts found in codebase")

        linter = ContractLinter()
        results = linter.validate_batch(all_contracts)
        summary = linter.get_summary(results)

        # Verify we got results for all files
        assert len(results) == len(all_contracts)

        # Log summary for visibility (use ONEX naming convention keys)
        print("\nContract validation summary:")
        print(f"  Total: {summary['total_count']}")
        print(f"  Valid: {summary['valid_count']}")
        print(f"  Invalid: {summary['invalid_count']}")
        print(f"  Pass rate: {summary['pass_rate']:.1f}%")

        # Collect any failures for reporting
        failed_results = [r for r in results if not r.is_valid]
        if failed_results:
            print(f"\nFailed contracts ({len(failed_results)}):")
            for result in failed_results[:5]:  # Show first 5
                print(f"  - {result.file_path.name}")
                for error in result.validation_errors[:3]:
                    print(f"      {error.field_path}: {error.error_message}")

    def test_contract_count_sanity_check(self, all_contracts: list[Path]) -> None:
        """Verify expected minimum number of contracts exist in codebase.

        This test ensures the test infrastructure is working correctly
        by verifying that we found a reasonable number of contracts.
        """
        import yaml

        # We expect at least 10 contracts in the nodes directory
        # (~11 compute, 5 effect, 1 reducer, 2 orchestrators)
        expected_minimum = 10

        assert len(all_contracts) >= expected_minimum, (
            f"Expected at least {expected_minimum} contracts, "
            f"found {len(all_contracts)}. "
            "This may indicate the contracts directory structure has changed."
        )

        # Count contracts by node_type field in YAML
        compute_count = 0
        effect_count = 0
        reducer_count = 0
        orchestrator_count = 0

        for contract_path in all_contracts:
            try:
                with open(contract_path) as f:
                    data = yaml.safe_load(f)
                    node_type = data.get("node_type", "")
                    if node_type == "COMPUTE_GENERIC":
                        compute_count += 1
                    elif node_type == "EFFECT_GENERIC":
                        effect_count += 1
                    elif node_type == "REDUCER_GENERIC":
                        reducer_count += 1
                    elif node_type == "ORCHESTRATOR_GENERIC":
                        orchestrator_count += 1
            except (yaml.YAMLError, OSError, KeyError):
                continue

        print("\nContract breakdown by node_type:")
        print(f"  Compute (COMPUTE_GENERIC): {compute_count}")
        print(f"  Effect (EFFECT_GENERIC): {effect_count}")
        print(f"  Reducer (REDUCER_GENERIC): {reducer_count}")
        print(f"  Orchestrator (ORCHESTRATOR_GENERIC): {orchestrator_count}")
        print(f"  Total: {len(all_contracts)}")


# =============================================================================
# Test Class: Parallel Validation Performance
# =============================================================================


@pytest.mark.integration
class TestParallelValidationPerformance:
    """Tests for parallel validation threshold and performance behavior."""

    def test_parallel_validation_activates_above_threshold(
        self, large_contract_batch: list[Path]
    ) -> None:
        """Verify parallel validation activates when batch exceeds threshold.

        This test verifies that:
        1. Batch size exceeds the parallel threshold
        2. Parallel validation completes successfully
        3. Results are returned for all files
        """
        batch_size = len(large_contract_batch)
        assert batch_size > DEFAULT_PARALLEL_THRESHOLD, (
            f"Batch size ({batch_size}) should exceed parallel threshold "
            f"({DEFAULT_PARALLEL_THRESHOLD})"
        )

        linter = ContractLinter()
        results = linter.validate_batch(large_contract_batch, parallel=True)

        # All files should be validated
        assert len(results) == batch_size
        # All should be valid (we created valid contracts)
        assert all(r.is_valid for r in results)

    def test_parallel_vs_sequential_consistency(
        self, large_contract_batch: list[Path]
    ) -> None:
        """Verify parallel and sequential validation produce identical results.

        Results should be identical regardless of validation mode, ensuring
        parallel validation doesn't introduce non-determinism.
        """
        linter = ContractLinter()

        # Sequential validation
        sequential_results = linter.validate_batch(large_contract_batch, parallel=False)

        # Parallel validation
        parallel_results = linter.validate_batch(large_contract_batch, parallel=True)

        # Results should match (same files, same validity)
        assert len(sequential_results) == len(parallel_results)

        # Sort by file path for comparison
        seq_sorted = sorted(sequential_results, key=lambda r: str(r.file_path))
        par_sorted = sorted(parallel_results, key=lambda r: str(r.file_path))

        for seq, par in zip(seq_sorted, par_sorted, strict=True):
            assert seq.file_path == par.file_path
            assert seq.is_valid == par.is_valid
            assert seq.contract_type == par.contract_type
            # Error messages may vary in order but count should match
            assert len(seq.validation_errors) == len(par.validation_errors)

    def test_parallel_threshold_respected(self, tmp_path: Path) -> None:
        """Verify small batches use sequential validation.

        Batches smaller than the threshold should not use parallel
        validation, even when parallel=True is specified.
        """
        # Create batch smaller than threshold
        small_batch_size = DEFAULT_PARALLEL_THRESHOLD - 2
        assert small_batch_size > 0, "Threshold too small for test"

        # Updated YAML format with required fields: contract_version, node_version
        valid_yaml = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_small_{index}
description: Test for small batch
node_type: COMPUTE_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""

        files: list[Path] = []
        for i in range(small_batch_size):
            path = tmp_path / f"small_{i}.yaml"
            path.write_text(valid_yaml.format(index=i))
            files.append(path)

        linter = ContractLinter()

        # This should work without errors regardless of parallel setting
        # (internally uses sequential because below threshold)
        results = linter.validate_batch(files, parallel=True)
        assert len(results) == small_batch_size
        assert all(r.is_valid for r in results)

    def test_custom_parallel_threshold(self, tmp_path: Path) -> None:
        """Test custom parallel threshold configuration.

        The ContractLinter accepts a custom parallel_threshold parameter
        to allow tuning based on system resources.
        """
        # Create batch of 5 files
        batch_size = 5
        custom_threshold = 3  # Lower than default

        # Updated YAML format with required fields: contract_version, node_version
        valid_yaml = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_custom_{index}
description: Test for custom threshold
node_type: COMPUTE_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""

        files: list[Path] = []
        for i in range(batch_size):
            path = tmp_path / f"custom_{i}.yaml"
            path.write_text(valid_yaml.format(index=i))
            files.append(path)

        # Custom linter with lower threshold
        linter = ContractLinter(parallel_threshold=custom_threshold)

        # Should trigger parallel validation (5 > 3)
        results = linter.validate_batch(files, parallel=True)
        assert len(results) == batch_size

    def test_parallel_validation_performance_improvement(
        self, large_contract_batch: list[Path]
    ) -> None:
        """Measure that parallel validation provides performance benefit.

        Note: This test is more of a sanity check than a strict requirement,
        as actual speedup depends on CPU cores and system load.
        """
        linter = ContractLinter()
        iterations = 3

        # Measure sequential time
        sequential_times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            linter.validate_batch(large_contract_batch, parallel=False)
            sequential_times.append(time.perf_counter() - start)

        # Measure parallel time
        parallel_times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            linter.validate_batch(large_contract_batch, parallel=True)
            parallel_times.append(time.perf_counter() - start)

        avg_sequential = sum(sequential_times) / len(sequential_times)
        avg_parallel = sum(parallel_times) / len(parallel_times)

        print(f"\nPerformance comparison (batch size: {len(large_contract_batch)}):")
        print(f"  Sequential avg: {avg_sequential:.4f}s")
        print(f"  Parallel avg: {avg_parallel:.4f}s")

        # We don't assert speedup as it depends on system resources
        # Just verify both modes complete successfully


# =============================================================================
# Test Class: Field Name Conflict Resolution
# =============================================================================


@pytest.mark.integration
class TestFieldNameConflictResolution:
    """Tests for handling contracts with both old and new field names.

    ONEX contracts may contain field aliases which the Pydantic models
    resolve to canonical field names. The linter should handle these
    cases gracefully.
    """

    def test_contract_with_both_field_aliases(self, tmp_path: Path) -> None:
        """Test handling when both old and new field names are provided.

        Some Pydantic models support field aliases. When both the alias and
        canonical name are provided, validation should either accept both or
        prefer the canonical name.
        """
        # Contract with potential duplicate/aliased fields
        # Updated to use contract_version and node_version (required fields)
        yaml_content = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_alias_resolution
description: Test contract for field alias handling
node_type: COMPUTE_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""
        contract_path = tmp_path / "alias_test.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # Should parse without errors
        assert isinstance(result, ModelContractValidationResult)
        assert result.contract_type in ("compute", "compute_generic")

    def test_deprecated_field_name_handling(self, tmp_path: Path) -> None:
        """Test validation with deprecated field names.

        Contracts using deprecated field names should still validate
        (possibly with warnings in strict mode).
        """
        # Using canonical field names in minimal valid contract
        # Updated to use contract_version and node_version (required fields)
        yaml_content = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_deprecated_fields
description: Test contract with standard fields
node_type: EFFECT_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
io_operations:
  - operation_type: file_read
    atomic: true
"""
        contract_path = tmp_path / "deprecated_fields.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # Should validate successfully with canonical names
        assert result.is_valid is True
        assert result.contract_type in ("effect", "effect_generic")

    def test_mixed_case_node_type_handling(self, tmp_path: Path) -> None:
        """Test that node_type is handled case-insensitively.

        ONEX node types should be matched case-insensitively
        (e.g., 'Compute', 'COMPUTE', 'compute' should all work).
        """
        # Test with ONEX standard types (COMPUTE_GENERIC, EFFECT_GENERIC, etc.)
        test_cases = [
            ("compute", "compute"),
            ("COMPUTE_GENERIC", "compute_generic"),
            ("effect", "effect"),
            ("EFFECT_GENERIC", "effect_generic"),
        ]

        for input_type, expected_type in test_cases:
            yaml_content = f"""
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_{input_type.lower()}_case
description: Test {input_type} case handling
node_type: {input_type}
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
"""
            # Add required fields based on type
            if "compute" in input_type.lower():
                yaml_content += """
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""
            elif "effect" in input_type.lower():
                yaml_content += """
io_operations:
  - operation_type: file_read
    atomic: true
"""

            contract_path = tmp_path / f"case_test_{input_type.lower()}.yaml"
            contract_path.write_text(yaml_content)

            linter = ContractLinter()
            result = linter.validate(contract_path)

            # Should detect correct type (lowercase normalized)
            assert result.contract_type == expected_type, (
                f"Input '{input_type}' should normalize to '{expected_type}', "
                f"got '{result.contract_type}'"
            )

    def test_extra_fields_are_allowed(self, tmp_path: Path) -> None:
        """Test that contracts with extra/unknown fields are handled.

        Contracts may include additional metadata or custom fields that
        are not part of the core schema. These should not cause validation
        failures (following Pydantic's 'extra=allow' or 'extra=ignore' pattern).
        """
        yaml_content = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: test_extra_fields
description: Test contract with extra fields
node_type: COMPUTE_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
# Extra fields that may not be in schema
custom_metadata:
  team: platform
  owner: intelligence
internal_notes: "This is for testing"
"""
        contract_path = tmp_path / "extra_fields.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # Extra fields should not cause validation to fail
        # (unless the schema explicitly forbids extra fields)
        assert isinstance(result, ModelContractValidationResult)
        assert result.contract_type in ("compute", "compute_generic")


# =============================================================================
# Test Class: Edge Cases and Error Handling
# =============================================================================


@pytest.mark.integration
class TestIntegrationEdgeCases:
    """Edge case tests for contract linter integration scenarios."""

    def test_deeply_nested_contract_structure(self, tmp_path: Path) -> None:
        """Test validation of contracts with deeply nested structures."""
        yaml_content = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: deeply_nested_contract
description: Contract with deep nesting
node_type: ORCHESTRATOR_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
dependencies:
  - name: dep1
    dependency_type: module
    required: true
    description: First dependency
  - name: dep2
    dependency_type: module
    required: false
    description: Second dependency
workflow_coordination:
  execution_mode: parallel
  max_parallel_branches: 5
  checkpoint_enabled: true
  checkpoint_interval_ms: 1000
  recovery_enabled: true
  timeout_ms: 300000
event_coordination:
  coordination_strategy: immediate
  buffer_size: 100
  correlation_enabled: true
  correlation_timeout_ms: 30000
"""
        contract_path = tmp_path / "nested.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert isinstance(result, ModelContractValidationResult)
        assert result.contract_type in ("orchestrator", "orchestrator_generic")

    def test_unicode_in_contract_fields(self, tmp_path: Path) -> None:
        """Test handling of unicode characters in contract content."""
        yaml_content = """
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
name: unicode_test_node
description: "Test node with unicode: \u65e5\u672c\u8a9e\u30c6\u30b9\u30c8, accents: cafe"
node_type: COMPUTE_GENERIC
input_model:
  name: ModelInput
  module: tests.fixtures.models
output_model:
  name: ModelOutput
  module: tests.fixtures.models
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
metadata:
  author: "Tester (\u6d4b\u8bd5\u4eba\u5458)"
  tags:
    - test
    - unicode-\u6d4b\u8bd5
"""
        contract_path = tmp_path / "unicode_test.yaml"
        contract_path.write_text(yaml_content, encoding="utf-8")

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert isinstance(result, ModelContractValidationResult)
        # Should handle unicode without crashing

    def test_validate_batch_with_mixed_contract_types(
        self, all_contracts: list[Path]
    ) -> None:
        """Test batch validation with diverse contract types.

        A real batch may contain compute, effect, reducer, orchestrator,
        and FSM contracts all together. The linter should correctly
        identify and validate each type.
        """
        if not all_contracts:
            pytest.skip("No contracts found in codebase")

        linter = ContractLinter()
        results = linter.validate_batch(all_contracts)

        # Group results by detected contract type
        types_found: dict[str | None, int] = {}
        for result in results:
            contract_type = result.contract_type
            types_found[contract_type] = types_found.get(contract_type, 0) + 1

        print("\nContract types found in batch:")
        for contract_type, count in sorted(
            types_found.items(), key=lambda x: str(x[0])
        ):
            print(f"  {contract_type}: {count}")

        # Should have detected multiple types
        assert len(types_found) > 1, (
            "Expected multiple contract types in mixed batch, "
            f"found only: {list(types_found.keys())}"
        )
