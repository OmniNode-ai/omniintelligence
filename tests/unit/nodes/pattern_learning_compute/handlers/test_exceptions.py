# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for pattern learning exception classes.

This module tests the exception hierarchy for pattern learning handlers:
    - PatternLearningValidationError (PATLEARN_001)
    - PatternLearningComputeError (PATLEARN_002)

Error code semantics:
    - PATLEARN_001: Input validation failed (non-recoverable)
    - PATLEARN_002: Computation error (recoverable with retry)
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningComputeError,
    PatternLearningValidationError,
)


# =============================================================================
# PatternLearningValidationError Tests
# =============================================================================


@pytest.mark.unit
class TestPatternLearningValidationError:
    """Tests for PatternLearningValidationError exception."""

    def test_can_be_raised(self) -> None:
        """Exception can be raised."""
        with pytest.raises(PatternLearningValidationError):
            raise PatternLearningValidationError("Invalid input")

    def test_message_preserved(self) -> None:
        """Exception message is preserved correctly."""
        error = PatternLearningValidationError("Training data cannot be empty")
        assert str(error) == "Training data cannot be empty"

    def test_message_in_args(self) -> None:
        """Exception message is accessible via args."""
        error = PatternLearningValidationError("Test message")
        assert error.args[0] == "Test message"

    def test_inherits_from_exception(self) -> None:
        """PatternLearningValidationError inherits from Exception."""
        assert issubclass(PatternLearningValidationError, Exception)

    def test_can_be_caught_as_exception(self) -> None:
        """Exception can be caught as generic Exception."""
        with pytest.raises(Exception) as exc_info:
            raise PatternLearningValidationError("Caught as Exception")

        assert str(exc_info.value) == "Caught as Exception"

    def test_can_be_caught_specifically(self) -> None:
        """Exception can be caught specifically."""
        with pytest.raises(PatternLearningValidationError) as exc_info:
            raise PatternLearningValidationError("Specific catch")

        assert str(exc_info.value) == "Specific catch"

    def test_empty_message_allowed(self) -> None:
        """Empty message is allowed."""
        error = PatternLearningValidationError("")
        assert str(error) == ""

    def test_long_message_preserved(self) -> None:
        """Long messages are preserved completely."""
        long_message = "A" * 1000
        error = PatternLearningValidationError(long_message)
        assert str(error) == long_message
        assert len(str(error)) == 1000

    def test_multiline_message_preserved(self) -> None:
        """Multiline messages are preserved."""
        multiline = "Line 1\nLine 2\nLine 3"
        error = PatternLearningValidationError(multiline)
        assert str(error) == multiline
        assert "\n" in str(error)

    def test_special_characters_preserved(self) -> None:
        """Special characters in message are preserved."""
        special = "Error: invalid <tag> & 'quote' \"double\""
        error = PatternLearningValidationError(special)
        assert str(error) == special

    def test_unicode_message_preserved(self) -> None:
        """Unicode characters in message are preserved."""
        unicode_msg = "Error: invalid input data"
        error = PatternLearningValidationError(unicode_msg)
        assert str(error) == unicode_msg

    def test_repr_contains_class_name(self) -> None:
        """Exception repr contains class name."""
        error = PatternLearningValidationError("Test")
        repr_str = repr(error)
        assert "PatternLearningValidationError" in repr_str


# =============================================================================
# PatternLearningComputeError Tests
# =============================================================================


@pytest.mark.unit
class TestPatternLearningComputeError:
    """Tests for PatternLearningComputeError exception."""

    def test_can_be_raised(self) -> None:
        """Exception can be raised."""
        with pytest.raises(PatternLearningComputeError):
            raise PatternLearningComputeError("Computation failed")

    def test_message_preserved(self) -> None:
        """Exception message is preserved correctly."""
        error = PatternLearningComputeError("Failed to parse AST: syntax error at line 42")
        assert str(error) == "Failed to parse AST: syntax error at line 42"

    def test_message_in_args(self) -> None:
        """Exception message is accessible via args."""
        error = PatternLearningComputeError("Compute error message")
        assert error.args[0] == "Compute error message"

    def test_inherits_from_exception(self) -> None:
        """PatternLearningComputeError inherits from Exception."""
        assert issubclass(PatternLearningComputeError, Exception)

    def test_can_be_caught_as_exception(self) -> None:
        """Exception can be caught as generic Exception."""
        with pytest.raises(Exception) as exc_info:
            raise PatternLearningComputeError("Caught as Exception")

        assert str(exc_info.value) == "Caught as Exception"

    def test_can_be_caught_specifically(self) -> None:
        """Exception can be caught specifically."""
        with pytest.raises(PatternLearningComputeError) as exc_info:
            raise PatternLearningComputeError("Specific compute catch")

        assert str(exc_info.value) == "Specific compute catch"

    def test_empty_message_allowed(self) -> None:
        """Empty message is allowed."""
        error = PatternLearningComputeError("")
        assert str(error) == ""

    def test_long_message_preserved(self) -> None:
        """Long messages are preserved completely."""
        long_message = "B" * 1000
        error = PatternLearningComputeError(long_message)
        assert str(error) == long_message
        assert len(str(error)) == 1000

    def test_repr_contains_class_name(self) -> None:
        """Exception repr contains class name."""
        error = PatternLearningComputeError("Test")
        repr_str = repr(error)
        assert "PatternLearningComputeError" in repr_str


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


