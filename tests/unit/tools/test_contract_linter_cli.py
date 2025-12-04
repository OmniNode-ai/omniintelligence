# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter CLI entry point and exit codes.

Tests for CLI behavior including argument parsing, exit codes, JSON output,
verbose output, and subprocess invocation.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from omniintelligence.tools.contract_linter import main

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
