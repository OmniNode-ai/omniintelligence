"""
Unit Tests for Correlation ID Sanitization

Tests the security.sanitize_correlation_id function to ensure it properly
prevents log injection attacks and validates correlation ID format.

Created: 2025-10-15
Purpose: Comprehensive security testing for correlation ID sanitization

Test Coverage:
1. Valid correlation IDs (UUIDs, alphanumeric with hyphens/underscores)
2. Log injection attacks (newlines, carriage returns, null bytes)
3. ANSI escape code injection
4. Control character injection
5. Length validation
6. Edge cases (None, empty, whitespace)
7. Unicode and special characters
8. Format validation helper function
"""

from unittest.mock import patch

import pytest
from utils.security import (
    MAX_CORRELATION_ID_LENGTH,
    sanitize_correlation_id,
    validate_correlation_id_format,
)


class TestSanitizeCorrelationIdValid:
    """Test cases for valid correlation IDs that should pass sanitization."""

    def test_valid_uuid_format(self):
        """Test that valid UUID format passes sanitization."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = sanitize_correlation_id(valid_uuid)
        assert result == valid_uuid

    def test_valid_alphanumeric(self):
        """Test that alphanumeric IDs pass sanitization."""
        valid_id = "abc123def456"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id

    def test_valid_with_underscores(self):
        """Test that IDs with underscores pass sanitization."""
        valid_id = "request_id_12345"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id

    def test_valid_with_hyphens(self):
        """Test that IDs with hyphens pass sanitization."""
        valid_id = "request-id-12345"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id

    def test_valid_mixed_case(self):
        """Test that mixed case IDs pass sanitization."""
        valid_id = "AbC123-DeF456_GhI789"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id

    def test_valid_numeric_only(self):
        """Test that numeric-only IDs pass sanitization."""
        valid_id = "1234567890"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id

    def test_valid_max_length(self):
        """Test that IDs at maximum length pass sanitization."""
        valid_id = "a" * MAX_CORRELATION_ID_LENGTH
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id


class TestSanitizeCorrelationIdLogInjection:
    """Test cases for log injection attack prevention."""

    def test_newline_injection(self):
        """Test that newline characters are blocked."""
        malicious_id = "valid_id\nINJECTED_LOG_ENTRY"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_carriage_return_injection(self):
        """Test that carriage return characters are blocked."""
        malicious_id = "valid_id\rINJECTED_LOG_ENTRY"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_null_byte_injection(self):
        """Test that null bytes are blocked."""
        malicious_id = "valid_id\x00INJECTED"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_tab_injection(self):
        """Test that tab characters are blocked."""
        malicious_id = "valid_id\tINJECTED"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_vertical_tab_injection(self):
        """Test that vertical tab characters are blocked."""
        malicious_id = "valid_id\vINJECTED"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_form_feed_injection(self):
        """Test that form feed characters are blocked."""
        malicious_id = "valid_id\fINJECTED"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_backspace_injection(self):
        """Test that backspace characters are blocked."""
        malicious_id = "valid_id\bINJECTED"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_multi_line_injection(self):
        """Test that multi-line injection attempts are blocked."""
        malicious_id = "valid_id\n[2025-10-15] ERROR: Forged log entry\nreal_id"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"


class TestSanitizeCorrelationIdAnsiEscapes:
    """Test cases for ANSI escape code injection prevention."""

    def test_ansi_color_code_injection(self):
        """Test that ANSI color codes are blocked."""
        malicious_id = "valid_id\x1b[31mRED_TEXT\x1b[0m"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_ansi_cursor_movement(self):
        """Test that ANSI cursor movement codes are blocked."""
        malicious_id = "valid_id\x1b[2J\x1b[H"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_ansi_clear_screen(self):
        """Test that ANSI clear screen codes are blocked."""
        malicious_id = "valid_id\x1bc"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_ansi_bold_injection(self):
        """Test that ANSI bold codes are blocked."""
        malicious_id = "valid_id\x1b[1mBOLD_TEXT\x1b[0m"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"


class TestSanitizeCorrelationIdControlChars:
    """Test cases for control character injection prevention."""

    def test_bell_character(self):
        """Test that bell character is blocked."""
        malicious_id = "valid_id\x07"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_escape_character(self):
        """Test that escape character is blocked."""
        malicious_id = "valid_id\x1b"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_delete_character(self):
        """Test that delete character is blocked."""
        malicious_id = "valid_id\x7f"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_high_control_chars(self):
        """Test that high control characters (0x80-0x9f) are blocked."""
        malicious_id = "valid_id\x80\x9f"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"


class TestSanitizeCorrelationIdLengthValidation:
    """Test cases for length validation."""

    def test_exceeds_max_length(self):
        """Test that IDs exceeding max length are rejected."""
        too_long = "a" * (MAX_CORRELATION_ID_LENGTH + 1)
        result = sanitize_correlation_id(too_long)
        assert result == "unknown"

    def test_extremely_long_id(self):
        """Test that extremely long IDs are rejected."""
        too_long = "a" * 10000
        result = sanitize_correlation_id(too_long)
        assert result == "unknown"

    def test_max_length_minus_one(self):
        """Test that IDs just under max length pass."""
        valid_id = "a" * (MAX_CORRELATION_ID_LENGTH - 1)
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id


class TestSanitizeCorrelationIdEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_none_input(self):
        """Test that None input returns 'unknown'."""
        result = sanitize_correlation_id(None)
        assert result == "unknown"

    def test_empty_string(self):
        """Test that empty string returns 'unknown'."""
        result = sanitize_correlation_id("")
        assert result == "unknown"

    def test_whitespace_only(self):
        """Test that whitespace-only string returns 'unknown'."""
        result = sanitize_correlation_id("   ")
        assert result == "unknown"

    def test_single_space(self):
        """Test that single space returns 'unknown'."""
        result = sanitize_correlation_id(" ")
        assert result == "unknown"

    def test_spaces_in_middle(self):
        """Test that IDs with spaces are rejected."""
        invalid_id = "valid id with spaces"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"


class TestSanitizeCorrelationIdSpecialChars:
    """Test cases for special characters and Unicode."""

    def test_dollar_sign(self):
        """Test that dollar sign is rejected."""
        invalid_id = "id$with$dollar"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_percent_sign(self):
        """Test that percent sign is rejected."""
        invalid_id = "id%with%percent"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_at_sign(self):
        """Test that at sign is rejected."""
        invalid_id = "id@with@at"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_unicode_characters(self):
        """Test that Unicode characters are rejected."""
        invalid_id = "id_with_émojis_🎉"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_slash_characters(self):
        """Test that forward/back slashes are rejected."""
        invalid_id = "id/with/slash"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_path_traversal_attempt(self):
        """Test that path traversal attempts are rejected."""
        invalid_id = "../../../etc/passwd"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"

    def test_sql_injection_attempt(self):
        """Test that SQL injection attempts are rejected."""
        invalid_id = "id'; DROP TABLE users; --"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"


class TestSanitizeCorrelationIdAllowUnknownFlag:
    """Test cases for allow_unknown parameter behavior."""

    def test_allow_unknown_true_with_invalid(self):
        """Test that invalid ID returns 'unknown' when allow_unknown=True."""
        invalid_id = "invalid\nid"
        result = sanitize_correlation_id(invalid_id, allow_unknown=True)
        assert result == "unknown"

    def test_allow_unknown_false_with_invalid(self):
        """Test that invalid ID raises ValueError when allow_unknown=False."""
        invalid_id = "invalid\nid"
        with pytest.raises(ValueError, match="contains control characters"):
            sanitize_correlation_id(invalid_id, allow_unknown=False)

    def test_allow_unknown_false_with_none(self):
        """Test that None raises ValueError when allow_unknown=False."""
        with pytest.raises(ValueError, match="cannot be None or empty"):
            sanitize_correlation_id(None, allow_unknown=False)

    def test_allow_unknown_false_with_too_long(self):
        """Test that too-long ID raises ValueError when allow_unknown=False."""
        too_long = "a" * (MAX_CORRELATION_ID_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_correlation_id(too_long, allow_unknown=False)

    def test_allow_unknown_false_with_special_chars(self):
        """Test that special chars raise ValueError when allow_unknown=False."""
        invalid_id = "id@with@special"
        with pytest.raises(ValueError, match="contains invalid characters"):
            sanitize_correlation_id(invalid_id, allow_unknown=False)

    def test_allow_unknown_true_with_valid(self):
        """Test that valid ID passes when allow_unknown=True."""
        valid_id = "valid-id-123"
        result = sanitize_correlation_id(valid_id, allow_unknown=True)
        assert result == valid_id

    def test_allow_unknown_false_with_valid(self):
        """Test that valid ID passes when allow_unknown=False."""
        valid_id = "valid-id-123"
        result = sanitize_correlation_id(valid_id, allow_unknown=False)
        assert result == valid_id


class TestSanitizeCorrelationIdMaxLengthParam:
    """Test cases for custom max_length parameter."""

    def test_custom_max_length_pass(self):
        """Test that ID under custom max_length passes."""
        valid_id = "abc123"
        result = sanitize_correlation_id(valid_id, max_length=10)
        assert result == valid_id

    def test_custom_max_length_fail(self):
        """Test that ID over custom max_length fails."""
        too_long = "abc123456789"
        result = sanitize_correlation_id(too_long, max_length=10)
        assert result == "unknown"

    def test_custom_max_length_exact(self):
        """Test that ID at exactly custom max_length passes."""
        exact_length = "abcdefghij"  # 10 chars
        result = sanitize_correlation_id(exact_length, max_length=10)
        assert result == exact_length


class TestValidateCorrelationIdFormat:
    """Test cases for validate_correlation_id_format helper function."""

    def test_valid_format_returns_true(self):
        """Test that valid format returns True."""
        valid_id = "abc123-def456"
        assert validate_correlation_id_format(valid_id) is True

    def test_invalid_format_returns_false(self):
        """Test that invalid format returns False."""
        invalid_id = "invalid\nid"
        assert validate_correlation_id_format(invalid_id) is False

    def test_none_returns_false(self):
        """Test that None returns False."""
        assert validate_correlation_id_format(None) is False

    def test_empty_returns_false(self):
        """Test that empty string returns False."""
        assert validate_correlation_id_format("") is False

    def test_special_chars_returns_false(self):
        """Test that special characters return False."""
        invalid_id = "id@with@special"
        assert validate_correlation_id_format(invalid_id) is False

    def test_too_long_returns_false(self):
        """Test that too-long ID returns False."""
        too_long = "a" * (MAX_CORRELATION_ID_LENGTH + 1)
        assert validate_correlation_id_format(too_long) is False

    def test_valid_uuid_returns_true(self):
        """Test that valid UUID returns True."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert validate_correlation_id_format(valid_uuid) is True


