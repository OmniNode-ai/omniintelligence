# SPDX-License-Identifier: Apache-2.0
"""
Contract Linter CLI for ONEX Node Contract Validation.

Validates YAML contract files against the ONEX schema using omnibase_core
Pydantic models. Provides structured error output with field paths
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
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

# Import omnibase_core Pydantic models and validation infrastructure
from omnibase_core.models.contracts.subcontracts import (
    ModelFSMSubcontract,
    ModelWorkflowCoordinationSubcontract,
)
from omnibase_core.models.errors.model_onex_error import ModelOnexError
from omnibase_core.validation.contract_validator import ProtocolContractValidator
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

# Maximum file size for YAML contracts (1MB default)
MAX_YAML_SIZE_BYTES = 1024 * 1024  # 1MB

# Regex pattern for valid Python-style field identifiers (lowercase snake_case)
# Matches: field_name, version, _private, field123
# Rejects: FieldName (uppercase), "field name" (spaces), 123field (starts with digit)
FIELD_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

# Map node_type values (case-insensitive) to contract_type for ProtocolContractValidator
VALID_NODE_TYPES: frozenset[str] = frozenset(
    {"compute", "effect", "reducer", "orchestrator"}
)


def _is_safe_path(file_path: Path, allowed_dir: Path | None = None) -> bool:
    """Check if path is safe (no traversal attacks).

    This helper function detects path traversal attempts like "../../../etc/passwd".
    It is reserved for future strict mode implementation and is NOT enforced by
    default to maintain backward compatibility with existing usage patterns.

    When strict mode is implemented, this function will be used to validate
    file paths before processing to prevent malicious path traversal attacks.

    Args:
        file_path: Path to validate
        allowed_dir: If provided, path must be within this directory

    Returns:
        True if path is safe, False otherwise

    Examples:
        >>> _is_safe_path(Path("/home/user/contract.yaml"))
        True
        >>> _is_safe_path(Path("../../../etc/passwd"))
        False
        >>> _is_safe_path(Path("foo/../../../etc/passwd"))
        False
        >>> _is_safe_path(Path("/home/user/contract.yaml"), Path("/home/user"))
        True
        >>> _is_safe_path(Path("/etc/passwd"), Path("/home/user"))
        False
    """
    try:
        resolved = file_path.resolve()
        # Check for path traversal attempts in the original path string
        # This catches attempts like "../../../etc/passwd" before resolution
        if ".." in str(file_path):
            return False
        # If allowed_dir specified, ensure path is within it
        if allowed_dir:
            allowed_resolved = allowed_dir.resolve()
            return str(resolved).startswith(str(allowed_resolved))
        return True
    except (OSError, ValueError):
        return False


class EnumContractErrorType(str, Enum):
    """
    Enumeration of contract validation error types.

    Values are string-based for easy serialization and compatibility with
    existing error handling code.
    """

    MISSING_FIELD = "missing_field"
    INVALID_VALUE = "invalid_value"
    INVALID_TYPE = "invalid_type"
    INVALID_ENUM = "invalid_enum"
    VALIDATION_ERROR = "validation_error"
    FILE_NOT_FOUND = "file_not_found"
    NOT_A_FILE = "not_a_file"
    FILE_READ_ERROR = "file_read_error"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"
    YAML_PARSE_ERROR = "yaml_parse_error"
    UNKNOWN_CONTRACT_TYPE = "unknown_contract_type"
    UNEXPECTED_ERROR = "unexpected_error"


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
    error_type: EnumContractErrorType

    def to_dict(self) -> dict[str, str]:
        """Convert error to dictionary representation."""
        return {
            "field": self.field,
            "message": self.message,
            "error_type": self.error_type.value,
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


def _pydantic_error_to_contract_error(
    error: ErrorDetails,
) -> ContractValidationError:
    """
    Convert a Pydantic validation error to ContractValidationError.

    Args:
        error: Single error dict from ValidationError.errors() - a pydantic_core.ErrorDetails
               TypedDict containing 'type', 'loc', 'msg', 'input', and optional 'ctx'/'url' fields.

    Returns:
        ContractValidationError with appropriate field path and message
    """
    # Build field path from location tuple
    loc = error.get("loc", ())
    field_path = ".".join(str(part) for part in loc) if loc else "root"

    # Map Pydantic error types to our error categories
    error_type = error.get("type", "validation_error")
    error_type_map = {
        "missing": EnumContractErrorType.MISSING_FIELD,
        "value_error": EnumContractErrorType.INVALID_VALUE,
        "type_error": EnumContractErrorType.INVALID_TYPE,
        "string_type": EnumContractErrorType.INVALID_TYPE,
        "int_type": EnumContractErrorType.INVALID_TYPE,
        "model_type": EnumContractErrorType.INVALID_TYPE,
        "enum": EnumContractErrorType.INVALID_ENUM,
        "too_short": EnumContractErrorType.INVALID_VALUE,
        "too_long": EnumContractErrorType.INVALID_VALUE,
        "literal_error": EnumContractErrorType.INVALID_ENUM,
    }

    mapped_type = error_type_map.get(error_type, EnumContractErrorType.VALIDATION_ERROR)

    return ContractValidationError(
        field=field_path,
        message=error.get("msg", "Validation error"),
        error_type=mapped_type,
    )


def _detect_contract_type(data: dict[str, Any]) -> str:
    """
    Detect the type of contract from YAML content.

    Detection priority:
    1. FSM subcontract - has state_machine_name or states
    2. Workflow - has workflow_type and (steps or subcontract_name)
    3. Node contract - has node_type
    4. Generic subcontract - has operations but no node_type

    Args:
        data: Parsed YAML data

    Returns:
        Contract type string: 'fsm_subcontract', 'workflow', 'node_contract',
        'subcontract', or 'unknown'
    """
    # FSM subcontract detection
    if "state_machine_name" in data or "states" in data:
        return "fsm_subcontract"

    # Workflow detection - check for workflow-specific fields
    if "workflow_type" in data or (
        "subcontract_name" in data and "max_concurrent_workflows" in data
    ):
        return "workflow"

    # Node contract detection
    if "node_type" in data:
        return "node_contract"

    # Generic subcontract detection
    if "operations" in data and "node_type" not in data:
        return "subcontract"

    return "unknown"


def _is_valid_node_type(node_type: str | None) -> bool:
    """
    Check if node_type is a valid ONEX node architecture type.

    Args:
        node_type: The node_type value from the contract (case-insensitive)

    Returns:
        True if valid node type, False otherwise
    """
    if node_type is None:
        return False
    return node_type.lower() in VALID_NODE_TYPES


class ContractLinter:
    """
    Validates ONEX contract YAML files against Pydantic model schemas.

    Uses omnibase_core Pydantic models (ModelContractCompute, ModelContractEffect,
    etc.) for validation instead of manual field checking. Supports:
    - Node contracts (compute, effect, reducer, orchestrator)
    - FSM subcontracts
    - Workflow coordination subcontracts
    - Generic subcontracts

    Args:
        strict: Reserved for future strict validation mode. Not yet implemented.
            When implemented, will enable additional validation checks such as
            deprecation warnings as errors, stricter type coercion rules, etc.
        schema_version: Reserved for future schema version selection. Not yet
            implemented. Currently only "1.0.0" is supported.
    """

    def __init__(
        self,
        strict: bool = False,
        schema_version: str = "1.0.0",
    ) -> None:
        """Initialize the contract linter.

        Args:
            strict: Reserved for future strict validation mode. Not yet implemented.
                When implemented, strict mode will enable additional validation checks
                such as: deprecation warnings treated as errors, stricter type coercion
                rules, path traversal protection (via `_is_safe_path`), and enforcement
                of optional best-practice fields.
            schema_version: Reserved for future schema version selection. Not yet
                implemented. Will allow validating contracts against different schema
                versions for backward compatibility. Currently only "1.0.0" is supported.

        Raises:
            NotImplementedError: If strict=True is passed (not yet implemented).
            NotImplementedError: If schema_version other than "1.0.0" is passed
                (not yet supported).

        Note:
            The `strict` and `schema_version` parameters are stored as instance
            attributes (`_strict` and `_schema_version`) but are not currently used
            in validation logic. They exist to establish the API surface for future
            enhancements without breaking backward compatibility.
        """
        # TODO(OMN-241): Implement strict validation mode
        # Planned features for strict=True:
        # - Enable path traversal protection using _is_safe_path()
        # - Treat deprecation warnings as validation errors
        # - Enforce stricter type coercion (e.g., reject string "true" for bool)
        # - Require optional best-practice fields (e.g., description, examples)
        if strict:
            raise NotImplementedError(
                "Strict mode is reserved for future implementation. "
                "Currently only default validation is supported."
            )

        # TODO(OMN-241): Implement schema version selection
        # Planned features for schema_version:
        # - Support multiple schema versions (1.0.0, 1.1.0, 2.0.0, etc.)
        # - Enable backward-compatible validation for older contracts
        # - Provide migration hints when validating old schemas
        if schema_version != "1.0.0":
            raise NotImplementedError(
                f"Schema version '{schema_version}' is not yet supported. "
                "Currently only '1.0.0' is available."
            )

        self._strict = strict
        self._schema_version = schema_version

    def _validate_with_pydantic_model(
        self,
        data: dict[str, Any],
        model_class: type[BaseModel],
        path: Path,
        contract_type_name: str,
    ) -> ContractValidationResult:
        """
        Validate contract data against a Pydantic model.

        Args:
            data: Parsed YAML data
            model_class: Pydantic model class to validate against
            path: Path to the contract file
            contract_type_name: Human-readable contract type name

        Returns:
            ContractValidationResult with validation status and errors
        """
        try:
            model_class.model_validate(data)
            return ContractValidationResult(
                file_path=path,
                valid=True,
                errors=[],
                contract_type=contract_type_name,
            )
        except ValidationError as e:
            errors = [_pydantic_error_to_contract_error(err) for err in e.errors()]
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=contract_type_name,
            )
        except ModelOnexError as e:
            # Handle custom ONEX validation errors from omnibase_core
            errors = [
                ContractValidationError(
                    field="contract",
                    message=str(e),
                    error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            ]
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=contract_type_name,
            )
        except Exception as e:
            # Catch any unexpected errors during Pydantic model validation
            errors = [
                ContractValidationError(
                    field="contract",
                    message=f"Unexpected error during validation: {e}",
                    error_type=EnumContractErrorType.UNEXPECTED_ERROR,
                )
            ]
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=contract_type_name,
            )

    def _validate_fsm_subcontract(
        self,
        data: dict[str, Any],
        path: Path,
    ) -> ContractValidationResult:
        """
        Validate FSM subcontract using ModelFSMSubcontract Pydantic model.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        return self._validate_with_pydantic_model(
            data, ModelFSMSubcontract, path, "fsm_subcontract"
        )

    def _validate_workflow(
        self,
        data: dict[str, Any],
        path: Path,
    ) -> ContractValidationResult:
        """
        Validate workflow contract using ModelWorkflowCoordinationSubcontract.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        return self._validate_with_pydantic_model(
            data, ModelWorkflowCoordinationSubcontract, path, "workflow"
        )

    def _validate_node_contract(
        self,
        data: dict[str, Any],
        path: Path,
    ) -> ContractValidationResult:
        """
        Validate node contract using ProtocolContractValidator.

        Uses the omnibase_core validation infrastructure which handles
        Pydantic model validation with proper error handling for ModelOnexError.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        errors: list[ContractValidationError] = []

        # Get node_type and validate
        node_type = data.get("node_type")
        if node_type is None:
            errors.append(
                ContractValidationError(
                    field="node_type",
                    message="Missing required field: node_type",
                    error_type=EnumContractErrorType.MISSING_FIELD,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Normalize node_type to lowercase for lookup
        node_type_lower = node_type.lower() if isinstance(node_type, str) else None

        if not _is_valid_node_type(node_type_lower):
            valid_types = ", ".join(sorted(VALID_NODE_TYPES))
            errors.append(
                ContractValidationError(
                    field="node_type",
                    message=f"Invalid node_type: '{node_type}'. Must be one of: {valid_types}",
                    error_type=EnumContractErrorType.INVALID_ENUM,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Use ProtocolContractValidator for full validation
        try:
            validator = ProtocolContractValidator()
            result = validator.validate_contract_file(
                path,
                contract_type=node_type_lower,
            )
        except Exception as e:
            # Catch unexpected errors from ProtocolContractValidator
            errors.append(
                ContractValidationError(
                    field="contract",
                    message=f"Unexpected error during node contract validation: {e}",
                    error_type=EnumContractErrorType.UNEXPECTED_ERROR,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=node_type_lower,
            )

        # Convert ProtocolContractValidator result to our format
        for violation in result.violations:
            # Parse field from violation message if it starts with a field name pattern
            field_name = "contract"
            if ":" in violation:
                # Only treat as field name if it matches valid identifier pattern
                potential_field = violation.split(":", 1)[0].strip()
                # Use regex to validate field name (lowercase snake_case identifiers)
                if potential_field and FIELD_IDENTIFIER_PATTERN.match(potential_field):
                    field_name = potential_field

            errors.append(
                ContractValidationError(
                    field=field_name,
                    message=violation,
                    error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            )

        return ContractValidationResult(
            file_path=path,
            valid=result.is_valid,
            errors=errors,
            contract_type=node_type_lower,
        )

    def _validate_subcontract(
        self,
        data: dict[str, Any],
        path: Path,
    ) -> ContractValidationResult:
        """
        Validate generic subcontract with basic structure checks.

        Generic subcontracts have operations but no node_type. Since there's
        no specific Pydantic model for these, we do minimal validation.
        Operations can be either a list or a dict (for named operations).

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ContractValidationResult with validation status and errors
        """
        errors: list[ContractValidationError] = []

        # Check for basic required fields
        required_fields = ("name", "version", "description", "operations")
        for field_name in required_fields:
            if field_name not in data:
                errors.append(
                    ContractValidationError(
                        field=field_name,
                        message=f"Missing required field: {field_name}",
                        error_type=EnumContractErrorType.MISSING_FIELD,
                    )
                )

        # Validate operations is a list or dict if present
        if "operations" in data:
            operations = data["operations"]
            if not isinstance(operations, (list, dict)):
                errors.append(
                    ContractValidationError(
                        field="operations",
                        message="Operations must be a list or dict",
                        error_type=EnumContractErrorType.INVALID_TYPE,
                    )
                )

        return ContractValidationResult(
            file_path=path,
            valid=len(errors) == 0,
            errors=errors,
            contract_type="subcontract",
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
                    error_type=EnumContractErrorType.FILE_NOT_FOUND,
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
                    error_type=EnumContractErrorType.NOT_A_FILE,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Check file size before loading to prevent memory issues
        try:
            file_size = path.stat().st_size
            if file_size > MAX_YAML_SIZE_BYTES:
                errors.append(
                    ContractValidationError(
                        field="file",
                        message=f"File size ({file_size} bytes) exceeds maximum allowed ({MAX_YAML_SIZE_BYTES} bytes)",
                        error_type=EnumContractErrorType.FILE_TOO_LARGE,
                    )
                )
                return ContractValidationResult(
                    file_path=path,
                    valid=False,
                    errors=errors,
                    contract_type=None,
                )
        except OSError as e:
            errors.append(
                ContractValidationError(
                    field="file",
                    message=f"Error checking file size: {e}",
                    error_type=EnumContractErrorType.FILE_READ_ERROR,
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
                    error_type=EnumContractErrorType.FILE_READ_ERROR,
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
                    error_type=EnumContractErrorType.EMPTY_FILE,
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
                    error_type=EnumContractErrorType.YAML_PARSE_ERROR,
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
                    error_type=EnumContractErrorType.EMPTY_FILE,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
            )

        # Detect contract type and route to appropriate validator
        contract_type = _detect_contract_type(data)

        if contract_type == "fsm_subcontract":
            return self._validate_fsm_subcontract(data, path)
        elif contract_type == "workflow":
            return self._validate_workflow(data, path)
        elif contract_type == "node_contract":
            return self._validate_node_contract(data, path)
        elif contract_type == "subcontract":
            return self._validate_subcontract(data, path)
        else:
            # Unknown contract type - try to provide helpful error
            errors.append(
                ContractValidationError(
                    field="root",
                    message=(
                        "Unable to detect contract type. Expected one of: "
                        "node contract (with node_type), FSM subcontract "
                        "(with state_machine_name/states), workflow (with workflow_type), "
                        "or subcontract (with operations)"
                    ),
                    error_type=EnumContractErrorType.UNKNOWN_CONTRACT_TYPE,
                )
            )
            return ContractValidationResult(
                file_path=path,
                valid=False,
                errors=errors,
                contract_type=None,
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
        help="Enable strict validation mode (reserved for future use, not yet implemented)",
    )

    parsed_args = parser.parse_args(args)

    # No contracts provided
    if not parsed_args.contracts:
        parser.print_help()
        return 2

    try:
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
            any(
                e.error_type
                in (
                    EnumContractErrorType.FILE_NOT_FOUND,
                    EnumContractErrorType.NOT_A_FILE,
                    EnumContractErrorType.FILE_READ_ERROR,
                )
                for e in r.errors
            )
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

    except NotImplementedError as e:
        # Handle NotImplementedError from ContractLinter init (strict mode, unsupported schema)
        if parsed_args.json:
            error_output = json.dumps(
                {
                    "error": str(e),
                    "error_type": "not_implemented",
                },
                indent=2,
            )
        else:
            error_output = f"Error: {e}"
        print(error_output, file=sys.stderr)
        return 2

    except Exception as e:
        # Catch any unexpected errors and provide a clean error message
        if parsed_args.json:
            error_output = json.dumps(
                {
                    "error": f"Unexpected error: {e}",
                    "error_type": "unexpected_error",
                },
                indent=2,
            )
        else:
            error_output = f"Unexpected error: {e}"
        print(error_output, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
