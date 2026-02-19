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
import fnmatch
import json
import keyword
import logging
import os
import re
import sys
import time as time_module  # Avoid conflict with potential 'time' variable names
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# Import omnibase_core Pydantic models and validation infrastructure
from omnibase_core.models.contracts.subcontracts import (
    ModelFSMSubcontract,
    ModelWorkflowCoordinationSubcontract,
)
from omnibase_core.models.errors.model_onex_error import ModelOnexError
from pydantic import BaseModel, ValidationError

from omniintelligence.constants import PERCENTAGE_MULTIPLIER
from omniintelligence.tools.enum_contract_error_type import EnumContractErrorType
from omniintelligence.tools.model_contract_validation_error import (
    ModelContractValidationError,
)
from omniintelligence.tools.model_contract_validation_result import (
    ModelContractValidationResult,
)
from omniintelligence.tools.stubs.contract_validator import ProtocolContractValidator

# Module-level logger for contract linter operations
# Outputs to stderr to avoid polluting stdout which is used for CLI results
logger = logging.getLogger(__name__)

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


def is_python_keyword(name: str) -> bool:
    """
    Check if a name is a Python reserved keyword.

    Uses the standard library `keyword.iskeyword()` function to check
    against all Python reserved keywords (if, for, class, def, return, etc.).

    Args:
        name: The identifier name to check

    Returns:
        True if the name is a Python reserved keyword, False otherwise

    Examples:
        >>> is_python_keyword("class")
        True
        >>> is_python_keyword("field_name")
        False
    """
    return keyword.iskeyword(name)


def is_dunder_name(name: str) -> bool:
    """
    Check if a name is a Python dunder (double underscore) name.

    Dunder names start AND end with double underscores (__). These are
    reserved for Python's internal use (e.g., __init__, __str__, __dict__).

    Single leading underscore (_private) is allowed for convention-based
    private attributes. Double leading underscore (__mangled) without
    trailing underscores is allowed for name mangling.

    Args:
        name: The identifier name to check

    Returns:
        True if the name is a dunder name (starts AND ends with __), False otherwise

    Examples:
        >>> is_dunder_name("__init__")
        True
        >>> is_dunder_name("__dict__")
        True
        >>> is_dunder_name("_private")
        False
        >>> is_dunder_name("__mangled")
        False
    """
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def has_invalid_trailing_underscore(name: str) -> bool:
    """
    Check if a name has an invalid trailing underscore.

    Names ending with a single underscore are typically used to avoid
    conflicts with Python keywords (e.g., class_ instead of class).
    However, ONEX naming conventions discourage trailing underscores
    for field names as they indicate workarounds rather than clean design.

    Single leading underscore (_private) is valid for private attributes.
    Names ending with underscore but starting with underscore are valid
    (e.g., _internal_ is a valid pattern).

    Args:
        name: The identifier name to check

    Returns:
        True if the name ends with underscore but doesn't start with underscore,
        False otherwise

    Examples:
        >>> has_invalid_trailing_underscore("class_")
        True
        >>> has_invalid_trailing_underscore("return_")
        True
        >>> has_invalid_trailing_underscore("field_name")
        False
        >>> has_invalid_trailing_underscore("_private")
        False
        >>> has_invalid_trailing_underscore("_internal_")
        False
    """
    # Don't flag dunder names here - they're handled by is_dunder_name
    if is_dunder_name(name):
        return False
    # Valid: doesn't end with underscore, or starts with underscore (private convention)
    # Invalid: ends with underscore but doesn't start with underscore
    return name.endswith("_") and not name.startswith("_")


def validate_field_identifier(name: str) -> tuple[bool, str | None]:
    """
    Validate a field identifier against ONEX naming conventions.

    Checks for:
    1. Basic identifier pattern (lowercase snake_case)
    2. Underscore-only names (e.g., "_", "__", "___")
    3. Python reserved keywords
    4. Dunder names (double underscore start AND end)
    5. Invalid trailing underscores

    Args:
        name: The field identifier to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.

    Examples:
        >>> validate_field_identifier("field_name")
        (True, None)
        >>> validate_field_identifier("_")
        (False, "Field name '_' contains only underscores ...")
        >>> validate_field_identifier("class")
        (False, "Field name 'class' is a Python reserved keyword")
        >>> validate_field_identifier("__init__")
        (False, "Field name '__init__' uses Python dunder naming ...")
        >>> validate_field_identifier("class_")
        (False, "Field name 'class_' has trailing underscore ...")
    """
    # Check basic pattern first
    if not FIELD_IDENTIFIER_PATTERN.match(name):
        return (False, f"Field name '{name}' does not match snake_case pattern")

    # Reject underscore-only names (e.g., "_", "__", "___")
    # These match the pattern but are not meaningful identifiers
    if name.strip("_") == "":
        return (
            False,
            f"Field name '{name}' contains only underscores "
            "(must include at least one alphanumeric character)",
        )

    # Check for Python reserved keywords
    if is_python_keyword(name):
        return (False, f"Field name '{name}' is a Python reserved keyword")

    # Check for dunder names
    if is_dunder_name(name):
        return (
            False,
            f"Field name '{name}' uses Python dunder naming "
            "(reserved for internal use)",
        )

    # Check for trailing underscore (keyword workaround pattern)
    if has_invalid_trailing_underscore(name):
        return (
            False,
            f"Field name '{name}' has trailing underscore "
            "(use a different name instead of keyword workaround)",
        )

    return (True, None)


