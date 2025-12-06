# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter CLI entry point and exit codes.

Tests for CLI behavior including argument parsing, exit codes, JSON output,
verbose output, and subprocess invocation.
"""

import json
import subprocess
import sys
import time as time_module
from pathlib import Path
from unittest.mock import patch

import pytest

from omniintelligence.tools.contract_linter import (
    ContractLinter,
    _watch_and_validate,
    main,
)
from tests.unit.tools.conftest import (
    create_mock_sleep_function,
    create_mock_stat_function,
)

# =============================================================================
# Test Class: CLI Entry Point
# =============================================================================


@pytest.mark.unit
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

        assert exit_code == 1  # Convention: 1 for validation errors

    def test_cli_exit_code_on_file_not_found(self, tmp_path: Path):
        """Test CLI returns non-zero exit code when file not found."""
        nonexistent_path = tmp_path / "nonexistent.yaml"

        with patch("sys.argv", ["contract_linter", str(nonexistent_path)]):
            exit_code = main()

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
        """Test CLI with --json flag outputs JSON with expected structure.

        JSON output always includes:
        - results: array of validation result objects
        - summary: object with total, valid, and invalid counts

        Each result object includes:
        - file_path: string path to the contract file
        - valid: boolean indicating validation result
        - errors: list of error objects (empty for valid contracts)
        - contract_type: string indicating detected contract type
        """
        contract_path = tmp_path / "valid.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(contract_path), "--json"],
        ):
            main()

        captured = capsys.readouterr()
        # Should be valid JSON with expected structure
        parsed = json.loads(captured.out)

        # Top-level structure must include results and summary
        assert "results" in parsed, "JSON output must include 'results' array"
        assert "summary" in parsed, "JSON output must include 'summary' object"

        # Validate results is a list with exactly one entry
        assert isinstance(parsed["results"], list), "'results' must be a list"
        assert len(parsed["results"]) == 1, "Should have exactly one result"

        # Validate summary structure
        summary = parsed["summary"]
        assert "total" in summary, "Summary must include 'total'"
        assert "valid_count" in summary, "Summary must include 'valid_count'"
        assert "invalid_count" in summary, "Summary must include 'invalid_count'"
        assert summary["total"] == 1, "Total should be 1"
        assert summary["valid_count"] == 1, "Valid count should be 1"
        assert summary["invalid_count"] == 0, "Invalid count should be 0"

        # Validate the single result entry
        result = parsed["results"][0]
        assert "file_path" in result, "Result must include 'file_path'"
        assert "is_valid" in result, "Result must include 'is_valid'"
        assert "validation_errors" in result, "Result must include 'validation_errors'"
        assert "contract_type" in result, "Result must include 'contract_type'"

        # Validate types
        assert isinstance(result["file_path"], str), "'file_path' must be a string"
        assert isinstance(result["is_valid"], bool), "'is_valid' must be a boolean"
        assert isinstance(result["validation_errors"], list), (
            "'validation_errors' must be a list"
        )
        assert result["contract_type"] is None or isinstance(
            result["contract_type"], str
        ), "'contract_type' must be string or null"

        # Validate values for valid contract
        assert result["is_valid"] is True, "Valid contract should have is_valid=true"
        assert result["validation_errors"] == [], (
            "Valid contract should have empty validation_errors list"
        )
        assert result["contract_type"] == "compute", (
            "Contract type should be 'compute' for compute contract"
        )

    def test_cli_verbose_flag(
        self, tmp_path: Path, invalid_missing_name_yaml: str, capsys
    ):
        """Test CLI with --verbose flag shows detailed error output.

        Verbose mode shows field-level error details with format:
          - {field}: {message}

        For a contract missing the 'name' field, verbose output must show:
        - [FAIL] marker for the failing file
        - The field name 'name' in the error details
        - An error message indicating the field is required/missing
        """
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        with patch(
            "sys.argv",
            ["contract_linter", str(contract_path), "--verbose"],
        ):
            main()

        captured = capsys.readouterr()
        output = captured.out

        # Verbose output must show FAIL status
        assert "[FAIL]" in output, (
            "Verbose output must show [FAIL] for invalid contract"
        )

        # Verbose output must show the field name in error details
        # The format is "  - {field}: {message}"
        assert "name" in output, (
            "Verbose output must show 'name' field in error details"
        )

        # Verbose output must show indented error line (verbose format)
        assert "  - " in output, (
            "Verbose output must show indented error lines with '  - ' prefix"
        )

        # Verbose output must indicate the field is required/missing
        assert "required" in output.lower() or "missing" in output.lower(), (
            "Verbose output must indicate field is required or missing"
        )


# =============================================================================
# Test Class: CLI Exit Codes (Direct main() calls)
# =============================================================================


@pytest.mark.unit
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
        """Exit code 1 when batch has mix of valid files and missing files.

        When some files exist and are valid, but others are missing, the overall
        exit code should be 1 rather than 2, because exit code 2 is reserved for
        cases where ALL files have file-level errors (none could be validated).
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

    def test_exit_code_semantics_with_all_error_types(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        invalid_missing_name_yaml: str,
    ):
        """Exit code 1 when batch has valid, invalid (validation error), AND missing files.

        Exit code semantics:
        - 0: All files valid
        - 1: Any validation failure OR mix of file/validation issues
        - 2: ALL files have file-level errors (none could be validated)

        This test validates the most complex case: a batch containing:
        1. A valid contract (passes validation)
        2. An invalid contract (validation error - missing required field)
        3. A missing file (file-level error - not found)

        Expected exit code is 1 because:
        - At least one file was successfully read and processed (valid.yaml)
        - At least one file had validation errors (invalid.yaml)
        - Not ALL files had file-level errors, so exit code 2 does not apply
        """
        valid = tmp_path / "valid.yaml"
        valid.write_text(valid_compute_contract_yaml)
        invalid = tmp_path / "invalid.yaml"
        invalid.write_text(invalid_missing_name_yaml)
        missing = tmp_path / "missing.yaml"  # Don't create this file

        exit_code = main([str(valid), str(invalid), str(missing)])

        assert exit_code == 1, "Expected exit code 1 when mix of all error types"

    def test_exit_code_2_only_file_errors_multiple_types(
        self,
        tmp_path: Path,
    ):
        """Exit code 2 when ALL files have file-level errors (various types).

        Exit code 2 is specifically for cases where NO files could be validated
        because ALL of them had file-level errors. This includes:
        - File not found
        - Path is a directory (not a file)
        - Permission denied (not tested here as it requires OS-level setup)

        This test validates that when multiple files ALL have file-level errors
        (even of different types), the exit code is 2.
        """
        nonexistent1 = tmp_path / "nonexistent1.yaml"
        nonexistent2 = tmp_path / "nonexistent2.yaml"
        directory_path = tmp_path / "subdir"
        directory_path.mkdir()  # Create as directory, not file

        # All three have file-level errors: 2 not found + 1 directory
        exit_code = main([str(nonexistent1), str(nonexistent2), str(directory_path)])

        assert exit_code == 2, (
            "Expected exit code 2 when ALL files have file-level errors"
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


@pytest.mark.integration
class TestCLIExitCodesSubprocess:
    """Tests for CLI exit codes using subprocess to test actual CLI invocation.

    These tests verify the CLI behaves correctly when invoked as a module,
    which is how it would be used in CI/CD pipelines and pre-commit hooks.

    Note: These tests spawn subprocesses and are marked as integration tests.
    Fixtures are provided by conftest.py.
    """

    def test_subprocess_exit_code_0_on_valid_contract(self, valid_contract_file: Path):
        """Test CLI returns exit code 0 when validating a valid contract."""
        result = subprocess.run(
            [
                sys.executable,  # Use sys.executable for portability across environments
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
                sys.executable,
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
                sys.executable,
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
                sys.executable,
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
                sys.executable,
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

    def test_subprocess_exit_code_0_on_batch_all_valid(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        valid_effect_contract_yaml: str,
    ):
        """Test CLI returns exit code 0 when all batch files are valid."""
        # Use fixtures instead of inline YAML to avoid duplication with conftest.py
        valid1 = tmp_path / "valid1.yaml"
        valid1.write_text(valid_compute_contract_yaml)
        valid2 = tmp_path / "valid2.yaml"
        valid2.write_text(valid_effect_contract_yaml)

        result = subprocess.run(
            [
                sys.executable,
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
                sys.executable,
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
        """Test CLI JSON output includes valid=true on success.

        JSON output always has consistent structure: {"results": [...], "summary": {...}}
        regardless of the number of files validated.
        """
        result = subprocess.run(
            [
                sys.executable,
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
        # Consistent structure: results array and summary object
        assert "results" in output
        assert "summary" in output
        assert len(output["results"]) == 1
        assert output["results"][0]["is_valid"] is True
        assert output["results"][0]["validation_errors"] == []
        assert output["summary"]["total"] == 1
        assert output["summary"]["valid_count"] == 1

    def test_subprocess_json_output_on_failure(self, invalid_contract_file: Path):
        """Test CLI JSON output includes is_valid=false and errors on failure.

        JSON output always has consistent structure: {"results": [...], "summary": {...}}
        regardless of the number of files validated.
        """
        result = subprocess.run(
            [
                sys.executable,
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
        # Consistent structure: results array and summary object
        assert "results" in output
        assert "summary" in output
        assert len(output["results"]) == 1
        assert output["results"][0]["is_valid"] is False
        assert len(output["results"][0]["validation_errors"]) > 0
        assert output["summary"]["total"] == 1
        assert output["summary"]["invalid_count"] == 1

    def test_subprocess_verbose_output_shows_field_errors(
        self, invalid_contract_file: Path
    ):
        """Test CLI verbose output shows field-level error details.

        The invalid_contract_file fixture uses invalid_missing_name_yaml which
        is missing the required 'name' field. Verbose output should show:
        - [FAIL] marker for the failing file
        - The field name 'name' in the error details
        - Indented error lines with '  - ' prefix (verbose format)
        - An indication that the field is required/missing
        """
        result = subprocess.run(
            [
                sys.executable,
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

        # Verbose output must show FAIL status
        assert "FAIL" in result.stdout, (
            f"Verbose output must show FAIL for invalid contract. Got: {result.stdout}"
        )

        # Verbose output must show the 'name' field specifically (since that's the
        # missing field in invalid_contract_file fixture)
        assert "name" in result.stdout.lower(), (
            f"Verbose output must show 'name' field in error details. Got: {result.stdout}"
        )

        # Verbose output must show indented error line (verbose format uses '  - ')
        assert "  - " in result.stdout, (
            f"Verbose output must show indented error lines with '  - ' prefix. "
            f"Got: {result.stdout}"
        )

        # Verbose output must indicate the field is required/missing
        stdout_lower = result.stdout.lower()
        assert "required" in stdout_lower or "missing" in stdout_lower, (
            f"Verbose output must indicate field is required or missing. "
            f"Got: {result.stdout}"
        )


# =============================================================================
# Test Class: CLI Watch Mode
# =============================================================================


@pytest.mark.unit
class TestCLIWatchMode:
    """Tests for CLI watch mode functionality."""

    def test_watch_flag_is_recognized(self, tmp_path: Path):
        """Test that --watch flag is recognized by argument parser."""
        contract = tmp_path / "test.yaml"
        contract.write_text("name: test\nnode_type: COMPUTE\n")

        # The watch mode runs indefinitely, so we test argument parsing only
        # by mocking the watch function
        with patch(
            "omniintelligence.tools.contract_linter._watch_and_validate"
        ) as mock_watch:
            mock_watch.return_value = None
            exit_code = main([str(contract), "--watch"])

        assert exit_code == 0
        mock_watch.assert_called_once()

    def test_watch_short_flag_is_recognized(self, tmp_path: Path):
        """Test that -w short flag is recognized by argument parser."""
        contract = tmp_path / "test.yaml"
        contract.write_text("name: test\nnode_type: COMPUTE\n")

        with patch(
            "omniintelligence.tools.contract_linter._watch_and_validate"
        ) as mock_watch:
            mock_watch.return_value = None
            exit_code = main([str(contract), "-w"])

        assert exit_code == 0
        mock_watch.assert_called_once()

    def test_watch_mode_passes_correct_arguments(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test that watch mode passes correct arguments to _watch_and_validate."""
        contract = tmp_path / "valid.yaml"
        contract.write_text(valid_compute_contract_yaml)

        with patch(
            "omniintelligence.tools.contract_linter._watch_and_validate"
        ) as mock_watch:
            mock_watch.return_value = None
            main([str(contract), "--watch", "--verbose", "--json"])

        # Verify the arguments passed to _watch_and_validate
        args, _kwargs = mock_watch.call_args
        assert len(args) == 4
        # args[0] is linter instance
        assert args[1] == [str(contract)]  # file_paths
        assert args[2] is True  # json_output
        assert args[3] is True  # verbose

    def test_watch_mode_with_multiple_files(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        valid_effect_contract_yaml: str,
    ):
        """Test that watch mode accepts multiple files."""
        contract1 = tmp_path / "contract1.yaml"
        contract1.write_text(valid_compute_contract_yaml)
        contract2 = tmp_path / "contract2.yaml"
        contract2.write_text(valid_effect_contract_yaml)

        with patch(
            "omniintelligence.tools.contract_linter._watch_and_validate"
        ) as mock_watch:
            mock_watch.return_value = None
            main([str(contract1), str(contract2), "--watch"])

        args, _kwargs = mock_watch.call_args
        assert len(args[1]) == 2
        assert str(contract1) in args[1]
        assert str(contract2) in args[1]


@pytest.mark.unit
class TestWatchAndValidateFunction:
    """Tests for the _watch_and_validate helper function.

    These tests use consolidated mock helpers from conftest.py to avoid
    duplication of complex mocking logic. See conftest.py for documentation
    of the magic numbers (WATCH_STAT_CALLS_BEFORE_CHANGE and
    WATCH_ITERATIONS_BEFORE_EXIT) used in the mock implementations.
    """

    def test_watch_detects_file_change(
        self,
        tmp_path: Path,
        valid_compute_contract_yaml: str,
        capsys,
    ):
        """Test that watch mode detects file changes and re-validates."""
        contract = tmp_path / "watch_test.yaml"
        contract.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        initial_stat = contract.stat()
        initial_mtime = initial_stat.st_mtime

        # Use mutable list containers for counters (allows closure modification)
        stat_call_counter = [0]
        iteration_counter = [0]

        # Create mock functions using consolidated helpers
        mock_stat = create_mock_stat_function(
            contract, initial_stat, initial_mtime, stat_call_counter
        )
        mock_sleep = create_mock_sleep_function(iteration_counter)

        with patch.object(Path, "stat", mock_stat):
            with patch.object(time_module, "sleep", mock_sleep):
                _watch_and_validate(linter, [str(contract)], False, False)

        captured = capsys.readouterr()
        assert "Watching for file changes" in captured.out
        assert "Change detected" in captured.out
        assert "Watch mode stopped" in captured.out

    def test_watch_handles_keyboard_interrupt(
        self, tmp_path: Path, valid_compute_contract_yaml: str, capsys
    ):
        """Test that watch mode exits cleanly on Ctrl+C."""
        contract = tmp_path / "watch_test.yaml"
        contract.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()

        def mock_sleep(seconds):
            """Immediately raise KeyboardInterrupt to simulate Ctrl+C."""
            raise KeyboardInterrupt

        with patch.object(time_module, "sleep", mock_sleep):
            _watch_and_validate(linter, [str(contract)], False, False)

        captured = capsys.readouterr()
        assert "Watch mode stopped" in captured.out

    def test_watch_with_json_output(
        self, tmp_path: Path, valid_compute_contract_yaml: str, capsys
    ):
        """Test that watch mode outputs JSON when json_output is True."""
        contract = tmp_path / "watch_test.yaml"
        contract.write_text(valid_compute_contract_yaml)

        linter = ContractLinter()
        initial_stat = contract.stat()
        initial_mtime = initial_stat.st_mtime

        # Use mutable list containers for counters (allows closure modification)
        stat_call_counter = [0]
        iteration_counter = [0]

        # Create mock functions using consolidated helpers
        mock_stat = create_mock_stat_function(
            contract, initial_stat, initial_mtime, stat_call_counter
        )
        mock_sleep = create_mock_sleep_function(iteration_counter)

        with patch.object(Path, "stat", mock_stat):
            with patch.object(time_module, "sleep", mock_sleep):
                _watch_and_validate(linter, [str(contract)], True, False)

        captured = capsys.readouterr()
        # JSON output should contain valid JSON with "is_valid" key
        assert '"is_valid"' in captured.out or '"results"' in captured.out
