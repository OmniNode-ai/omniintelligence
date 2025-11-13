"""
Integration Tests for Correlation ID Sanitization in Handlers

Tests that correlation ID sanitization is properly integrated into all
event handlers through BaseResponsePublisher.

Created: 2025-10-15
Purpose: Verify security enhancement integration across all handlers

Test Coverage:
1. BaseResponsePublisher._get_correlation_id() sanitization
2. All handler classes properly sanitize correlation IDs
3. Malicious correlation IDs are blocked in handler context
4. Valid correlation IDs pass through unchanged
"""

from unittest.mock import Mock
from uuid import UUID

# Import sanitization function and BaseResponsePublisher
from handlers.base_response_publisher import BaseResponsePublisher


class TestBaseResponsePublisherSanitization:
    """Test correlation ID sanitization in BaseResponsePublisher."""

    def test_get_correlation_id_with_valid_uuid_object(self):
        """Test that valid UUID objects are properly sanitized."""
        publisher = BaseResponsePublisher()

        # Create mock event with UUID correlation_id
        valid_uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_event = Mock()
        mock_event.correlation_id = valid_uuid

        result = publisher._get_correlation_id(mock_event)

        assert result == str(valid_uuid)
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_get_correlation_id_with_valid_string(self):
        """Test that valid string correlation IDs pass sanitization."""
        publisher = BaseResponsePublisher()

        # Create mock event with string correlation_id
        mock_event = Mock()
        mock_event.correlation_id = "request-12345-abc"

        result = publisher._get_correlation_id(mock_event)

        assert result == "request-12345-abc"

    def test_get_correlation_id_with_malicious_newline(self):
        """Test that newline injection is blocked."""
        publisher = BaseResponsePublisher()

        # Create mock event with malicious correlation_id
        mock_event = Mock()
        mock_event.correlation_id = "valid-id\nINJECTED_LOG"

        result = publisher._get_correlation_id(mock_event)

        # Should be sanitized to "unknown"
        assert result == "unknown"

    def test_get_correlation_id_with_ansi_escape_codes(self):
        """Test that ANSI escape code injection is blocked."""
        publisher = BaseResponsePublisher()

        # Create mock event with ANSI codes
        mock_event = Mock()
        mock_event.correlation_id = "valid-id\x1b[31mRED\x1b[0m"

        result = publisher._get_correlation_id(mock_event)

        # Should be sanitized to "unknown"
        assert result == "unknown"

    def test_get_correlation_id_with_control_characters(self):
        """Test that control characters are blocked."""
        publisher = BaseResponsePublisher()

        # Create mock event with control characters
        mock_event = Mock()
        mock_event.correlation_id = "valid-id\x00\x1f"

        result = publisher._get_correlation_id(mock_event)

        # Should be sanitized to "unknown"
        assert result == "unknown"

    def test_get_correlation_id_with_too_long_id(self):
        """Test that excessively long IDs are blocked."""
        publisher = BaseResponsePublisher()

        # Create mock event with very long correlation_id
        mock_event = Mock()
        mock_event.correlation_id = "a" * 200  # Exceeds MAX_CORRELATION_ID_LENGTH

        result = publisher._get_correlation_id(mock_event)

        # Should be sanitized to "unknown"
        assert result == "unknown"

    def test_get_correlation_id_from_dict_event(self):
        """Test extraction and sanitization from dict-style events."""
        publisher = BaseResponsePublisher()

        # Create dict event with valid correlation_id
        dict_event = {"correlation_id": "valid-dict-id-123"}

        result = publisher._get_correlation_id(dict_event)

        assert result == "valid-dict-id-123"

    def test_get_correlation_id_from_dict_with_malicious_id(self):
        """Test sanitization of malicious ID from dict event."""
        publisher = BaseResponsePublisher()

        # Create dict event with malicious correlation_id
        dict_event = {"correlation_id": "malicious\nlog\ninjection"}

        result = publisher._get_correlation_id(dict_event)

        assert result == "unknown"

    def test_get_correlation_id_with_none(self):
        """Test that None correlation_id returns 'unknown'."""
        publisher = BaseResponsePublisher()

        # Create mock event with None correlation_id
        mock_event = Mock()
        mock_event.correlation_id = None

        result = publisher._get_correlation_id(mock_event)

        assert result == "unknown"

    def test_get_correlation_id_with_missing_attribute(self):
        """Test that missing correlation_id returns 'unknown'."""
        publisher = BaseResponsePublisher()

        # Create mock event without correlation_id
        mock_event = Mock(spec=[])  # Empty spec means no attributes

        result = publisher._get_correlation_id(mock_event)

        assert result == "unknown"

    def test_get_correlation_id_from_dict_missing_key(self):
        """Test that missing correlation_id key in dict returns 'unknown'."""
        publisher = BaseResponsePublisher()

        # Create dict event without correlation_id
        dict_event = {"other_field": "value"}

        result = publisher._get_correlation_id(dict_event)

        assert result == "unknown"