# Map node_type values (case-insensitive) to contract_type for ProtocolContractValidator
# Base types are the fundamental categories; extended types (e.g., COMPUTE_GENERIC) are also valid
VALID_NODE_TYPE_BASES: frozenset[str] = frozenset(
    {"compute", "effect", "reducer", "orchestrator"}
)

# Extended node types include the base type with optional suffixes (e.g., COMPUTE_GENERIC)
VALID_NODE_TYPES: frozenset[str] = frozenset(
    {
        # Base types
        "compute",
        "effect",
        "reducer",
        "orchestrator",
        # Extended generic types
        "compute_generic",
        "effect_generic",
        "reducer_generic",
        "orchestrator_generic",
    }
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

# Patterns for sensitive environment variable names that should be redacted in error output.
# These patterns use fnmatch-style wildcards (* matches any characters).
# Values of matching env vars will be replaced with REDACTED_VALUE in error messages.
SENSITIVE_ENV_VAR_PATTERNS: tuple[str, ...] = (
    # API keys and secrets
    "*_KEY",
    "*_SECRET",
    "*_PASSWORD",
    "*_TOKEN",
    "*_API_KEY",
    "*_APIKEY",
    # Credentials and auth
    "*_PRIVATE_*",
    "*_CREDENTIAL*",
    "*_AUTH_*",
    # Connection strings and URLs with credentials
    "DATABASE_URL",
    "*_CONNECTION_STRING",
    "*_DSN",
    # Cloud provider credentials
    "AWS_*",
    "AZURE_*",
    "GCP_*",
    "GOOGLE_*",
    # Certificates and keys
    "*_CERT",
    "*_CERTIFICATE",
    "*_PEM",
    "*_RSA",
    "*_PRIVATE_KEY",
)

# Redaction placeholder for sensitive values
REDACTED_VALUE = "***REDACTED***"


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
        logger.debug("Detected contract type: fsm_subcontract")
        return "fsm_subcontract"

    # Workflow detection - check for workflow-specific fields
    if "workflow_type" in data or (
        "subcontract_name" in data and "max_concurrent_workflows" in data
    ):
        logger.debug("Detected contract type: workflow")
        return "workflow"

    # Node contract detection
    if "node_type" in data:
        logger.debug(
            "Detected contract type: node_contract (node_type=%s)",
            data["node_type"],  # Key existence already verified above
        )
        return "node_contract"

    # Generic subcontract detection
    if "operations" in data and "node_type" not in data:
        logger.debug("Detected contract type: subcontract")
        return "subcontract"

    logger.debug("Unable to detect contract type, returning 'unknown'")
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


def _is_sensitive_env_var(env_var_name: str) -> bool:
    """
    Check if an environment variable name matches sensitive patterns.

    Uses fnmatch for glob-style pattern matching against SENSITIVE_ENV_VAR_PATTERNS.
    Pattern matching is case-insensitive for robustness.

    Args:
        env_var_name: The environment variable name to check

    Returns:
        True if the env var name matches any sensitive pattern, False otherwise

    Examples:
        >>> _is_sensitive_env_var("AWS_SECRET_ACCESS_KEY")
        True
        >>> _is_sensitive_env_var("DATABASE_URL")
        True
        >>> _is_sensitive_env_var("PATH")
        False
        >>> _is_sensitive_env_var("MY_API_KEY")
        True
    """
    # Normalize to uppercase for case-insensitive matching
    upper_name = env_var_name.upper()
    return any(
        fnmatch.fnmatch(upper_name, pattern) for pattern in SENSITIVE_ENV_VAR_PATTERNS
    )


def _get_sensitive_env_values() -> frozenset[str]:
    """
    Get the set of sensitive environment variable values that should be redacted.

    Scans current environment for variables matching SENSITIVE_ENV_VAR_PATTERNS
    and returns their values. Empty values are excluded since they don't need
    redaction and could cause false positives.

    Returns:
        Frozen set of sensitive environment variable values to redact

    Note:
        This function is called once during error message formatting to minimize
        performance impact. The result should be cached if used repeatedly.
    """
    sensitive_values: set[str] = set()
    for env_name, env_value in os.environ.items():
        if env_value and _is_sensitive_env_var(env_name):
            sensitive_values.add(env_value)
    return frozenset(sensitive_values)


def redact_sensitive_values(message: str) -> str:
    """
    Redact sensitive environment variable values from a message string.

    Scans the message for values of environment variables that match
    SENSITIVE_ENV_VAR_PATTERNS and replaces them with REDACTED_VALUE.
    This prevents accidental exposure of secrets in error messages, logs,
    or other output.

    Args:
        message: The message string that may contain sensitive values

    Returns:
        The message with sensitive values replaced by REDACTED_VALUE

    Security:
        - Only redacts values of env vars matching SENSITIVE_ENV_VAR_PATTERNS
        - Empty env var values are not redacted (no false positives)
        - Redaction is case-sensitive to avoid false positives on partial matches
        - Values shorter than 3 characters are not redacted to avoid false positives
    """
    if not message:
        return message

    sensitive_values = _get_sensitive_env_values()

    redacted_message = message
    for value in sensitive_values:
        # Skip very short values to avoid false positives
        # (e.g., single character or empty values matching common words)
        if len(value) < 3:
            continue
        redacted_message = redacted_message.replace(value, REDACTED_VALUE)

    return redacted_message


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
                    error_message=redact_sensitive_values(str(e)),
                    validation_error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            ]
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=contract_type_name,
            )
        except TypeError as e:
            # Type errors during model construction (e.g., wrong argument types)
            validation_errors = [
                ModelContractValidationError(
                    field_path="contract",
                    error_message=redact_sensitive_values(
                        f"Type error during validation: {e}"
                    ),
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
            # Intentionally broad: catch any unexpected errors during Pydantic model
            # validation. ValidationError and ModelOnexError are caught above; this
            # catches truly unexpected errors that may occur during model construction.
            validation_errors = [
                ModelContractValidationError(
                    field_path="contract",
                    error_message=redact_sensitive_values(
                        f"Unexpected error during validation: {e}"
                    ),
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
        except (FileNotFoundError, PermissionError) as e:
            # File system errors during validation
            validation_errors.append(
                ModelContractValidationError(
                    field_path="contract",
                    error_message=redact_sensitive_values(
                        f"File access error during validation: {e}"
                    ),
                    validation_error_type=EnumContractErrorType.FILE_NOT_FOUND
                    if isinstance(e, FileNotFoundError)
                    else EnumContractErrorType.UNEXPECTED_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=node_type_lower,
            )
        except ValueError as e:
            # Configuration or value errors from validator
            validation_errors.append(
                ModelContractValidationError(
                    field_path="contract",
                    error_message=redact_sensitive_values(
                        f"Invalid contract configuration: {e}"
                    ),
                    validation_error_type=EnumContractErrorType.VALIDATION_ERROR,
                )
            )
            return ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=node_type_lower,
            )
        except Exception as e:
            # Intentionally broad: catch unexpected errors from external
            # ProtocolContractValidator. Specific exceptions are caught above.
            validation_errors.append(
                ModelContractValidationError(
                    field_path="contract",
                    error_message=redact_sensitive_values(
                        f"Unexpected error during node contract validation: {e}"
                    ),
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
        logger.debug("Starting validation for: %s", path)
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
                    error_message=redact_sensitive_values(
                        f"Error checking file size: {e}"
                    ),
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
                    error_message=redact_sensitive_values(f"Error reading file: {e}"),
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

        # Warn about missing optional but recommended fields (non-critical)
        if "description" not in data:
            logger.warning(
                "Contract '%s' is missing optional 'description' field "
                "(recommended for documentation)",
                path,
            )

        if contract_type == "fsm_subcontract":
            result = self._validate_fsm_subcontract(data, path)
        elif contract_type == "workflow":
            result = self._validate_workflow(data, path)
        elif contract_type == "node_contract":
            result = self._validate_node_contract(data, path)
        elif contract_type == "subcontract":
            result = self._validate_subcontract(data, path)
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
            result = ModelContractValidationResult(
                file_path=path,
                is_valid=False,
                validation_errors=validation_errors,
                contract_type=None,
            )

        # Log validation result
        if result.is_valid:
            logger.debug(
                "Validation passed for: %s (type=%s)", path, result.contract_type
            )
        else:
            logger.debug(
                "Validation failed for: %s (type=%s, error_count=%d)",
                path,
                result.contract_type,
                len(result.validation_errors),
            )

        return result

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
        file_count = len(file_paths)
        logger.debug("Starting batch validation for %d file(s)", file_count)

        if parallel and file_count > self._parallel_threshold:
            max_workers = min(
                file_count, os.cpu_count() or DEFAULT_MAX_WORKERS_FALLBACK
            )
            logger.debug(
                "Using parallel validation with %d workers (threshold=%d)",
                max_workers,
                self._parallel_threshold,
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(
                    executor.map(
                        self.validate,
                        [Path(fp) if isinstance(fp, str) else fp for fp in file_paths],
                    )
                )
        else:
            logger.debug("Using sequential validation")
            results = [self.validate(fp) for fp in file_paths]

        # Log batch summary at INFO level
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = file_count - valid_count
        logger.info(
            "Batch validation complete: %d/%d passed, %d failed",
            valid_count,
            file_count,
            invalid_count,
        )

        return results

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

        pass_rate = (
            (valid_count / total_count * PERCENTAGE_MULTIPLIER)
            if total_count > 0
            else 0.0
        )

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


def _configure_logging(verbose: bool) -> None:
    """Configure logging based on verbosity flag.

    Sets up the module logger to output to stderr so it doesn't interfere
    with stdout CLI output. In verbose mode, enables DEBUG level logging.
    In non-verbose mode, only WARNING and above are shown.

    Args:
        verbose: If True, enable DEBUG level logging. If False, only WARNING+.
    """
    # Configure handler to write to stderr (not stdout)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Set log level based on verbose flag
    log_level = logging.DEBUG if verbose else logging.WARNING
    logger.setLevel(log_level)
    handler.setLevel(log_level)

    # Remove existing handlers to avoid duplicates on repeated calls
    logger.handlers.clear()
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    if verbose:
        logger.debug("Debug logging enabled")


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
    logger.info("Watch mode started for %d file(s)", len(file_paths))

    # Convert to Path objects for file operations
    paths = [Path(fp) for fp in file_paths]

    # Track last modification times
    mtimes: dict[Path, float] = {}
    for fp in paths:
        if fp.exists():
            mtimes[fp] = fp.stat().st_mtime
            logger.debug("Tracking file: %s (mtime=%.2f)", fp, mtimes[fp])

    try:
        while True:
            changed = False
            changed_files: list[Path] = []
            for fp in paths:
                if fp.exists():
                    current_mtime = fp.stat().st_mtime
                    if fp not in mtimes or mtimes[fp] != current_mtime:
                        mtimes[fp] = current_mtime
                        changed = True
                        changed_files.append(fp)

            if changed:
                logger.info(
                    "File change detected: %s",
                    ", ".join(str(f) for f in changed_files),
                )
                timestamp = time_module.strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Change detected, re-validating...")
                results = linter.validate_batch(file_paths)
                if json_output:
                    print(_format_json_output(results))
                else:
                    print(_format_text_output(results, verbose=verbose))

            time_module.sleep(WATCH_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Watch mode stopped by user")
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
        help="Show detailed error messages and enable debug logging to stderr",
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

    # Configure logging based on verbose flag
    _configure_logging(parsed_args.verbose)

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
                    "error": redact_sensitive_values(str(e)),
                    "cli_error_type": "not_implemented",
                },
                indent=JSON_INDENT_SPACES,
            )
        else:
            error_output = f"Error: {redact_sensitive_values(str(e))}"
        print(error_output, file=sys.stderr)
        return 2

    except (FileNotFoundError, PermissionError) as e:
        # File system errors (file not found, permission denied)
        cli_error_type = (
            "file_not_found"
            if isinstance(e, FileNotFoundError)
            else "permission_denied"
        )
        if parsed_args.json:
            error_output = json.dumps(
                {
                    "error": redact_sensitive_values(str(e)),
                    "cli_error_type": cli_error_type,
                },
                indent=JSON_INDENT_SPACES,
            )
        else:
            error_output = f"Error: {redact_sensitive_values(str(e))}"
        print(error_output, file=sys.stderr)
        return 2

    except KeyboardInterrupt:
        # User interrupted execution
        if parsed_args.json:
            error_output = json.dumps(
                {
                    "error": "Operation cancelled by user",
                    "cli_error_type": "interrupted",
                },
                indent=JSON_INDENT_SPACES,
            )
        else:
            error_output = "Operation cancelled by user"
        print(error_output, file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # Intentionally broad: CLI top-level exception handler to catch any unexpected
        # errors and provide a clean error message. Specific exceptions are caught above.
        if parsed_args.json:
            error_output = json.dumps(
                {
                    "error": redact_sensitive_values(f"Unexpected error: {e}"),
                    "cli_error_type": "unexpected_error",
                },
                indent=JSON_INDENT_SPACES,
            )
        else:
            error_output = f"Unexpected error: {redact_sensitive_values(str(e))}"
        print(error_output, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
