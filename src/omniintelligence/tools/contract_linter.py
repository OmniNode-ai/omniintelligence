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
from typing import TYPE_CHECKING

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

# Type alias for parsed YAML data. YAML values can be any scalar (str, int, float, bool, None)
# or compound (list, dict) type. Using `object` instead of `Any` provides type safety by
# requiring explicit type narrowing (via isinstance checks) before using values.
YamlData = dict[str, object]

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

# Default number of worker threads when os.cpu_count() returns None
# Used as fallback for parallel batch validation
DEFAULT_MAX_WORKERS_FALLBACK = 4

# Watch mode poll interval in seconds
# Controls how frequently files are checked for changes in --watch mode
WATCH_POLL_INTERVAL_SECONDS = 1

# JSON output indentation (spaces)
# Used for human-readable JSON formatting in CLI output
JSON_INDENT_SPACES = 2


class EnumContractErrorType(str, Enum):
    """
    Enumeration of contract validation error types.

    Values are string-based for easy serialization and integration with
    error handling pipelines.
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

    Uses __slots__ instead of BaseModel for minimal memory footprint when
    handling thousands of validation errors during batch contract validation.

    Attributes:
        field_path: The field path where the error occurred (e.g., "version.major")
        error_message: Human-readable error description
        validation_error_type: Category of error (missing_field, invalid_type, invalid_value, etc.)
    """

    __slots__ = ("error_message", "field_path", "validation_error_type")

    # Type annotations for mypy (required for __slots__ classes using object.__setattr__)
    field_path: str
    error_message: str
    validation_error_type: EnumContractErrorType

    def __init__(
        self,
        *,
        field_path: str,
        error_message: str,
        validation_error_type: EnumContractErrorType,
    ) -> None:
        """Initialize validation error with ONEX-compliant field names.

        Args:
            field_path: The field path where the error occurred
            error_message: Human-readable error description
            validation_error_type: Category of error
        """
        object.__setattr__(self, "field_path", field_path)
        object.__setattr__(self, "error_message", error_message)
        object.__setattr__(self, "validation_error_type", validation_error_type)

    def to_dict(self) -> dict[str, str]:
        """Convert error to dictionary representation."""
        return {
            "field_path": self.field_path,
            "error_message": self.error_message,
            "validation_error_type": self.validation_error_type.value,
        }

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"{self.field_path}: {self.error_message} ({self.validation_error_type})"

    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"ModelContractValidationError("
            f"field_path={self.field_path!r}, "
            f"error_message={self.error_message!r}, "
            f"validation_error_type={self.validation_error_type!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality with another error."""
        if not isinstance(other, ModelContractValidationError):
            return NotImplemented
        return (
            self.field_path == other.field_path
            and self.error_message == other.error_message
            and self.validation_error_type == other.validation_error_type
        )

    def __hash__(self) -> int:
        """Return hash of the error."""
        return hash((self.field_path, self.error_message, self.validation_error_type))


class ModelContractValidationResult:
    """
    Result of validating a contract file.

    Uses __slots__ instead of BaseModel for minimal memory footprint when
    handling thousands of validation results during batch contract validation.

    Attributes:
        file_path: Path to the validated contract file
        is_valid: Whether the contract passed all validation checks
        validation_errors: List of validation errors found
        contract_type: Detected contract type (compute, effect, etc.) or None
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
        is_valid: bool,
        validation_errors: list[ModelContractValidationError] | None = None,
        contract_type: str | None = None,
    ) -> None:
        """Initialize validation result with ONEX-compliant field names.

        Args:
            file_path: Path to the validated contract file
            is_valid: Whether the contract passed validation
            validation_errors: List of validation errors found (defaults to empty list)
            contract_type: Detected contract type
        """
        object.__setattr__(self, "file_path", file_path)
        object.__setattr__(self, "is_valid", is_valid)
        object.__setattr__(
            self,
            "validation_errors",
            validation_errors if validation_errors is not None else [],
        )
        object.__setattr__(self, "contract_type", contract_type)

    def to_dict(self) -> dict[str, object]:
        """Convert result to dictionary representation."""
        return {
            "file_path": str(self.file_path),
            "is_valid": self.is_valid,
            "validation_errors": [e.to_dict() for e in self.validation_errors],
            "contract_type": self.contract_type,
        }

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


def _pydantic_error_to_contract_error(
    error: ErrorDetails,
) -> ModelContractValidationError:
    """
    Convert a Pydantic validation error to ModelContractValidationError.

    Args:
        error: Single error dict from ValidationError.errors() - a pydantic_core.ErrorDetails
               TypedDict containing 'type', 'loc', 'msg', 'input', and optional 'ctx'/'url' fields.

    Returns:
        ModelContractValidationError with appropriate field path and message
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
        validation_error_type=mapped_type,
    )


