# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter model/dataclass structures.

Tests for ContractValidationResult and ContractValidationError data structures
used by the Contract Linter CLI.
"""

from pathlib import Path

import pytest

from omniintelligence.tools.contract_linter import (
    ContractValidationError,
    ContractValidationResult,
    EnumContractErrorType,
)

# =============================================================================
# Test Class: ContractValidationResult
# =============================================================================


@pytest.mark.unit
class TestContractValidationResult:
    """Tests for ContractValidationResult data structure."""

    def test_result_success_creation(self):
        """Test creating a successful validation result."""
        result = ContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            valid=True,
            errors=[],
            contract_type="compute",
        )

        assert result.valid is True
        assert result.file_path == Path("/path/to/contract.yaml")
        assert result.errors == []
        assert result.contract_type == "compute"

    def test_result_failure_creation(self):
        """Test creating a failed validation result."""
        errors = [
            ContractValidationError(
                field="name",
                message="Field required",
                error_type=EnumContractErrorType.MISSING_FIELD,
            )
        ]
        result = ContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            valid=False,
            errors=errors,
            contract_type=None,
        )

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].field == "name"
        assert result.contract_type is None

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            valid=True,
            errors=[],
            contract_type="effect",
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["valid"] is True
        assert result_dict["file_path"] == "/path/to/contract.yaml"
        assert result_dict["contract_type"] == "effect"


# =============================================================================
# Test Class: ContractValidationError
# =============================================================================


@pytest.mark.unit
class TestContractValidationError:
    """Tests for ContractValidationError structure with field paths."""

    def test_error_creation(self):
        """Test creating a validation error."""
        error = ContractValidationError(
            field="name",
            message="Field required",
            error_type=EnumContractErrorType.MISSING_FIELD,
        )

        assert error.field == "name"
        assert error.message == "Field required"
        assert error.error_type is EnumContractErrorType.MISSING_FIELD

    def test_error_with_nested_field_path(self):
        """Test error with nested field path (e.g., version.major)."""
        error = ContractValidationError(
            field="version.major",
            message="Value must be a non-negative integer",
            error_type=EnumContractErrorType.INVALID_VALUE,
        )

        assert error.field == "version.major"
        assert "non-negative integer" in error.message

    def test_error_with_list_index_path(self):
        """Test error with list index in field path (e.g., io_operations.0.name)."""
        error = ContractValidationError(
            field="io_operations.0.name",
            message="Field required",
            error_type=EnumContractErrorType.MISSING_FIELD,
        )

        assert error.field == "io_operations.0.name"

    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        error = ContractValidationError(
            field="node_type",
            message="Invalid value 'invalid_type'",
            error_type=EnumContractErrorType.INVALID_ENUM,
        )

        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert error_dict["field"] == "node_type"
        assert error_dict["message"] == "Invalid value 'invalid_type'"
        assert error_dict["error_type"] == "invalid_enum"

    def test_error_string_representation(self):
        """Test string representation of error."""
        error = ContractValidationError(
            field="description",
            message="Field required",
            error_type=EnumContractErrorType.MISSING_FIELD,
        )

        error_str = str(error)

        assert "description" in error_str
        assert "Field required" in error_str
