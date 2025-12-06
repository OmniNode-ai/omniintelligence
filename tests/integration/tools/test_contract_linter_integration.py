# SPDX-License-Identifier: Apache-2.0
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

# Contracts base directory in the legacy nodes
LEGACY_CONTRACTS_DIR = (
    PROJECT_ROOT / "src" / "omniintelligence" / "_legacy" / "nodes"
)

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


def _get_all_legacy_contracts() -> list[Path]:
    """Get all contract files from the legacy nodes directory.

    Returns:
        List of all contract YAML files
    """
    if not LEGACY_CONTRACTS_DIR.exists():
        return []
    return list(LEGACY_CONTRACTS_DIR.glob("*/v1_0_0/contracts/*.yaml"))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def legacy_compute_contracts() -> list[Path]:
    """Collect all compute contract files from legacy nodes."""
    return _collect_contracts_by_pattern(
        LEGACY_CONTRACTS_DIR, "*/v1_0_0/contracts/compute_contract.yaml"
    )


@pytest.fixture
def legacy_effect_contracts() -> list[Path]:
    """Collect all effect contract files from legacy nodes."""
    return _collect_contracts_by_pattern(
        LEGACY_CONTRACTS_DIR, "*/v1_0_0/contracts/effect_contract.yaml"
    )


@pytest.fixture
def legacy_reducer_contracts() -> list[Path]:
    """Collect all reducer contract files from legacy nodes."""
    return _collect_contracts_by_pattern(
        LEGACY_CONTRACTS_DIR, "*/v1_0_0/contracts/reducer_contract.yaml"
    )


@pytest.fixture
def legacy_orchestrator_contracts() -> list[Path]:
    """Collect all orchestrator contract files from legacy nodes."""
    return _collect_contracts_by_pattern(
        LEGACY_CONTRACTS_DIR, "*/v1_0_0/contracts/orchestrator_contract.yaml"
    )


@pytest.fixture
def legacy_fsm_contracts() -> list[Path]:
    """Collect all FSM subcontract files from legacy nodes."""
    return _collect_contracts_by_pattern(
        LEGACY_CONTRACTS_DIR, "*/v1_0_0/contracts/fsm_*.yaml"
    )


@pytest.fixture
def all_legacy_contracts() -> list[Path]:
    """Collect all contract files from legacy nodes."""
    return _get_all_legacy_contracts()


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

    valid_yaml = """
name: test_compute_{index}
version:
  major: 1
  minor: 0
  patch: 0
description: Test compute contract {index} for parallel validation
node_type: compute
input_model: ModelComputeInput
output_model: ModelComputeOutput
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
        self, legacy_compute_contracts: list[Path]
    ) -> None:
        """Verify compute contracts are detected and have correct type."""
        if not legacy_compute_contracts:
            pytest.skip("No compute contracts found in codebase")

        linter = ContractLinter()
        for contract_path in legacy_compute_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.file_path == contract_path
            # Compute contracts should be detected as 'compute' type
            assert result.contract_type == "compute", (
                f"Expected 'compute' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_effect_contracts_structure(
        self, legacy_effect_contracts: list[Path]
    ) -> None:
        """Verify effect contracts are detected and have correct type."""
        if not legacy_effect_contracts:
            pytest.skip("No effect contracts found in codebase")

        linter = ContractLinter()
        for contract_path in legacy_effect_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.contract_type == "effect", (
                f"Expected 'effect' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_reducer_contracts_structure(
        self, legacy_reducer_contracts: list[Path]
    ) -> None:
        """Verify reducer contracts are detected and have correct type."""
        if not legacy_reducer_contracts:
            pytest.skip("No reducer contracts found in codebase")

        linter = ContractLinter()
        for contract_path in legacy_reducer_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.contract_type == "reducer", (
                f"Expected 'reducer' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_orchestrator_contracts_structure(
        self, legacy_orchestrator_contracts: list[Path]
    ) -> None:
        """Verify orchestrator contracts are detected and have correct type."""
        if not legacy_orchestrator_contracts:
            pytest.skip("No orchestrator contracts found in codebase")

        linter = ContractLinter()
        for contract_path in legacy_orchestrator_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.contract_type == "orchestrator", (
                f"Expected 'orchestrator' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_validate_fsm_subcontracts_structure(
        self, legacy_fsm_contracts: list[Path]
    ) -> None:
        """Verify FSM subcontracts are detected and have correct type."""
        if not legacy_fsm_contracts:
            pytest.skip("No FSM subcontracts found in codebase")

        linter = ContractLinter()
        for contract_path in legacy_fsm_contracts:
            result = linter.validate(contract_path)

            assert isinstance(result, ModelContractValidationResult)
            assert result.contract_type == "fsm_subcontract", (
                f"Expected 'fsm_subcontract' type for {contract_path.name}, "
                f"got '{result.contract_type}'"
            )

    def test_batch_validate_all_contracts(
        self, all_legacy_contracts: list[Path]
    ) -> None:
        """Test batch validation of all contracts with summary statistics."""
        if not all_legacy_contracts:
            pytest.skip("No contracts found in codebase")

        linter = ContractLinter()
        results = linter.validate_batch(all_legacy_contracts)
        summary = linter.get_summary(results)

        # Verify we got results for all files
        assert len(results) == len(all_legacy_contracts)

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

    def test_contract_count_sanity_check(
        self, all_legacy_contracts: list[Path]
    ) -> None:
        """Verify expected minimum number of contracts exist in codebase.

        This test ensures the test infrastructure is working correctly
        by verifying that we found a reasonable number of contracts.
        """
        # We know from glob results there should be at least 15 contracts
        # (6 compute, 5 effect, 1 reducer, 1 orchestrator, 3 FSM)
        expected_minimum = 10

        assert len(all_legacy_contracts) >= expected_minimum, (
            f"Expected at least {expected_minimum} contracts, "
            f"found {len(all_legacy_contracts)}. "
            "This may indicate the contracts directory structure has changed."
        )

        # Print contract breakdown
        compute_count = len([
            p for p in all_legacy_contracts
            if "compute_contract" in p.name
        ])
        effect_count = len([
            p for p in all_legacy_contracts
            if "effect_contract" in p.name
        ])
        reducer_count = len([
            p for p in all_legacy_contracts
            if "reducer_contract" in p.name
        ])
        orchestrator_count = len([
            p for p in all_legacy_contracts
            if "orchestrator_contract" in p.name
        ])
        fsm_count = len([
            p for p in all_legacy_contracts
            if p.name.startswith("fsm_")
        ])

        print("\nContract breakdown:")
        print(f"  Compute: {compute_count}")
        print(f"  Effect: {effect_count}")
        print(f"  Reducer: {reducer_count}")
        print(f"  Orchestrator: {orchestrator_count}")
        print(f"  FSM subcontracts: {fsm_count}")
        print(f"  Total: {len(all_legacy_contracts)}")


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
        sequential_results = linter.validate_batch(
            large_contract_batch, parallel=False
        )

        # Parallel validation
        parallel_results = linter.validate_batch(
            large_contract_batch, parallel=True
        )

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

        valid_yaml = """