class TestSanitizeCorrelationIdLogging:
    """Test cases for logging behavior during sanitization."""

    @patch("utils.security.logger")
    def test_logs_warning_for_control_chars(self, mock_logger):
        """Test that warning is logged for control characters."""
        invalid_id = "invalid\nid"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"
        mock_logger.warning.assert_called_once()
        assert "control characters" in mock_logger.warning.call_args[0][0]

    @patch("utils.security.logger")
    def test_logs_warning_for_invalid_chars(self, mock_logger):
        """Test that warning is logged for invalid characters."""
        invalid_id = "invalid@id"
        result = sanitize_correlation_id(invalid_id)
        assert result == "unknown"
        mock_logger.warning.assert_called_once()
        assert "invalid characters" in mock_logger.warning.call_args[0][0]

    @patch("utils.security.logger")
    def test_logs_warning_for_too_long(self, mock_logger):
        """Test that warning is logged for too-long IDs."""
        too_long = "a" * (MAX_CORRELATION_ID_LENGTH + 1)
        result = sanitize_correlation_id(too_long)
        assert result == "unknown"
        mock_logger.warning.assert_called_once()
        assert "maximum length" in mock_logger.warning.call_args[0][0]

    @patch("utils.security.logger")
    def test_no_logs_for_valid_id(self, mock_logger):
        """Test that no warnings are logged for valid IDs."""
        valid_id = "valid-id-123"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id
        mock_logger.warning.assert_not_called()


