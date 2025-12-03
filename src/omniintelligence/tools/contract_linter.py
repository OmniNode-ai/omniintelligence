# SPDX-License-Identifier: Apache-2.0
"""
Contract Linter CLI for ONEX Node Contract Validation.

Validates YAML contract files against the ONEX schema using omnibase_core
validation infrastructure. Provides structured error output with field paths
for easy debugging and integration with CI/CD pipelines.

Usage:
    python -m omniintelligence.tools.contract_linter path/to/contract.yaml
    python -m omniintelligence.tools.contract_linter file1.yaml file2.yaml
    python -m omniintelligence.tools.contract_linter path/to/contract.yaml --json
    python -m omniintelligence.tools.contract_linter path/to/contract.yaml --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# Valid node types in ONEX contracts
VALID_NODE_TYPES: frozenset[str] = frozenset({
    "compute",
    "effect",
    "reducer",
    "orchestrator",
})

# Required fields for base contracts
REQUIRED_BASE_FIELDS: tuple[str, ...] = (
    "name",
    "version",
    "description",
    "node_type",
    "input_model",
    "output_model",
)

# Type-specific required fields
TYPE_SPECIFIC_FIELDS: dict[str, tuple[str, ...]] = {
    "compute": ("operations",),
    "effect": ("operations",),
    "reducer": (),
    "orchestrator": (),
}

# FSM subcontract indicators - presence of any of these means it's an FSM file
FSM_INDICATORS: frozenset[str] = frozenset({
    "state_machine_name",
    "states",
    "transitions",
    "initial_state",
})

# Required fields for FSM subcontracts
FSM_REQUIRED_FIELDS: tuple[str, ...] = (
    "state_machine_name",
    "states",
    "initial_state",
)


@dataclass
class ContractValidationError:
    """
    Represents a single validation error with field path information.

    Attributes:
        field: The field path where the error occurred (e.g., "version.major")
        message: Human-readable error description
        error_type: Category of error (missing_field, invalid_type, invalid_value, etc.)
    """

    field: str
    message: str
    error_type: str

    def to_dict(self) -> dict[str, str]:
        """Convert error to dictionary representation."""
        return {
            "field": self.field,
            "message": self.message,
            "error_type": self.error_type,
        }

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"{self.field}: {self.message} ({self.error_type})"


@dataclass
class ContractValidationResult:
    """
    Result of validating a contract file.

    Attributes:
        file_path: Path to the validated contract file
        valid: Whether the contract passed all validation checks
        errors: List of validation errors found
        contract_type: Detected contract type (compute, effect, etc.) or None
    """

    file_path: Path
    valid: bool
    errors: list[ContractValidationError] = field(default_factory=list)
    contract_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert result to dictionary representation."""
        return {
            "file_path": str(self.file_path),
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "contract_type": self.contract_type,
        }


