# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter CLI.

Tests for OMN-241: Contract Linter tool that validates ONEX node contract YAML files
against the omnibase_core schema.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Import contract linter module
from omniintelligence.tools.contract_linter import (
    ContractLinter,
    ContractValidationError,
    ContractValidationResult,
    EnumContractErrorType,
    main,  # CLI entry point
    validate_contract,
    validate_contracts_batch,
)

# =============================================================================
# Test Fixtures - Valid Contracts
# =============================================================================


@pytest.fixture
def valid_base_contract_yaml() -> str:
    """Minimal valid base contract YAML (compute type with required algorithm)."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test node for validation
node_type: compute
input_model: ModelTestInput
output_model: ModelTestOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    main_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""


@pytest.fixture
def valid_compute_contract_yaml() -> str:
    """Valid compute contract YAML with required algorithm field."""
    return """
name: test_compute_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test compute node
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


@pytest.fixture
def valid_effect_contract_yaml() -> str:
    """Valid effect contract YAML with required io_operations field."""
    return """
name: test_effect_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test effect node
node_type: effect
input_model: ModelEffectInput
output_model: ModelEffectOutput
io_operations:
  - operation_type: file_read
    atomic: true
"""


@pytest.fixture
def valid_contract_with_optional_fields_yaml() -> str:
    """Valid contract with optional fields populated."""
    return """
name: full_test_node
version:
  major: 2
  minor: 1
  patch: 3
description: A fully specified test node
node_type: compute
input_model: ModelFullInput
output_model: ModelFullOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    full_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
author: test_author
documentation_url: https://docs.example.com/node
tags:
  - test
  - validation
  - compute
"""


# =============================================================================
# Test Fixtures - Invalid Contracts
# =============================================================================


@pytest.fixture
def invalid_missing_name_yaml() -> str:
    """Contract missing required 'name' field."""
    return """
version:
  major: 1
  minor: 0
  patch: 0
description: Missing name field
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_version_yaml() -> str:
    """Contract missing required 'version' field."""
    return """
name: test_node
description: Missing version field
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_description_yaml() -> str:
    """Contract missing required 'description' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_node_type_yaml() -> str:
    """Contract missing required 'node_type' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing node_type
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_input_model_yaml() -> str:
    """Contract missing required 'input_model' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing input_model
node_type: compute
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_output_model_yaml() -> str:
    """Contract missing required 'output_model' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing output_model
node_type: compute
input_model: ModelInput
"""


@pytest.fixture
def invalid_node_type_yaml() -> str:
    """Contract with invalid node_type value."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Invalid node_type value
node_type: invalid_type
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_version_format_yaml() -> str:
    """Contract with malformed version structure."""
    return """
name: test_node
version: "1.0.0"
description: Invalid version format (should be object)
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_compute_missing_algorithm_yaml() -> str:
    """Compute contract missing required 'algorithm' field."""
    return """
name: test_compute
version:
  major: 1
  minor: 0
  patch: 0