class TestSanitizeCorrelationIdRealWorldScenarios:
    """Test cases for real-world scenarios and attack vectors."""

    def test_log_forging_attack(self):
        """Test protection against log forging attacks."""
        # Attacker tries to inject fake error log
        malicious_id = "abc123\n[2025-10-15 10:00:00] ERROR: System compromised!"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_terminal_hijacking_attack(self):
        """Test protection against terminal hijacking via ANSI codes."""
        # Attacker tries to hide malicious activity with ANSI clear screen
        malicious_id = "abc123\x1b[2J\x1b[H"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_log_aggregation_bypass(self):
        """Test protection against log aggregation bypass attempts."""
        # Attacker tries to break log parsing with control chars
        malicious_id = "abc123\x00HIDDEN\nFAKE_LOG"
        result = sanitize_correlation_id(malicious_id)
        assert result == "unknown"

    def test_legitimate_uuid_v4(self):
        """Test that legitimate UUID v4 passes."""
        valid_uuid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        result = sanitize_correlation_id(valid_uuid)
        assert result == valid_uuid

    def test_legitimate_custom_id(self):
        """Test that legitimate custom correlation IDs pass."""
        valid_custom = "req_12345_user_67890"
        result = sanitize_correlation_id(valid_custom)
        assert result == valid_custom

    def test_kafka_key_compatibility(self):
        """Test that sanitized IDs are safe for Kafka keys."""
        # Kafka keys should not contain special chars that could cause issues
        valid_id = "partition-0-offset-12345"
        result = sanitize_correlation_id(valid_id)
        assert result == valid_id
        # Verify no special chars that could affect Kafka
        assert "\n" not in result
        assert "\r" not in result
        assert "\x00" not in result
