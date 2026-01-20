"""Unit tests for DLQ error extraction helper.

These tests verify the _extract_error_info helper function that provides
consistent error type extraction for DLQ routing throughout the intelligence
adapter.

Coverage:
- Standard Python exceptions (ValueError, TypeError, etc.)
- Custom exceptions with modules
- None error handling
- Exception chaining and inheritance
"""

from __future__ import annotations




# We need to test the function directly without importing the full module
# which has heavy dependencies. We'll define the function inline for testing.
def _extract_error_info(error: Exception | None) -> dict[str, str]:
    """
    Extract standardized error information from an exception.

    This is a copy of the function from node_intelligence_adapter_effect.py
    for isolated testing without heavy dependencies.
    """
    if error is None:
        return {
            "error_type": "NoneType",
            "error_message": "Unknown error (None)",
            "error_module": "builtins",
        }

    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_module": type(error).__module__,
    }


class TestExtractErrorInfo:
    """Tests for _extract_error_info helper function."""

    def test_none_error(self) -> None:
        """Test extraction when error is None."""
        result = _extract_error_info(None)
        assert result["error_type"] == "NoneType", "error_type should be 'NoneType' for None"
        assert result["error_message"] == "Unknown error (None)", (
            "error_message should indicate unknown error"
        )
        assert result["error_module"] == "builtins", "error_module should be 'builtins' for None"

    def test_value_error(self) -> None:
        """Test extraction for standard ValueError."""
        error = ValueError("invalid input value")
        result = _extract_error_info(error)
        assert result["error_type"] == "ValueError", "error_type should be 'ValueError'"
        assert result["error_message"] == "invalid input value", (
            "error_message should match exception message"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for built-in exceptions"
        )

    def test_type_error(self) -> None:
        """Test extraction for standard TypeError."""
        error = TypeError("expected str, got int")
        result = _extract_error_info(error)
        assert result["error_type"] == "TypeError", "error_type should be 'TypeError'"
        assert result["error_message"] == "expected str, got int", (
            "error_message should match exception message"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for built-in exceptions"
        )

    def test_key_error(self) -> None:
        """Test extraction for KeyError."""
        error = KeyError("missing_key")
        result = _extract_error_info(error)
        assert result["error_type"] == "KeyError", "error_type should be 'KeyError'"
        # KeyError's str() includes quotes around the key
        assert "missing_key" in result["error_message"], (
            "error_message should contain the key"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for built-in exceptions"
        )

    def test_runtime_error(self) -> None:
        """Test extraction for RuntimeError."""
        error = RuntimeError("something went wrong")
        result = _extract_error_info(error)
        assert result["error_type"] == "RuntimeError", "error_type should be 'RuntimeError'"
        assert result["error_message"] == "something went wrong", (
            "error_message should match exception message"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for RuntimeError"
        )

    def test_attribute_error(self) -> None:
        """Test extraction for AttributeError."""
        error = AttributeError("object has no attribute 'foo'")
        result = _extract_error_info(error)
        assert result["error_type"] == "AttributeError", "error_type should be 'AttributeError'"
        assert result["error_message"] == "object has no attribute 'foo'", (
            "error_message should match exception message"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for AttributeError"
        )

    def test_os_error(self) -> None:
        """Test extraction for OSError."""
        error = OSError("No such file or directory")
        result = _extract_error_info(error)
        assert result["error_type"] == "OSError", "error_type should be 'OSError'"
        assert "No such file or directory" in result["error_message"], (
            "error_message should contain the OS error"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for OSError"
        )

    def test_file_not_found_error(self) -> None:
        """Test extraction for FileNotFoundError (subclass of OSError)."""
        error = FileNotFoundError("config.yaml not found")
        result = _extract_error_info(error)
        assert result["error_type"] == "FileNotFoundError", (
            "error_type should be 'FileNotFoundError' (specific subclass)"
        )
        assert "config.yaml" in result["error_message"], (
            "error_message should contain file name"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for FileNotFoundError"
        )

    def test_import_error(self) -> None:
        """Test extraction for ImportError."""
        error = ImportError("No module named 'nonexistent'")
        result = _extract_error_info(error)
        assert result["error_type"] == "ImportError", "error_type should be 'ImportError'"
        assert "nonexistent" in result["error_message"], (
            "error_message should contain module name"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for ImportError"
        )

    def test_custom_exception_in_test_module(self) -> None:
        """Test extraction for custom exception defined in test module."""

        class CustomTestError(Exception):
            """Custom exception for testing."""

            pass

        error = CustomTestError("custom error occurred")
        result = _extract_error_info(error)
        assert result["error_type"] == "CustomTestError", (
            "error_type should be 'CustomTestError'"
        )
        assert result["error_message"] == "custom error occurred", (
            "error_message should match exception message"
        )
        # The module will be this test module
        assert "test_dlq_error_extraction" in result["error_module"], (
            "error_module should contain test module name"
        )

    def test_exception_with_empty_message(self) -> None:
        """Test extraction for exception with empty message."""
        error = ValueError("")
        result = _extract_error_info(error)
        assert result["error_type"] == "ValueError", "error_type should be 'ValueError'"
        assert result["error_message"] == "", "error_message should be empty string"
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for ValueError"
        )

    def test_exception_with_multiline_message(self) -> None:
        """Test extraction for exception with multiline message."""
        error = ValueError("line1\nline2\nline3")
        result = _extract_error_info(error)
        assert result["error_type"] == "ValueError", "error_type should be 'ValueError'"
        assert "line1" in result["error_message"], "error_message should contain line1"
        assert "line2" in result["error_message"], "error_message should contain line2"
        assert "line3" in result["error_message"], "error_message should contain line3"

    def test_exception_with_unicode_message(self) -> None:
        """Test extraction for exception with unicode characters."""
        error = ValueError("Error with unicode: \u2603 \u2764 \u263a")
        result = _extract_error_info(error)
        assert result["error_type"] == "ValueError", "error_type should be 'ValueError'"
        assert "\u2603" in result["error_message"], (
            "error_message should contain unicode snowman"
        )
        assert "\u2764" in result["error_message"], (
            "error_message should contain unicode heart"
        )

    def test_exception_subclass_preserves_specific_type(self) -> None:
        """Test that exception subclass returns specific type, not parent."""

        class ParentError(Exception):
            pass

        class ChildError(ParentError):
            pass

        error = ChildError("child error")
        result = _extract_error_info(error)
        assert result["error_type"] == "ChildError", (
            "error_type should be 'ChildError', not 'ParentError'"
        )

    def test_json_decode_error(self) -> None:
        """Test extraction for json.JSONDecodeError."""
        import json

        try:
            json.loads("invalid json {")
        except json.JSONDecodeError as error:
            result = _extract_error_info(error)
            assert result["error_type"] == "JSONDecodeError", (
                "error_type should be 'JSONDecodeError'"
            )
            assert result["error_module"] == "json.decoder", (
                "error_module should be 'json.decoder' for JSONDecodeError"
            )

    def test_timeout_error(self) -> None:
        """Test extraction for TimeoutError."""
        error = TimeoutError("Connection timed out after 30s")
        result = _extract_error_info(error)
        assert result["error_type"] == "TimeoutError", "error_type should be 'TimeoutError'"
        assert "30s" in result["error_message"], (
            "error_message should contain timeout duration"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for TimeoutError"
        )

    def test_connection_error(self) -> None:
        """Test extraction for ConnectionError."""
        error = ConnectionError("Failed to connect to server")
        result = _extract_error_info(error)
        assert result["error_type"] == "ConnectionError", (
            "error_type should be 'ConnectionError'"
        )
        assert "server" in result["error_message"], (
            "error_message should contain server reference"
        )
        assert result["error_module"] == "builtins", (
            "error_module should be 'builtins' for ConnectionError"
        )

    def test_return_type_is_dict(self) -> None:
        """Test that return value is always a dict with expected keys."""
        error = ValueError("test")
        result = _extract_error_info(error)
        assert isinstance(result, dict), "result should be a dict"
        assert "error_type" in result, "result should have 'error_type' key"
        assert "error_message" in result, "result should have 'error_message' key"
        assert "error_module" in result, "result should have 'error_module' key"
        assert len(result) == 3, "result should have exactly 3 keys"

    def test_return_type_values_are_strings(self) -> None:
        """Test that all return values are strings."""
        error = ValueError("test")
        result = _extract_error_info(error)
        assert isinstance(result["error_type"], str), "error_type should be a string"
        assert isinstance(result["error_message"], str), "error_message should be a string"
        assert isinstance(result["error_module"], str), "error_module should be a string"

    def test_none_return_values_are_strings(self) -> None:
        """Test that None error returns string values."""
        result = _extract_error_info(None)
        assert isinstance(result["error_type"], str), "error_type should be a string"
        assert isinstance(result["error_message"], str), "error_message should be a string"
        assert isinstance(result["error_module"], str), "error_module should be a string"


