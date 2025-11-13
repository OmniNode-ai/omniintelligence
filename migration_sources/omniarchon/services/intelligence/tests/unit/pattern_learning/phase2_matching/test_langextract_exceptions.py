"""
Comprehensive Test Suite for Langextract Exceptions

Tests cover:
- All custom exception types
- Exception inheritance hierarchy
- Error message formatting
- Exception attributes and metadata
- Exception handling patterns
- Edge cases and boundary conditions

Target: >90% code coverage for exceptions_langextract.py (24 statements)
"""

import pytest
from archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
    LangextractError,
    LangextractRateLimitError,
    LangextractServerError,
    LangextractTimeoutError,
    LangextractUnavailableError,
    LangextractValidationError,
)

# ============================================================================
# Base Exception Tests
# ============================================================================


class TestLangextractError:
    """Test base LangextractError exception."""

    def test_basic_error_creation(self):
        """Test creating basic error with message."""
        error = LangextractError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.status_code is None
        assert error.response_data == {}

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = LangextractError("Error with status", status_code=500)

        assert error.message == "Error with status"
        assert error.status_code == 500

    def test_error_with_response_data(self):
        """Test error with response data."""
        response_data = {"detail": "Server error", "code": "INTERNAL_ERROR"}
        error = LangextractError(
            "Error with data", status_code=500, response_data=response_data
        )

        assert error.response_data == response_data
        assert error.response_data["detail"] == "Server error"

    def test_error_with_none_response_data(self):
        """Test error with None response_data defaults to empty dict."""
        error = LangextractError("Test", response_data=None)

        assert error.response_data == {}

    def test_error_inheritance(self):
        """Test LangextractError inherits from Exception."""
        error = LangextractError("Test")

        assert isinstance(error, Exception)

    def test_error_can_be_raised(self):
        """Test error can be raised and caught."""
        with pytest.raises(LangextractError) as exc_info:
            raise LangextractError("Test error")

        assert str(exc_info.value) == "Test error"

    def test_error_can_be_caught_as_exception(self):
        """Test error can be caught as generic Exception."""
        with pytest.raises(Exception) as exc_info:
            raise LangextractError("Test error")

        assert isinstance(exc_info.value, LangextractError)


# ============================================================================
# LangextractUnavailableError Tests
# ============================================================================


class TestLangextractUnavailableError:
    """Test LangextractUnavailableError exception."""

    def test_default_error_message(self):
        """Test error with default message."""
        error = LangextractUnavailableError()

        assert "unavailable" in str(error).lower()
        assert error.status_code == 503

    def test_custom_error_message(self):
        """Test error with custom message."""
        error = LangextractUnavailableError("Service is down")

        assert str(error) == "Service is down"
        assert error.status_code == 503

    def test_error_inheritance(self):
        """Test inherits from LangextractError."""
        error = LangextractUnavailableError()

        assert isinstance(error, LangextractError)
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test can be raised and caught."""
        with pytest.raises(LangextractUnavailableError):
            raise LangextractUnavailableError("Test")

    def test_can_be_caught_as_base_error(self):
        """Test can be caught as LangextractError."""
        with pytest.raises(LangextractError):
            raise LangextractUnavailableError("Test")


# ============================================================================
# LangextractTimeoutError Tests
# ============================================================================


class TestLangextractTimeoutError:
    """Test LangextractTimeoutError exception."""

    def test_default_error_message(self):
        """Test error with default message."""
        error = LangextractTimeoutError()

        assert "timed out" in str(error).lower()
        assert error.status_code == 408
        assert error.timeout_seconds is None

    def test_custom_error_message(self):
        """Test error with custom message."""
        error = LangextractTimeoutError("Request took too long")

        assert str(error) == "Request took too long"
        assert error.status_code == 408

    def test_error_with_timeout_value(self):
        """Test error with timeout_seconds attribute."""
        error = LangextractTimeoutError("Timeout after 5 seconds", timeout_seconds=5.0)

        assert error.timeout_seconds == 5.0
        assert error.status_code == 408

    def test_error_inheritance(self):
        """Test inherits from LangextractError."""
        error = LangextractTimeoutError()

        assert isinstance(error, LangextractError)
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test can be raised and caught."""
        with pytest.raises(LangextractTimeoutError) as exc_info:
            raise LangextractTimeoutError(timeout_seconds=10.0)

        assert exc_info.value.timeout_seconds == 10.0


