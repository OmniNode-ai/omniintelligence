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
import os
import re
import sys
import time as time_module  # Avoid conflict with potential 'time' variable names
from concurrent.futures import ThreadPoolExecutor
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
    from collections.abc import Sequence

    from pydantic_core import ErrorDetails

# Maximum file size for YAML contracts (1MB default)
MAX_YAML_SIZE_BYTES = 1024 * 1024  # 1MB

# Default threshold for parallel validation (number of files)
# When batch size exceeds this threshold, parallel validation is enabled
DEFAULT_PARALLEL_THRESHOLD = 10

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
        >>> _is_safe_path(Path("/allowed/path-extra/file.yaml"), Path("/allowed/path"))
        False  # Must not match prefix-similar paths
    """
    try:
        resolved = file_path.resolve()
        # Check for path traversal attempts in the original path string
        # This catches attempts like "../../../etc/passwd" before resolution
        if ".." in str(file_path):
            return False
        # If allowed_dir specified, ensure path is within it using proper path
        # containment check. String prefix matching has false positives:
        # e.g., "/allowed/path-extra" would incorrectly match "/allowed/path"
        if allowed_dir:
            allowed_resolved = allowed_dir.resolve()
            # Use is_relative_to() for proper path containment (Python 3.9+)
            # This correctly handles edge cases like "/allowed/path-extra"
            # not being inside "/allowed/path"
            try:
                resolved.relative_to(allowed_resolved)
                return True
            except ValueError:
                # resolved is not relative to allowed_resolved
                return False
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


class ModelContractValidationError:
    """
    Represents a single validation error with field path information.

    Attributes:
        field_path: The field path where the error occurred (e.g., "version.major")
        error_message: Human-readable error description
        error_type: Category of error (missing_field, invalid_type, invalid_value, etc.)

    Backward Compatibility:
        Constructor accepts both old names (`field`, `message`) and new ONEX-compliant
        names (`field_path`, `error_message`). The `field` and `message` properties
        are provided as aliases for read access.
    """

    __slots__ = ("error_message", "error_type", "field_path")

    # Type annotations for mypy (required for __slots__ classes using object.__setattr__)
    field_path: str
    error_message: str
    error_type: EnumContractErrorType

    def __init__(
        self,
        *,
        field_path: str | None = None,
        error_message: str | None = None,
        error_type: EnumContractErrorType,
        # Backward compatibility aliases
        field: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize validation error with ONEX-compliant or legacy field names.

        Args:
            field_path: The field path where the error occurred (preferred)
            error_message: Human-readable error description (preferred)
            error_type: Category of error
            field: Deprecated alias for field_path (backward compatibility)
            message: Deprecated alias for error_message (backward compatibility)

        Raises:
            ValueError: If neither field_path nor field is provided
            ValueError: If neither error_message nor message is provided
        """
        # Resolve field_path from new or old name
        resolved_field_path = field_path if field_path is not None else field
        if resolved_field_path is None:
            raise ValueError("Either 'field_path' or 'field' must be provided")

        # Resolve error_message from new or old name
        resolved_error_message = error_message if error_message is not None else message
        if resolved_error_message is None:
            raise ValueError("Either 'error_message' or 'message' must be provided")

        object.__setattr__(self, "field_path", resolved_field_path)
        object.__setattr__(self, "error_message", resolved_error_message)
        object.__setattr__(self, "error_type", error_type)

    # Backward compatibility properties
    @property
    def field(self) -> str:
        """Backward compatibility alias for field_path."""
        return self.field_path

    @property
    def message(self) -> str:
        """Backward compatibility alias for error_message."""
        return self.error_message

    def to_dict(self) -> dict[str, str]:
        """Convert error to dictionary representation.

        Note: Serializes field_path as "field" and error_message as "message"
        for backward compatibility with existing consumers.
        """
        return {
            "field": self.field_path,
            "message": self.error_message,
            "error_type": self.error_type.value,
        }

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"{self.field_path}: {self.error_message} ({self.error_type})"

    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"ModelContractValidationError("
            f"field_path={self.field_path!r}, "
            f"error_message={self.error_message!r}, "
            f"error_type={self.error_type!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality with another error."""
        if not isinstance(other, ModelContractValidationError):
            return NotImplemented
        return (
            self.field_path == other.field_path
            and self.error_message == other.error_message
            and self.error_type == other.error_type
        )

    def __hash__(self) -> int:
        """Return hash of the error."""
        return hash((self.field_path, self.error_message, self.error_type))