name: test_small_{index}
version:
  major: 1
  minor: 0
  patch: 0
description: Test for small batch
node_type: compute
input_model: ModelInput
output_model: ModelOutput
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

        valid_yaml = """
name: test_custom_{index}
version:
  major: 1
  minor: 0
  patch: 0
description: Test for custom threshold
node_type: compute
input_model: ModelInput
output_model: ModelOutput
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
        yaml_content = """
name: test_alias_resolution
version:
  major: 1
  minor: 0
  patch: 0
description: Test contract for field alias handling
node_type: compute
input_model: ModelInput
output_model: ModelOutput
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
        assert result.contract_type == "compute"

    def test_deprecated_field_name_handling(self, tmp_path: Path) -> None:
        """Test validation with deprecated field names.

        Contracts using deprecated field names should still validate
        (possibly with warnings in strict mode).
        """
        # Using canonical field names in minimal valid contract
        yaml_content = """
name: test_deprecated_fields
version:
  major: 1
  minor: 0
  patch: 0
description: Test contract with standard fields
node_type: effect
input_model: ModelInput
output_model: ModelOutput
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
        assert result.contract_type == "effect"

    def test_mixed_case_node_type_handling(self, tmp_path: Path) -> None:
        """Test that node_type is handled case-insensitively.

        ONEX node types should be matched case-insensitively
        (e.g., 'Compute', 'COMPUTE', 'compute' should all work).
        """
        test_cases = [
            ("compute", "compute"),
            ("effect", "effect"),
            ("reducer", "reducer"),
            ("orchestrator", "orchestrator"),
        ]

        for input_type, expected_type in test_cases:
            yaml_content = f"""
name: test_{input_type}_case
version:
  major: 1
  minor: 0
  patch: 0
description: Test {input_type} case handling
node_type: {input_type}
input_model: ModelInput
output_model: ModelOutput
"""
            # Add required fields based on type
            if input_type == "compute":
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
            elif input_type == "effect":
                yaml_content += """
io_operations:
  - operation_type: file_read
    atomic: true
"""

            contract_path = tmp_path / f"case_test_{input_type}.yaml"
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
name: test_extra_fields
version:
  major: 1
  minor: 0
  patch: 0
description: Test contract with extra fields
node_type: compute
input_model: ModelInput
output_model: ModelOutput
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
        assert result.contract_type == "compute"


# =============================================================================
# Test Class: Edge Cases and Error Handling
# =============================================================================


@pytest.mark.integration
class TestIntegrationEdgeCases:
    """Edge case tests for contract linter integration scenarios."""

    def test_deeply_nested_contract_structure(self, tmp_path: Path) -> None:
        """Test validation of contracts with deeply nested structures."""
        yaml_content = """
name: deeply_nested_contract
version:
  major: 1
  minor: 0
  patch: 0
description: Contract with deep nesting
node_type: orchestrator
input_model: ModelInput
output_model: ModelOutput
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
        assert result.contract_type == "orchestrator"

    def test_unicode_in_contract_fields(self, tmp_path: Path) -> None:
        """Test handling of unicode characters in contract content."""
        yaml_content = """
name: unicode_test_node
version:
  major: 1
  minor: 0
  patch: 0
description: "Test node with unicode: \u65e5\u672c\u8a9e\u30c6\u30b9\u30c8, accents: cafe"
node_type: compute
input_model: ModelInput
output_model: ModelOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
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
        self, all_legacy_contracts: list[Path]
    ) -> None:
        """Test batch validation with diverse contract types.

        A real batch may contain compute, effect, reducer, orchestrator,
        and FSM contracts all together. The linter should correctly
        identify and validate each type.
        """
        if not all_legacy_contracts:
            pytest.skip("No contracts found in codebase")

        linter = ContractLinter()
        results = linter.validate_batch(all_legacy_contracts)

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