# ============================================================================
# LangextractValidationError Tests
# ============================================================================


class TestLangextractValidationError:
    """Test LangextractValidationError exception."""

    def test_basic_validation_error(self):
        """Test error with just message."""
        error = LangextractValidationError("Invalid request")

        assert str(error) == "Invalid request"
        assert error.status_code == 422
        assert error.validation_errors == []

    def test_error_with_validation_errors(self):
        """Test error with validation error list."""
        validation_errors = [
            {"loc": ["body", "content"], "msg": "field required"},
            {"loc": ["body", "min_confidence"], "msg": "must be >= 0.0"},
        ]

        error = LangextractValidationError(
            "Validation failed", validation_errors=validation_errors
        )

        assert error.validation_errors == validation_errors
        assert len(error.validation_errors) == 2
        assert error.status_code == 422

    def test_error_with_none_validation_errors(self):
        """Test error with None validation_errors defaults to empty list."""
        error = LangextractValidationError("Test", validation_errors=None)

        assert error.validation_errors == []

    def test_error_inheritance(self):
        """Test inherits from LangextractError."""
        error = LangextractValidationError("Test")

        assert isinstance(error, LangextractError)
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test can be raised and caught."""
        validation_errors = [{"loc": ["test"], "msg": "error"}]

        with pytest.raises(LangextractValidationError) as exc_info:
            raise LangextractValidationError(
                "Test", validation_errors=validation_errors
            )

        assert len(exc_info.value.validation_errors) == 1


# ============================================================================
# LangextractRateLimitError Tests
# ============================================================================


class TestLangextractRateLimitError:
    """Test LangextractRateLimitError exception."""

    def test_default_error_message(self):
        """Test error with default message."""
        error = LangextractRateLimitError()

        assert "rate limit" in str(error).lower()
        assert error.status_code == 429
        assert error.retry_after is None

    def test_custom_error_message(self):
        """Test error with custom message."""
        error = LangextractRateLimitError("Too many requests")

        assert str(error) == "Too many requests"
        assert error.status_code == 429

    def test_error_with_retry_after(self):
        """Test error with retry_after attribute."""
        error = LangextractRateLimitError("Rate limit exceeded", retry_after=60)

        assert error.retry_after == 60
        assert error.status_code == 429

    def test_error_inheritance(self):
        """Test inherits from LangextractError."""
        error = LangextractRateLimitError()

        assert isinstance(error, LangextractError)
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test can be raised and caught."""
        with pytest.raises(LangextractRateLimitError) as exc_info:
            raise LangextractRateLimitError(retry_after=120)

        assert exc_info.value.retry_after == 120


# ============================================================================
# LangextractServerError Tests
# ============================================================================