# Backward compatibility alias
ContractValidationError = ModelContractValidationError


class ModelContractValidationResult:
    """
    Result of validating a contract file.

    Attributes:
        file_path: Path to the validated contract file
        is_valid: Whether the contract passed all validation checks
        validation_errors: List of validation errors found
        contract_type: Detected contract type (compute, effect, etc.) or None

    Backward Compatibility:
        Constructor accepts both old names (`valid`, `errors`) and new ONEX-compliant
        names (`is_valid`, `validation_errors`). The `valid` and `errors` properties
        are provided as aliases for read access.
    """

    __slots__ = ("contract_type", "file_path", "is_valid", "validation_errors")

    # Type annotations for mypy (required for __slots__ classes using object.__setattr__)
    file_path: Path
    is_valid: bool
    validation_errors: list[ModelContractValidationError]
    contract_type: str | None

    def __init__(
        self,
        *,
        file_path: Path,
        is_valid: bool | None = None,
        validation_errors: list[ModelContractValidationError] | None = None,
        contract_type: str | None = None,
        # Backward compatibility aliases
        valid: bool | None = None,
        errors: list[ModelContractValidationError] | None = None,
    ) -> None:
        """Initialize validation result with ONEX-compliant or legacy field names.

        Args:
            file_path: Path to the validated contract file
            is_valid: Whether the contract passed validation (preferred)
            validation_errors: List of validation errors found (preferred)
            contract_type: Detected contract type
            valid: Deprecated alias for is_valid (backward compatibility)
            errors: Deprecated alias for validation_errors (backward compatibility)

        Raises:
            ValueError: If neither is_valid nor valid is provided
        """
        # Resolve is_valid from new or old name
        resolved_is_valid = is_valid if is_valid is not None else valid
        if resolved_is_valid is None:
            raise ValueError("Either 'is_valid' or 'valid' must be provided")

        # Resolve validation_errors from new or old name (default to empty list)
        resolved_validation_errors = (
            validation_errors if validation_errors is not None else errors
        )
        if resolved_validation_errors is None:
            resolved_validation_errors = []

        object.__setattr__(self, "file_path", file_path)
        object.__setattr__(self, "is_valid", resolved_is_valid)
        object.__setattr__(self, "validation_errors", resolved_validation_errors)
        object.__setattr__(self, "contract_type", contract_type)

    def to_dict(self) -> dict[str, object]:
        """Convert result to dictionary representation.

        Note: Serializes is_valid as "valid" and validation_errors as "errors"
        for backward compatibility with existing consumers.
        """
        return {
            "file_path": str(self.file_path),
            "valid": self.is_valid,
            "errors": [e.to_dict() for e in self.validation_errors],
            "contract_type": self.contract_type,
        }

    # Backward compatibility properties
    @property
    def valid(self) -> bool:
        """Backward compatibility alias for is_valid."""
        return self.is_valid

    @property
    def errors(self) -> list[ModelContractValidationError]:
        """Backward compatibility alias for validation_errors."""
        return self.validation_errors

    def __repr__(self) -> str:
        """Return detailed representation of the result."""
        return (
            f"ModelContractValidationResult("
            f"file_path={self.file_path!r}, "
            f"is_valid={self.is_valid!r}, "
            f"validation_errors={self.validation_errors!r}, "
            f"contract_type={self.contract_type!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality with another result."""
        if not isinstance(other, ModelContractValidationResult):
            return NotImplemented
        return (
            self.file_path == other.file_path
            and self.is_valid == other.is_valid
            and self.validation_errors == other.validation_errors
            and self.contract_type == other.contract_type
        )

    # Explicitly mark as unhashable since __eq__ is defined
    # This is required by PLW1641 (object-with-eq-but-no-hash)
    __hash__ = None  # type: ignore[assignment]


# Backward compatibility alias
ContractValidationResult = ModelContractValidationResult


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

    return ModelContractValidationError(
        field_path=field_path,
        error_message=error.get("msg", "Validation error"),
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
        parallel_threshold: Minimum number of files to trigger parallel validation
            when parallel=True is passed to validate_batch(). Defaults to 10.
    """

    def __init__(
        self,
        strict: bool = False,
        schema_version: str = "1.0.0",
        parallel_threshold: int = DEFAULT_PARALLEL_THRESHOLD,
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
            parallel_threshold: Minimum number of files to trigger parallel validation
                when parallel=True is passed to validate_batch(). Defaults to 10.
                Set to 0 to always use parallel validation when parallel=True.

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
        self._parallel_threshold = parallel_threshold

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
            return ModelContractValidationResult(
                file_path=path,
                is_valid=True,
                validation_errors=[],
                contract_type=contract_type_name,
            )
        except ValidationError as e:
            validation_errors = [
                _pydantic_error_to_contract_error(err) for err in e.errors()
            ]
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=contract_type_name,
            )
        except ModelOnexError as e:
            # Handle custom ONEX validation errors from omnibase_core
            validation_errors = [
                ModelContractValidationError(
                    field_path="contract",
                    error_message=str(e),
                    error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            ]
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=contract_type_name,
            )
        except Exception as e:
            # Catch any unexpected errors during Pydantic model validation
            validation_errors = [
                ModelContractValidationError(
                    field_path="contract",
                    error_message=f"Unexpected error during validation: {e}",
                    error_type=EnumContractErrorType.UNEXPECTED_ERROR,
                )
            ]
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
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
        validation_errors: list[ModelContractValidationError] = []

        # Get node_type and validate
        node_type = data.get("node_type")
        if node_type is None:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="node_type",
                    error_message="Missing required field: node_type",
                    error_type=EnumContractErrorType.MISSING_FIELD,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Normalize node_type to lowercase for lookup
        node_type_lower = node_type.lower() if isinstance(node_type, str) else None

        if not _is_valid_node_type(node_type_lower):
            valid_types = ", ".join(sorted(VALID_NODE_TYPES))
            validation_errors.append(
                ModelContractValidationError(
                    field_path="node_type",
                    error_message=f"Invalid node_type: '{node_type}'. Must be one of: {valid_types}",
                    error_type=EnumContractErrorType.INVALID_ENUM,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
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
            validation_errors.append(
                ModelContractValidationError(
                    field_path="contract",
                    error_message=f"Unexpected error during node contract validation: {e}",
                    error_type=EnumContractErrorType.UNEXPECTED_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
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

            validation_errors.append(
                ModelContractValidationError(
                    field_path=field_name,
                    error_message=violation,
                    error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            )

        return ModelContractValidationResult(
            file_path=path,
            is_valid=result.is_valid,
            validation_errors=validation_errors,
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
        validation_errors: list[ModelContractValidationError] = []

        # Check for basic required fields
        required_fields = ("name", "version", "description", "operations")
        for field_name in required_fields:
            if field_name not in data:
                validation_errors.append(
                    ModelContractValidationError(
                        field_path=field_name,
                        error_message=f"Missing required field: {field_name}",
                        error_type=EnumContractErrorType.MISSING_FIELD,
                    )
                )

        # Validate operations is a list or dict if present
        if "operations" in data:
            operations = data["operations"]
            if not isinstance(operations, list | dict):
                validation_errors.append(
                    ModelContractValidationError(
                        field_path="operations",
                        error_message="Operations must be a list or dict",
                        error_type=EnumContractErrorType.INVALID_TYPE,
                    )
                )

        return ModelContractValidationResult(
            file_path=path,
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors,
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
        validation_errors: list[ModelContractValidationError] = []

        # Check file exists
        if not path.exists():
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message=f"File not found: {path}",
                    error_type=EnumContractErrorType.FILE_NOT_FOUND,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Check it's a file, not a directory
        if path.is_dir():
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message=f"Path is a directory, not a file: {path}",
                    error_type=EnumContractErrorType.NOT_A_FILE,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Check file size before loading to prevent memory issues
        try:
            file_size = path.stat().st_size
            if file_size > MAX_YAML_SIZE_BYTES:
                validation_errors.append(
                    ModelContractValidationError(
                        field_path="file",
                        error_message=f"File size ({file_size} bytes) exceeds maximum allowed ({MAX_YAML_SIZE_BYTES} bytes)",
                        error_type=EnumContractErrorType.FILE_TOO_LARGE,
                    )
                )
                return ModelContractValidationResult(
                    file_path=path,
                    is_valid=False,
                    validation_errors=validation_errors,
                    contract_type=None,
                )
        except OSError as e:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message=f"Error checking file size: {e}",
                    error_type=EnumContractErrorType.FILE_READ_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Read and parse YAML
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message=f"Error reading file: {e}",
                    error_type=EnumContractErrorType.FILE_READ_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Check for empty content
        if not content.strip():
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message="File is empty",
                    error_type=EnumContractErrorType.EMPTY_FILE,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Parse YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="yaml",
                    error_message=f"Invalid YAML syntax: {e}",
                    error_type=EnumContractErrorType.YAML_PARSE_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Check for empty YAML (comments only)
        if data is None:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message="File contains no YAML content (only comments or empty)",
                    error_type=EnumContractErrorType.EMPTY_FILE,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
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
            validation_errors.append(
                ModelContractValidationError(
                    field_path="root",
                    error_message=(
                        "Unable to detect contract type. Expected one of: "
                        "node contract (with node_type), FSM subcontract "
                        "(with state_machine_name/states), workflow (with workflow_type), "
                        "or subcontract (with operations)"
                    ),
                    error_type=EnumContractErrorType.UNKNOWN_CONTRACT_TYPE,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

    def validate_batch(
        self,
        file_paths: Sequence[str | Path],
        parallel: bool = False,
    ) -> list[ContractValidationResult]:
        """
        Validate multiple contract files.

        Args:
            file_paths: Sequence of paths to contract files
            parallel: If True and batch size exceeds parallel_threshold,
                use parallel validation with ThreadPoolExecutor

        Returns:
            List of validation results for each file
        """
        if parallel and len(file_paths) > self._parallel_threshold:
            max_workers = min(len(file_paths), os.cpu_count() or 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                return list(
                    executor.map(
                        self.validate,
                        [Path(fp) if isinstance(fp, str) else fp for fp in file_paths],
                    )
                )
        return [self.validate(fp) for fp in file_paths]

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
    file_paths: Sequence[str | Path],
    parallel: bool = False,
) -> list[ContractValidationResult]:
    """
    Standalone function to validate multiple contract files.

    Args:
        file_paths: Sequence of paths to contract files
        parallel: If True and batch size > 10, use parallel validation

    Returns:
        List of validation results
    """
    linter = ContractLinter()
    return linter.validate_batch(file_paths, parallel=parallel)


def _format_text_output(
    results: list[ContractValidationResult],
    verbose: bool = False,
) -> str:
    """
    Format validation results as human-readable text.

    In non-verbose mode, shows a brief error count for each failing file.
    In verbose mode, shows detailed error information with field paths.

    Args:
        results: List of validation results
        verbose: Whether to include detailed error information

    Returns:
        Formatted text output
    """
    lines: list[str] = []

    for result in results:
        status = "PASS" if result.valid else "FAIL"
        if result.valid:
            lines.append(f"[{status}] {result.file_path}")
        # In non-verbose mode, show error count; in verbose mode, just show FAIL
        # (detailed errors follow on subsequent lines)
        elif verbose:
            lines.append(f"[{status}] {result.file_path}")
            for error in result.errors:
                lines.append(f"  - {error.field_path}: {error.error_message}")
        else:
            # Surface brief error summary even in non-verbose mode
            error_count = len(result.errors)
            lines.append(f"[{status}] {result.file_path} ({error_count} error(s))")

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

    Always returns a consistent structure with 'results' array and 'summary' object,
    regardless of the number of results. This ensures predictable parsing by consumers.

    Args:
        results: List of validation results

    Returns:
        JSON string with structure: {"results": [...], "summary": {...}}
    """
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


def _watch_and_validate(
    linter: ContractLinter,
    file_paths: list[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Watch files for changes and re-validate.

    Polls files every 1 second and re-validates when changes are detected.
    Runs until interrupted with Ctrl+C.

    Args:
        linter: ContractLinter instance to use for validation
        file_paths: List of file paths (as strings) to watch
        json_output: If True, output results as JSON
        verbose: If True, show detailed error messages in text output
    """
    print("Watching for file changes... (Ctrl+C to stop)")

    # Convert to Path objects for file operations
    paths = [Path(fp) for fp in file_paths]

    # Track last modification times
    mtimes: dict[Path, float] = {}
    for fp in paths:
        if fp.exists():
            mtimes[fp] = fp.stat().st_mtime

    try:
        while True:
            changed = False
            for fp in paths:
                if fp.exists():
                    current_mtime = fp.stat().st_mtime
                    if fp not in mtimes or mtimes[fp] != current_mtime:
                        mtimes[fp] = current_mtime
                        changed = True

            if changed:
                timestamp = time_module.strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Change detected, re-validating...")
                results = linter.validate_batch(file_paths)
                if json_output:
                    print(_format_json_output(results))
                else:
                    print(_format_text_output(results, verbose=verbose))

            time_module.sleep(1)  # Poll every 1 second
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")


def main(args: list[str] | None = None) -> int:
    """
    CLI entry point for contract linter.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code following Unix conventions:
            0 - Success: All contracts passed validation
            1 - Validation failure: One or more contracts have schema violations
                (e.g., missing required fields, invalid values, malformed YAML)
            2 - Input error: File-level issues preventing validation
                (e.g., file not found, path is a directory, permission denied)
                OR usage error (no arguments provided, strict mode not implemented)

    Exit Code Decision Logic:
        - If ALL files have file-level errors (FILE_NOT_FOUND, NOT_A_FILE,
          FILE_READ_ERROR), return 2 (input error).
        - If ANY file exists but fails validation, return 1 (validation failure).
        - If all files pass validation, return 0 (success).

    Examples:
        # All valid contracts
        $ contract_linter valid1.yaml valid2.yaml
        # Exit code: 0

        # One invalid contract (missing required field)
        $ contract_linter invalid.yaml
        # Exit code: 1

        # File not found
        $ contract_linter nonexistent.yaml
        # Exit code: 2

        # Mix of valid and missing files - returns 1 (not all are file errors)
        $ contract_linter valid.yaml nonexistent.yaml
        # Exit code: 1
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

    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Watch for file changes and re-validate automatically",
    )

    parsed_args = parser.parse_args(args)

    # No contracts provided
    if not parsed_args.contracts:
        parser.print_help()
        return 2

    try:
        # Create linter instance
        linter = ContractLinter(strict=parsed_args.strict)

        # Handle watch mode
        if parsed_args.watch:
            _watch_and_validate(
                linter, parsed_args.contracts, parsed_args.json, parsed_args.verbose
            )
            return 0

        # Normal validation mode
        results = linter.validate_batch(parsed_args.contracts)

        # Format and print output
        if parsed_args.json:
            output = _format_json_output(results)
        else:
            output = _format_text_output(results, verbose=parsed_args.verbose)

        print(output)

        # Determine exit code based on error types and validation results
        # See docstring for detailed exit code semantics

        # Check if any results have file-level errors (cannot be validated at all)
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

        # Exit code 2: ALL files had file-level errors (none could be validated)
        # This indicates an input problem, not a validation failure
        if has_file_errors and all(not r.valid for r in results):
            return 2

        # Exit code 1: At least one file failed validation (schema violations)
        # This includes: missing fields, invalid values, malformed YAML, etc.
        has_validation_errors = any(not r.valid for r in results)
        if has_validation_errors:
            return 1

        # Exit code 0: All files passed validation successfully
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
