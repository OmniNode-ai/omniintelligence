"""
Comprehensive unit tests for Entity ID Validator.

Tests validation logic for all entity types with both valid and invalid formats,
edge cases, performance benchmarks, and Pydantic integration.

**Test Coverage**:
- FILE entity IDs (hash-based, path-based, placeholders)
- ENTITY entity IDs (hash-based, stubs)
- FUNCTION entity IDs
- CLASS entity IDs
- Convenience functions
- Pydantic integration
- Performance benchmarks
"""

import time

import pytest
from pydantic import BaseModel, ValidationError, field_validator
from utils.entity_id_validator import (
    EntityIDValidator,
    EntityType,
    ValidationResult,
    is_deprecated_format,
    is_placeholder_format,
    validate_entity_entity_id,
    validate_file_entity_id,
)

# =============================================================================
# FILE Entity ID Tests
# =============================================================================


class TestFileEntityIDValidation:
    """Tests for FILE entity_id validation."""

    @pytest.mark.parametrize(
        "valid_id",
        [
            "file_91f521860bc3",  # Standard format
            "file_a1b2c3d4e5f6",  # All hex chars
            "file_000000000000",  # All zeros (edge case)
            "file_ffffffffffff",  # All f's (edge case)
            "file_abcdef123456",  # Mixed hex
        ],
    )
    def test_valid_file_entity_ids(self, valid_id: str):
        """Test that valid hash-based FILE entity IDs pass validation."""
        result = EntityIDValidator.validate_file_id(valid_id)

        assert result.is_valid is True
        assert result.entity_type == EntityType.FILE
        assert result.error_message is None
        assert result.detected_format == "hash-based"

    @pytest.mark.parametrize(
        "deprecated_id,expected_substring",
        [
            ("file:omniarchon:asyncio", "DEPRECATED"),
            ("file:omniarchon:httpx", "Path-based"),
            ("file:project:/path/to/file.py", "DEPRECATED"),
            (
                "file:archon:archon://projects/omniarchon/documents/file.py",
                "hash-based format",
            ),
        ],
    )
    def test_deprecated_path_based_file_ids(
        self, deprecated_id: str, expected_substring: str
    ):
        """Test that deprecated path-based FILE entity IDs fail validation."""
        result = EntityIDValidator.validate_file_id(deprecated_id)

        assert result.is_valid is False
        assert result.entity_type == EntityType.FILE
        assert result.error_message is not None
        assert expected_substring in result.error_message
        assert result.detected_format == "path-based (deprecated)"

    @pytest.mark.parametrize(
        "placeholder_id",
        [
            "file_placeholder_abc123",
            "FILE_PLACEHOLDER_XYZ",
            "file_placeholder_",
        ],
    )
    def test_placeholder_file_ids(self, placeholder_id: str):
        """Test that placeholder FILE entity IDs fail validation."""
        result = EntityIDValidator.validate_file_id(placeholder_id)

        assert result.is_valid is False
        assert result.entity_type == EntityType.FILE
        assert "placeholder" in result.error_message.lower()
        assert result.detected_format == "placeholder (invalid)"

    @pytest.mark.parametrize(
        "invalid_id,reason",
        [
            ("file_91f521860bc", "Too short (11 chars)"),
            ("file_91f521860bc34", "Too long (13 chars)"),
            ("file_91F521860BC3", "Uppercase hex (should be lowercase)"),
            ("file_91g521860bc3", "Invalid hex char 'g'"),
            ("file_", "Missing hash"),
            ("file", "Missing underscore and hash"),
            ("91f521860bc3", "Missing 'file_' prefix"),
            ("file:91f521860bc3", "Wrong separator (colon)"),
        ],
    )
    def test_invalid_file_entity_ids(self, invalid_id: str, reason: str):
        """Test that malformed FILE entity IDs fail validation."""
        result = EntityIDValidator.validate_file_id(invalid_id)

        assert (
            result.is_valid is False
        ), f"Expected {invalid_id} to be invalid ({reason})"
        assert result.entity_type == EntityType.FILE
        assert result.error_message is not None
        assert (
            "INVALID" in result.error_message
            or "does not match" in result.error_message
        )


