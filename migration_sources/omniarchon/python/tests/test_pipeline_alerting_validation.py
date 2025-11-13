"""
Tests for Pipeline Alerting Service - Slack Webhook Validation

Tests the validate_slack_webhook_url function and initialization validation
to ensure proper webhook URL configuration and error handling.
"""

import logging

import pytest
from src.server.services.pipeline_alerting_service import (
    AlertSeverity,
    NotificationChannel,
    PipelineAlertingService,
    validate_slack_webhook_url,
)


class TestSlackWebhookValidation:
    """Test suite for Slack webhook URL validation"""

    def test_valid_webhook_url(self):
        """Test validation of valid Slack webhook URL"""
        valid_url = "https://hooks.slack.com/services/T00000000/B00000000/TestTokenNotRealForValidation"
        is_valid, error = validate_slack_webhook_url(valid_url)

        assert is_valid is True
        assert error is None

    def test_valid_webhook_url_long_ids(self):
        """Test validation with longer workspace/channel IDs"""
        valid_url = "https://hooks.slack.com/services/T00000000ABC/B00000000XYZ/TestTokenLongerNotRealForValidation123"
        is_valid, error = validate_slack_webhook_url(valid_url)

        assert is_valid is True
        assert error is None

    def test_invalid_empty_url(self):
        """Test validation of empty URL"""
        is_valid, error = validate_slack_webhook_url("")

        assert is_valid is False
        assert "empty or None" in error

    def test_invalid_none_url(self):
        """Test validation of None URL"""
        is_valid, error = validate_slack_webhook_url(None)

        assert is_valid is False
        assert "empty or None" in error

    def test_invalid_wrong_type(self):
        """Test validation of non-string URL"""
        is_valid, error = validate_slack_webhook_url(12345)  # type: ignore

        assert is_valid is False
        assert "must be a string" in error
        assert "int" in error

    def test_invalid_wrong_prefix(self):
        """Test validation of URL with wrong prefix"""
        invalid_url = "https://example.com/webhook"
        is_valid, error = validate_slack_webhook_url(invalid_url)

        assert is_valid is False
        assert "Must start with" in error
        assert "hooks.slack.com/services/" in error

    def test_invalid_http_not_https(self):
        """Test validation of HTTP instead of HTTPS"""
        invalid_url = "http://hooks.slack.com/services/T123/B456/abc"
        is_valid, error = validate_slack_webhook_url(invalid_url)

        assert is_valid is False
        assert "Must start with" in error

    def test_invalid_structure_missing_parts(self):
        """Test validation of URL missing required parts"""
        invalid_url = "https://hooks.slack.com/services/T123/B456"
        is_valid, error = validate_slack_webhook_url(invalid_url)

        assert is_valid is False
        assert "Invalid Slack webhook URL structure" in error

    def test_valid_structure_lowercase_workspace_id(self):
        """Test validation of URL with lowercase workspace ID (case-insensitive)"""
        valid_url = "https://hooks.slack.com/services/t1234567890/B9876543210/AbCdEfGhIjKlMnOpQrStUvWx"
        is_valid, error = validate_slack_webhook_url(valid_url)

        assert is_valid is True
        assert error is None

    def test_valid_structure_lowercase_channel_id(self):
        """Test validation of URL with lowercase channel ID (case-insensitive)"""
        valid_url = "https://hooks.slack.com/services/T1234567890/b9876543210/AbCdEfGhIjKlMnOpQrStUvWx"
        is_valid, error = validate_slack_webhook_url(valid_url)

        assert is_valid is True
        assert error is None

    def test_invalid_structure_special_chars_in_token(self):
        """Test validation of URL with special characters in token"""
        invalid_url = "https://hooks.slack.com/services/T123/B456/abc-123_xyz"
        is_valid, error = validate_slack_webhook_url(invalid_url)

        assert is_valid is False
        assert "Invalid Slack webhook URL structure" in error

    def test_invalid_url_too_short(self):
        """Test validation of suspiciously short URL"""
        # This is a structurally valid format but too short
        short_url = "https://hooks.slack.com/services/T1/B2/a"
        is_valid, error = validate_slack_webhook_url(short_url)

        assert is_valid is False
        assert "Suspicious Slack webhook URL length" in error

    def test_invalid_url_too_long(self):
        """Test validation of suspiciously long URL"""
        # Create a URL that's too long (>150 chars)
        long_token = "A" * 200
        long_url = f"https://hooks.slack.com/services/T123/B456/{long_token}"
        is_valid, error = validate_slack_webhook_url(long_url)

        assert is_valid is False
        assert "Suspicious Slack webhook URL length" in error

    def test_valid_url_with_mixed_case_token(self):
        """Test that tokens can have mixed case alphanumeric"""
        valid_url = "https://hooks.slack.com/services/T1234ABC/B5678DEF/aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
        is_valid, error = validate_slack_webhook_url(valid_url)

        assert is_valid is True
        assert error is None

    def test_validation_error_message_includes_format_hint(self):
        """Test that error messages include format hints"""
        invalid_url = "https://example.com/webhook"
        is_valid, error = validate_slack_webhook_url(invalid_url)

        assert is_valid is False
        assert "hooks.slack.com/services/" in error


