# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelContractValidationResult - result of contract file validation."""

from __future__ import annotations

from pathlib import Path

from omniintelligence.tools.model_contract_validation_error import (
    ModelContractValidationError,
)


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
