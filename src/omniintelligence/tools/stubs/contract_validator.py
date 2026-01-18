# SPDX-License-Identifier: Apache-2.0
"""
Stub implementation of ProtocolContractValidator.

This module provides a stub implementation of the ProtocolContractValidator
that would normally be provided by omnibase_core.validation.contract_validator.
The stub performs basic YAML structure validation for ONEX node contracts.

This is a temporary implementation until the actual omnibase_core module
provides the ProtocolContractValidator class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProtocolContractValidatorResult:
    """
    Result of contract validation.

    Attributes:
        is_valid: Whether the contract passed all validation checks.
        violations: List of violation messages (strings) describing validation failures.
    """

    is_valid: bool = True
    violations: list[str] = field(default_factory=list)


class ProtocolContractValidator:
    """
    Stub implementation of ProtocolContractValidator for ONEX node contracts.

    This validator performs basic structural validation of YAML contract files.
    It checks for required fields based on the contract_type (compute, effect,
    reducer, orchestrator).

    This is a stub implementation that provides basic validation functionality
    until the full omnibase_core.validation.contract_validator module is available.
    """

    # Required fields for all node contracts
    # Note: version can be either 'version', 'contract_version', or 'node_version'
    COMMON_REQUIRED_FIELDS: tuple[str, ...] = (
        "name",
        "node_type",
        "description",
        "input_model",
        "output_model",
    )

    # Alternative version field names (at least one must be present)
    VERSION_FIELDS: tuple[str, ...] = (
        "version",
        "contract_version",
        "node_version",
    )

    # Additional required fields per node type
    # Keys include both base types (compute, effect) and extended types (compute_generic, etc.)
    # NOTE: algorithm and io_operations are optional for stub contracts
    NODE_TYPE_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
        # Base types - no additional required fields for stubs
        "compute": (),
        "effect": (),
        "reducer": (),
        "orchestrator": (),
        # Extended generic types - no additional required fields for stubs
        "compute_generic": (),
        "effect_generic": (),
        "reducer_generic": (),
        "orchestrator_generic": (),
    }

    # Recommended fields (generate warnings, not violations)
    RECOMMENDED_FIELDS: tuple[str, ...] = (
        "author",
        "performance",
    )

    def __init__(self) -> None:
        """Initialize the contract validator."""
        pass

    def validate_contract_file(
        self,
        path: Path | str,
        *,
        contract_type: str | None = None,
    ) -> ProtocolContractValidatorResult:
        """
        Validate a contract YAML file.

        Args:
            path: Path to the YAML contract file.
            contract_type: Expected contract type (compute, effect, reducer, orchestrator).
                          If None, the type is inferred from the file content.

        Returns:
            ProtocolContractValidatorResult with validation status and any violations.
        """
        path = Path(path) if isinstance(path, str) else path
        violations: list[str] = []

        # Load and parse YAML
        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except FileNotFoundError:
            return ProtocolContractValidatorResult(
                is_valid=False,
                violations=[f"file: Contract file not found: {path}"],
            )
        except yaml.YAMLError as e:
            return ProtocolContractValidatorResult(
                is_valid=False,
                violations=[f"yaml: Invalid YAML syntax: {e}"],
            )
        except OSError as e:
            return ProtocolContractValidatorResult(
                is_valid=False,
                violations=[f"file: Error reading contract file: {e}"],
            )

        # Check for valid parsed content
        if data is None:
            return ProtocolContractValidatorResult(
                is_valid=False,
                violations=["file: Contract file is empty or contains only comments"],
            )

        if not isinstance(data, dict):
            return ProtocolContractValidatorResult(
                is_valid=False,
                violations=[
                    f"structure: Contract must be a YAML mapping, got {type(data).__name__}"
                ],
            )

        # Validate common required fields
        violations.extend(self._validate_required_fields(data, self.COMMON_REQUIRED_FIELDS))

        # Validate that at least one version field is present
        violations.extend(self._validate_version_fields(data))

        # Get or validate node_type
        node_type = data.get("node_type")
        if (
            contract_type
            and node_type
            and isinstance(node_type, str)
            and node_type.lower() != contract_type.lower()
        ):
            violations.append(
                f"node_type: Expected '{contract_type}', got '{node_type}'"
            )

        # Validate node-type-specific fields
        effective_type = contract_type or (
            node_type.lower() if isinstance(node_type, str) else None
        )
        if effective_type and effective_type in self.NODE_TYPE_REQUIRED_FIELDS:
            violations.extend(
                self._validate_required_fields(
                    data, self.NODE_TYPE_REQUIRED_FIELDS[effective_type]
                )
            )

        # Note: Version structure validation is now handled by _validate_version_fields

        # Validate name if present
        if "name" in data:
            violations.extend(self._validate_name(data["name"]))

        return ProtocolContractValidatorResult(
            is_valid=len(violations) == 0,
            violations=violations,
        )

    def _validate_required_fields(
        self,
        data: dict[str, Any],
        required_fields: tuple[str, ...],
    ) -> list[str]:
        """Check for missing required fields."""
        violations: list[str] = []
        for field_name in required_fields:
            if field_name not in data:
                violations.append(f"{field_name}: Missing required field")
            elif data[field_name] is None:
                violations.append(f"{field_name}: Field cannot be null")
        return violations

    def _validate_version_fields(self, data: dict[str, Any]) -> list[str]:
        """Validate that at least one version field is present.

        ONEX contracts can use 'version', 'contract_version', or 'node_version'.
        At least one must be present. If present, validates the structure.
        """
        violations: list[str] = []

        # Check if any version field is present
        version_fields_present = [
            field for field in self.VERSION_FIELDS if field in data
        ]

        if not version_fields_present:
            violations.append(
                f"version: Missing required version field. "
                f"Expected one of: {', '.join(self.VERSION_FIELDS)}"
            )
        else:
            # Validate each present version field
            for field in version_fields_present:
                violations.extend(self._validate_version_structure(data[field], field))

        return violations

    def _validate_version_structure(
        self, version: Any, field_name: str = "version"
    ) -> list[str]:
        """Validate version field structure.

        Version must be an object with major, minor, and patch fields.
        String versions like "1.0.0" are not valid for ONEX contracts.
        """
        violations: list[str] = []

        if isinstance(version, str):
            # String version is not valid for ONEX contracts - must be object
            violations.append(
                f"{field_name}: Expected object with major/minor/patch fields, got string '{version}'"
            )
        elif isinstance(version, dict):
            # Structured version object - validate required fields
            if "major" not in version:
                violations.append(f"{field_name}.major: Missing required field")
            if "minor" not in version:
                violations.append(f"{field_name}.minor: Missing required field")
            if "patch" not in version:
                violations.append(f"{field_name}.patch: Missing required field")
        elif version is not None:
            violations.append(
                f"{field_name}: Expected object with major/minor/patch, got {type(version).__name__}"
            )

        return violations

    def _validate_version(self, version: Any) -> list[str]:
        """Validate version field structure.

        Version must be an object with major, minor, and patch fields.
        String versions like "1.0.0" are not valid for ONEX contracts.
        """
        violations: list[str] = []

        if isinstance(version, str):
            # String version is not valid for ONEX contracts - must be object
            violations.append(
                f"version: Expected object with major/minor/patch fields, got string '{version}'"
            )
        elif isinstance(version, dict):
            # Structured version object - validate required fields
            if "major" not in version:
                violations.append("version.major: Missing required field")
            if "minor" not in version:
                violations.append("version.minor: Missing required field")
            if "patch" not in version:
                violations.append("version.patch: Missing required field")
        elif version is not None:
            violations.append(
                f"version: Expected object with major/minor/patch, got {type(version).__name__}"
            )

        return violations

    def _validate_name(self, name: Any) -> list[str]:
        """Validate name field."""
        violations: list[str] = []

        if not isinstance(name, str):
            violations.append(f"name: Expected string, got {type(name).__name__}")
        elif not name.strip():
            violations.append("name: Cannot be empty or whitespace only")

        return violations