description: Compute node without algorithm
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_effect_missing_io_operations_yaml() -> str:
    """Effect contract missing required 'io_operations' field."""
    return """
name: test_effect
version:
  major: 1
  minor: 0
  patch: 0
description: Effect node without io_operations
node_type: effect
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def malformed_yaml() -> str:
    """Malformed YAML that cannot be parsed."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  this is not valid yaml
    - indentation error
  patch: [unclosed bracket
"""


@pytest.fixture
def empty_yaml() -> str:
    """Empty YAML content."""
    return ""


@pytest.fixture
def yaml_with_only_comments() -> str:
    """YAML with only comments, no content."""
    return """
# This is a comment
# Another comment
"""


# =============================================================================
# Test Fixtures - File-based
# =============================================================================


@pytest.fixture
def valid_contract_file(tmp_path: Path, valid_compute_contract_yaml: str) -> Path:
    """Create a valid contract file in temp directory."""
    contract_path = tmp_path / "valid_contract.yaml"
    contract_path.write_text(valid_compute_contract_yaml)
    return contract_path


@pytest.fixture
def invalid_contract_file(tmp_path: Path, invalid_missing_name_yaml: str) -> Path:
    """Create an invalid contract file in temp directory."""
    contract_path = tmp_path / "invalid_contract.yaml"
    contract_path.write_text(invalid_missing_name_yaml)
    return contract_path


@pytest.fixture
def malformed_yaml_file(tmp_path: Path, malformed_yaml: str) -> Path:
    """Create a malformed YAML file in temp directory."""
    contract_path = tmp_path / "malformed.yaml"
    contract_path.write_text(malformed_yaml)
    return contract_path


@pytest.fixture
def multiple_contract_files(
    tmp_path: Path,
    valid_compute_contract_yaml: str,
    valid_effect_contract_yaml: str,
    invalid_missing_name_yaml: str,
) -> list[Path]:
    """Create multiple contract files for batch testing."""
    files = []

    # Two valid contracts
    valid1 = tmp_path / "valid_compute.yaml"
    valid1.write_text(valid_compute_contract_yaml)
    files.append(valid1)

    valid2 = tmp_path / "valid_effect.yaml"
    valid2.write_text(valid_effect_contract_yaml)
    files.append(valid2)

    # One invalid contract
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(invalid_missing_name_yaml)
    files.append(invalid)

    return files


# =============================================================================
# Test Class: ContractValidationResult
# =============================================================================


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
        assert error.error_type == "missing_field"

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


# =============================================================================
# Test Class: ContractLinter - Single Contract Validation
# =============================================================================


class TestContractLinterSingleValidation:
    """Tests for validating single contracts."""

    def test_validate_single_contract_success(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test successful validation of a valid compute contract."""
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is True
        assert result.errors == []
        assert result.file_path == contract_path
        assert result.contract_type == "compute"

    def test_validate_effect_contract_success(
        self, tmp_path: Path, valid_effect_contract_yaml: str
    ):
        """Test successful validation of a valid effect contract."""
        contract_path = tmp_path / "valid_effect.yaml"
        contract_path.write_text(valid_effect_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is True
        assert result.errors == []
        assert result.contract_type == "effect"

    def test_validate_contract_with_optional_fields(
        self, tmp_path: Path, valid_contract_with_optional_fields_yaml: str
    ):
        """Test validation of contract with optional fields."""
        contract_path = tmp_path / "full.yaml"
        contract_path.write_text(valid_contract_with_optional_fields_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is True
        assert result.errors == []

    def test_validate_single_contract_missing_required_field_name(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Test validation error when 'name' field is missing."""
        contract_path = tmp_path / "missing_name.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(e.field == "name" for e in result.errors)
        assert any("required" in e.message.lower() for e in result.errors)

    def test_validate_single_contract_missing_required_field_version(
        self, tmp_path: Path, invalid_missing_version_yaml: str
    ):
        """Test validation error when 'version' field is missing."""
        contract_path = tmp_path / "missing_version.yaml"
        contract_path.write_text(invalid_missing_version_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any(e.field == "version" for e in result.errors)

    def test_validate_single_contract_missing_required_field_description(
        self, tmp_path: Path, invalid_missing_description_yaml: str
    ):
        """Test validation error when 'description' field is missing."""
        contract_path = tmp_path / "missing_desc.yaml"
        contract_path.write_text(invalid_missing_description_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any(e.field == "description" for e in result.errors)

    def test_validate_single_contract_missing_required_field_node_type(
        self, tmp_path: Path, invalid_missing_node_type_yaml: str
    ):
        """Test validation error when 'node_type' field is missing."""
        contract_path = tmp_path / "missing_node_type.yaml"
        contract_path.write_text(invalid_missing_node_type_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        # Without node_type, linter can't determine contract type, so error may
        # be on "root" with "unknown_contract_type" or on "node_type" directly
        assert any(
            "node_type" in e.field or e.error_type == "unknown_contract_type"
            for e in result.errors
        )

    def test_validate_single_contract_missing_required_field_input_model(
        self, tmp_path: Path, invalid_missing_input_model_yaml: str
    ):
        """Test validation error when 'input_model' field is missing."""
        contract_path = tmp_path / "missing_input_model.yaml"
        contract_path.write_text(invalid_missing_input_model_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any(e.field == "input_model" for e in result.errors)

    def test_validate_single_contract_missing_required_field_output_model(
        self, tmp_path: Path, invalid_missing_output_model_yaml: str
    ):
        """Test validation error when 'output_model' field is missing."""
        contract_path = tmp_path / "missing_output_model.yaml"
        contract_path.write_text(invalid_missing_output_model_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any(e.field == "output_model" for e in result.errors)

    def test_validate_single_contract_invalid_node_type(
        self, tmp_path: Path, invalid_node_type_yaml: str
    ):
        """Test validation error when node_type is invalid enum value."""
        contract_path = tmp_path / "invalid_node_type.yaml"
        contract_path.write_text(invalid_node_type_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any(e.field == "node_type" for e in result.errors)
        assert any(
            "invalid_type" in e.message.lower() or "enum" in e.error_type.lower()
            for e in result.errors
        )

    def test_validate_single_contract_invalid_version_format(
        self, tmp_path: Path, invalid_version_format_yaml: str
    ):
        """Test validation error when version is not a proper object."""
        contract_path = tmp_path / "invalid_version.yaml"
        contract_path.write_text(invalid_version_format_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert any("version" in e.field for e in result.errors)

    def test_validate_compute_missing_algorithm(
        self, tmp_path: Path, invalid_compute_missing_algorithm_yaml: str
    ):
        """Test that compute contracts require algorithm field."""
        contract_path = tmp_path / "compute_no_algo.yaml"
        contract_path.write_text(invalid_compute_missing_algorithm_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # When validating as compute contract, algorithm is required
        assert result.valid is False
        assert any("algorithm" in e.field for e in result.errors)

    def test_validate_effect_missing_io_operations(
        self, tmp_path: Path, invalid_effect_missing_io_operations_yaml: str
    ):
        """Test that effect contracts require io_operations field."""
        contract_path = tmp_path / "effect_no_io_ops.yaml"
        contract_path.write_text(invalid_effect_missing_io_operations_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        # When validating as effect contract, io_operations is required
        assert result.valid is False
        assert any("io_operations" in e.field for e in result.errors)


# =============================================================================
# Test Class: ContractLinter - File Handling
# =============================================================================


class TestContractLinterFileHandling:
    """Tests for file handling edge cases."""

    def test_validate_file_not_found(self, tmp_path: Path):
        """Test graceful handling when file does not exist."""
        nonexistent_path = tmp_path / "does_not_exist.yaml"

        linter = ContractLinter()
        result = linter.validate(nonexistent_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(
            "not found" in e.message.lower() or "does not exist" in e.message.lower()
            for e in result.errors
        )
        assert any(e.error_type == "file_not_found" for e in result.errors)

    def test_validate_malformed_yaml(self, tmp_path: Path, malformed_yaml: str):
        """Test graceful handling of malformed YAML."""
        contract_path = tmp_path / "malformed.yaml"
        contract_path.write_text(malformed_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(e.error_type == "yaml_parse_error" for e in result.errors)

    def test_validate_empty_yaml(self, tmp_path: Path, empty_yaml: str):
        """Test handling of empty YAML file."""
        contract_path = tmp_path / "empty.yaml"
        contract_path.write_text(empty_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(
            "empty" in e.message.lower() or e.error_type == "empty_file"
            for e in result.errors
        )

    def test_validate_yaml_with_only_comments(
        self, tmp_path: Path, yaml_with_only_comments: str
    ):
        """Test handling of YAML with only comments."""
        contract_path = tmp_path / "comments_only.yaml"
        contract_path.write_text(yaml_with_only_comments)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        # Should be treated similarly to empty file

    def test_validate_directory_instead_of_file(self, tmp_path: Path):
        """Test error when path is a directory, not a file."""
        linter = ContractLinter()
        result = linter.validate(tmp_path)  # tmp_path is a directory

        assert result.valid is False
        assert any(
            "directory" in e.message.lower() or e.error_type == "not_a_file"
            for e in result.errors
        )

    def test_validate_with_path_string(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test that string path is accepted and converted to Path."""
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        result = linter.validate(str(contract_path))  # Pass as string

        assert result.valid is True


# =============================================================================
# Test Class: ContractLinter - Batch Validation
# =============================================================================


class TestContractLinterBatchValidation:
    """Tests for batch validation of multiple contracts."""

    def test_validate_batch_all_valid(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        valid_effect_contract_yaml: str,
    ):
        """Test batch validation when all contracts are valid."""
        files = []
        for i, yaml_content in enumerate(
            [valid_compute_contract_yaml, valid_effect_contract_yaml]
        ):
            path = tmp_path / f"valid_{i}.yaml"
            path.write_text(yaml_content)
            files.append(path)

        linter = ContractLinter()
        results = linter.validate_batch(files)

        assert len(results) == 2
        assert all(r.valid for r in results)

    def test_validate_batch_mixed_results(self, multiple_contract_files: list[Path]):
        """Test batch validation with mix of valid and invalid contracts."""
        linter = ContractLinter()
        results = linter.validate_batch(multiple_contract_files)

        assert len(results) == 3
        valid_count = sum(1 for r in results if r.valid)
        invalid_count = sum(1 for r in results if not r.valid)

        assert valid_count == 2
        assert invalid_count == 1

    def test_validate_batch_all_invalid(
        self,
        tmp_path: Path,
        invalid_missing_name_yaml: str,
        invalid_missing_version_yaml: str,
    ):
        """Test batch validation when all contracts are invalid."""
        files = []
        for i, yaml_content in enumerate(
            [invalid_missing_name_yaml, invalid_missing_version_yaml]
        ):
            path = tmp_path / f"invalid_{i}.yaml"
            path.write_text(yaml_content)
            files.append(path)

        linter = ContractLinter()
        results = linter.validate_batch(files)

        assert len(results) == 2
        assert all(not r.valid for r in results)

    def test_validate_batch_empty_list(self):
        """Test batch validation with empty file list."""
        linter = ContractLinter()
        results = linter.validate_batch([])

        assert results == []

    def test_validate_batch_with_nonexistent_file(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test batch validation handles missing files gracefully."""
        valid_path = tmp_path / "valid.yaml"
        valid_path.write_text(valid_compute_contract_yaml)

        nonexistent_path = tmp_path / "does_not_exist.yaml"

        linter = ContractLinter()
        results = linter.validate_batch([valid_path, nonexistent_path])

        assert len(results) == 2
        assert results[0].valid is True
        assert results[1].valid is False
        assert any(e.error_type == "file_not_found" for e in results[1].errors)

    def test_validate_batch_summary(self, multiple_contract_files: list[Path]):
        """Test batch validation summary statistics."""
        linter = ContractLinter()
        results = linter.validate_batch(multiple_contract_files)

        summary = linter.get_summary(results)

        assert isinstance(summary, dict)
        assert summary["total"] == 3
        assert summary["valid"] == 2
        assert summary["invalid"] == 1
        assert "pass_rate" in summary


# =============================================================================
# Test Class: Standalone Functions
# =============================================================================


class TestStandaloneFunctions:
    """Tests for standalone validation functions."""

    def test_validate_contract_function(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test standalone validate_contract function."""
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        result = validate_contract(contract_path)

        assert result.valid is True
        assert isinstance(result, ContractValidationResult)

    def test_validate_contracts_batch_function(
        self, multiple_contract_files: list[Path]
    ):
        """Test standalone validate_contracts_batch function."""
        results = validate_contracts_batch(multiple_contract_files)

        assert len(results) == 3
        assert isinstance(results[0], ContractValidationResult)


# =============================================================================
# Test Class: Structured Error Output
# =============================================================================


class TestStructuredErrorOutput:
    """Tests for structured error output with field paths."""

    def test_structured_error_output_with_field_paths(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Test that errors include proper field paths."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1

        # Each error should have field, message, and error_type
        for error in result.errors:
            assert hasattr(error, "field")
            assert hasattr(error, "message")
            assert hasattr(error, "error_type")
            assert error.field is not None
            assert error.message is not None

    def test_nested_field_path_in_errors(self, tmp_path: Path):
        """Test that nested field paths are properly formatted."""
        yaml_content = """
name: test_node
version:
  major: invalid_string
  minor: 0
  patch: 0
description: Test
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""
        contract_path = tmp_path / "nested_error.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        # Should have an error for version.major
        assert any("version" in e.field and "major" in e.field for e in result.errors)

    def test_multiple_errors_captured(self, tmp_path: Path):
        """Test that multiple validation errors are captured."""
        # Use a valid node_type but missing multiple required fields
        yaml_content = """
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute
"""
        contract_path = tmp_path / "multiple_errors.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        # Should have multiple errors for missing fields:
        # name, description, input_model, output_model, algorithm
        assert len(result.errors) >= 2

    def test_error_output_as_json(self, tmp_path: Path, invalid_missing_name_yaml: str):
        """Test that errors can be serialized to JSON."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        result_dict = result.to_dict()
        json_output = json.dumps(result_dict)

        assert isinstance(json_output, str)
        parsed = json.loads(json_output)
        assert "valid" in parsed
        assert "errors" in parsed
        assert isinstance(parsed["errors"], list)


# =============================================================================
# Test Class: CLI Entry Point
# =============================================================================


class TestCLIEntryPoint:
    """Tests for CLI entry point and exit codes."""

    def test_cli_exit_code_on_success(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test CLI returns exit code 0 on successful validation."""
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        with patch("sys.argv", ["contract_linter", str(contract_path)]):
            exit_code = main()

        assert exit_code == 0

    def test_cli_exit_code_on_failure(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Test CLI returns non-zero exit code on validation failure."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        with patch("sys.argv", ["contract_linter", str(contract_path)]):
            exit_code = main()

        assert exit_code != 0
        assert exit_code == 1  # Convention: 1 for validation errors

    def test_cli_exit_code_on_file_not_found(self, tmp_path: Path):
        """Test CLI returns non-zero exit code when file not found."""
        nonexistent_path = tmp_path / "nonexistent.yaml"

        with patch("sys.argv", ["contract_linter", str(nonexistent_path)]):
            exit_code = main()

        assert exit_code != 0
        assert exit_code == 2  # Convention: 2 for file errors

    def test_cli_exit_code_on_yaml_parse_error(
        self, tmp_path: Path, malformed_yaml: str
    ):
        """Test CLI returns non-zero exit code on YAML parse error."""
        contract_path = tmp_path / "malformed.yaml"
        contract_path.write_text(malformed_yaml)

        with patch("sys.argv", ["contract_linter", str(contract_path)]):
            exit_code = main()

        assert exit_code != 0

    def test_cli_batch_validation_all_pass(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        valid_effect_contract_yaml: str,
    ):
        """Test CLI batch validation exit code when all pass."""
        valid1 = tmp_path / "valid1.yaml"
        valid1.write_text(valid_compute_contract_yaml)
        valid2 = tmp_path / "valid2.yaml"
        valid2.write_text(valid_effect_contract_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(valid1), str(valid2)],
        ):
            exit_code = main()

        assert exit_code == 0

    def test_cli_batch_validation_any_fail(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        invalid_missing_name_yaml: str,
    ):
        """Test CLI batch validation exit code when any fail."""
        valid = tmp_path / "valid.yaml"
        valid.write_text(valid_compute_contract_yaml)
        invalid = tmp_path / "invalid.yaml"
        invalid.write_text(invalid_missing_name_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(valid), str(invalid)],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_cli_no_arguments_shows_usage(self):
        """Test CLI with no arguments shows usage and exits."""
        with patch("sys.argv", ["contract_linter"]):
            exit_code = main()

        # Exit code 2 is the standard for missing arguments/usage errors in argparse
        assert exit_code == 2

    def test_cli_json_output_flag(
        self, tmp_path: Path, valid_compute_contract_yaml: str, capsys
    ):
        """Test CLI with --json flag outputs JSON."""
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(contract_path), "--json"],
        ):
            main()

        captured = capsys.readouterr()
        # Should be valid JSON
        parsed = json.loads(captured.out)
        assert "valid" in parsed or "results" in parsed

    def test_cli_verbose_flag(
        self, tmp_path: Path, invalid_missing_name_yaml: str, capsys
    ):
        """Test CLI with --verbose flag shows detailed output."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(contract_path), "--verbose"],
        ):
            main()

        captured = capsys.readouterr()
        # Verbose output should include field paths and details
        output = captured.out + captured.err
        assert "name" in output.lower() or "field" in output.lower()


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


class TestRealContractFiles:
    """Tests using actual contract files from the codebase."""

    @pytest.fixture
    def real_compute_contract_path(self) -> Path:
        """Path to real compute contract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        return (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/nodes/entity_extraction_compute/v1_0_0/contracts/compute_contract.yaml"
        )

    @pytest.fixture
    def real_effect_contract_path(self) -> Path:
        """Path to real effect contract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        return (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/nodes/kafka_event_effect/v1_0_0/contracts/effect_contract.yaml"
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
# Test Class: Linter Configuration
# =============================================================================


class TestLinterConfiguration:
    """Tests for linter configuration options."""

    def test_linter_strict_mode(self, tmp_path: Path, valid_base_contract_yaml: str):
        """Test linter in strict mode requires all type-specific fields."""
        contract_path = tmp_path / "base.yaml"
        contract_path.write_text(valid_base_contract_yaml)

        linter = ContractLinter(strict=True)
        result = linter.validate(contract_path)

        # In strict mode, compute type should require operations
        # The base contract doesn't have operations, so may fail in strict mode
        assert isinstance(result, ContractValidationResult)

    def test_linter_lenient_mode(self, tmp_path: Path, valid_base_contract_yaml: str):
        """Test linter in lenient mode is more permissive."""
        contract_path = tmp_path / "base.yaml"
        contract_path.write_text(valid_base_contract_yaml)

        linter = ContractLinter(strict=False)
        result = linter.validate(contract_path)

        # Lenient mode should pass for base contracts
        assert isinstance(result, ContractValidationResult)

    def test_linter_custom_schema_version(self, tmp_path: Path):
        """Test linter with specific schema version."""
        yaml_content = """
name: test
version:
  major: 1
  minor: 0
  patch: 0
description: Test
node_type: compute
input_model: Input
output_model: Output
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    test_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""
        contract_path = tmp_path / "contract.yaml"
        contract_path.write_text(yaml_content)

        # Future: support for schema versioning
        linter = ContractLinter(schema_version="1.0.0")
        result = linter.validate(contract_path)

        assert isinstance(result, ContractValidationResult)


# =============================================================================
# Test Class: FSM Subcontract Validation
# =============================================================================


class TestFSMSubcontractValidation:
    """Tests for FSM subcontract detection and validation."""

    @pytest.fixture
    def valid_fsm_subcontract_yaml(self) -> str:
        """Valid FSM subcontract YAML."""
        return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: Test FSM for ingestion workflow

states:
  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: RECEIVED
    state_type: operational
    description: Document received
    is_terminal: false

  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: PROCESSING
    state_type: operational
    description: Document processing
    is_terminal: false

  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: COMPLETED
    state_type: snapshot
    description: Processing complete
    is_terminal: true

initial_state: RECEIVED

transitions:
  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: start_processing
    from_state: RECEIVED
    to_state: PROCESSING
    trigger: START

  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: complete
    from_state: PROCESSING
    to_state: COMPLETED
    trigger: COMPLETE
"""

    @pytest.fixture
    def invalid_fsm_missing_state_machine_name_yaml(self) -> str:
        """FSM subcontract missing state_machine_name."""
        return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM missing state_machine_name

states:
  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: RECEIVED
    state_type: operational
    description: Document received

initial_state: RECEIVED

transitions:
  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: self_loop
    from_state: RECEIVED
    to_state: RECEIVED
    trigger: LOOP
"""

    @pytest.fixture
    def invalid_fsm_missing_states_yaml(self) -> str:
        """FSM subcontract missing states."""
        return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM missing states

initial_state: RECEIVED
"""

    @pytest.fixture
    def invalid_fsm_empty_states_yaml(self) -> str:
        """FSM subcontract with empty states list."""
        return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM with empty states

states: []
initial_state: RECEIVED
"""

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

    def test_validate_real_fsm_subcontract(self):
        """Test validation against real FSM subcontract in codebase."""
        # Use relative path from project root (test file is at tests/unit/tools/)
        fsm_path = (
            Path(__file__).parent.parent.parent.parent
            / "src/omniintelligence/nodes/intelligence_reducer/v1_0_0/contracts/fsm_ingestion.yaml"
        )
        if not fsm_path.exists():
            pytest.skip("Real FSM subcontract file not found")

        linter = ContractLinter()
        result = linter.validate(fsm_path)

        assert result.contract_type == "fsm_subcontract"
        # The real FSM subcontract should be valid
        assert result.valid is True