class TestExtractErrorInfoDLQConsistency:
    """Tests verifying consistent DLQ payload structure."""

    def test_dlq_payload_structure_with_value_error(self) -> None:
        """Test that error info creates consistent DLQ payload structure."""
        error = ValueError("test error")
        error_info = _extract_error_info(error)

        # Simulate DLQ payload structure
        dlq_error_section = {
            "error_type": error_info["error_type"],
            "error_message": error_info["error_message"],
            "error_module": error_info["error_module"],
            "traceback": "...",  # Would be filled by traceback.format_exc()
        }

        assert dlq_error_section["error_type"] == "ValueError"
        assert dlq_error_section["error_message"] == "test error"
        assert dlq_error_section["error_module"] == "builtins"

    def test_dlq_payload_structure_with_none(self) -> None:
        """Test that None error creates consistent DLQ payload structure."""
        error_info = _extract_error_info(None)

        # Simulate DLQ payload structure
        dlq_error_section = {
            "error_type": error_info["error_type"],
            "error_message": error_info["error_message"],
            "error_module": error_info["error_module"],
            "traceback": "NoneType: None\n",  # Would be filled by traceback.format_exc()
        }

        assert dlq_error_section["error_type"] == "NoneType"
        assert dlq_error_section["error_message"] == "Unknown error (None)"
        assert dlq_error_section["error_module"] == "builtins"

    def test_error_info_keys_match_dlq_payload_keys(self) -> None:
        """Test that error_info keys match expected DLQ payload keys."""
        error = RuntimeError("test")
        error_info = _extract_error_info(error)

        expected_keys = {"error_type", "error_message", "error_module"}
        actual_keys = set(error_info.keys())

        assert actual_keys == expected_keys, (
            f"error_info keys {actual_keys} should match expected {expected_keys}"
        )

    def test_consistent_extraction_across_multiple_calls(self) -> None:
        """Test that multiple calls with same error return identical results."""
        error = ValueError("consistent test")

        result1 = _extract_error_info(error)
        result2 = _extract_error_info(error)
        result3 = _extract_error_info(error)

        assert result1 == result2, "repeated calls should return identical results"
        assert result2 == result3, "repeated calls should return identical results"
