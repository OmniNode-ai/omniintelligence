# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter core validation functionality.

Tests for single contract validation, file handling edge cases, and batch
validation using the ContractLinter class.
"""

from pathlib import Path

from omniintelligence.tools.contract_linter import (
    MAX_YAML_SIZE_BYTES,
    ContractLinter,
    ContractValidationResult,
    EnumContractErrorType,
    validate_contract,
    validate_contracts_batch,
)

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
            "node_type" in e.field
            or e.error_type is EnumContractErrorType.UNKNOWN_CONTRACT_TYPE
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
            "invalid_type" in e.message.lower()
            or e.error_type is EnumContractErrorType.INVALID_ENUM
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
        assert any(e.error_type is EnumContractErrorType.FILE_NOT_FOUND for e in result.errors)

    def test_validate_malformed_yaml(self, tmp_path: Path, malformed_yaml: str):
        """Test graceful handling of malformed YAML."""
        contract_path = tmp_path / "malformed.yaml"
        contract_path.write_text(malformed_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(e.error_type is EnumContractErrorType.YAML_PARSE_ERROR for e in result.errors)

    def test_validate_empty_yaml(self, tmp_path: Path, empty_yaml: str):
        """Test handling of empty YAML file."""
        contract_path = tmp_path / "empty.yaml"
        contract_path.write_text(empty_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.valid is False
        assert len(result.errors) >= 1
        assert any(
            "empty" in e.message.lower()
            or e.error_type is EnumContractErrorType.EMPTY_FILE
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
            "directory" in e.message.lower()
            or e.error_type is EnumContractErrorType.NOT_A_FILE
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
        assert any(e.error_type is EnumContractErrorType.FILE_TOO_LARGE for e in result.errors)

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
        assert not any(e.error_type is EnumContractErrorType.FILE_TOO_LARGE for e in result.errors)


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
        assert any(e.error_type is EnumContractErrorType.FILE_NOT_FOUND for e in results[1].errors)

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