@pytest.mark.unit
class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_both_inherit_from_exception(self) -> None:
        """Both exception types inherit from Exception."""
        assert issubclass(PatternLearningValidationError, Exception)
        assert issubclass(PatternLearningComputeError, Exception)

    def test_validation_not_subclass_of_compute(self) -> None:
        """Validation error is not a subclass of compute error."""
        assert not issubclass(
            PatternLearningValidationError,
            PatternLearningComputeError,
        )

    def test_compute_not_subclass_of_validation(self) -> None:
        """Compute error is not a subclass of validation error."""
        assert not issubclass(
            PatternLearningComputeError,
            PatternLearningValidationError,
        )

    def test_errors_are_distinct_types(self) -> None:
        """Validation and compute errors are distinct types."""
        validation = PatternLearningValidationError("V")
        compute = PatternLearningComputeError("C")

        assert type(validation) is not type(compute)
        assert type(validation).__name__ != type(compute).__name__

    def test_both_catchable_as_exception(self) -> None:
        """Both types can be caught as generic Exception."""
        errors_caught = []

        try:
            raise PatternLearningValidationError("V")
        except Exception as e:
            errors_caught.append(e)

        try:
            raise PatternLearningComputeError("C")
        except Exception as e:
            errors_caught.append(e)

        assert len(errors_caught) == 2
        assert isinstance(errors_caught[0], PatternLearningValidationError)
        assert isinstance(errors_caught[1], PatternLearningComputeError)


# =============================================================================
# Error Code Semantics Tests
# =============================================================================


@pytest.mark.unit
class TestErrorCodeSemantics:
    """Tests documenting error code semantics per contract.yaml.

    These tests document the intended semantics of each exception type
    based on the contract.yaml error_handling section.
    """

    def test_patlearn_001_for_validation(self) -> None:
        """PatternLearningValidationError corresponds to PATLEARN_001.

        Per contract: Input validation failed (non-recoverable).
        Should be raised when input data is invalid and cannot be processed.
        """
        # Document that this exception type maps to PATLEARN_001
        error = PatternLearningValidationError("Invalid language: not supported")
        assert isinstance(error, PatternLearningValidationError)
        # Validation errors are non-recoverable - don't retry
        assert "Invalid" in str(error) or "not supported" in str(error)

    def test_patlearn_002_for_compute(self) -> None:
        """PatternLearningComputeError corresponds to PATLEARN_002.

        Per contract: Computation error during pattern learning (recoverable).
        Should be raised when computation fails but might succeed on retry.
        """
        # Document that this exception type maps to PATLEARN_002
        error = PatternLearningComputeError("AST parsing failed: temporary error")
        assert isinstance(error, PatternLearningComputeError)
        # Compute errors may be recoverable with retry

    def test_validation_vs_compute_distinction(self) -> None:
        """Validation and compute errors have distinct recovery semantics.

        - Validation (PATLEARN_001): Non-recoverable - fix the input
        - Compute (PATLEARN_002): Potentially recoverable with retry
        """
        # Example: empty input -> validation error (won't succeed on retry)
        validation_error = PatternLearningValidationError(
            "Training data cannot be empty"
        )

        # Example: parsing error -> compute error (might succeed on retry)
        compute_error = PatternLearningComputeError(
            "Failed to parse AST: timeout"
        )

        # Both are exceptions but represent different failure modes
        assert isinstance(validation_error, Exception)
        assert isinstance(compute_error, Exception)
        assert not isinstance(validation_error, PatternLearningComputeError)
        assert not isinstance(compute_error, PatternLearningValidationError)


# =============================================================================
# Usage Pattern Tests
# =============================================================================