# =============================================================================
# ENTITY Entity ID Tests
# =============================================================================


class TestEntityEntityIDValidation:
    """Tests for ENTITY entity_id validation."""

    @pytest.mark.parametrize(
        "valid_id",
        [
            "entity_7275cb2b_f839d8c2",  # Standard format
            "entity_79775386_91f52186",  # Another example
            "entity_00000000_00000000",  # Edge case: all zeros
            "entity_ffffffff_ffffffff",  # Edge case: all f's
        ],
    )
    def test_valid_entity_entity_ids(self, valid_id: str):
        """Test that valid hash-based ENTITY entity IDs pass validation."""
        result = EntityIDValidator.validate_entity_id(valid_id)

        assert result.is_valid is True
        assert result.entity_type == EntityType.ENTITY
        assert result.error_message is None
        assert result.detected_format == "hash-based"

    @pytest.mark.parametrize(
        "stub_id",
        [
            "httpx",  # Simple module name
            "inline",  # Another module
            "time",  # Standard library
            "json",  # Standard library
            "sys",  # Standard library
            "_private",  # Leading underscore
            "my_module",  # Underscore in name
        ],
    )
    def test_valid_stub_entity_ids(self, stub_id: str):
        """Test that valid stub ENTITY entity IDs pass validation."""
        result = EntityIDValidator.validate_entity_id(stub_id)

        assert result.is_valid is True
        assert result.entity_type == EntityType.STUB
        assert result.error_message is None
        assert result.detected_format == "stub"

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "entity_7275cb2b",  # Missing second hash
            "entity_7275cb2b_f839d8c",  # Second hash too short (7 chars)
            "entity_7275cb2b_f839d8c22",  # Second hash too long (9 chars)
            "entity_7275CB2B_f839d8c2",  # Uppercase hex
            "entity_7275gb2b_f839d8c2",  # Invalid hex char 'g'
            "entity__f839d8c2",  # Missing first hash
            "entity_7275cb2b_",  # Missing second hash
            "7275cb2b_f839d8c2",  # Missing 'entity_' prefix
            "file:module",  # Path-based format
        ],
    )
    def test_invalid_entity_entity_ids(self, invalid_id: str):
        """Test that malformed ENTITY entity IDs fail validation."""
        result = EntityIDValidator.validate_entity_id(invalid_id)

        assert result.is_valid is False, f"Expected {invalid_id} to be invalid"
        assert result.entity_type == EntityType.ENTITY
        assert result.error_message is not None


# =============================================================================
# FUNCTION Entity ID Tests
# =============================================================================


class TestFunctionEntityIDValidation:
    """Tests for FUNCTION entity_id validation."""

    @pytest.mark.parametrize(
        "valid_id",
        [
            "function_a1b2c3d4e5f6",
            "function_123456789abc",
            "function_000000000000",
            "function_ffffffffffff",
        ],
    )
    def test_valid_function_entity_ids(self, valid_id: str):
        """Test that valid hash-based FUNCTION entity IDs pass validation."""
        result = EntityIDValidator.validate_function_id(valid_id)

        assert result.is_valid is True
        assert result.entity_type == EntityType.FUNCTION
        assert result.error_message is None
        assert result.detected_format == "hash-based"

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "function_a1b2c3d4e5f",  # Too short
            "function_a1b2c3d4e5f66",  # Too long
            "function_A1B2C3D4E5F6",  # Uppercase
            "function_",  # Missing hash
        ],
    )
    def test_invalid_function_entity_ids(self, invalid_id: str):
        """Test that malformed FUNCTION entity IDs fail validation."""
        result = EntityIDValidator.validate_function_id(invalid_id)

        assert result.is_valid is False
        assert result.entity_type == EntityType.FUNCTION
        assert result.error_message is not None


