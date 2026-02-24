# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelContractValidationError - single validation error for contract linting."""

from __future__ import annotations

from omniintelligence.tools.enum_contract_error_type import EnumContractErrorType


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