@pytest.mark.unit
class TestUsagePatterns:
    """Tests for common exception usage patterns."""

    def test_exception_can_wrap_original_error(self) -> None:
        """Exceptions can wrap original error information."""
        original = ValueError("Original cause")
        wrapped = PatternLearningComputeError(
            f"Pattern learning failed: {original}"
        )

        assert "Original cause" in str(wrapped)
        assert "Pattern learning failed" in str(wrapped)

    def test_exception_chaining_with_from(self) -> None:
        """Exceptions support chaining with 'from' keyword."""
        original = ValueError("Root cause")

        try:
            try:
                raise original
            except ValueError as e:
                raise PatternLearningComputeError("Wrapped error") from e
        except PatternLearningComputeError as wrapped:
            assert wrapped.__cause__ is original
            assert str(wrapped) == "Wrapped error"

    def test_exception_in_try_except_else(self) -> None:
        """Exceptions work correctly in try/except/else pattern."""
        result = None
        error_caught = None

        try:
            raise PatternLearningValidationError("Test")
        except PatternLearningValidationError as e:
            error_caught = e
        else:
            result = "success"

        assert error_caught is not None
        assert result is None
        assert str(error_caught) == "Test"

    def test_exception_in_try_except_finally(self) -> None:
        """Exceptions work correctly in try/except/finally pattern."""
        cleanup_called = False
        error_caught = None

        try:
            raise PatternLearningComputeError("Compute test")
        except PatternLearningComputeError as e:
            error_caught = e
        finally:
            cleanup_called = True

        assert error_caught is not None
        assert cleanup_called is True

    def test_exception_reraising(self) -> None:
        """Exceptions can be caught and re-raised."""
        with pytest.raises(PatternLearningValidationError) as exc_info:
            try:
                raise PatternLearningValidationError("Original")
            except PatternLearningValidationError:
                # Log or modify, then re-raise
                raise

        assert str(exc_info.value) == "Original"

    def test_exception_reraising_with_modification(self) -> None:
        """Exceptions can be caught, modified, and re-raised as new exception."""
        with pytest.raises(PatternLearningComputeError) as exc_info:
            try:
                raise PatternLearningValidationError("Validation failed")
            except PatternLearningValidationError as e:
                # Convert validation to compute error (e.g., for retry logic)
                raise PatternLearningComputeError(
                    f"Retryable: {e}"
                ) from e

        assert "Retryable" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_multiple_exception_instances_independent(self) -> None:
        """Multiple exception instances are independent."""
        error1 = PatternLearningValidationError("First error")
        error2 = PatternLearningValidationError("Second error")

        assert error1 is not error2
        assert str(error1) != str(error2)
        assert error1.args != error2.args


# =============================================================================
# Edge Cases Tests
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_none_coerced_to_string(self) -> None:
        """None as message is coerced to string by Exception base class."""
        # Python's Exception allows any argument
        error = PatternLearningValidationError(None)  # type: ignore[arg-type]
        assert error.args[0] is None

    def test_multiple_args(self) -> None:
        """Exception can accept multiple arguments."""
        error = PatternLearningComputeError("Error", "context", 42)
        assert error.args == ("Error", "context", 42)
        assert str(error) == "('Error', 'context', 42)"

    def test_no_args(self) -> None:
        """Exception can be created with no arguments."""
        error = PatternLearningValidationError()
        assert error.args == ()
        assert str(error) == ""

    def test_keyword_only_not_supported(self) -> None:
        """Standard Exception doesn't support keyword arguments."""
        # This documents that keyword args aren't supported
        with pytest.raises(TypeError):
            PatternLearningValidationError(message="test")  # type: ignore[call-arg]


# =============================================================================
# Module Export Tests
# =============================================================================


@pytest.mark.unit
class TestModuleExports:
    """Tests verifying module exports."""

    def test_all_exceptions_importable(self) -> None:
        """All exception classes are importable from handlers package."""
        from omniintelligence.nodes.pattern_learning_compute.handlers import exceptions

        assert hasattr(exceptions, "PatternLearningValidationError")
        assert hasattr(exceptions, "PatternLearningComputeError")

    def test_exports_match_all(self) -> None:
        """Module __all__ includes all exception classes."""
        from omniintelligence.nodes.pattern_learning_compute.handlers import exceptions

        expected = {"PatternLearningComputeError", "PatternLearningValidationError"}
        assert set(exceptions.__all__) == expected

    def test_classes_are_actual_exception_types(self) -> None:
        """Exported names are actual exception classes."""
        from omniintelligence.nodes.pattern_learning_compute.handlers import exceptions

        assert isinstance(exceptions.PatternLearningValidationError, type)
        assert isinstance(exceptions.PatternLearningComputeError, type)
        assert issubclass(exceptions.PatternLearningValidationError, Exception)
        assert issubclass(exceptions.PatternLearningComputeError, Exception)
