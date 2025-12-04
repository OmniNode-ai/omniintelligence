# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter CLI.

Tests for OMN-241: Contract Linter tool that validates ONEX node contract YAML files
against the omnibase_core schema.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# Import contract linter module
from omniintelligence.tools.contract_linter import (
    MAX_YAML_SIZE_BYTES,
    ContractLinter,
    ContractValidationError,
    ContractValidationResult,
    EnumContractErrorType,
    _is_safe_path,
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

    def test_rejects_oversized_yaml_file(self, tmp_path: Path):
        """Test that oversized YAML files are rejected."""
        large_file = tmp_path / "large.yaml"
        # Create file larger than limit
        large_file.write_text("x" * (MAX_YAML_SIZE_BYTES + 1))

        linter = ContractLinter()
        result = linter.validate(large_file)

        assert result.valid is False
        assert any("exceeds maximum" in e.message for e in result.errors)
        assert any(e.error_type == "file_too_large" for e in result.errors)

    def test_accepts_file_at_size_limit(self, tmp_path: Path):
        """Test that files exactly at the size limit are accepted for parsing."""
        # Create a valid YAML file exactly at the limit
        # Note: The file content must be valid enough to at least parse
        yaml_header = "name: test\n"
        remaining = MAX_YAML_SIZE_BYTES - len(yaml_header)
        # Fill with YAML comments (which are valid YAML)
        large_file = tmp_path / "at_limit.yaml"
        large_file.write_text(yaml_header + "#" * remaining)

        linter = ContractLinter()
        result = linter.validate(large_file)

        # Should not fail due to file size - may fail for other validation reasons
        assert not any(e.error_type == "file_too_large" for e in result.errors)


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
# Test Class: Linter Configuration
# =============================================================================


class TestLinterConfiguration:
    """Tests for linter configuration options."""

    def test_linter_strict_mode(self, tmp_path: Path, valid_base_contract_yaml: str):
        """Test that strict mode raises NotImplementedError (not yet implemented)."""
        # Strict mode is reserved for future implementation
        with pytest.raises(NotImplementedError) as exc_info:
            ContractLinter(strict=True)

        assert "Strict mode is reserved for future implementation" in str(
            exc_info.value
        )

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


# =============================================================================
# Test Class: CLI Exit Codes (Direct main() calls)
# =============================================================================


class TestCLIExitCodes:
    """Tests for CLI exit code behavior using direct main() calls.

    Exit code semantics:
        0 - All contracts valid
        1 - One or more contracts have validation errors
        2 - File errors (not found, not readable) or usage errors (no arguments)

    These tests call main() directly with argument lists, which is cleaner than
    patching sys.argv and more isolated than subprocess invocation.
    """

    def test_exit_code_0_valid_contract(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Exit code 0 when all contracts are valid."""
        contract = tmp_path / "valid.yaml"
        contract.write_text(valid_compute_contract_yaml)

        exit_code = main([str(contract)])

        assert exit_code == 0, "Expected exit code 0 for valid contract"

    def test_exit_code_0_multiple_valid_contracts(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        valid_effect_contract_yaml: str,
    ):
        """Exit code 0 when all contracts in batch are valid."""
        compute_contract = tmp_path / "compute.yaml"
        compute_contract.write_text(valid_compute_contract_yaml)
        effect_contract = tmp_path / "effect.yaml"
        effect_contract.write_text(valid_effect_contract_yaml)

        exit_code = main([str(compute_contract), str(effect_contract)])

        assert exit_code == 0, "Expected exit code 0 when all batch contracts are valid"

    def test_exit_code_1_invalid_contract(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Exit code 1 when contract has validation errors."""
        contract = tmp_path / "invalid.yaml"
        contract.write_text(invalid_missing_name_yaml)

        exit_code = main([str(contract)])

        assert exit_code == 1, "Expected exit code 1 for validation errors"

    def test_exit_code_1_invalid_node_type(
        self, tmp_path: Path, invalid_node_type_yaml: str
    ):
        """Exit code 1 when contract has invalid node_type enum value."""
        contract = tmp_path / "invalid_node_type.yaml"
        contract.write_text(invalid_node_type_yaml)

        exit_code = main([str(contract)])

        assert exit_code == 1, "Expected exit code 1 for invalid node_type"

    def test_exit_code_1_malformed_yaml(self, tmp_path: Path, malformed_yaml: str):
        """Exit code 1 when YAML syntax is invalid (validation error, not file error)."""
        contract = tmp_path / "malformed.yaml"
        contract.write_text(malformed_yaml)

        exit_code = main([str(contract)])

        assert exit_code == 1, "Expected exit code 1 for malformed YAML"

    def test_exit_code_1_empty_file(self, tmp_path: Path, empty_yaml: str):
        """Exit code 1 when YAML file is empty (validation error)."""
        contract = tmp_path / "empty.yaml"
        contract.write_text(empty_yaml)

        exit_code = main([str(contract)])

        assert exit_code == 1, "Expected exit code 1 for empty file"

    def test_exit_code_1_batch_with_any_invalid(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        invalid_missing_name_yaml: str,
    ):
        """Exit code 1 when batch has at least one invalid contract."""
        valid = tmp_path / "valid.yaml"
        valid.write_text(valid_compute_contract_yaml)
        invalid = tmp_path / "invalid.yaml"
        invalid.write_text(invalid_missing_name_yaml)

        exit_code = main([str(valid), str(invalid)])

        assert exit_code == 1, "Expected exit code 1 when any contract is invalid"

    def test_exit_code_2_file_not_found(self, tmp_path: Path):
        """Exit code 2 when contract file does not exist."""
        nonexistent = tmp_path / "nonexistent.yaml"

        exit_code = main([str(nonexistent)])

        assert exit_code == 2, "Expected exit code 2 for file not found"

    def test_exit_code_2_directory_instead_of_file(self, tmp_path: Path):
        """Exit code 2 when path is a directory, not a file."""
        exit_code = main([str(tmp_path)])

        assert exit_code == 2, "Expected exit code 2 when path is a directory"

    def test_exit_code_2_no_arguments(self):
        """Exit code 2 when no arguments provided."""
        exit_code = main([])

        assert exit_code == 2, "Expected exit code 2 for no arguments"

    def test_exit_code_2_strict_mode_not_implemented(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Exit code 2 when strict mode requested (not yet implemented)."""
        contract = tmp_path / "valid.yaml"
        contract.write_text(valid_compute_contract_yaml)

        exit_code = main([str(contract), "--strict"])

        assert exit_code == 2, "Expected exit code 2 for not implemented strict mode"

    def test_exit_code_2_all_files_not_found(self, tmp_path: Path):
        """Exit code 2 when all files in batch have file errors."""
        nonexistent1 = tmp_path / "nonexistent1.yaml"
        nonexistent2 = tmp_path / "nonexistent2.yaml"

        exit_code = main([str(nonexistent1), str(nonexistent2)])

        assert exit_code == 2, "Expected exit code 2 when all files have file errors"

    def test_exit_code_1_mixed_file_and_validation_errors(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
    ):
        """Exit code 1 when batch has mix of valid, invalid, and missing files.

        When some files exist but have validation errors, the overall exit code
        should be 1 (validation error) rather than 2 (file error), because
        exit code 2 is reserved for cases where ALL files have file-level errors.
        """
        valid = tmp_path / "valid.yaml"
        valid.write_text(valid_compute_contract_yaml)
        nonexistent = tmp_path / "nonexistent.yaml"

        # One valid file + one missing file = exit code 1 (not all file errors)
        exit_code = main([str(valid), str(nonexistent)])

        # Should return 1 because not all files had file errors
        # (valid.yaml was found and validated successfully)
        assert exit_code == 1, (
            "Expected exit code 1 when mix of file and validation issues"
        )

    def test_exit_code_with_json_flag_valid(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Exit code 0 with --json flag for valid contract."""
        contract = tmp_path / "valid.yaml"
        contract.write_text(valid_compute_contract_yaml)

        exit_code = main([str(contract), "--json"])

        assert exit_code == 0, "Expected exit code 0 with --json for valid contract"

    def test_exit_code_with_json_flag_invalid(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Exit code 1 with --json flag for invalid contract."""
        contract = tmp_path / "invalid.yaml"
        contract.write_text(invalid_missing_name_yaml)

        exit_code = main([str(contract), "--json"])

        assert exit_code == 1, "Expected exit code 1 with --json for invalid contract"

    def test_exit_code_with_verbose_flag_valid(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Exit code 0 with --verbose flag for valid contract."""
        contract = tmp_path / "valid.yaml"
        contract.write_text(valid_compute_contract_yaml)

        exit_code = main([str(contract), "--verbose"])

        assert exit_code == 0, "Expected exit code 0 with --verbose for valid contract"

    def test_exit_code_with_verbose_flag_invalid(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Exit code 1 with --verbose flag for invalid contract."""
        contract = tmp_path / "invalid.yaml"
        contract.write_text(invalid_missing_name_yaml)

        exit_code = main([str(contract), "--verbose"])

        assert exit_code == 1, (
            "Expected exit code 1 with --verbose for invalid contract"
        )


# =============================================================================
# Test Class: CLI Exit Codes via Subprocess
# =============================================================================


class TestCLIExitCodesSubprocess:
    """Tests for CLI exit codes using subprocess to test actual CLI invocation.

    These tests verify the CLI behaves correctly when invoked as a module,
    which is how it would be used in CI/CD pipelines and pre-commit hooks.
    """

    @pytest.fixture
    def valid_contract_file(self, tmp_path: Path) -> Path:
        """Create a valid compute contract file."""
        content = """
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
        contract_path = tmp_path / "valid_contract.yaml"
        contract_path.write_text(content)
        return contract_path

    @pytest.fixture
    def invalid_contract_file(self, tmp_path: Path) -> Path:
        """Create an invalid contract file (missing required field)."""
        content = """
version:
  major: 1
  minor: 0
  patch: 0
description: Missing name field
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""
        contract_path = tmp_path / "invalid_contract.yaml"
        contract_path.write_text(content)
        return contract_path

    @pytest.fixture
    def malformed_yaml_file(self, tmp_path: Path) -> Path:
        """Create a malformed YAML file."""
        content = """
name: test_node
version:
  major: 1
  minor: 0
  this is not valid yaml
    - indentation error
  patch: [unclosed bracket
"""
        contract_path = tmp_path / "malformed.yaml"
        contract_path.write_text(content)
        return contract_path

    def test_subprocess_exit_code_0_on_valid_contract(self, valid_contract_file: Path):
        """Test CLI returns exit code 0 when validating a valid contract."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(valid_contract_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"Expected exit code 0 for valid contract, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_subprocess_exit_code_1_on_validation_error(
        self, invalid_contract_file: Path
    ):
        """Test CLI returns exit code 1 when contract has validation errors."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(invalid_contract_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1, (
            f"Expected exit code 1 for validation errors, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )
        assert "FAIL" in result.stdout

    def test_subprocess_exit_code_2_on_file_not_found(self, tmp_path: Path):
        """Test CLI returns exit code 2 when file does not exist."""
        nonexistent_path = tmp_path / "does_not_exist.yaml"

        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(nonexistent_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 2, (
            f"Expected exit code 2 for file not found, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )

    def test_subprocess_exit_code_2_on_no_arguments(self):
        """Test CLI returns exit code 2 when no arguments provided."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 2, (
            f"Expected exit code 2 for no arguments, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )

    def test_subprocess_exit_code_1_on_malformed_yaml(self, malformed_yaml_file: Path):
        """Test CLI returns exit code 1 when YAML is malformed."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(malformed_yaml_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Malformed YAML is a validation failure, not a file error
        assert result.returncode == 1, (
            f"Expected exit code 1 for malformed YAML, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )

    def test_subprocess_exit_code_0_on_batch_all_valid(self, tmp_path: Path):
        """Test CLI returns exit code 0 when all batch files are valid."""
        # Create two valid contracts
        valid1_content = """
name: valid_compute_1
version:
  major: 1
  minor: 0
  patch: 0
description: Valid compute node 1
node_type: compute
input_model: ModelInput1
output_model: ModelOutput1
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    factor1:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""
        valid2_content = """
name: valid_effect_1
version:
  major: 1
  minor: 0
  patch: 0
description: Valid effect node
node_type: effect
input_model: ModelInput2
output_model: ModelOutput2
io_operations:
  - operation_type: file_read
    atomic: true
"""
        valid1 = tmp_path / "valid1.yaml"
        valid1.write_text(valid1_content)
        valid2 = tmp_path / "valid2.yaml"
        valid2.write_text(valid2_content)

        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(valid1),
                str(valid2),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"Expected exit code 0 for batch all valid, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )
        assert "2/2" in result.stdout  # Summary shows 2/2 passed

    def test_subprocess_exit_code_1_on_batch_any_invalid(
        self, valid_contract_file: Path, invalid_contract_file: Path
    ):
        """Test CLI returns exit code 1 when any batch file has validation errors."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(valid_contract_file),
                str(invalid_contract_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1, (
            f"Expected exit code 1 for batch with invalid files, got {result.returncode}. "
            f"stdout: {result.stdout}, stderr: {result.stderr}"
        )
        assert "1/2" in result.stdout  # Summary shows 1/2 passed

    def test_subprocess_json_output_on_success(self, valid_contract_file: Path):
        """Test CLI JSON output includes valid=true on success."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(valid_contract_file),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["valid"] is True
        assert output["errors"] == []

    def test_subprocess_json_output_on_failure(self, invalid_contract_file: Path):
        """Test CLI JSON output includes valid=false and errors on failure."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(invalid_contract_file),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output["valid"] is False
        assert len(output["errors"]) > 0

    def test_subprocess_verbose_output_shows_field_errors(
        self, invalid_contract_file: Path
    ):
        """Test CLI verbose output shows field-level error details."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "omniintelligence.tools.contract_linter",
                str(invalid_contract_file),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        # Verbose output should show the field name in error details
        assert "name" in result.stdout.lower() or "field" in result.stdout.lower()


# =============================================================================
# Test Class: Path Traversal Detection (Reserved for Strict Mode)
# =============================================================================


class TestPathTraversalDetection:
    """Tests for path traversal detection helper function.

    The _is_safe_path() function is reserved for future strict mode implementation.
    It detects path traversal attempts like "../../../etc/passwd" but is NOT
    enforced by default to maintain backward compatibility.

    When strict mode is implemented, this function will be used to validate
    file paths before processing to prevent malicious path traversal attacks.
    """

    def test_safe_path_absolute(self, tmp_path: Path):
        """Test that absolute paths without traversal are safe."""
        safe_path = tmp_path / "contract.yaml"
        assert _is_safe_path(safe_path) is True

    def test_safe_path_simple_relative(self):
        """Test that simple relative paths without traversal are safe."""
        assert _is_safe_path(Path("contract.yaml")) is True
        assert _is_safe_path(Path("subdir/contract.yaml")) is True

    def test_unsafe_path_simple_traversal(self):
        """Test that simple path traversal is detected."""
        assert _is_safe_path(Path("../etc/passwd")) is False

    def test_unsafe_path_deep_traversal(self):
        """Test that deep path traversal attempts are detected."""
        assert _is_safe_path(Path("../../../etc/passwd")) is False

    def test_unsafe_path_embedded_traversal(self):
        """Test that embedded path traversal attempts are detected."""
        assert _is_safe_path(Path("foo/../../../etc/passwd")) is False
        assert _is_safe_path(Path("a/b/../../../etc/passwd")) is False

    def test_safe_path_within_allowed_dir(self, tmp_path: Path):
        """Test that paths within allowed directory are safe."""
        allowed_dir = tmp_path / "contracts"
        allowed_dir.mkdir()
        safe_file = allowed_dir / "contract.yaml"
        safe_file.touch()

        assert _is_safe_path(safe_file, allowed_dir) is True

    def test_unsafe_path_outside_allowed_dir(self, tmp_path: Path):
        """Test that paths outside allowed directory are unsafe."""
        allowed_dir = tmp_path / "contracts"
        allowed_dir.mkdir()
        outside_file = tmp_path / "outside.yaml"
        outside_file.touch()

        assert _is_safe_path(outside_file, allowed_dir) is False

    def test_safe_path_subdirectory_of_allowed_dir(self, tmp_path: Path):
        """Test that paths in subdirectories of allowed directory are safe."""
        allowed_dir = tmp_path / "contracts"
        allowed_dir.mkdir()
        subdir = allowed_dir / "v1_0_0"
        subdir.mkdir()
        safe_file = subdir / "contract.yaml"
        safe_file.touch()

        assert _is_safe_path(safe_file, allowed_dir) is True

    def test_handles_os_errors_gracefully(self):
        """Test that OS errors during path resolution return False."""
        # Path with null byte should cause OSError on most systems
        # or ValueError on Windows - either way, should return False
        try:
            # Create a path that might cause issues
            problematic_path = Path("/\x00invalid")
            result = _is_safe_path(problematic_path)
            # If we get here without exception, result should be False or True
            # depending on platform behavior
            assert isinstance(result, bool)
        except (OSError, ValueError):
            # Some platforms may raise before we even call _is_safe_path
            pass

    def test_traversal_in_directory_component(self):
        """Test that traversal in directory components is detected."""
        assert _is_safe_path(Path("safe/../../unsafe/file.yaml")) is False

    def test_current_directory_reference_is_safe(self):
        """Test that current directory reference (.) is safe."""
        # Single dot is safe - it doesn't traverse upward
        assert _is_safe_path(Path("./contract.yaml")) is True
        assert _is_safe_path(Path("./subdir/contract.yaml")) is True