class TestLangextractServerError:
    """Test LangextractServerError exception."""

    def test_basic_server_error(self):
        """Test error with just message."""
        error = LangextractServerError("Server error")

        assert str(error) == "Server error"
        assert error.status_code == 500
        # response_data defaults to None, but base class sets it to {} if None
        assert error.response_data == {} or error.response_data is None

    def test_error_with_custom_status_code(self):
        """Test error with custom 5xx status code."""
        error = LangextractServerError("Bad Gateway", status_code=502)

        assert error.status_code == 502

    def test_error_with_response_data(self):
        """Test error with response data."""
        response_data = {"error": "Internal server error", "trace_id": "abc123"}

        error = LangextractServerError(
            "Server error", status_code=500, response_data=response_data
        )

        assert error.response_data == response_data
        assert error.response_data["trace_id"] == "abc123"

    def test_error_inheritance(self):
        """Test inherits from LangextractError."""
        error = LangextractServerError("Test")

        assert isinstance(error, LangextractError)
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test can be raised and caught."""
        with pytest.raises(LangextractServerError) as exc_info:
            raise LangextractServerError("Test", status_code=503)

        assert exc_info.value.status_code == 503


# ============================================================================
# Exception Hierarchy and Catching Tests
# ============================================================================


class TestExceptionHierarchy:
    """Test exception inheritance and catching patterns."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from LangextractError."""
        exceptions = [
            LangextractUnavailableError(),
            LangextractTimeoutError(),
            LangextractValidationError("test"),
            LangextractRateLimitError(),
            LangextractServerError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, LangextractError)
            assert isinstance(exc, Exception)

    def test_catching_any_langextract_error(self):
        """Test catching all langextract errors with base exception."""
        error_types = [
            LangextractUnavailableError,
            LangextractTimeoutError,
            LangextractValidationError,
            LangextractRateLimitError,
            LangextractServerError,
        ]

        for ErrorClass in error_types:
            with pytest.raises(LangextractError):
                if ErrorClass == LangextractValidationError:
                    raise ErrorClass("test")
                elif ErrorClass == LangextractServerError:
                    raise ErrorClass("test")
                else:
                    raise ErrorClass()

    def test_specific_exception_catching(self):
        """Test catching specific exception types."""
        # Catch specific type
        with pytest.raises(LangextractTimeoutError):
            raise LangextractTimeoutError()

        # Doesn't catch other types
        with pytest.raises(LangextractUnavailableError):
            with pytest.raises(LangextractTimeoutError):
                raise LangextractUnavailableError()

    def test_exception_message_preservation(self):
        """Test exception messages are preserved through hierarchy."""
        message = "Custom error message"

        errors = [
            LangextractError(message),
            LangextractUnavailableError(message),
            LangextractTimeoutError(message),
            LangextractValidationError(message),
            LangextractRateLimitError(message),
            LangextractServerError(message),
        ]

        for error in errors:
            assert str(error) == message


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_empty_error_message(self):
        """Test error with empty message."""
        error = LangextractError("")

        assert str(error) == ""
        assert error.message == ""

    def test_very_long_error_message(self):
        """Test error with very long message."""
        long_message = "Error: " + ("x" * 10000)
        error = LangextractError(long_message)

        assert len(str(error)) > 10000

    def test_special_characters_in_message(self):
        """Test error message with special characters."""
        special_message = "Error: \n\t\"quoted\" 'text' with $pecial @#$% characters"
        error = LangextractError(special_message)

        assert str(error) == special_message

    def test_unicode_in_error_message(self):
        """Test error message with unicode characters."""
        unicode_message = "Error: 你好 world 🚀 émoji"
        error = LangextractError(unicode_message)

        assert str(error) == unicode_message

    def test_none_status_code(self):
        """Test error with explicit None status code."""
        error = LangextractError("Test", status_code=None)

        assert error.status_code is None

    def test_zero_timeout(self):
        """Test timeout error with zero timeout."""
        error = LangextractTimeoutError(timeout_seconds=0.0)

        assert error.timeout_seconds == 0.0

    def test_negative_retry_after(self):
        """Test rate limit with negative retry_after (edge case)."""
        error = LangextractRateLimitError(retry_after=-1)

        assert error.retry_after == -1

    def test_empty_response_data(self):
        """Test error with empty response_data dict."""
        error = LangextractError("Test", response_data={})

        assert error.response_data == {}

    def test_nested_response_data(self):
        """Test error with nested response_data structure."""
        nested_data = {
            "error": {
                "code": "INTERNAL_ERROR",
                "details": {"trace_id": "abc123", "timestamp": "2025-10-02T00:00:00Z"},
            }
        }

        error = LangextractServerError("Test", response_data=nested_data)

        assert error.response_data["error"]["code"] == "INTERNAL_ERROR"
        assert error.response_data["error"]["details"]["trace_id"] == "abc123"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