# =============================================================================
# CLASS Entity ID Tests
# =============================================================================


class TestClassEntityIDValidation:
    """Tests for CLASS entity_id validation."""

    @pytest.mark.parametrize(
        "valid_id",
        [
            "class_1234567890ab",
            "class_abcdef123456",
            "class_000000000000",
            "class_ffffffffffff",
        ],
    )
    def test_valid_class_entity_ids(self, valid_id: str):
        """Test that valid hash-based CLASS entity IDs pass validation."""
        result = EntityIDValidator.validate_class_id(valid_id)

        assert result.is_valid is True
        assert result.entity_type == EntityType.CLASS
        assert result.error_message is None
        assert result.detected_format == "hash-based"

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "class_1234567890a",  # Too short
            "class_1234567890abc",  # Too long
            "class_1234567890AB",  # Uppercase
            "class_",  # Missing hash
        ],
    )
    def test_invalid_class_entity_ids(self, invalid_id: str):
        """Test that malformed CLASS entity IDs fail validation."""
        result = EntityIDValidator.validate_class_id(invalid_id)

        assert result.is_valid is False
        assert result.entity_type == EntityType.CLASS
        assert result.error_message is not None


# =============================================================================
# Comprehensive Validation Tests
# =============================================================================


class TestComprehensiveValidation:
    """Tests for comprehensive validate() method."""

    def test_validate_with_file_type(self):
        """Test validate() dispatches to FILE validator."""
        result = EntityIDValidator.validate("file_91f521860bc3", "FILE")

        assert result.is_valid is True
        assert result.entity_type == EntityType.FILE

    def test_validate_with_entity_type(self):
        """Test validate() dispatches to ENTITY validator."""
        result = EntityIDValidator.validate("entity_7275cb2b_f839d8c2", "ENTITY")

        assert result.is_valid is True
        assert result.entity_type == EntityType.ENTITY

    def test_validate_with_function_type(self):
        """Test validate() dispatches to FUNCTION validator."""
        result = EntityIDValidator.validate("function_a1b2c3d4e5f6", "FUNCTION")

        assert result.is_valid is True
        assert result.entity_type == EntityType.FUNCTION

    def test_validate_with_class_type(self):
        """Test validate() dispatches to CLASS validator."""
        result = EntityIDValidator.validate("class_1234567890ab", "CLASS")

        assert result.is_valid is True
        assert result.entity_type == EntityType.CLASS

    def test_validate_with_case_insensitive_type(self):
        """Test validate() handles case-insensitive entity types."""
        result = EntityIDValidator.validate("file_91f521860bc3", "file")

        assert result.is_valid is True

    def test_validate_with_unsupported_type(self):
        """Test validate() raises ValueError for unsupported types."""
        with pytest.raises(ValueError) as exc_info:
            EntityIDValidator.validate("some_id", "UNSUPPORTED")

        assert "Unsupported entity_type" in str(exc_info.value)


# =============================================================================
# Pydantic Integration Tests
# =============================================================================


