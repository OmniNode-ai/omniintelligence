"""
Slack Alerting Module for Event Processing Failures

Provides Slack webhook integration for real-time alerting on event processing failures,
DLQ routing, and other critical operational issues.

Created: 2025-10-24
Purpose: Enable real-time Slack notifications for Kafka event processing failures
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SlackAlertingService:
    """
    Slack alerting service for event processing failures.

    Sends formatted Slack messages for:
    - Event processing failures
    - High failure rates
    - DLQ routing events
    - Consumer health degradation

    Features:
    - Async Slack webhook calls
    - Rate limiting to prevent spam
    - Retry logic with exponential backoff
    - Alert deduplication
    - Rich message formatting with blocks
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        rate_limit_seconds: int = 60,
        max_retries: int = 3,
        enabled: bool = True,
    ):
        """
        Initialize Slack alerting service.

        Args:
            webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
            rate_limit_seconds: Minimum seconds between alerts of same type (default: 60)
            max_retries: Maximum retry attempts for failed webhook calls (default: 3)
            enabled: Whether alerting is enabled (default: True, can disable via SLACK_ALERTING_ENABLED env var)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries

        # Check if alerting is enabled via environment variable
        env_enabled = os.getenv("SLACK_ALERTING_ENABLED", "true").lower() == "true"
        self.enabled = enabled and env_enabled and bool(self.webhook_url)

        # Rate limiting and deduplication
        self._last_alert_times: Dict[str, float] = {}
        self._alert_lock = asyncio.Lock()

        # HTTP client (initialized lazily)
        self._client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "alerts_sent": 0,
            "alerts_failed": 0,
            "alerts_rate_limited": 0,
        }

        if not self.enabled:
            if not self.webhook_url:
                logger.warning(
                    "Slack alerting disabled: SLACK_WEBHOOK_URL not configured"
                )
            else:
                logger.info("Slack alerting disabled via configuration")
        else:
            logger.info(
                f"Slack alerting enabled with rate limit: {rate_limit_seconds}s"
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for Slack webhook calls."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.ERROR,
        fields: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> bool:
        """
        Send Slack alert with rate limiting and deduplication.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity level
            fields: Additional fields to include in alert
            dedupe_key: Key for deduplication (prevents duplicate alerts within rate limit window)

        Returns:
            True if alert sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Slack alerting disabled, skipping alert: {title}")
            return False

        # Apply rate limiting
        async with self._alert_lock:
            current_time = datetime.now(timezone.utc).timestamp()
            dedupe_key = dedupe_key or f"{title}:{severity.value}"

            if dedupe_key in self._last_alert_times:
                time_since_last = current_time - self._last_alert_times[dedupe_key]
                if time_since_last < self.rate_limit_seconds:
                    self.metrics["alerts_rate_limited"] += 1
                    logger.debug(
                        f"Rate limiting alert: {dedupe_key} "
                        f"(last sent {time_since_last:.1f}s ago)"
                    )
                    return False

            self._last_alert_times[dedupe_key] = current_time

        # Build Slack message
        slack_message = self._build_slack_message(title, message, severity, fields)

        # Send to Slack with retries
        success = await self._send_to_slack(slack_message)

        if success:
            self.metrics["alerts_sent"] += 1
        else:
            self.metrics["alerts_failed"] += 1

        return success

    def _build_slack_message(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build formatted Slack message with blocks.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity level
            fields: Additional fields to display

        Returns:
            Slack message payload
        """
        # Color mapping for severity levels
        color_map = {
            AlertSeverity.INFO: "#36a64f",  # Green
            AlertSeverity.WARNING: "#ff9800",  # Orange
            AlertSeverity.ERROR: "#f44336",  # Red
            AlertSeverity.CRITICAL: "#9c27b0",  # Purple
        }

        # Emoji mapping for severity levels
        emoji_map = {
            AlertSeverity.INFO: ":information_source:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.ERROR: ":x:",
            AlertSeverity.CRITICAL: ":rotating_light:",
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji_map[severity]} {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            },
        ]

        # Add fields if provided
        if fields:
            field_elements = []
            for key, value in fields.items():
                field_elements.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*{key}:*\n{value}",
                    }
                )

            blocks.append(
                {
                    "type": "section",
                    "fields": field_elements,
                }
            )

        # Add timestamp footer
        timestamp = datetime.now(timezone.utc).isoformat()
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Timestamp:* {timestamp} | *Service:* Intelligence Service",
                    }
                ],
            }
        )

        return {
            "attachments": [
                {
                    "color": color_map[severity],
                    "blocks": blocks,
                }
            ]
        }

    async def _send_to_slack(self, message: Dict[str, Any]) -> bool:
        """
        Send message to Slack webhook with retry logic.

        Args:
            message: Slack message payload

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.error("Cannot send Slack alert: webhook URL not configured")
            return False

        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    self.webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    logger.debug(
                        f"Slack alert sent successfully (attempt {attempt + 1})"
                    )
                    return True
                else:
                    logger.warning(
                        f"Slack webhook returned status {response.status_code}: {response.text} "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to send Slack alert (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2**attempt)

        logger.error(f"Failed to send Slack alert after {self.max_retries} attempts")
        return False

    async def alert_event_processing_failure(
        self,
        event_type: str,
        error_type: str,
        error_message: str,
        failure_count: int,
        total_events: int,
    ) -> bool:
        """
        Send alert for event processing failure.

        Args:
            event_type: Type of event that failed
            error_type: Category of error
            error_message: Error message
            failure_count: Number of failures for this event type
            total_events: Total events processed

        Returns:
            True if alert sent successfully
        """
        failure_rate = (failure_count / total_events * 100) if total_events > 0 else 0

        title = f"Event Processing Failure: {event_type}"
        message = (
            f"Event processing failed for `{event_type}` with error type `{error_type}`"
        )

        fields = {
            "Event Type": event_type,
            "Error Type": error_type,
            "Error Message": (
                error_message[:200] + "..."
                if len(error_message) > 200
                else error_message
            ),
            "Failure Count": str(failure_count),
            "Total Events": str(total_events),
            "Failure Rate": f"{failure_rate:.2f}%",
        }

        severity = AlertSeverity.ERROR
        if failure_rate > 50:
            severity = AlertSeverity.CRITICAL

        return await self.send_alert(
            title=title,
            message=message,
            severity=severity,
            fields=fields,
            dedupe_key=f"event_failure:{event_type}:{error_type}",
        )

    async def alert_high_failure_rate(
        self,
        failure_rate: float,
        failure_count: int,
        total_events: int,
        time_window_minutes: int = 5,
    ) -> bool:
        """
        Send alert for high overall failure rate.

        Args:
            failure_rate: Failure rate percentage (0-100)
            failure_count: Number of failures
            total_events: Total events processed
            time_window_minutes: Time window for calculation

        Returns:
            True if alert sent successfully
        """
        title = "⚠️ High Event Processing Failure Rate"
        message = (
            f"Event processing failure rate is `{failure_rate:.2f}%` "
            f"over the last {time_window_minutes} minutes"
        )

        fields = {
            "Failure Rate": f"{failure_rate:.2f}%",
            "Failed Events": str(failure_count),
            "Total Events": str(total_events),
            "Time Window": f"{time_window_minutes} minutes",
        }

        severity = AlertSeverity.WARNING
        if failure_rate > 50:
            severity = AlertSeverity.CRITICAL
        elif failure_rate > 25:
            severity = AlertSeverity.ERROR

        return await self.send_alert(
            title=title,
            message=message,
            severity=severity,
            fields=fields,
            dedupe_key="high_failure_rate",
        )

    async def alert_dlq_routing(
        self,
        topic: str,
        error_type: str,
        dlq_count: int,
    ) -> bool:
        """
        Send alert for DLQ routing event.

        Args:
            topic: Original topic name
            error_type: Type of error that caused DLQ routing
            dlq_count: Total messages routed to DLQ

        Returns:
            True if alert sent successfully
        """
        title = f"Message Routed to DLQ: {topic}"
        message = f"Message from topic `{topic}` routed to DLQ due to `{error_type}`"

        fields = {
            "Topic": topic,
            "Error Type": error_type,
            "Total DLQ Messages": str(dlq_count),
        }

        return await self.send_alert(
            title=title,
            message=message,
            severity=AlertSeverity.WARNING,
            fields=fields,
            dedupe_key=f"dlq_routing:{topic}:{error_type}",
        )

    async def alert_consumer_unhealthy(
        self,
        health_status: str,
        error_rate: float,
        uptime_seconds: float,
    ) -> bool:
        """
        Send alert for unhealthy consumer status.

        Args:
            health_status: Current health status
            error_rate: Current error rate percentage
            uptime_seconds: Consumer uptime in seconds

        Returns:
            True if alert sent successfully
        """
        title = "Kafka Consumer Unhealthy"
        message = f"Kafka consumer health status is `{health_status}`"

        fields = {
            "Status": health_status,
            "Error Rate": f"{error_rate:.2f}%",
            "Uptime": f"{uptime_seconds / 3600:.2f} hours",
        }

        severity = AlertSeverity.ERROR
        if health_status == "unhealthy":
            severity = AlertSeverity.CRITICAL

        return await self.send_alert(
            title=title,
            message=message,
            severity=severity,
            fields=fields,
            dedupe_key="consumer_unhealthy",
        )

    def get_metrics(self) -> Dict[str, int]:
        """
        Get alerting metrics.

        Returns:
            Dictionary with metrics:
            - alerts_sent: Total alerts sent successfully
            - alerts_failed: Total alerts that failed to send
            - alerts_rate_limited: Total alerts skipped due to rate limiting
        """
        return dict(self.metrics)


# Singleton instance
_slack_alerting_service: Optional[SlackAlertingService] = None


def get_slack_alerting_service() -> SlackAlertingService:
    """
    Get singleton Slack alerting service instance.

    Returns:
        SlackAlertingService instance
    """
    global _slack_alerting_service

    if _slack_alerting_service is None:
        _slack_alerting_service = SlackAlertingService()

    return _slack_alerting_service
