# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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
    # Note: For node contracts, BOTH contract_version AND node_version are required.
    # For non-node contracts, at least one version field must be present.
    COMMON_REQUIRED_FIELDS: tuple[str, ...] = (
        "name",
        "node_type",
        "description",
        "input_model",
        "output_model",
    )

    # Version field names recognized by the validator.
    # - "contract_version": Required for node contracts (contract schema version)
    # - "node_version": Required for node contracts (implementation version)
    # Note: Node contracts MUST have both contract_version AND node_version.
    #       Non-node contracts require at least one of these fields.
    VERSION_FIELDS: tuple[str, ...] = (
        "contract_version",
        "node_version",
    )

    # Required version fields for node contracts.
    # Node contracts MUST have BOTH of these version fields:
    # - contract_version: Defines the contract schema version (e.g., {major: 1, minor: 0, patch: 0})
    # - node_version: Defines the node implementation version (e.g., {major: 1, minor: 0, patch: 0})
    # This is enforced by _validate_version_fields() when is_node_contract=True.
    NODE_CONTRACT_REQUIRED_VERSION_FIELDS: tuple[str, ...] = (
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
        violations.extend(
            self._validate_required_fields(data, self.COMMON_REQUIRED_FIELDS)
        )

        # Determine if this is a node contract (has node_type field)
        node_type = data.get("node_type")
        is_node_contract = node_type is not None and isinstance(node_type, str)

        # Validate version fields - node contracts require both contract_version and node_version
        violations.extend(
            self._validate_version_fields(data, is_node_contract=is_node_contract)
        )

        # Validate node_type matches expected contract_type (if provided)
        # Note: is_node_contract already verified node_type is a non-None string
        # Use isinstance check to satisfy mypy's type narrowing
        if (
            contract_type
            and is_node_contract
            and isinstance(node_type, str)
            and node_type.lower() != contract_type.lower()
        ):
            violations.append(
                f"node_type: Expected '{contract_type}', got '{node_type}'"
            )

        # Validate node-type-specific fields
        # Use isinstance check to satisfy mypy's type narrowing
        effective_type = contract_type or (
            node_type.lower()
            if is_node_contract and isinstance(node_type, str)
            else None
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
        data: dict[str, object],
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

    def _validate_version_fields(
        self, data: dict[str, object], is_node_contract: bool = True
    ) -> list[str]:
        """Validate version fields are present and valid.

        For node contracts, BOTH contract_version AND node_version are required
        as defined in NODE_CONTRACT_REQUIRED_VERSION_FIELDS.
        For other contracts, at least one version field must be present.

        Args:
            data: The contract data to validate.
            is_node_contract: If True, enforces both contract_version and node_version
                as required by NODE_CONTRACT_REQUIRED_VERSION_FIELDS.
        """
        violations: list[str] = []

        # Check if any version field is present
        version_fields_present = [
            field for field in self.VERSION_FIELDS if field in data
        ]

        if is_node_contract:
            # Node contracts MUST have ALL fields in NODE_CONTRACT_REQUIRED_VERSION_FIELDS
            # This enforces both contract_version AND node_version
            for required_field in self.NODE_CONTRACT_REQUIRED_VERSION_FIELDS:
                if required_field not in data:
                    field_descriptions = {
                        "contract_version": "the contract schema version",
                        "node_version": "the node implementation version",
                    }
                    desc = field_descriptions.get(required_field, "a version")
                    violations.append(
                        f"{required_field}: Missing required field for node contract. "
                        f"Node contracts must specify {desc}."
                    )
            # Validate structure of present version fields
            for field in version_fields_present:
                violations.extend(self._validate_version_structure(data[field], field))
        else:
            # Non-node contracts need at least one version field
            if not version_fields_present:
                violations.append(
                    f"version: Missing required version field. "
                    f"Expected one of: {', '.join(self.VERSION_FIELDS)}"
                )
            else:
                # Validate each present version field
                for field in version_fields_present:
                    violations.extend(
                        self._validate_version_structure(data[field], field)
                    )

        return violations

    def _validate_version_structure(
        self, version: object, field_name: str = "version"
    ) -> list[str]:
        """Validate version field structure and semantic version format.

        Version must be an object with major, minor, and patch fields.
        Each component must be a non-negative integer following semantic versioning.
        String versions like "1.0.0" are not valid for ONEX contracts.

        Args:
            version: The version value to validate.
            field_name: The field name for error messages (e.g., "contract_version").

        Returns:
            List of violation messages for any validation failures.
        """
        violations: list[str] = []

        if version is None:
            violations.append(f"{field_name}: Version field cannot be null")
            return violations

        if isinstance(version, str):
            # String version is not valid for ONEX contracts - must be object
            violations.append(
                f"{field_name}: Expected object with major/minor/patch fields, got string '{version}'. "
                f"Use structured format: {field_name}: {{major: 1, minor: 0, patch: 0}}"
            )
        elif isinstance(version, dict):
            # Structured version object - validate required fields and their types
            version_components = ("major", "minor", "patch")

            for component in version_components:
                if component not in version:
                    violations.append(
                        f"{field_name}.{component}: Missing required field. "
                        f"Semantic version requires major, minor, and patch components."
                    )
                else:
                    component_value = version[component]
                    violations.extend(
                        self._validate_version_component(
                            component_value, f"{field_name}.{component}"
                        )
                    )
        else:
            violations.append(
                f"{field_name}: Expected object with major/minor/patch, got {type(version).__name__}. "
                f"Use structured format: {field_name}: {{major: 1, minor: 0, patch: 0}}"
            )

        return violations

    def _validate_version_component(
        self, value: object, component_path: str
    ) -> list[str]:
        """Validate a single version component (major, minor, or patch).

        Args:
            value: The component value to validate.
            component_path: Full path for error messages (e.g., "contract_version.major").

        Returns:
            List of violation messages for any validation failures.
        """
        violations: list[str] = []

        if value is None:
            violations.append(f"{component_path}: Version component cannot be null")
        elif not isinstance(value, int):
            violations.append(
                f"{component_path}: Expected non-negative integer, got {type(value).__name__} ({value!r})"
            )
        elif value < 0:
            violations.append(
                f"{component_path}: Version component must be non-negative, got {value}"
            )

        return violations

    def _validate_name(self, name: object) -> list[str]:
        """Validate name field."""
        violations: list[str] = []

        if not isinstance(name, str):
            violations.append(f"name: Expected string, got {type(name).__name__}")
        elif not name.strip():
            violations.append("name: Cannot be empty or whitespace only")

        return violations