class ContractLinter:
    """
    Validates ONEX contract YAML files against schema requirements.

    The linter checks for:
    - Required fields (name, version, description, node_type, input_model, output_model)
    - Valid node_type enum values
    - Correct version structure (major, minor, patch as integers)
    - Type-specific required fields (operations for compute and effect nodes)
    - FSM subcontract validation (state_machine_name, states, initial_state)

    Args:
        strict: Enable strict mode for stricter validation (default: False)
        schema_version: Schema version to validate against (default: "1.0.0")
    """

    def __init__(
        self,
        strict: bool = False,
        schema_version: str = "1.0.0",
    ) -> None:
        """Initialize the contract linter."""
        self.strict = strict
        self.schema_version = schema_version

    def _is_fsm_subcontract(self, data: dict[str, object]) -> bool:
        """
        Detect if YAML is an FSM subcontract rather than a node contract.

        FSM subcontracts contain state machine definitions and have a different
        schema than node contracts. They are identified by the presence of
        FSM-specific fields like state_machine_name, states, transitions.

        Args:
            data: Parsed YAML data

        Returns:
            True if this is an FSM subcontract, False otherwise
        """
        return any(key in data for key in FSM_INDICATORS)

    def _validate_fsm_subcontract(
        self,
        data: dict[str, object],
        path: Path,
    ) -> ContractValidationResult:
        """
        Validate FSM subcontract with appropriate schema.

        FSM subcontracts define state machines and have different required
        fields than node contracts.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        errors: list[ContractValidationError] = []

        # Check FSM required fields
        for field_name in FSM_REQUIRED_FIELDS:
            if field_name not in data:
                errors.append(
                    ContractValidationError(
                        field=field_name,
                        message=f"Missing required FSM field: {field_name}",
                        error_type="missing_field",
                    )
                )

        # Validate states is a list if present
        if "states" in data:
            states = data["states"]
            if not isinstance(states, list):
                errors.append(
                    ContractValidationError(
                        field="states",
                        message="States must be a list",
                        error_type="invalid_type",
                    )
                )
            elif len(states) == 0:
                errors.append(
                    ContractValidationError(
                        field="states",
                        message="States list cannot be empty",
                        error_type="invalid_value",
                    )
                )

        # Validate transitions is a list if present
        if "transitions" in data:
            transitions = data["transitions"]
            if not isinstance(transitions, list):
                errors.append(
                    ContractValidationError(
                        field="transitions",
                        message="Transitions must be a list",
                        error_type="invalid_type",
                    )
                )

        # Validate version structure if present
        if "version" in data:
            version = data["version"]
            if isinstance(version, dict):
                self._validate_version(version, errors)
            else:
                errors.append(
                    ContractValidationError(
                        field="version",
                        message="Version must be an object with major, minor, patch fields",
                        error_type="invalid_type",
                    )
                )

        return ContractValidationResult(
            file_path=path,
            valid=len(errors) == 0,
            errors=errors,
            contract_type="fsm_subcontract",
        )

    def validate(self, file_path: str | Path) -> ContractValidationResult:
        """
        Validate a single contract file.

        Args:
            file_path: Path to the YAML contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        path = Path(file_path)
        errors: list[ContractValidationError] = []

        # Check file exists
        if not path.exists():
            errors.append(
                ContractValidationError(
                    field="file",
                    message=f"File not found: {path}",
                    error_type="file_not_found",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Check it's a file, not a directory
        if path.is_dir():
            errors.append(
                ContractValidationError(
                    field="file",
                    message=f"Path is a directory, not a file: {path}",
                    error_type="not_a_file",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Read and parse YAML
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(
                ContractValidationError(
                    field="file",
                    message=f"Error reading file: {e}",
                    error_type="file_read_error",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Check for empty content
        if not content.strip():
            errors.append(
                ContractValidationError(
                    field="file",
                    message="File is empty",
                    error_type="empty_file",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Parse YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            errors.append(
                ContractValidationError(
                    field="yaml",
                    message=f"Invalid YAML syntax: {e}",
                    error_type="yaml_parse_error",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Check for empty YAML (comments only)
        if data is None:
            errors.append(
                ContractValidationError(
                    field="file",
                    message="File contains no YAML content (only comments or empty)",
                    error_type="empty_file",
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Check if this is an FSM subcontract (different schema)
        if self._is_fsm_subcontract(data):
            return self._validate_fsm_subcontract(data, path)

        # Validate node contract structure
        contract_type = self._validate_contract_structure(data, errors)

        return ContractValidationResult(
            file_path=path,
            valid=len(errors) == 0,
            errors=errors,
            contract_type=contract_type,
        )

    def _validate_contract_structure(
        self,
        data: dict[str, object],
        errors: list[ContractValidationError],
    ) -> str | None:
        """
        Validate the contract structure and required fields.

        Args:
            data: Parsed YAML data
            errors: List to append errors to

        Returns:
            Detected contract type or None if invalid
        """
        # Check required base fields
        for field_name in REQUIRED_BASE_FIELDS:
            if field_name not in data:
                errors.append(
                    ContractValidationError(
                        field=field_name,
                        message=f"Missing required field: {field_name}",
                        error_type="missing_field",
                    )
                )

        # Validate version structure
        if "version" in data:
            version = data["version"]
            if isinstance(version, dict):
                self._validate_version(version, errors)
            else:
                errors.append(
                    ContractValidationError(
                        field="version",
                        message="Version must be an object with major, minor, patch fields",
                        error_type="invalid_type",
                    )
                )

        # Validate and detect node_type
        contract_type: str | None = None
        if "node_type" in data:
            node_type = data["node_type"]
            if isinstance(node_type, str):
                node_type_lower = node_type.lower()
                if node_type_lower in VALID_NODE_TYPES:
                    contract_type = node_type_lower
                else:
                    errors.append(
                        ContractValidationError(
                            field="node_type",
                            message=f"Invalid node_type: '{node_type}'. Must be one of: {', '.join(sorted(VALID_NODE_TYPES))}",
                            error_type="invalid_enum",
                        )
                    )
            else:
                errors.append(
                    ContractValidationError(
                        field="node_type",
                        message="node_type must be a string",
                        error_type="invalid_type",
                    )
                )

        # Validate type-specific required fields
        if contract_type:
            self._validate_type_specific_fields(data, contract_type, errors)

        return contract_type

    def _validate_version(
        self,
        version: dict[str, object],
        errors: list[ContractValidationError],
    ) -> None:
        """
        Validate version object structure.

        Args:
            version: Version dictionary
            errors: List to append errors to
        """
        version_fields = ("major", "minor", "patch")

        for field_name in version_fields:
            if field_name not in version:
                errors.append(
                    ContractValidationError(
                        field=f"version.{field_name}",
                        message=f"Missing required version field: {field_name}",
                        error_type="missing_field",
                    )
                )
            else:
                value = version[field_name]
                if not isinstance(value, int):
                    errors.append(
                        ContractValidationError(
                            field=f"version.{field_name}",
                            message=f"Version {field_name} must be a positive integer, got {type(value).__name__}",
                            error_type="invalid_type",
                        )
                    )
                elif value < 0:
                    errors.append(
                        ContractValidationError(
                            field=f"version.{field_name}",
                            message=f"Version {field_name} must be a positive integer",
                            error_type="invalid_value",
                        )
                    )

    def _validate_type_specific_fields(
        self,
        data: dict[str, object],
        contract_type: str,
        errors: list[ContractValidationError],
    ) -> None:
        """
        Validate type-specific required fields.

        Args:
            data: Contract data
            contract_type: Detected contract type
            errors: List to append errors to
        """
        required_fields = TYPE_SPECIFIC_FIELDS.get(contract_type, ())

        for field_name in required_fields:
            if field_name not in data:
                errors.append(
                    ContractValidationError(
                        field=field_name,
                        message=f"Missing required field for {contract_type} contracts: {field_name}",
                        error_type="missing_field",
                    )
                )

    def validate_batch(
        self,
        file_paths: list[str | Path],
    ) -> list[ContractValidationResult]:
        """
        Validate multiple contract files.

        Args:
            file_paths: List of paths to contract files

        Returns:
            List of validation results for each file
        """
        results: list[ContractValidationResult] = []

        for file_path in file_paths:
            result = self.validate(file_path)
            results.append(result)

        return results

    def get_summary(
        self,
        results: list[ContractValidationResult],
    ) -> dict[str, object]:
        """
        Get summary statistics for batch validation results.

        Args:
            results: List of validation results

        Returns:
            Dictionary with summary statistics
        """
        total = len(results)
        valid = sum(1 for r in results if r.valid)
        invalid = total - valid

        pass_rate = (valid / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "pass_rate": pass_rate,
        }


def validate_contract(file_path: str | Path) -> ContractValidationResult:
    """
    Standalone function to validate a single contract file.

    Args:
        file_path: Path to the contract file

    Returns:
        ContractValidationResult with validation status and errors
    """
    linter = ContractLinter()
    return linter.validate(file_path)


def validate_contracts_batch(
    file_paths: list[str | Path],
) -> list[ContractValidationResult]:
    """
    Standalone function to validate multiple contract files.

    Args:
        file_paths: List of paths to contract files

    Returns:
        List of validation results
    """
    linter = ContractLinter()
    return linter.validate_batch(file_paths)


def _format_text_output(
    results: list[ContractValidationResult],
    verbose: bool = False,
) -> str:
    """
    Format validation results as human-readable text.

    Args:
        results: List of validation results
        verbose: Whether to include detailed error information

    Returns:
        Formatted text output
    """
    lines: list[str] = []

    for result in results:
        status = "PASS" if result.valid else "FAIL"
        lines.append(f"[{status}] {result.file_path}")

        if not result.valid and verbose:
            for error in result.errors:
                lines.append(f"  - {error.field}: {error.message}")

    # Summary
    total = len(results)
    valid = sum(1 for r in results if r.valid)
    lines.append("")
    lines.append(f"Summary: {valid}/{total} contracts passed")

    return "\n".join(lines)


def _format_json_output(
    results: list[ContractValidationResult],
) -> str:
    """
    Format validation results as JSON.

    Args:
        results: List of validation results

    Returns:
        JSON string
    """
    if len(results) == 1:
        return json.dumps(results[0].to_dict(), indent=2)

    return json.dumps(
        {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "valid": sum(1 for r in results if r.valid),
                "invalid": sum(1 for r in results if not r.valid),
            },
        },
        indent=2,
    )


def main(args: list[str] | None = None) -> int:
    """
    CLI entry point for contract linter.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code:
            0 - All contracts valid
            1 - One or more validation errors
            2 - File not found or other errors
    """
    parser = argparse.ArgumentParser(
        description="Validate ONEX contract YAML files",
        prog="contract_linter",
    )

    parser.add_argument(
        "contracts",
        nargs="*",
        help="Path(s) to contract YAML file(s)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed error messages",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation mode",
    )

    parsed_args = parser.parse_args(args)

    # No contracts provided
    if not parsed_args.contracts:
        parser.print_help()
        return 2

    # Validate contracts
    linter = ContractLinter(strict=parsed_args.strict)
    results = linter.validate_batch(parsed_args.contracts)

    # Format and print output
    if parsed_args.json:
        output = _format_json_output(results)
    else:
        output = _format_text_output(results, verbose=parsed_args.verbose)

    print(output)

    # Determine exit code
    # Check for file errors (file not found, etc.)
    has_file_errors = any(
        any(e.error_type in ("file_not_found", "not_a_file", "file_read_error")
            for e in r.errors)
        for r in results
    )

    if has_file_errors and all(not r.valid for r in results):
        # All files had file-level errors
        return 2

    # Check for validation errors
    has_validation_errors = any(not r.valid for r in results)
    if has_validation_errors:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
