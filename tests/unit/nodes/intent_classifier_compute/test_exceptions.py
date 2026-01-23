# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for intent classification exception classes.

This module tests the exception hierarchy including:
    - IntentClassificationError (base exception)
    - IntentClassificationValidationError (INTENT_001)
    - IntentClassificationComputeError (INTENT_002)
    - Error code assignment
    - Exception inheritance
    - Message handling
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.intent_classifier_compute.handlers import (
    IntentClassificationComputeError,
    IntentClassificationError,
    IntentClassificationValidationError,
)


# =============================================================================
# IntentClassificationError Tests (Base Exception)
# =============================================================================


class TestIntentClassificationError:
    """Tests for the base IntentClassificationError exception."""

    def test_creates_with_message_only(self) -> None:
        """Test that exception can be created with message only."""
        error = IntentClassificationError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.code is None

    def test_creates_with_message_and_code(self) -> None:
        """Test that exception can be created with message and code."""
        error = IntentClassificationError("Custom error", code="INTENT_999")
        assert str(error) == "Custom error"
        assert error.message == "Custom error"
        assert error.code == "INTENT_999"

    def test_inherits_from_exception(self) -> None:
        """Test that IntentClassificationError inherits from Exception."""
        assert issubclass(IntentClassificationError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        """Test that exception can be raised and caught."""
        with pytest.raises(IntentClassificationError) as exc_info:
            raise IntentClassificationError("Test error", code="TEST_001")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.code == "TEST_001"

    def test_message_attribute_matches_str(self) -> None:
        """Test that message attribute matches str() output."""
        error = IntentClassificationError("Error message")
        assert error.message == str(error)

    def test_none_code_allowed(self) -> None:
        """Test that None code is explicitly allowed."""
        error = IntentClassificationError("No code", code=None)
        assert error.code is None


# =============================================================================
# IntentClassificationValidationError Tests
# =============================================================================


class TestIntentClassificationValidationError:
    """Tests for IntentClassificationValidationError exception."""

    def test_has_correct_error_code(self) -> None:
        """Test that validation error has code INTENT_001."""
        error = IntentClassificationValidationError("Invalid input")
        assert error.code == "INTENT_001"

    def test_message_preserved(self) -> None:
        """Test that message is preserved correctly."""
        error = IntentClassificationValidationError("Content cannot be empty")
        assert error.message == "Content cannot be empty"
        assert str(error) == "Content cannot be empty"

    def test_inherits_from_base_exception(self) -> None:
        """Test that it inherits from IntentClassificationError."""
        assert issubclass(
            IntentClassificationValidationError,
            IntentClassificationError,
        )

    def test_can_be_caught_as_base_exception(self) -> None:
        """Test that it can be caught as IntentClassificationError."""
        with pytest.raises(IntentClassificationError) as exc_info:
            raise IntentClassificationValidationError("Validation failed")

        assert exc_info.value.code == "INTENT_001"

    def test_can_be_caught_specifically(self) -> None:
        """Test that it can be caught specifically."""
        with pytest.raises(IntentClassificationValidationError):
            raise IntentClassificationValidationError("Specific catch")

    def test_error_code_not_overridable(self) -> None:
        """Test that error code is always INTENT_001."""
        # The constructor only takes message, code is hardcoded
        error = IntentClassificationValidationError("Test")
        assert error.code == "INTENT_001"

    def test_empty_message_allowed(self) -> None:
        """Test that empty message is allowed."""
        error = IntentClassificationValidationError("")
        assert error.message == ""
        assert error.code == "INTENT_001"

    def test_long_message_preserved(self) -> None:
        """Test that long messages are preserved completely."""
        long_message = "A" * 1000
        error = IntentClassificationValidationError(long_message)
        assert error.message == long_message
        assert len(error.message) == 1000


# =============================================================================
# IntentClassificationComputeError Tests
# =============================================================================


class TestIntentClassificationComputeError:
    """Tests for IntentClassificationComputeError exception."""

    def test_has_correct_error_code(self) -> None:
        """Test that compute error has code INTENT_002."""
        error = IntentClassificationComputeError("Computation failed")
        assert error.code == "INTENT_002"

    def test_message_preserved(self) -> None:
        """Test that message is preserved correctly."""
        error = IntentClassificationComputeError("Failed to compute embeddings")
        assert error.message == "Failed to compute embeddings"
        assert str(error) == "Failed to compute embeddings"

    def test_inherits_from_base_exception(self) -> None:
        """Test that it inherits from IntentClassificationError."""
        assert issubclass(
            IntentClassificationComputeError,
            IntentClassificationError,
        )

    def test_can_be_caught_as_base_exception(self) -> None:
        """Test that it can be caught as IntentClassificationError."""
        with pytest.raises(IntentClassificationError) as exc_info:
            raise IntentClassificationComputeError("Compute error")

        assert exc_info.value.code == "INTENT_002"

    def test_can_be_caught_specifically(self) -> None:
        """Test that it can be caught specifically."""
        with pytest.raises(IntentClassificationComputeError):
            raise IntentClassificationComputeError("Specific compute error")

    def test_error_code_not_overridable(self) -> None:
        """Test that error code is always INTENT_002."""
        error = IntentClassificationComputeError("Test")
        assert error.code == "INTENT_002"

    def test_distinguishable_from_validation_error(self) -> None:
        """Test that compute error is distinguishable from validation error."""
        compute_error = IntentClassificationComputeError("Compute")
        validation_error = IntentClassificationValidationError("Validation")

        assert compute_error.code != validation_error.code
        assert compute_error.code == "INTENT_002"
        assert validation_error.code == "INTENT_001"


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_both_errors_inherit_from_base(self) -> None:
        """Test that both error types inherit from base."""
        assert issubclass(
            IntentClassificationValidationError,
            IntentClassificationError,
        )
        assert issubclass(
            IntentClassificationComputeError,
            IntentClassificationError,
        )

    def test_validation_not_subclass_of_compute(self) -> None:
        """Test that validation is not a subclass of compute error."""
        assert not issubclass(
            IntentClassificationValidationError,
            IntentClassificationComputeError,
        )

    def test_compute_not_subclass_of_validation(self) -> None:
        """Test that compute is not a subclass of validation error."""
        assert not issubclass(
            IntentClassificationComputeError,
            IntentClassificationValidationError,
        )

    def test_all_inherit_from_standard_exception(self) -> None:
        """Test that all exception types inherit from Exception."""
        assert issubclass(IntentClassificationError, Exception)
        assert issubclass(IntentClassificationValidationError, Exception)
        assert issubclass(IntentClassificationComputeError, Exception)

    def test_catch_base_catches_both_subclasses(self) -> None:
        """Test that catching base exception catches both subclasses."""
        errors_caught = []

        try:
            raise IntentClassificationValidationError("V")
        except IntentClassificationError as e:
            errors_caught.append(e)

        try:
            raise IntentClassificationComputeError("C")
        except IntentClassificationError as e:
            errors_caught.append(e)

        assert len(errors_caught) == 2
        assert errors_caught[0].code == "INTENT_001"
        assert errors_caught[1].code == "INTENT_002"


# =============================================================================
# Error Code Semantics Tests
# =============================================================================


class TestErrorCodeSemantics:
    """Tests for error code semantic meaning."""

    def test_intent_001_for_validation(self) -> None:
        """Test that INTENT_001 is reserved for validation errors."""
        # According to contract, INTENT_001 = validation (non-recoverable)
        error = IntentClassificationValidationError("Invalid")
        assert error.code == "INTENT_001"

    def test_intent_002_for_compute(self) -> None:
        """Test that INTENT_002 is reserved for compute errors."""
        # According to contract, INTENT_002 = computation (recoverable)
        error = IntentClassificationComputeError("Failed")
        assert error.code == "INTENT_002"

    def test_error_codes_are_unique(self) -> None:
        """Test that each error type has a unique code."""
        codes = {
            IntentClassificationValidationError("").code,
            IntentClassificationComputeError("").code,
        }
        assert len(codes) == 2

    def test_error_codes_follow_pattern(self) -> None:
        """Test that error codes follow INTENT_NNN pattern."""
        import re

        pattern = re.compile(r"^INTENT_\d{3}$")

        validation_code = IntentClassificationValidationError("").code
        compute_code = IntentClassificationComputeError("").code

        assert pattern.match(validation_code), f"Invalid code format: {validation_code}"
        assert pattern.match(compute_code), f"Invalid code format: {compute_code}"


# =============================================================================
# Usage Pattern Tests
# =============================================================================


class TestUsagePatterns:
    """Tests for common exception usage patterns."""

    def test_error_chain_preserves_info(self) -> None:
        """Test that error chaining preserves information."""
        original = ValueError("Original error")
        wrapped = IntentClassificationComputeError(f"Wrapped: {original}")

        assert "Original error" in wrapped.message

    def test_exception_in_context_manager(self) -> None:
        """Test exception behavior in context manager."""
        caught_exception = None

        try:
            raise IntentClassificationValidationError("Context test")
        except IntentClassificationValidationError as e:
            caught_exception = e

        assert caught_exception is not None
        assert caught_exception.code == "INTENT_001"

    def test_exception_repr_meaningful(self) -> None:
        """Test that exception has meaningful repr."""
        error = IntentClassificationValidationError("Test message")
        # Default Exception repr includes class name and message
        repr_str = repr(error)
        assert "IntentClassificationValidationError" in repr_str

    def test_exception_can_be_reraised(self) -> None:
        """Test that exception can be raised again after catching."""
        error = IntentClassificationComputeError("Original")

        with pytest.raises(IntentClassificationComputeError) as exc_info:
            try:
                raise error
            except IntentClassificationComputeError as e:
                # Modify or log, then reraise
                raise e

        assert exc_info.value is error
        assert exc_info.value.code == "INTENT_002"

    def test_multiple_exceptions_independent(self) -> None:
        """Test that multiple exception instances are independent."""
        error1 = IntentClassificationValidationError("First")
        error2 = IntentClassificationValidationError("Second")

        assert error1.message != error2.message
        assert error1 is not error2
        # But same error code (class-level)
        assert error1.code == error2.code
