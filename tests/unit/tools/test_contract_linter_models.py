# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter model/dataclass structures.

Tests for ModelContractValidationResult and ModelContractValidationError data structures
used by the Contract Linter CLI.

Note: These tests require omnibase_core to be installed.
"""

from pathlib import Path

import pytest

# Skip entire module if omnibase_core is not available
pytest.importorskip(
    "omnibase_core", reason="omnibase_core required for contract linter tests"
)

from omniintelligence.tools.contract_linter import (
    EnumContractErrorType,
    ModelContractValidationError,
    ModelContractValidationResult,
)

# =============================================================================
# Test Class: ModelContractValidationResult
# =============================================================================


@pytest.mark.unit
class TestModelContractValidationResult:
    """Tests for ModelContractValidationResult data structure."""

    def test_result_success_creation(self):
        """Test creating a successful validation result."""
        result = ModelContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            is_valid=True,
            validation_errors=[],
            contract_type="compute",
        )

        assert result.is_valid is True
        assert result.file_path == Path("/path/to/contract.yaml")
        assert result.validation_errors == []
        assert result.contract_type == "compute"

    def test_result_failure_creation(self):
        """Test creating a failed validation result."""
        errors = [
            ModelContractValidationError(
                field_path="name",
                error_message="Field required",
                validation_error_type=EnumContractErrorType.MISSING_FIELD,
            )
        ]
        result = ModelContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            is_valid=False,
            validation_errors=errors,
            contract_type=None,
        )

        assert result.is_valid is False
        assert len(result.validation_errors) == 1
        assert result.validation_errors[0].field_path == "name"
        assert result.contract_type is None

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ModelContractValidationResult(
            file_path=Path("/path/to/contract.yaml"),
            is_valid=True,
            validation_errors=[],
            contract_type="effect",
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["is_valid"] is True
        assert result_dict["file_path"] == "/path/to/contract.yaml"
        assert result_dict["contract_type"] == "effect"


# =============================================================================
# Test Class: ModelContractValidationError
# =============================================================================


@pytest.mark.unit
class TestModelContractValidationError:
    """Tests for ModelContractValidationError structure with field paths."""

    def test_error_creation(self):
        """Test creating a validation error."""
        error = ModelContractValidationError(
            field_path="name",
            error_message="Field required",
            validation_error_type=EnumContractErrorType.MISSING_FIELD,
        )

        assert error.field_path == "name"
        assert error.error_message == "Field required"
        assert error.validation_error_type is EnumContractErrorType.MISSING_FIELD

    def test_error_with_nested_field_path(self):
        """Test error with nested field path (e.g., version.major)."""
        error = ModelContractValidationError(
            field_path="version.major",
            error_message="Value must be a non-negative integer",
            validation_error_type=EnumContractErrorType.INVALID_VALUE,
        )

        assert error.field_path == "version.major"
        assert "non-negative integer" in error.error_message

    def test_error_with_list_index_path(self):
        """Test error with list index in field path (e.g., io_operations.0.name)."""
        error = ModelContractValidationError(
            field_path="io_operations.0.name",
            error_message="Field required",
            validation_error_type=EnumContractErrorType.MISSING_FIELD,
        )

        assert error.field_path == "io_operations.0.name"

    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        error = ModelContractValidationError(
            field_path="node_type",
            error_message="Invalid value 'invalid_type'",
            validation_error_type=EnumContractErrorType.INVALID_ENUM,
        )

        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert error_dict["field_path"] == "node_type"
        assert error_dict["error_message"] == "Invalid value 'invalid_type'"
        assert error_dict["validation_error_type"] == "invalid_enum"

    def test_error_string_representation(self):
        """Test string representation of error."""
        error = ModelContractValidationError(
            field_path="description",
            error_message="Field required",
            validation_error_type=EnumContractErrorType.MISSING_FIELD,
        )

        error_str = str(error)

        assert "description" in error_str
        assert "Field required" in error_str