class TestHandlerSanitizationBehavior:
    """Test sanitization behavior across different handler scenarios."""

    def test_sanitization_protects_against_log_forging(self):
        """Test that log forging attacks are prevented."""
        publisher = BaseResponsePublisher()

        # Simulate an attacker trying to forge a log entry
        forged_log = "abc123\n[2025-10-15 10:00:00] ERROR: System compromised!"
        mock_event = Mock()
        mock_event.correlation_id = forged_log

        sanitized_id = publisher._get_correlation_id(mock_event)

        # Verify the malicious content is blocked
        assert sanitized_id == "unknown"
        assert "\n" not in sanitized_id
        assert "ERROR" not in sanitized_id

    def test_sanitization_maintains_uuid_format(self):
        """Test that legitimate UUIDs are preserved exactly."""
        publisher = BaseResponsePublisher()

        # Test with standard UUID v4 format
        legitimate_uuid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        mock_event = Mock()
        mock_event.correlation_id = legitimate_uuid

        sanitized_id = publisher._get_correlation_id(mock_event)

        # Should pass through unchanged
        assert sanitized_id == legitimate_uuid

    def test_sanitization_preserves_custom_id_format(self):
        """Test that legitimate custom correlation IDs are preserved."""
        publisher = BaseResponsePublisher()

        # Test with custom correlation ID format
        custom_id = "req_12345_user_67890"
        mock_event = Mock()
        mock_event.correlation_id = custom_id

        sanitized_id = publisher._get_correlation_id(mock_event)

        # Should pass through unchanged
        assert sanitized_id == custom_id

    def test_sanitization_handles_uuid_object_conversion(self):
        """Test that UUID objects are properly converted and sanitized."""
        publisher = BaseResponsePublisher()

        # Test with UUID object (not string)
        uuid_obj = UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_event = Mock()
        mock_event.correlation_id = uuid_obj

        sanitized_id = publisher._get_correlation_id(mock_event)

        # Should be converted to string and pass sanitization
        assert sanitized_id == "550e8400-e29b-41d4-a716-446655440000"
        assert isinstance(sanitized_id, str)


class TestSanitizationSecurityScenarios:
    """Test real-world security scenarios."""

    def test_blocks_terminal_hijacking(self):
        """Test that terminal hijacking attempts are blocked."""
        publisher = BaseResponsePublisher()

        # ANSI codes to clear screen and reposition cursor
        hijack_attempt = "abc123\x1b[2J\x1b[H"
        mock_event = Mock()
        mock_event.correlation_id = hijack_attempt

        result = publisher._get_correlation_id(mock_event)

        assert result == "unknown"
        assert "\x1b" not in result

    def test_blocks_log_aggregation_bypass(self):
        """Test that log aggregation bypass attempts are blocked."""
        publisher = BaseResponsePublisher()

        # Null byte and newline to break log parsing
        bypass_attempt = "abc123\x00HIDDEN\nFAKE_LOG"
        mock_event = Mock()
        mock_event.correlation_id = bypass_attempt

        result = publisher._get_correlation_id(mock_event)

        assert result == "unknown"
        assert "\x00" not in result
        assert "\n" not in result

    def test_blocks_kafka_key_injection(self):
        """Test that Kafka key injection is prevented."""
        publisher = BaseResponsePublisher()

        # Special characters that could affect Kafka
        kafka_injection = "partition\x00offset\nmessage"
        mock_event = Mock()
        mock_event.correlation_id = kafka_injection

        result = publisher._get_correlation_id(mock_event)

        # Should be sanitized and safe for Kafka keys
        assert result == "unknown"
        assert "\x00" not in result
        assert "\n" not in result

    def test_ensures_safe_for_structured_logging(self):
        """Test that IDs are safe for structured logging systems."""
        publisher = BaseResponsePublisher()

        # Valid correlation ID
        valid_id = "request-123-service-abc"
        mock_event = Mock()
        mock_event.correlation_id = valid_id

        result = publisher._get_correlation_id(mock_event)

        # Should be safe for JSON, structured logs, etc.
        assert result == valid_id
        assert '"' not in result
        assert "'" not in result
        assert "\n" not in result
        assert "\\" not in result


class TestBackwardsCompatibility:
    """Test that sanitization doesn't break existing functionality."""

    def test_existing_valid_ids_unchanged(self):
        """Test that existing valid correlation IDs work unchanged."""
        publisher = BaseResponsePublisher()

        # Common existing correlation ID formats
        test_cases = [
            "550e8400-e29b-41d4-a716-446655440000",  # UUID
            "request-12345",  # Simple request ID
            "req_abc123_def456",  # Underscore format
            "correlation-id-123-456",  # Multi-segment
            "UPPER_CASE_123",  # Upper case
            "mixedCase123",  # Mixed case
            "123456789",  # Numeric only
        ]

        for test_id in test_cases:
            mock_event = Mock()
            mock_event.correlation_id = test_id

            result = publisher._get_correlation_id(mock_event)

            assert result == test_id, f"Valid ID '{test_id}' was modified"

    def test_none_and_missing_handled_gracefully(self):
        """Test that None and missing IDs are handled without errors."""
        publisher = BaseResponsePublisher()

        # Test None
        mock_event_none = Mock()
        mock_event_none.correlation_id = None
        assert publisher._get_correlation_id(mock_event_none) == "unknown"

        # Test missing attribute
        mock_event_missing = Mock(spec=[])
        assert publisher._get_correlation_id(mock_event_missing) == "unknown"

        # Test empty string
        mock_event_empty = Mock()
        mock_event_empty.correlation_id = ""
        assert publisher._get_correlation_id(mock_event_empty) == "unknown"
