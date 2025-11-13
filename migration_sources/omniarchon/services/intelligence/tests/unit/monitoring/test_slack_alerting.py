"""
Unit Tests for Slack Alerting Service

Tests the Slack webhook integration, rate limiting, alert formatting,
and error handling for event processing failure alerts.

Created: 2025-10-24
"""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from monitoring.slack_alerting import (
    AlertSeverity,
    SlackAlertingService,
    get_slack_alerting_service,
)


class TestSlackAlertingService:
    """Test suite for SlackAlertingService"""

    @pytest.fixture
    def mock_webhook_url(self):
        """Mock Slack webhook URL"""
        return "https://hooks.slack.com/services/TEST/WEBHOOK/URL"

    @pytest.fixture
    def alerting_service(self, mock_webhook_url):
        """Create SlackAlertingService instance for testing"""
        return SlackAlertingService(
            webhook_url=mock_webhook_url,
            rate_limit_seconds=60,
            max_retries=3,
            enabled=True,
        )

    @pytest.fixture
    def disabled_service(self):
        """Create disabled SlackAlertingService"""
        return SlackAlertingService(
            webhook_url=None,
            enabled=False,
        )

    @pytest.mark.asyncio
    async def test_initialization_enabled(self, mock_webhook_url):
        """Test service initialization when enabled"""
        service = SlackAlertingService(webhook_url=mock_webhook_url, enabled=True)

        assert service.enabled is True
        assert service.webhook_url == mock_webhook_url
        assert service.rate_limit_seconds == 60
        assert service.max_retries == 3
        assert service.metrics["alerts_sent"] == 0
        assert service.metrics["alerts_failed"] == 0

    @pytest.mark.asyncio
    async def test_initialization_disabled_no_webhook(self):
        """Test service initialization when webhook URL not provided"""
        service = SlackAlertingService(webhook_url=None, enabled=True)

        assert service.enabled is False
        assert service.webhook_url is None

    @pytest.mark.asyncio
    async def test_initialization_disabled_via_config(self, mock_webhook_url):
        """Test service initialization when disabled via config"""
        service = SlackAlertingService(webhook_url=mock_webhook_url, enabled=False)

        assert service.enabled is False
        assert service.webhook_url == mock_webhook_url

    @pytest.mark.asyncio
    async def test_send_alert_when_disabled(self, disabled_service):
        """Test that alerts are not sent when service is disabled"""
        result = await disabled_service.send_alert(
            title="Test Alert",
            message="This should not be sent",
            severity=AlertSeverity.ERROR,
        )

        assert result is False
        assert disabled_service.metrics["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_send_alert_success(self, alerting_service, mock_webhook_url):
        """Test successful alert sending"""
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(
            alerting_service, "_send_to_slack", return_value=True
        ) as mock_send:
            result = await alerting_service.send_alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
            )

            assert result is True
            assert alerting_service.metrics["alerts_sent"] == 1
            assert alerting_service.metrics["alerts_failed"] == 0
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_failure(self, alerting_service):
        """Test alert sending failure"""
        with patch.object(
            alerting_service, "_send_to_slack", return_value=False
        ) as mock_send:
            result = await alerting_service.send_alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
            )

            assert result is False
            assert alerting_service.metrics["alerts_sent"] == 0
            assert alerting_service.metrics["alerts_failed"] == 1

    @pytest.mark.asyncio
    async def test_rate_limiting(self, alerting_service):
        """Test alert rate limiting prevents duplicate alerts"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            # Send first alert
            result1 = await alerting_service.send_alert(
                title="Test Alert",
                message="First message",
                severity=AlertSeverity.ERROR,
                dedupe_key="test_key",
            )

            # Send duplicate alert immediately
            result2 = await alerting_service.send_alert(
                title="Test Alert",
                message="Duplicate message",
                severity=AlertSeverity.ERROR,
                dedupe_key="test_key",
            )

            assert result1 is True
            assert result2 is False
            assert alerting_service.metrics["alerts_sent"] == 1
            assert alerting_service.metrics["alerts_rate_limited"] == 1

    @pytest.mark.asyncio
    async def test_rate_limiting_different_keys(self, alerting_service):
        """Test that different dedupe keys are not rate limited"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            result1 = await alerting_service.send_alert(
                title="Test Alert 1",
                message="First message",
                severity=AlertSeverity.ERROR,
                dedupe_key="key1",
            )

            result2 = await alerting_service.send_alert(
                title="Test Alert 2",
                message="Second message",
                severity=AlertSeverity.ERROR,
                dedupe_key="key2",
            )

            assert result1 is True
            assert result2 is True
            assert alerting_service.metrics["alerts_sent"] == 2
            assert alerting_service.metrics["alerts_rate_limited"] == 0

    @pytest.mark.asyncio
    async def test_build_slack_message_info(self, alerting_service):
        """Test Slack message building for INFO severity"""
        message = alerting_service._build_slack_message(
            title="Info Alert",
            message="This is an info message",
            severity=AlertSeverity.INFO,
            fields={"Field1": "Value1", "Field2": "Value2"},
        )

        assert "attachments" in message
        assert len(message["attachments"]) == 1
        assert message["attachments"][0]["color"] == "#36a64f"  # Green
        assert (
            len(message["attachments"][0]["blocks"]) == 4
        )  # Header, section, fields, context

    @pytest.mark.asyncio
    async def test_build_slack_message_warning(self, alerting_service):
        """Test Slack message building for WARNING severity"""
        message = alerting_service._build_slack_message(
            title="Warning Alert",
            message="This is a warning",
            severity=AlertSeverity.WARNING,
            fields=None,
        )

        assert message["attachments"][0]["color"] == "#ff9800"  # Orange
        assert (
            len(message["attachments"][0]["blocks"]) == 3
        )  # Header, section, context (no fields)

    @pytest.mark.asyncio
    async def test_build_slack_message_error(self, alerting_service):
        """Test Slack message building for ERROR severity"""
        message = alerting_service._build_slack_message(
            title="Error Alert",
            message="This is an error",
            severity=AlertSeverity.ERROR,
            fields=None,
        )

        assert message["attachments"][0]["color"] == "#f44336"  # Red

    @pytest.mark.asyncio
    async def test_build_slack_message_critical(self, alerting_service):
        """Test Slack message building for CRITICAL severity"""
        message = alerting_service._build_slack_message(
            title="Critical Alert",
            message="This is critical",
            severity=AlertSeverity.CRITICAL,
            fields=None,
        )

        assert message["attachments"][0]["color"] == "#9c27b0"  # Purple

    @pytest.mark.asyncio
    async def test_alert_event_processing_failure(self, alerting_service):
        """Test event processing failure alert"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            result = await alerting_service.alert_event_processing_failure(
                event_type="codegen.request.validate",
                error_type="ValidationError",
                error_message="Invalid payload structure",
                failure_count=10,
                total_events=100,
            )

            assert result is True
            assert alerting_service.metrics["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_alert_high_failure_rate_warning(self, alerting_service):
        """Test high failure rate alert with WARNING severity"""
        with patch.object(
            alerting_service, "_send_to_slack", return_value=True
        ) as mock_send:
            result = await alerting_service.alert_high_failure_rate(
                failure_rate=15.0,
                failure_count=15,
                total_events=100,
                time_window_minutes=5,
            )

            assert result is True
            # Verify severity is WARNING for 15% failure rate
            call_args = mock_send.call_args[0][0]
            assert call_args["attachments"][0]["color"] == "#ff9800"  # Orange (warning)

    @pytest.mark.asyncio
    async def test_alert_high_failure_rate_critical(self, alerting_service):
        """Test high failure rate alert with CRITICAL severity"""
        with patch.object(
            alerting_service, "_send_to_slack", return_value=True
        ) as mock_send:
            result = await alerting_service.alert_high_failure_rate(
                failure_rate=55.0,
                failure_count=55,
                total_events=100,
                time_window_minutes=5,
            )

            assert result is True
            # Verify severity is CRITICAL for 55% failure rate
            call_args = mock_send.call_args[0][0]
            assert (
                call_args["attachments"][0]["color"] == "#9c27b0"
            )  # Purple (critical)

    @pytest.mark.asyncio
    async def test_alert_dlq_routing(self, alerting_service):
        """Test DLQ routing alert"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            result = await alerting_service.alert_dlq_routing(
                topic="omninode.codegen.request.validate.v1",
                error_type="deserialization_error",
                dlq_count=5,
            )

            assert result is True
            assert alerting_service.metrics["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_alert_consumer_unhealthy(self, alerting_service):
        """Test consumer unhealthy alert"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            result = await alerting_service.alert_consumer_unhealthy(
                health_status="degraded",
                error_rate=25.0,
                uptime_seconds=3600.0,
            )

            assert result is True
            assert alerting_service.metrics["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_send_to_slack_success(self, alerting_service, mock_webhook_url):
        """Test _send_to_slack with successful response"""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(alerting_service, "_get_client", return_value=mock_client):
            message = {"text": "Test message"}
            result = await alerting_service._send_to_slack(message)

            assert result is True
            mock_client.post.assert_called_once_with(
                mock_webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
            )

    @pytest.mark.asyncio
    async def test_send_to_slack_retry_on_failure(
        self, alerting_service, mock_webhook_url
    ):
        """Test _send_to_slack retries on failure"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(alerting_service, "_get_client", return_value=mock_client):
            message = {"text": "Test message"}
            result = await alerting_service._send_to_slack(message)

            assert result is False
            # Should retry 3 times (max_retries=3)
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_to_slack_exception_handling(self, alerting_service):
        """Test _send_to_slack handles exceptions gracefully"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))

        with patch.object(alerting_service, "_get_client", return_value=mock_client):
            message = {"text": "Test message"}
            result = await alerting_service._send_to_slack(message)

            assert result is False
            assert mock_client.post.call_count == 3  # Should retry

    @pytest.mark.asyncio
    async def test_get_metrics(self, alerting_service):
        """Test get_metrics returns current metrics"""
        with patch.object(alerting_service, "_send_to_slack", return_value=True):
            await alerting_service.send_alert("Test", "Message", AlertSeverity.INFO)

        metrics = alerting_service.get_metrics()

        assert "alerts_sent" in metrics
        assert "alerts_failed" in metrics
        assert "alerts_rate_limited" in metrics
        assert metrics["alerts_sent"] == 1

    @pytest.mark.asyncio
    async def test_close_client(self, alerting_service):
        """Test close() cleans up HTTP client"""
        mock_client = AsyncMock()
        alerting_service._client = mock_client

        await alerting_service.close()

        assert alerting_service._client is None
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_singleton_instance(self):
        """Test get_slack_alerting_service returns singleton"""
        service1 = get_slack_alerting_service()
        service2 = get_slack_alerting_service()

        assert service1 is service2


class TestAlertSeverity:
    """Test suite for AlertSeverity enum"""

    def test_severity_values(self):
        """Test AlertSeverity enum values"""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestEnvironmentConfiguration:
    """Test suite for environment variable configuration"""

    @pytest.mark.asyncio
    async def test_webhook_url_from_env(self, monkeypatch):
        """Test webhook URL loaded from environment variable"""
        test_url = "https://hooks.slack.com/services/ENV/TEST/URL"
        monkeypatch.setenv("SLACK_WEBHOOK_URL", test_url)

        service = SlackAlertingService()

        assert service.webhook_url == test_url

    @pytest.mark.asyncio
    async def test_enabled_from_env_true(self, monkeypatch):
        """Test enabled flag from environment variable (true)"""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://test.com/webhook")
        monkeypatch.setenv("SLACK_ALERTING_ENABLED", "true")

        service = SlackAlertingService()

        assert service.enabled is True

    @pytest.mark.asyncio
    async def test_enabled_from_env_false(self, monkeypatch):
        """Test enabled flag from environment variable (false)"""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://test.com/webhook")
        monkeypatch.setenv("SLACK_ALERTING_ENABLED", "false")

        service = SlackAlertingService()

        assert service.enabled is False