def _detect_contract_type(data: YamlData) -> str:
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
                rules, path traversal protection, and enforcement of optional
                best-practice fields.
            schema_version: Reserved for future schema version selection. Not yet
                implemented. Will allow validating contracts against different schema
                versions. Currently only "1.0.0" is supported.
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
            enhancements.
        """
        # TODO(OMN-470): Implement strict validation mode
        # Planned features for strict=True:
        # - Enable path traversal protection
        # - Treat deprecation warnings as validation errors
        # - Enforce stricter type coercion (e.g., reject string "true" for bool)
        # - Require optional best-practice fields (e.g., description, examples)
        if strict:
            raise NotImplementedError(
                "Strict mode is reserved for future implementation. "
                "Currently only default validation is supported."
            )

        # TODO(OMN-471): Implement schema version selection
        # Planned features for schema_version:
        # - Support multiple schema versions (1.0.0, 1.1.0, 2.0.0, etc.)
        # - Validate contracts against their specified schema version
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
        data: YamlData,
        model_class: type[BaseModel],
        path: Path,
        contract_type_name: str,
    ) -> ModelContractValidationResult:
        """
        Validate contract data against a Pydantic model.

        Args:
            data: Parsed YAML data
            model_class: Pydantic model class to validate against
            path: Path to the contract file
            contract_type_name: Human-readable contract type name

        Returns:
            ModelContractValidationResult with validation status and errors
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
                    validation_error_type=EnumContractErrorType.VALIDATION_ERROR,
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
                    validation_error_type=EnumContractErrorType.UNEXPECTED_ERROR,
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
        data: YamlData,
        path: Path,
    ) -> ModelContractValidationResult:
        """
        Validate FSM subcontract using ModelFSMSubcontract Pydantic model.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ModelContractValidationResult with validation status and errors
        """
        return self._validate_with_pydantic_model(
            data, ModelFSMSubcontract, path, "fsm_subcontract"
        )

    def _validate_workflow(
        self,
        data: YamlData,
        path: Path,
    ) -> ModelContractValidationResult:
        """
        Validate workflow contract using ModelWorkflowCoordinationSubcontract.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ModelContractValidationResult with validation status and errors
        """
        return self._validate_with_pydantic_model(
            data, ModelWorkflowCoordinationSubcontract, path, "workflow"
        )

    def _validate_node_contract(
        self,
        data: YamlData,
        path: Path,
    ) -> ModelContractValidationResult:
        """
        Validate node contract using ProtocolContractValidator.

        Uses the omnibase_core validation infrastructure which handles
        Pydantic model validation with proper error handling for ModelOnexError.

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ModelContractValidationResult with validation status and errors
        """
        validation_errors: list[ModelContractValidationError] = []

        # Get node_type and validate
        node_type = data.get("node_type")
        if node_type is None:
            validation_errors.append(
                ModelContractValidationError(
                    field_path="node_type",
                    error_message="Missing required field: node_type",
                    validation_error_type=EnumContractErrorType.MISSING_FIELD,
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
                    validation_error_type=EnumContractErrorType.INVALID_ENUM,
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
                    validation_error_type=EnumContractErrorType.UNEXPECTED_ERROR,
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
                    validation_error_type=EnumContractErrorType.VALIDATION_ERROR,
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
        data: YamlData,
        path: Path,
    ) -> ModelContractValidationResult:
        """
        Validate generic subcontract with basic structure checks.

        Generic subcontracts have operations but no node_type. Since there's
        no specific Pydantic model for these, we do minimal validation.
        Operations can be either a list or a dict (for named operations).

        Args:
            data: Parsed YAML data
            path: Path to the contract file

        Returns:
            ModelContractValidationResult with validation status and errors
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
                        validation_error_type=EnumContractErrorType.MISSING_FIELD,
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
                        validation_error_type=EnumContractErrorType.INVALID_TYPE,
                    )
                )

        return ModelContractValidationResult(
            file_path=path,
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors,
            contract_type="subcontract",
        )

    def validate(self, file_path: str | Path) -> ModelContractValidationResult:
        """
        Validate a single contract file.

        Args:
            file_path: Path to the YAML contract file

        Returns:
            ModelContractValidationResult with validation status and errors
        """
        path = Path(file_path)
        validation_errors: list[ModelContractValidationError] = []

        # Check file exists
        if not path.exists():
            validation_errors.append(
                ModelContractValidationError(
                    field_path="file",
                    error_message=f"File not found: {path}",
                    validation_error_type=EnumContractErrorType.FILE_NOT_FOUND,
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
                    validation_error_type=EnumContractErrorType.NOT_A_FILE,
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
                        validation_error_type=EnumContractErrorType.FILE_TOO_LARGE,
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
                    validation_error_type=EnumContractErrorType.FILE_READ_ERROR,
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
                    validation_error_type=EnumContractErrorType.FILE_READ_ERROR,
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
                    validation_error_type=EnumContractErrorType.EMPTY_FILE,
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
                    validation_error_type=EnumContractErrorType.YAML_PARSE_ERROR,
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
                    validation_error_type=EnumContractErrorType.EMPTY_FILE,
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
                    validation_error_type=EnumContractErrorType.UNKNOWN_CONTRACT_TYPE,
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
    ) -> list[ModelContractValidationResult]:
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
            max_workers = min(
                len(file_paths), os.cpu_count() or DEFAULT_MAX_WORKERS_FALLBACK
            )
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
        results: list[ModelContractValidationResult],
    ) -> dict[str, object]:
        """
        Get summary statistics for batch validation results.

        Args:
            results: List of validation results

        Returns:
            Dictionary with summary statistics using ONEX naming conventions:
            - total_count: Total number of contracts validated
            - valid_count: Number of contracts that passed validation
            - invalid_count: Number of contracts that failed validation
            - pass_rate: Percentage of contracts that passed (0.0-100.0)
        """
        total_count = len(results)
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = total_count - valid_count

        pass_rate = (valid_count / total_count * 100) if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "pass_rate": pass_rate,
        }


def validate_contract(file_path: str | Path) -> ModelContractValidationResult:
    """
    Standalone function to validate a single contract file.

    Args:
        file_path: Path to the contract file

    Returns:
        ModelContractValidationResult with validation status and errors
    """
    linter = ContractLinter()
    return linter.validate(file_path)


def validate_contracts_batch(
    file_paths: Sequence[str | Path],
    parallel: bool = False,
) -> list[ModelContractValidationResult]:
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
    results: list[ModelContractValidationResult],
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
        status = "PASS" if result.is_valid else "FAIL"
        if result.is_valid:
            lines.append(f"[{status}] {result.file_path}")
        # In non-verbose mode, show error count; in verbose mode, just show FAIL
        # (detailed errors follow on subsequent lines)
        elif verbose:
            lines.append(f"[{status}] {result.file_path}")
            for error in result.validation_errors:
                lines.append(f"  - {error.field_path}: {error.error_message}")
        else:
            # Surface brief error summary even in non-verbose mode
            error_count = len(result.validation_errors)
            lines.append(f"[{status}] {result.file_path} ({error_count} error(s))")

    # Summary
    total = len(results)
    valid = sum(1 for r in results if r.is_valid)
    lines.append("")
    lines.append(f"Summary: {valid}/{total} contracts passed")

    return "\n".join(lines)


def _format_json_output(
    results: list[ModelContractValidationResult],
) -> str:
    """
    Format validation results as JSON.

    Always returns a consistent structure with 'results' array and 'summary' object,
    regardless of the number of results. This ensures predictable parsing by consumers.

    Args:
        results: List of validation results

    Returns:
        JSON string with structure: {"results": [...], "summary": {...}}
        Summary uses ONEX naming conventions with *_count suffix for counts.
    """
    return json.dumps(
        {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total_count": len(results),
                "valid_count": sum(1 for r in results if r.is_valid),
                "invalid_count": sum(1 for r in results if not r.is_valid),
            },
        },
        indent=JSON_INDENT_SPACES,
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

            time_module.sleep(WATCH_POLL_INTERVAL_SECONDS)
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
                e.validation_error_type
                in (
                    EnumContractErrorType.FILE_NOT_FOUND,
                    EnumContractErrorType.NOT_A_FILE,
                    EnumContractErrorType.FILE_READ_ERROR,
                )
                for e in r.validation_errors
            )
            for r in results
        )

        # Exit code 2: ALL files had file-level errors (none could be validated)
        # This indicates an input problem, not a validation failure
        if has_file_errors and all(not r.is_valid for r in results):
            return 2

        # Exit code 1: At least one file failed validation (schema violations)
        # This includes: missing fields, invalid values, malformed YAML, etc.
        has_validation_errors = any(not r.is_valid for r in results)
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
                    "cli_error_type": "not_implemented",
                },
                indent=JSON_INDENT_SPACES,
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
                    "cli_error_type": "unexpected_error",
                },
                indent=JSON_INDENT_SPACES,
            )
        else:
            error_output = f"Unexpected error: {e}"
        print(error_output, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
