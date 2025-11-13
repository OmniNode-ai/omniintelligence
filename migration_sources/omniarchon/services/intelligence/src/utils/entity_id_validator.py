"""
Entity ID Validator with Schema Enforcement

Validates entity_id formats against canonical schema to prevent deprecated
path-based entity IDs and ensure schema compliance.

**Problem**: Mixed entity_id formats cause relationship disconnection
**Solution**: Runtime validation layer with clear error messages

**Entity ID Formats**:

FILE nodes:
  ✅ Valid:      file_<hash12>           (e.g., file_91f521860bc3)
  ❌ Deprecated: file:<project>:<module> (e.g., file:omniarchon:asyncio)
  ❌ Deprecated: file:<project>:<path>   (e.g., file:omniarchon:archon://...)

Entity nodes:
  ✅ Valid:      entity_<hash8>_<hash8>  (e.g., entity_7275cb2b_f839d8c2)
  ⚠️  Stub:      <simple_name>           (e.g., httpx, inline)

Function nodes:
  ✅ Valid:      function_<hash12>       (e.g., function_a1b2c3d4e5f6)

Class nodes:
  ✅ Valid:      class_<hash12>          (e.g., class_1234567890ab)

**Usage**:

```python
from utils.entity_id_validator import EntityIDValidator, validate_file_entity_id

# Quick validation
is_valid = validate_file_entity_id("file_91f521860bc3")  # True
is_valid = validate_file_entity_id("file:omniarchon:asyncio")  # False

# Comprehensive validation with error messages
result = EntityIDValidator.validate("file_91f521860bc3", "FILE")
if not result.is_valid:
    raise ValueError(result.error_message)

# Pydantic integration
from pydantic import BaseModel, field_validator

class FileNode(BaseModel):
    entity_id: str

    @field_validator('entity_id')
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        return EntityIDValidator.validate_and_raise(value, "FILE")
```

**Performance**: <1ms per validation (regex-based)
**Reference**: ENTITY_ID_FORMAT_REFERENCE.md, ENTITY_ID_SCHEMA_FIX_STRATEGY.md
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    """Supported entity types for validation."""

    FILE = "FILE"
    ENTITY = "ENTITY"
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    STUB = "STUB"


@dataclass(frozen=True)
class ValidationResult:
    """
    Structured validation result with detailed error information.

    Attributes:
        is_valid: Whether entity_id passes validation
        entity_type: Type of entity being validated
        error_message: Detailed error message if validation fails
        detected_format: Format detected (e.g., "hash-based", "path-based")
    """

    is_valid: bool
    entity_type: str
    error_message: Optional[str] = None
    detected_format: Optional[str] = None


class EntityIDValidator:
    """
    Entity ID validator with schema enforcement.

    Validates entity_id formats against canonical schema, rejecting deprecated
    path-based formats and enforcing hash-based entity IDs.

    **Expected Formats**:

    - FILE:     ^file_[a-f0-9]{12}$
    - ENTITY:   ^entity_[a-f0-9]{8}_[a-f0-9]{8}$
    - FUNCTION: ^function_[a-f0-9]{12}$
    - CLASS:    ^class_[a-f0-9]{12}$
    - STUB:     ^[a-z_][a-z0-9_]*$  (simple identifier, no colons/slashes)

    **Deprecated Formats** (validation fails):

    - Path-based FILE: file:<project>:<module>
    - Path-based FILE: file:<project>:<path>
    """

    # Canonical hash-based formats (VALID)
    FILE_HASH_PATTERN = re.compile(r"^file_[a-f0-9]{12}$")
    ENTITY_HASH_PATTERN = re.compile(r"^entity_[a-f0-9]{8}_[a-f0-9]{8}$")
    FUNCTION_HASH_PATTERN = re.compile(r"^function_[a-f0-9]{12}$")
    CLASS_HASH_PATTERN = re.compile(r"^class_[a-f0-9]{12}$")

    # Stub entity format (simple identifier, no special chars)
    STUB_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$", re.IGNORECASE)

    # Deprecated path-based formats (INVALID)
    PATH_BASED_PATTERN = re.compile(r"^file:[^:]+:.+$")
    PLACEHOLDER_PATTERN = re.compile(r"placeholder", re.IGNORECASE)

    @classmethod
    def validate_file_id(cls, entity_id: str) -> ValidationResult:
        """
        Validate FILE entity_id format.

        Args:
            entity_id: Entity ID to validate

        Returns:
            ValidationResult with validation status and error message

        Examples:
            >>> result = EntityIDValidator.validate_file_id("file_91f521860bc3")
            >>> result.is_valid
            True

            >>> result = EntityIDValidator.validate_file_id("file:omniarchon:asyncio")
            >>> result.is_valid
            False
            >>> result.error_message
            'DEPRECATED: Path-based FILE entity_id ...'
        """
        # Check for valid hash-based format
        if cls.FILE_HASH_PATTERN.match(entity_id):
            return ValidationResult(
                is_valid=True, entity_type=EntityType.FILE, detected_format="hash-based"
            )

        # Check for deprecated path-based format
        if cls.PATH_BASED_PATTERN.match(entity_id):
            return ValidationResult(
                is_valid=False,
                entity_type=EntityType.FILE,
                error_message=(
                    f"DEPRECATED: Path-based FILE entity_id '{entity_id}'. "
                    f"Use hash-based format: file_<hash12> "
                    f"(e.g., file_91f521860bc3)"
                ),
                detected_format="path-based (deprecated)",
            )

        # Check for placeholder format
        if cls.PLACEHOLDER_PATTERN.search(entity_id):
            return ValidationResult(
                is_valid=False,
                entity_type=EntityType.FILE,
                error_message=(
                    f"INVALID: Placeholder FILE entity_id '{entity_id}'. "
                    f"Use hash-based format: file_<hash12>"
                ),
                detected_format="placeholder (invalid)",
            )

        # Invalid format
        return ValidationResult(
            is_valid=False,
            entity_type=EntityType.FILE,
            error_message=(
                f"INVALID: FILE entity_id '{entity_id}' does not match expected format. "
                f"Expected: file_<hash12> (12 lowercase hex chars), "
                f"e.g., file_91f521860bc3"
            ),
            detected_format="unknown",
        )

    @classmethod
    def validate_entity_id(cls, entity_id: str) -> ValidationResult:
        """
        Validate ENTITY entity_id format.

        Args:
            entity_id: Entity ID to validate

        Returns:
            ValidationResult with validation status and error message

        Examples:
            >>> result = EntityIDValidator.validate_entity_id("entity_7275cb2b_f839d8c2")
            >>> result.is_valid
            True

            >>> result = EntityIDValidator.validate_entity_id("httpx")
            >>> result.is_valid
            True
            >>> result.detected_format
            'stub'
        """
        # Check for valid entity hash format
        if cls.ENTITY_HASH_PATTERN.match(entity_id):
            return ValidationResult(
                is_valid=True,
                entity_type=EntityType.ENTITY,
                detected_format="hash-based",
            )

        # Check for stub entity (simple identifier)
        # BUT: Reject if it looks like a malformed entity ID (starts with entity_/file_/class_/function_)
        if cls.STUB_PATTERN.match(entity_id):
            # Reject stubs that start with reserved prefixes
            lower_id = entity_id.lower()
            if any(
                lower_id.startswith(prefix)
                for prefix in ["entity_", "file_", "class_", "function_"]
            ):
                # This looks like a malformed entity ID, not a stub
                return ValidationResult(
                    is_valid=False,
                    entity_type=EntityType.ENTITY,
                    error_message=(
                        f"INVALID: ENTITY entity_id '{entity_id}' appears to be malformed. "
                        f"Entity IDs starting with 'entity_' must match format: entity_<hash8>_<hash8>. "
                        f"For stub entities, use simple identifiers without reserved prefixes."
                    ),
                    detected_format="malformed (reserved prefix)",
                )

            # Valid stub
            return ValidationResult(
                is_valid=True, entity_type=EntityType.STUB, detected_format="stub"
            )

        # Invalid format
        return ValidationResult(
            is_valid=False,
            entity_type=EntityType.ENTITY,
            error_message=(
                f"INVALID: ENTITY entity_id '{entity_id}' does not match expected format. "
                f"Expected: entity_<hash8>_<hash8> (two 8-char hex hashes), "
                f"e.g., entity_7275cb2b_f839d8c2, or simple stub identifier"
            ),
            detected_format="unknown",
        )

    @classmethod
    def validate_function_id(cls, entity_id: str) -> ValidationResult:
        """
        Validate FUNCTION entity_id format.

        Args:
            entity_id: Entity ID to validate

        Returns:
            ValidationResult with validation status and error message
        """
        if cls.FUNCTION_HASH_PATTERN.match(entity_id):
            return ValidationResult(
                is_valid=True,
                entity_type=EntityType.FUNCTION,
                detected_format="hash-based",
            )

        return ValidationResult(
            is_valid=False,
            entity_type=EntityType.FUNCTION,
            error_message=(
                f"INVALID: FUNCTION entity_id '{entity_id}' does not match expected format. "
                f"Expected: function_<hash12> (12 lowercase hex chars), "
                f"e.g., function_a1b2c3d4e5f6"
            ),
            detected_format="unknown",
        )

    @classmethod
    def validate_class_id(cls, entity_id: str) -> ValidationResult:
        """
        Validate CLASS entity_id format.

        Args:
            entity_id: Entity ID to validate

        Returns:
            ValidationResult with validation status and error message
        """
        if cls.CLASS_HASH_PATTERN.match(entity_id):
            return ValidationResult(
                is_valid=True,
                entity_type=EntityType.CLASS,
                detected_format="hash-based",
            )

        return ValidationResult(
            is_valid=False,
            entity_type=EntityType.CLASS,
            error_message=(
                f"INVALID: CLASS entity_id '{entity_id}' does not match expected format. "
                f"Expected: class_<hash12> (12 lowercase hex chars), "
                f"e.g., class_1234567890ab"
            ),
            detected_format="unknown",
        )

    @classmethod
    def validate(cls, entity_id: str, entity_type: str) -> ValidationResult:
        """
        Comprehensive validation with entity type detection.

        Args:
            entity_id: Entity ID to validate
            entity_type: Type of entity (FILE, ENTITY, FUNCTION, CLASS)

        Returns:
            ValidationResult with validation status and error message

        Raises:
            ValueError: If entity_type is not recognized

        Examples:
            >>> result = EntityIDValidator.validate("file_91f521860bc3", "FILE")
            >>> result.is_valid
            True

            >>> result = EntityIDValidator.validate("file:omniarchon:asyncio", "FILE")
            >>> result.is_valid
            False
        """
        # Normalize entity_type
        entity_type_upper = entity_type.upper()

        # Dispatch to appropriate validator
        if entity_type_upper == EntityType.FILE:
            return cls.validate_file_id(entity_id)
        elif (
            entity_type_upper == EntityType.ENTITY
            or entity_type_upper == EntityType.STUB
        ):
            return cls.validate_entity_id(entity_id)
        elif entity_type_upper == EntityType.FUNCTION:
            return cls.validate_function_id(entity_id)
        elif entity_type_upper == EntityType.CLASS:
            return cls.validate_class_id(entity_id)
        else:
            raise ValueError(
                f"Unsupported entity_type: '{entity_type}'. "
                f"Supported types: {[e.value for e in EntityType]}"
            )

    @classmethod
    def validate_and_raise(cls, entity_id: str, entity_type: str) -> str:
        """
        Validate and raise ValueError if invalid (for Pydantic validators).

        Args:
            entity_id: Entity ID to validate
            entity_type: Type of entity

        Returns:
            entity_id: Original entity_id if valid

        Raises:
            ValueError: If validation fails

        Examples:
            >>> EntityIDValidator.validate_and_raise("file_91f521860bc3", "FILE")
            'file_91f521860bc3'

            >>> EntityIDValidator.validate_and_raise("file:omniarchon:asyncio", "FILE")
            Traceback (most recent call last):
                ...
            ValueError: Entity ID validation failed: DEPRECATED: Path-based FILE entity_id ...
        """
        result = cls.validate(entity_id, entity_type)

        if not result.is_valid:
            raise ValueError(f"Entity ID validation failed: {result.error_message}")

        return entity_id


# Convenience functions for quick validation


def validate_file_entity_id(entity_id: str) -> bool:
    """
    Quick validation for FILE entity_id (returns boolean only).

    Args:
        entity_id: Entity ID to validate

    Returns:
        True if valid hash-based FILE entity_id, False otherwise

    Examples:
        >>> validate_file_entity_id("file_91f521860bc3")
        True

        >>> validate_file_entity_id("file:omniarchon:asyncio")
        False
    """
    result = EntityIDValidator.validate_file_id(entity_id)
    return result.is_valid


def validate_entity_entity_id(entity_id: str) -> bool:
    """
    Quick validation for ENTITY entity_id (returns boolean only).

    Args:
        entity_id: Entity ID to validate

    Returns:
        True if valid hash-based ENTITY entity_id or stub, False otherwise

    Examples:
        >>> validate_entity_entity_id("entity_7275cb2b_f839d8c2")
        True

        >>> validate_entity_entity_id("httpx")
        True
    """
    result = EntityIDValidator.validate_entity_id(entity_id)
    return result.is_valid


def is_deprecated_format(entity_id: str) -> bool:
    """
    Check if entity_id uses deprecated path-based format.

    Args:
        entity_id: Entity ID to check

    Returns:
        True if deprecated format, False otherwise

    Examples:
        >>> is_deprecated_format("file:omniarchon:asyncio")
        True

        >>> is_deprecated_format("file_91f521860bc3")
        False
    """
    return EntityIDValidator.PATH_BASED_PATTERN.match(entity_id) is not None


def is_placeholder_format(entity_id: str) -> bool:
    """
    Check if entity_id contains 'placeholder' (invalid format).

    Args:
        entity_id: Entity ID to check

    Returns:
        True if placeholder format, False otherwise

    Examples:
        >>> is_placeholder_format("file_placeholder_abc123")
        True

        >>> is_placeholder_format("file_91f521860bc3")
        False
    """
    return EntityIDValidator.PLACEHOLDER_PATTERN.search(entity_id) is not None