class TestPydanticIntegration:
    """Tests for Pydantic field validator integration."""

    def test_validate_and_raise_with_valid_id(self):
        """Test validate_and_raise() returns entity_id if valid."""
        entity_id = EntityIDValidator.validate_and_raise("file_91f521860bc3", "FILE")

        assert entity_id == "file_91f521860bc3"

    def test_validate_and_raise_with_invalid_id(self):
        """Test validate_and_raise() raises ValueError if invalid."""
        with pytest.raises(ValueError) as exc_info:
            EntityIDValidator.validate_and_raise("file:omniarchon:asyncio", "FILE")

        assert "Entity ID validation failed" in str(exc_info.value)
        assert "DEPRECATED" in str(exc_info.value)

    def test_pydantic_model_with_validator(self):
        """Test Pydantic model with entity_id field validator."""

        class FileNode(BaseModel):
            entity_id: str

            @field_validator("entity_id")
            @classmethod
            def validate_entity_id(cls, value: str) -> str:
                return EntityIDValidator.validate_and_raise(value, "FILE")

        # Valid entity_id
        node = FileNode(entity_id="file_91f521860bc3")
        assert node.entity_id == "file_91f521860bc3"

        # Invalid entity_id (deprecated format)
        with pytest.raises(ValidationError) as exc_info:
            FileNode(entity_id="file:omniarchon:asyncio")

        error_msg = str(exc_info.value)
        assert "Entity ID validation failed" in error_msg


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience helper functions."""

    def test_validate_file_entity_id_with_valid_id(self):
        """Test validate_file_entity_id() returns True for valid IDs."""
        assert validate_file_entity_id("file_91f521860bc3") is True

    def test_validate_file_entity_id_with_invalid_id(self):
        """Test validate_file_entity_id() returns False for invalid IDs."""
        assert validate_file_entity_id("file:omniarchon:asyncio") is False
        assert validate_file_entity_id("file_91f521860bc") is False  # Too short

    def test_validate_entity_entity_id_with_valid_hash(self):
        """Test validate_entity_entity_id() returns True for valid hash IDs."""
        assert validate_entity_entity_id("entity_7275cb2b_f839d8c2") is True

    def test_validate_entity_entity_id_with_valid_stub(self):
        """Test validate_entity_entity_id() returns True for valid stub IDs."""
        assert validate_entity_entity_id("httpx") is True
        assert validate_entity_entity_id("inline") is True

    def test_validate_entity_entity_id_with_invalid_id(self):
        """Test validate_entity_entity_id() returns False for invalid IDs."""
        assert (
            validate_entity_entity_id("entity_7275cb2b") is False
        )  # Missing second hash

    def test_is_deprecated_format_with_path_based_id(self):
        """Test is_deprecated_format() detects path-based IDs."""
        assert is_deprecated_format("file:omniarchon:asyncio") is True
        assert is_deprecated_format("file:project:/path/to/file.py") is True

    def test_is_deprecated_format_with_hash_based_id(self):
        """Test is_deprecated_format() returns False for hash-based IDs."""
        assert is_deprecated_format("file_91f521860bc3") is False

    def test_is_placeholder_format_with_placeholder_id(self):
        """Test is_placeholder_format() detects placeholder IDs."""
        assert is_placeholder_format("file_placeholder_abc123") is True
        assert is_placeholder_format("FILE_PLACEHOLDER_XYZ") is True

    def test_is_placeholder_format_with_normal_id(self):
        """Test is_placeholder_format() returns False for normal IDs."""
        assert is_placeholder_format("file_91f521860bc3") is False


# =============================================================================
# ValidationResult Structure Tests
# =============================================================================


class TestValidationResultStructure:
    """Tests for ValidationResult dataclass structure."""

    def test_valid_result_structure(self):
        """Test ValidationResult structure for valid entity_id."""
        result = EntityIDValidator.validate_file_id("file_91f521860bc3")

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.entity_type == EntityType.FILE
        assert result.error_message is None
        assert result.detected_format == "hash-based"

    def test_invalid_result_structure(self):
        """Test ValidationResult structure for invalid entity_id."""
        result = EntityIDValidator.validate_file_id("file:omniarchon:asyncio")

        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert result.entity_type == EntityType.FILE
        assert result.error_message is not None
        assert "DEPRECATED" in result.error_message
        assert result.detected_format == "path-based (deprecated)"

    def test_validation_result_is_frozen(self):
        """Test ValidationResult is immutable (frozen dataclass)."""
        result = EntityIDValidator.validate_file_id("file_91f521860bc3")

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            result.is_valid = False


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Performance benchmarks for entity_id validation."""

    def test_validation_performance_under_1ms(self):
        """Test that validation completes in <1ms (target: <1ms)."""
        entity_id = "file_91f521860bc3"
        iterations = 1000

        start_time = time.perf_counter()
        for _ in range(iterations):
            EntityIDValidator.validate_file_id(entity_id)
        end_time = time.perf_counter()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        # Assert average time is under 1ms
        assert avg_time_ms < 1.0, f"Validation took {avg_time_ms:.4f}ms (target: <1ms)"

    def test_comprehensive_validation_performance(self):
        """Test comprehensive validate() performance."""
        entity_id = "file_91f521860bc3"
        iterations = 1000

        start_time = time.perf_counter()
        for _ in range(iterations):
            EntityIDValidator.validate(entity_id, "FILE")
        end_time = time.perf_counter()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        # Assert average time is under 1ms
        assert avg_time_ms < 1.0, f"Comprehensive validation took {avg_time_ms:.4f}ms"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_string_entity_id(self):
        """Test validation handles empty string."""
        result = EntityIDValidator.validate_file_id("")

        assert result.is_valid is False

    def test_none_entity_id_raises_error(self):
        """Test validation raises error for None input."""
        with pytest.raises(TypeError):
            EntityIDValidator.validate_file_id(None)  # type: ignore

    def test_whitespace_entity_id(self):
        """Test validation handles whitespace."""
        result = EntityIDValidator.validate_file_id("   ")

        assert result.is_valid is False

    def test_entity_id_with_leading_trailing_whitespace(self):
        """Test validation rejects entity_id with whitespace."""
        result = EntityIDValidator.validate_file_id(" file_91f521860bc3 ")

        assert result.is_valid is False

    def test_entity_id_with_special_characters(self):
        """Test validation rejects entity_id with special characters."""
        result = EntityIDValidator.validate_file_id("file_91f521860bc3!")

        assert result.is_valid is False


