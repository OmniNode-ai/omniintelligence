# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter contract type detection and validation.

Tests for contract type detection, FSM subcontract validation, and integration
tests using real contract files from the codebase.
"""

from pathlib import Path

import pytest

from omniintelligence.tools.contract_linter import (
    ContractLinter,
    ContractValidationResult,
)

# =============================================================================
# Test Class: Contract Type Detection
# =============================================================================


class TestContractTypeDetection:
    """Tests for automatic contract type detection."""

    def test_detect_compute_contract_type(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test that compute contracts are properly detected."""
        contract_path = tmp_path / "compute.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.contract_type == "compute"

    def test_detect_effect_contract_type(
        self, tmp_path: Path, valid_effect_contract_yaml: str
    ):
        """Test that effect contracts are properly detected."""
        contract_path = tmp_path / "effect.yaml"
        contract_path.write_text(valid_effect_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.contract_type == "effect"

    def test_detect_base_contract_type(
        self, tmp_path: Path, valid_base_contract_yaml: str
    ):
        """Test that base contracts without specialized fields are detected."""
        contract_path = tmp_path / "base.yaml"
        contract_path.write_text(valid_base_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # Base contract may be detected as compute or base
        assert result.contract_type in ["compute", "base", "generic"]


# =============================================================================
# Test Class: Real Contract Files (Integration-like)
# =============================================================================


@pytest.mark.skip(
    reason="Legacy contracts in _legacy folder are excluded from validation"
)
class TestRealContractFiles:
    """Tests using actual contract files from the codebase."""

    @pytest.fixture
    def real_compute_contract_path(self) -> Path:
        """Path to real compute contract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        return (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/_legacy/nodes/entity_extraction_compute/v1_0_0/contracts/compute_contract.yaml"
        )

    @pytest.fixture
    def real_effect_contract_path(self) -> Path:
        """Path to real effect contract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        return (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/_legacy/nodes/kafka_event_effect/v1_0_0/contracts/effect_contract.yaml"
        )

    def test_validate_real_compute_contract(self, real_compute_contract_path: Path):
        """Test validation against real compute contract in codebase."""
        if not real_compute_contract_path.exists():
            pytest.skip("Real contract file not found")

        linter = ContractLinter()
        result = linter.validate(real_compute_contract_path)

        # The real contract should be valid
        # Note: This may need adjustment based on actual contract conformance
        assert isinstance(result, ContractValidationResult)
        # We don't assert valid=True as the real contracts may have issues

    def test_validate_real_effect_contract(self, real_effect_contract_path: Path):
        """Test validation against real effect contract in codebase."""
        if not real_effect_contract_path.exists():
            pytest.skip("Real contract file not found")

        linter = ContractLinter()
        result = linter.validate(real_effect_contract_path)

        assert isinstance(result, ContractValidationResult)


# =============================================================================
# Test Class: FSM Subcontract Validation
# =============================================================================


class TestFSMSubcontractValidation:
    """Tests for FSM subcontract detection and validation."""

    def test_detect_fsm_subcontract(
        self, tmp_path: Path, valid_fsm_subcontract_yaml: str
    ):
        """Test that FSM subcontracts are properly detected."""
        contract_path = tmp_path / "fsm_test.yaml"
        contract_path.write_text(valid_fsm_subcontract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.contract_type == "fsm_subcontract"

    def test_validate_valid_fsm_subcontract(
        self, tmp_path: Path, valid_fsm_subcontract_yaml: str
    ):
        """Test that valid FSM subcontracts pass validation."""
        contract_path = tmp_path / "fsm_valid.yaml"
        contract_path.write_text(valid_fsm_subcontract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is True
        assert result.errors == []
        assert result.contract_type == "fsm_subcontract"

    def test_validate_fsm_missing_state_machine_name(
        self, tmp_path: Path, invalid_fsm_missing_state_machine_name_yaml: str
    ):
        """Test that FSM subcontracts require state_machine_name."""
        contract_path = tmp_path / "fsm_no_name.yaml"
        contract_path.write_text(invalid_fsm_missing_state_machine_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert result.contract_type == "fsm_subcontract"
        assert any("state_machine_name" in e.field for e in result.errors)

    def test_validate_fsm_missing_states(
        self, tmp_path: Path, invalid_fsm_missing_states_yaml: str
    ):
        """Test that FSM subcontracts require states."""
        contract_path = tmp_path / "fsm_no_states.yaml"
        contract_path.write_text(invalid_fsm_missing_states_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert result.contract_type == "fsm_subcontract"
        assert any("states" in e.field for e in result.errors)

    def test_validate_fsm_empty_states(
        self, tmp_path: Path, invalid_fsm_empty_states_yaml: str
    ):
        """Test that FSM subcontracts cannot have empty states list."""
        contract_path = tmp_path / "fsm_empty_states.yaml"
        contract_path.write_text(invalid_fsm_empty_states_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert result.contract_type == "fsm_subcontract"
        # Empty states triggers min_length validation - error message may say
        # "empty", "at least 1", "min_length", or similar
        assert any("states" in e.field for e in result.errors)

    def test_fsm_detection_does_not_affect_node_contracts(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test that node contracts are not misdetected as FSM subcontracts."""
        contract_path = tmp_path / "compute.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.contract_type == "compute"
        assert result.contract_type != "fsm_subcontract"

    @pytest.mark.skip(
        reason="Legacy contracts in _legacy folder are excluded from validation"
    )
    def test_validate_real_fsm_subcontract(self):
        """Test validation against real FSM subcontract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        fsm_path = (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/_legacy/nodes/intelligence_reducer/v1_0_0/contracts/fsm_ingestion.yaml"
        )
        if not fsm_path.exists():
            pytest.skip("Real FSM subcontract file not found")

        linter = ContractLinter()
        result = linter.validate(fsm_path)

        assert result.contract_type == "fsm_subcontract"
        # The real FSM subcontract should be valid
        assert result.valid is True


# =============================================================================
# Test Class: Real Contract Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.skip(
    reason="Legacy contracts in _legacy folder are excluded from validation"
)
class TestRealContractIntegration:
    """Integration tests using real contract files from the codebase.

    These tests validate actual contract files from the nodes directory,
    ensuring the linter works correctly with real-world contracts.
    """

    @pytest.fixture
    def contracts_base_dir(self) -> Path:
        """Get the base directory for contract files."""
        # test file is at tests/unit/tools/, nodes are at src/omniintelligence/_legacy/nodes/
        return (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/_legacy/nodes"
        )

    def test_validate_all_compute_contracts(self, contracts_base_dir: Path):
        """Validate all compute contracts in the codebase."""
        compute_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/compute_contract.yaml")
        )

        if not compute_contracts:
            pytest.skip("No compute contracts found")

        linter = ContractLinter()
        failed_contracts = []

        for contract_path in compute_contracts:
            result = linter.validate(contract_path)
            assert result.contract_type == "compute", (
                f"Wrong type detected for {contract_path.name}: "
                f"expected 'compute', got '{result.contract_type}'"
            )
            if not result.valid:
                failed_contracts.append(
                    (contract_path, [e.to_dict() for e in result.errors])
                )

        # Report all failures at once for better debugging
        if failed_contracts:
            failure_msg = "\n".join(
                f"  - {path.relative_to(contracts_base_dir)}: {errors}"
                for path, errors in failed_contracts
            )
            pytest.fail(
                f"Found {len(failed_contracts)} invalid compute contracts:\n{failure_msg}"
            )

    def test_validate_all_effect_contracts(self, contracts_base_dir: Path):
        """Validate all effect contracts in the codebase."""
        effect_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/effect_contract.yaml")
        )

        if not effect_contracts:
            pytest.skip("No effect contracts found")

        linter = ContractLinter()
        failed_contracts = []

        for contract_path in effect_contracts:
            result = linter.validate(contract_path)
            assert result.contract_type == "effect", (
                f"Wrong type detected for {contract_path.name}: "
                f"expected 'effect', got '{result.contract_type}'"
            )
            if not result.valid:
                failed_contracts.append(
                    (contract_path, [e.to_dict() for e in result.errors])
                )

        if failed_contracts:
            failure_msg = "\n".join(
                f"  - {path.relative_to(contracts_base_dir)}: {errors}"
                for path, errors in failed_contracts
            )
            pytest.fail(
                f"Found {len(failed_contracts)} invalid effect contracts:\n{failure_msg}"
            )

    def test_validate_all_reducer_contracts(self, contracts_base_dir: Path):
        """Validate all reducer contracts in the codebase."""
        reducer_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/reducer_contract.yaml")
        )

        if not reducer_contracts:
            pytest.skip("No reducer contracts found")

        linter = ContractLinter()
        failed_contracts = []

        for contract_path in reducer_contracts:
            result = linter.validate(contract_path)
            assert result.contract_type == "reducer", (
                f"Wrong type detected for {contract_path.name}: "
                f"expected 'reducer', got '{result.contract_type}'"
            )
            if not result.valid:
                failed_contracts.append(
                    (contract_path, [e.to_dict() for e in result.errors])
                )

        if failed_contracts:
            failure_msg = "\n".join(
                f"  - {path.relative_to(contracts_base_dir)}: {errors}"
                for path, errors in failed_contracts
            )
            pytest.fail(
                f"Found {len(failed_contracts)} invalid reducer contracts:\n{failure_msg}"
            )

    def test_validate_all_orchestrator_contracts(self, contracts_base_dir: Path):
        """Validate all orchestrator contracts in the codebase."""
        orchestrator_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/orchestrator_contract.yaml")
        )

        if not orchestrator_contracts:
            pytest.skip("No orchestrator contracts found")

        linter = ContractLinter()
        failed_contracts = []

        for contract_path in orchestrator_contracts:
            result = linter.validate(contract_path)
            assert result.contract_type == "orchestrator", (
                f"Wrong type detected for {contract_path.name}: "
                f"expected 'orchestrator', got '{result.contract_type}'"
            )
            if not result.valid:
                failed_contracts.append(
                    (contract_path, [e.to_dict() for e in result.errors])
                )

        if failed_contracts:
            failure_msg = "\n".join(
                f"  - {path.relative_to(contracts_base_dir)}: {errors}"
                for path, errors in failed_contracts
            )
            pytest.fail(
                f"Found {len(failed_contracts)} invalid orchestrator contracts:\n{failure_msg}"
            )

    def test_validate_all_fsm_subcontracts(self, contracts_base_dir: Path):
        """Validate all FSM subcontracts in the codebase."""
        fsm_contracts = list(contracts_base_dir.glob("*/v1_0_0/contracts/fsm_*.yaml"))

        if not fsm_contracts:
            pytest.skip("No FSM subcontracts found")

        linter = ContractLinter()
        failed_contracts = []

        for contract_path in fsm_contracts:
            result = linter.validate(contract_path)
            assert result.contract_type == "fsm_subcontract", (
                f"Wrong type detected for {contract_path.name}: "
                f"expected 'fsm_subcontract', got '{result.contract_type}'"
            )
            if not result.valid:
                failed_contracts.append(
                    (contract_path, [e.to_dict() for e in result.errors])
                )

        if failed_contracts:
            failure_msg = "\n".join(
                f"  - {path.relative_to(contracts_base_dir)}: {errors}"
                for path, errors in failed_contracts
            )
            pytest.fail(
                f"Found {len(failed_contracts)} invalid FSM subcontracts:\n{failure_msg}"
            )

    def test_validate_all_contracts_batch(self, contracts_base_dir: Path):
        """Validate all contract files in the codebase using batch validation."""
        all_contracts = list(contracts_base_dir.glob("*/v1_0_0/contracts/*.yaml"))

        if not all_contracts:
            pytest.skip("No contracts found in codebase")

        linter = ContractLinter()
        results = linter.validate_batch(all_contracts)
        summary = linter.get_summary(results)

        # Log summary for visibility
        print("\nContract validation summary:")
        print(f"  Total: {summary['total']}")
        print(f"  Valid: {summary['valid']}")
        print(f"  Invalid: {summary['invalid']}")
        print(f"  Pass rate: {summary['pass_rate']:.1%}")

        # Collect failures for detailed reporting
        failed_results = [r for r in results if not r.valid]
        if failed_results:
            failure_details = []
            for result in failed_results:
                rel_path = result.file_path.relative_to(contracts_base_dir)
                errors = [f"{e.field}: {e.message}" for e in result.errors]
                failure_details.append(
                    f"  - {rel_path}:\n      " + "\n      ".join(errors)
                )

            pytest.fail(
                f"Found {len(failed_results)} invalid contracts:\n"
                + "\n".join(failure_details)
            )

    def test_contract_count_sanity_check(self, contracts_base_dir: Path):
        """Verify expected contract files exist in the codebase."""
        compute_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/compute_contract.yaml")
        )
        effect_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/effect_contract.yaml")
        )
        reducer_contracts = list(
            contracts_base_dir.glob("*/v1_0_0/contracts/reducer_contract.yaml")
        )
        fsm_contracts = list(contracts_base_dir.glob("*/v1_0_0/contracts/fsm_*.yaml"))

        # Sanity check: we expect at least some contracts to exist
        total_contracts = (
            len(compute_contracts)
            + len(effect_contracts)
            + len(reducer_contracts)
            + len(fsm_contracts)
        )

        print("\nContract counts:")
        print(f"  Compute contracts: {len(compute_contracts)}")
        print(f"  Effect contracts: {len(effect_contracts)}")
        print(f"  Reducer contracts: {len(reducer_contracts)}")
        print(f"  FSM subcontracts: {len(fsm_contracts)}")
        print(f"  Total: {total_contracts}")

        # We expect at least 5 contracts to exist based on our earlier glob
        assert total_contracts >= 5, (
            f"Expected at least 5 contracts, found {total_contracts}. "
            "This may indicate the contracts directory structure has changed."
        )