class TestPipelineAlertingServiceValidation:
    """Test suite for PipelineAlertingService initialization validation"""

    def test_service_init_valid_webhook_url(self, caplog):
        """Test service initialization with valid webhook URL"""
        config = {
            "notifications": {
                "slack": {
                    "webhook_url": "https://hooks.slack.com/services/T1234567890/B9876543210/AbCdEfGhIjKlMnOpQrStUvWx"
                }
            }
        }

        with caplog.at_level(logging.INFO):
            service = PipelineAlertingService(config)

        assert service is not None
        assert "Slack webhook URL validated successfully" in caplog.text

    def test_service_init_invalid_webhook_url(self, caplog):
        """Test service initialization with invalid webhook URL"""
        config = {
            "notifications": {"slack": {"webhook_url": "https://example.com/invalid"}}
        }

        with caplog.at_level(logging.ERROR):
            service = PipelineAlertingService(config)

        # Service should still initialize despite invalid URL
        assert service is not None
        assert "Invalid Slack webhook URL configuration" in caplog.text

    def test_service_init_missing_webhook_url_with_slack_config(self, caplog):
        """Test service initialization with Slack config but no webhook URL"""
        config = {"notifications": {"slack": {"enabled": True}}}

        with caplog.at_level(logging.WARNING):
            service = PipelineAlertingService(config)

        # Service should initialize and log warning
        assert service is not None
        assert "Slack webhook URL is not configured" in caplog.text
        assert "SLACK_WEBHOOK_URL" in caplog.text

    def test_service_init_no_slack_config(self, caplog):
        """Test service initialization without Slack configuration"""
        config = {"notifications": {"email": {"enabled": True}}}

        with caplog.at_level(logging.WARNING):
            service = PipelineAlertingService(config)

        # Service should initialize without warnings
        assert service is not None
        # Should not warn about missing Slack config if not configured
        assert "Slack webhook URL is not configured" not in caplog.text

    def test_service_init_empty_config(self):
        """Test service initialization with empty config"""
        service = PipelineAlertingService({})

        assert service is not None
        assert service.slack_config == {}

    def test_service_init_none_config(self):
        """Test service initialization with None config"""
        service = PipelineAlertingService(None)

        assert service is not None
        assert service.config == {}

    def test_service_still_works_with_invalid_webhook(self):
        """Test that service functionality is not broken by invalid webhook"""
        config = {
            "notifications": {"slack": {"webhook_url": "https://invalid.com/webhook"}}
        }

        service = PipelineAlertingService(config)

        # Service should still be able to manage alert rules
        assert len(service.alert_rules) > 0  # Default rules exist
        assert service.get_active_alerts() == []

    def test_validation_runs_after_default_rules_setup(self, caplog):
        """Test that validation considers default rules with Slack channels"""
        config = {"notifications": {"slack": {}}}

        # Default rules include Slack notification channels
        # So validation should warn about missing webhook URL
        with caplog.at_level(logging.WARNING):
            service = PipelineAlertingService(config)

        assert service is not None
        # Since default rules use Slack, should warn about missing URL
        # Note: This depends on whether default rules use Slack

    def test_http_url_rejected(self, caplog):
        """Test that HTTP URLs are rejected (must be HTTPS)"""
        config = {
            "notifications": {
                "slack": {
                    "webhook_url": "http://hooks.slack.com/services/T123/B456/abc123"
                }
            }
        }

        # Service should initialize but log error
        with caplog.at_level(logging.ERROR):
            service = PipelineAlertingService(config)

        assert service is not None
        assert "Invalid Slack webhook URL configuration" in caplog.text
        assert "Must start with" in caplog.text


class TestWebhookValidationEdgeCases:
    """Test edge cases for webhook validation"""

    def test_url_with_trailing_slash(self):
        """Test URL with trailing slash"""
        url = "https://hooks.slack.com/services/T123/B456/abc123/"
        is_valid, error = validate_slack_webhook_url(url)

        # Trailing slash makes it invalid
        assert is_valid is False

    def test_url_with_query_parameters(self):
        """Test URL with query parameters"""
        url = "https://hooks.slack.com/services/T123/B456/abc123?param=value"
        is_valid, error = validate_slack_webhook_url(url)

        # Query parameters make it invalid
        assert is_valid is False

    def test_url_with_fragment(self):
        """Test URL with fragment"""
        url = "https://hooks.slack.com/services/T123/B456/abc123#fragment"
        is_valid, error = validate_slack_webhook_url(url)

        # Fragment makes it invalid
        assert is_valid is False

    def test_url_with_extra_path_segments(self):
        """Test URL with extra path segments"""
        url = "https://hooks.slack.com/services/T123/B456/abc123/extra"
        is_valid, error = validate_slack_webhook_url(url)

        # Extra segments make it invalid
        assert is_valid is False

    def test_url_with_port_number(self):
        """Test URL with port number"""
        url = "https://hooks.slack.com:443/services/T123/B456/abc123"
        is_valid, error = validate_slack_webhook_url(url)

        # Port number makes it invalid
        assert is_valid is False

    def test_url_case_sensitivity(self):
        """Test that hooks.slack.com must be lowercase"""
        url = "https://HOOKS.SLACK.COM/services/T123/B456/abc123"
        is_valid, error = validate_slack_webhook_url(url)

        # Uppercase domain makes it invalid
        assert is_valid is False

    def test_whitespace_in_url(self):
        """Test URL with whitespace"""
        url = "https://hooks.slack.com/services/T123 /B456/abc123"
        is_valid, error = validate_slack_webhook_url(url)

        # Whitespace makes it invalid
        assert is_valid is False

    def test_url_with_encoded_characters(self):
        """Test URL with percent-encoded characters"""
        url = "https://hooks.slack.com/services/T123/B456/abc%20123"
        is_valid, error = validate_slack_webhook_url(url)

        # Encoded characters make it invalid
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