# =============================================================================
# Documentation Examples
# =============================================================================


class TestDocumentationExamples:
    """Tests to verify documentation examples work correctly."""

    def test_example_from_module_docstring(self):
        """Test examples from module-level docstring."""
        # Example 1: Quick validation
        is_valid = validate_file_entity_id("file_91f521860bc3")
        assert is_valid is True

        is_valid = validate_file_entity_id("file:omniarchon:asyncio")
        assert is_valid is False

        # Example 2: Comprehensive validation
        result = EntityIDValidator.validate("file_91f521860bc3", "FILE")
        assert result.is_valid is True

    def test_example_pydantic_integration(self):
        """Test Pydantic integration example from docstring."""

        class FileNode(BaseModel):
            entity_id: str

            @field_validator("entity_id")
            @classmethod
            def validate_entity_id(cls, value: str) -> str:
                return EntityIDValidator.validate_and_raise(value, "FILE")

        # Valid
        node = FileNode(entity_id="file_91f521860bc3")
        assert node.entity_id == "file_91f521860bc3"

        # Invalid
        with pytest.raises(ValidationError):
            FileNode(entity_id="file:omniarchon:asyncio")


# =============================================================================
# Test Summary
# =============================================================================


def test_all_tests_present():
    """
    Meta-test to ensure comprehensive test coverage.

    This test verifies that we have tests for all key areas:
    - FILE validation (valid, deprecated, placeholder, invalid)
    - ENTITY validation (hash-based, stubs, invalid)
    - FUNCTION validation
    - CLASS validation
    - Comprehensive validation
    - Pydantic integration
    - Convenience functions
    - ValidationResult structure
    - Performance benchmarks
    - Edge cases
    """
    # Count test methods across all test classes
    test_classes = [
        TestFileEntityIDValidation,
        TestEntityEntityIDValidation,
        TestFunctionEntityIDValidation,
        TestClassEntityIDValidation,
        TestComprehensiveValidation,
        TestPydanticIntegration,
        TestConvenienceFunctions,
        TestValidationResultStructure,
        TestPerformance,
        TestEdgeCases,
        TestDocumentationExamples,
    ]

    total_tests = sum(
        len([m for m in dir(cls) if m.startswith("test_")]) for cls in test_classes
    )

    # Ensure we have at least 40 test methods
    assert total_tests >= 40, f"Only {total_tests} test methods found (target: 40+)"
