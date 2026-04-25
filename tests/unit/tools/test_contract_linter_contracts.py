# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Unit tests for Contract Linter contract type detection and validation.

Tests for contract type detection, FSM subcontract validation, and integration
tests using real contract files from the codebase.

Note: These tests require omnibase_core to be installed.
"""

from pathlib import Path

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit


def _safe_relative_path(path: Path, base: Path) -> Path | str:
    """Safely compute relative path, falling back to absolute path if not possible.

    Args:
        path: The path to make relative.
        base: The base path to make it relative to.

    Returns:
        The relative path if possible, otherwise the absolute path as a string.
    """
    try:
        return path.relative_to(base)
    except ValueError:
        # Path is not relative to base, return absolute path
        return str(path)


# Skip entire module if omnibase_core is not available
pytest.importorskip(
    "omnibase_core", reason="omnibase_core required for contract linter tests"
)

from omniintelligence.tools.contract_linter import (
    ContractLinter,
)

# =============================================================================
# Test Class: Contract Type Detection
# =============================================================================


@pytest.mark.unit
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


# =============================================================================
# Test Class: FSM Subcontract Validation
# =============================================================================


@pytest.mark.unit
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

        assert result.is_valid is True
        assert result.validation_errors == []
        assert result.contract_type == "fsm_subcontract"

    def test_validate_fsm_missing_state_machine_name(
        self, tmp_path: Path, invalid_fsm_missing_state_machine_name_yaml: str
    ):
        """Test that FSM subcontracts require state_machine_name."""
        contract_path = tmp_path / "fsm_no_name.yaml"
        contract_path.write_text(invalid_fsm_missing_state_machine_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        assert result.contract_type == "fsm_subcontract"
        assert any(
            "state_machine_name" in e.field_path for e in result.validation_errors
        )

    def test_validate_fsm_missing_states(
        self, tmp_path: Path, invalid_fsm_missing_states_yaml: str
    ):
        """Test that FSM subcontracts require states."""
        contract_path = tmp_path / "fsm_no_states.yaml"
        contract_path.write_text(invalid_fsm_missing_states_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        assert result.contract_type == "fsm_subcontract"
        assert any("states" in e.field_path for e in result.validation_errors)

    def test_validate_fsm_empty_states(
        self, tmp_path: Path, invalid_fsm_empty_states_yaml: str
    ):
        """Test that FSM subcontracts cannot have empty states list."""
        contract_path = tmp_path / "fsm_empty_states.yaml"
        contract_path.write_text(invalid_fsm_empty_states_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        assert result.contract_type == "fsm_subcontract"
        # Empty states triggers min_length validation - error message may say
        # "empty", "at least 1", "min_length", or similar
        assert any("states" in e.field_path for e in result.validation_errors)

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


# =============================================================================
# Test Class: Safe Relative Path Helper
# =============================================================================


@pytest.mark.unit
class TestSafeRelativePath:
    """Tests for the _safe_relative_path helper function."""

    def test_relative_path_when_paths_share_base(self):
        """Test that relative path is returned when paths share a common base."""
        base = Path("/project/src")
        path = Path("/project/src/module/file.py")

        result = _safe_relative_path(path, base)

        assert result == Path("module/file.py")

    def test_absolute_path_when_paths_dont_share_base(self):
        """Test that absolute path is returned when paths don't share a base."""
        base = Path("/project/src")
        path = Path("/different/location/file.py")

        result = _safe_relative_path(path, base)

        # Should return the absolute path as string when relative_to fails
        assert result == "/different/location/file.py"

    def test_relative_path_with_same_path(self):
        """Test that empty path is returned when path equals base."""
        base = Path("/project/src")
        path = Path("/project/src")

        result = _safe_relative_path(path, base)

        assert result == Path(".")

    def test_relative_path_with_nested_paths(self):
        """Test relative path with deeply nested paths."""
        base = Path("/project")
        path = Path("/project/src/deep/nested/module/file.py")

        result = _safe_relative_path(path, base)

        assert result == Path("src/deep/nested/module/file.py")

    def test_absolute_path_when_base_is_child_of_path(self):
        """Test that absolute path is returned when base is a child of path."""
        base = Path("/project/src/module")
        path = Path("/project/src/file.py")

        result = _safe_relative_path(path, base)

        # Path is not under base, so absolute path should be returned
        assert result == "/project/src/file.py"

    def test_cross_drive_paths_on_windows_style(self, tmp_path: Path):
        """Test handling of paths that simulate cross-drive scenarios."""
        # Use tmp_path as a real base and create an unrelated path
        base = tmp_path / "project"
        path = Path("/completely/different/location/file.py")

        result = _safe_relative_path(path, base)

        # Should return absolute path when no common base
        assert result == "/completely/different/location/file.py"
