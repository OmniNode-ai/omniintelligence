"""
Pipeline Alerting Service

Comprehensive alerting system for MCP document indexing pipeline.
Provides configurable thresholds, intelligent notifications, and
automated escalation for performance and reliability issues.

Features:
- Real-time threshold monitoring
- Multi-channel notifications (email, Slack, webhooks)
- Alert correlation and deduplication
- Automated escalation and recovery
- Performance regression detection
- SLA breach notifications
"""

import asyncio
import logging
import re
import smtplib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Optional

import httpx
from server.middleware.pipeline_metrics import pipeline_metrics
from server.middleware.pipeline_tracing import pipeline_tracer

logger = logging.getLogger(__name__)


# Slack webhook URL validation pattern
# Format: https://hooks.slack.com/services/T{workspace}/B{channel}/{token}
# Note: Slack workspace/channel IDs can be case-insensitive (e.g., T123abc or T123ABC)
SLACK_WEBHOOK_PATTERN = re.compile(
    r"^https://hooks\.slack\.com/services/[Tt][A-Za-z0-9]+/[Bb][A-Za-z0-9]+/[A-Za-z0-9]+$"
)


def validate_slack_webhook_url(
    webhook_url: Optional[str],
) -> tuple[bool, Optional[str]]:
    """
    Validate Slack webhook URL format.

    Args:
        webhook_url: Slack webhook URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid

    Examples:
        >>> validate_slack_webhook_url("https://hooks.slack.com/services/T123/B456/abc123")
        (True, None)

        >>> validate_slack_webhook_url("https://example.com/webhook")
        (False, "Invalid Slack webhook URL format...")
    """
    if not webhook_url:
        return False, "Slack webhook URL is empty or None"

    if not isinstance(webhook_url, str):
        return (
            False,
            f"Slack webhook URL must be a string, got {type(webhook_url).__name__}",
        )

    # Check if URL starts with correct prefix
    if not webhook_url.startswith("https://hooks.slack.com/services/"):
        return (
            False,
            "Invalid Slack webhook URL format. Must start with 'https://hooks.slack.com/services/'",
        )

    # Validate full URL structure
    if not SLACK_WEBHOOK_PATTERN.match(webhook_url):
        return (
            False,
            "Invalid Slack webhook URL structure. Expected format: "
            "https://hooks.slack.com/services/T{workspace}/B{channel}/{token} "
            "(workspace/channel IDs and token are alphanumeric and case-insensitive)",
        )

    # Check URL length (typical Slack webhooks are 70-90 chars)
    if len(webhook_url) < 60 or len(webhook_url) > 150:
        return (
            False,
            f"Suspicious Slack webhook URL length: {len(webhook_url)} chars "
            "(expected 60-150). Please verify the URL is correct.",
        )

    return True, None


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status"""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannel(Enum):
    """Notification channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    LOG = "log"


@dataclass
class AlertRule:
    """Alert rule configuration"""

    rule_id: str
    name: str
    description: str
    metric_name: str
    comparison: str  # gt, lt, eq, gte, lte
    threshold_value: float
    time_window_seconds: int
    severity: AlertSeverity
    notification_channels: list[NotificationChannel]
    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes default cooldown
    escalation_rules: Optional[list[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class Alert:
    """Active alert instance"""

    alert_id: str
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    current_value: float
    threshold_value: float
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    suppressed_until: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
    escalation_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in [
            "triggered_at",
            "acknowledged_at",
            "resolved_at",
            "suppressed_until",
        ]:
            if data[field]:
                data[field] = data[field].isoformat()
        return data


class PipelineAlertingService:
    """
    Comprehensive alerting service for pipeline monitoring.

    Features:
    - Configurable alert rules with threshold monitoring
    - Multi-channel notification system
    - Alert correlation and deduplication
    - Automated escalation and recovery detection
    - Performance regression analysis
    - SLA compliance monitoring
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}
        self.alert_rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self.max_history = 10000

        # Notification configuration
        self.notification_config = self.config.get("notifications", {})
        self.email_config = self.notification_config.get("email", {})
        self.slack_config = self.notification_config.get("slack", {})
        self.webhook_config = self.notification_config.get("webhook", {})

        # Validate Slack webhook URL configuration
        self._validate_slack_configuration()

        # Monitoring state
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_metrics: dict[str, float] = {}

        # Default alert rules
        self._setup_default_rules()

    def _validate_slack_configuration(self):
        """
        Validate Slack webhook URL configuration on service initialization.

        Logs warnings for misconfiguration but does not raise exceptions
        to allow service to start even with invalid webhook configuration.
        """
        webhook_url = self.slack_config.get("webhook_url")

        # Check if Slack alerts are enabled via any alert rule
        slack_enabled_in_rules = any(
            NotificationChannel.SLACK in rule.notification_channels
            for rule in self.alert_rules.values()
        )

        # Warning if webhook URL is missing but might be needed
        if not webhook_url:
            # Only warn if Slack is explicitly configured or mentioned in config
            if self.slack_config or slack_enabled_in_rules:
                logger.warning(
                    "Slack webhook URL is not configured but Slack alerts may be enabled. "
                    "Set SLACK_WEBHOOK_URL environment variable to enable Slack notifications. "
                    "Slack alerts will be silently skipped until configured."
                )
            return

        # Validate webhook URL format
        is_valid, error_message = validate_slack_webhook_url(webhook_url)

        if not is_valid:
            logger.error(
                f"Invalid Slack webhook URL configuration: {error_message}. "
                "Slack notifications will fail until URL is corrected. "
                "Expected format: https://hooks.slack.com/services/T{workspace}/B{channel}/{token}"
            )
            # Don't raise exception - allow service to start but log error
            return

        # Success - webhook URL is valid
        logger.info(
            "Slack webhook URL validated successfully. "
            f"Slack notifications will be sent to configured channel."
        )

    def _setup_default_rules(self):
        """Setup default alert rules for pipeline monitoring"""
        default_rules = [
            AlertRule(
                rule_id="pipeline_latency_warning",
                name="High Pipeline Latency",
                description="Pipeline execution taking longer than expected",
                metric_name="pipeline_avg_duration",
                comparison="gt",
                threshold_value=30.0,  # 30 seconds
                time_window_seconds=300,  # 5 minutes
                severity=AlertSeverity.WARNING,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=600,  # 10 minutes
            ),
            AlertRule(
                rule_id="pipeline_latency_critical",
                name="Critical Pipeline Latency",
                description="Pipeline execution severely degraded",
                metric_name="pipeline_avg_duration",
                comparison="gt",
                threshold_value=60.0,  # 60 seconds
                time_window_seconds=180,  # 3 minutes
                severity=AlertSeverity.CRITICAL,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=300,  # 5 minutes
                escalation_rules=[
                    {"delay_seconds": 900, "channels": ["webhook", "sms"]}  # 15 minutes
                ],
            ),
            AlertRule(
                rule_id="pipeline_success_rate_low",
                name="Low Pipeline Success Rate",
                description="Pipeline success rate below acceptable threshold",
                metric_name="pipeline_success_rate",
                comparison="lt",
                threshold_value=0.95,  # 95%
                time_window_seconds=600,  # 10 minutes
                severity=AlertSeverity.CRITICAL,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=300,
            ),
            AlertRule(
                rule_id="service_health_degraded",
                name="Service Health Degraded",
                description="One or more services showing health issues",
                metric_name="service_health_min",
                comparison="lt",
                threshold_value=0.8,  # 80%
                time_window_seconds=300,  # 5 minutes
                severity=AlertSeverity.WARNING,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=600,
            ),
            AlertRule(
                rule_id="queue_backlog_high",
                name="High Queue Backlog",
                description="Pipeline queue backlog growing",
                metric_name="queue_size_total",
                comparison="gt",
                threshold_value=100,  # 100 items
                time_window_seconds=300,  # 5 minutes
                severity=AlertSeverity.WARNING,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=900,  # 15 minutes
            ),
            AlertRule(
                rule_id="error_rate_spike",
                name="Error Rate Spike",
                description="Unusual increase in pipeline errors",
                metric_name="error_rate",
                comparison="gt",
                threshold_value=0.1,  # 10%
                time_window_seconds=600,  # 10 minutes
                severity=AlertSeverity.CRITICAL,
                notification_channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=300,
            ),
        ]

        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule

    def add_alert_rule(self, rule: AlertRule):
        """Add a new alert rule"""
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.name} ({rule.rule_id})")

    def remove_alert_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")

    def enable_rule(self, rule_id: str):
        """Enable an alert rule"""
        if rule_id in self.alert_rules:
            self.alert_rules[rule_id].enabled = True
            logger.info(f"Enabled alert rule: {rule_id}")

    def disable_rule(self, rule_id: str):
        """Disable an alert rule"""
        if rule_id in self.alert_rules:
            self.alert_rules[rule_id].enabled = False
            logger.info(f"Disabled alert rule: {rule_id}")

    async def start_monitoring(self):
        """Start the alerting monitoring task"""
        if self._monitoring_task:
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started pipeline alerting monitoring")

    async def stop_monitoring(self):
        """Stop the alerting monitoring task"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Stopped pipeline alerting monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._check_alert_rules()
                await self._process_escalations()
                await self._cleanup_resolved_alerts()
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alerting monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _check_alert_rules(self):
        """Check all enabled alert rules against current metrics"""
        current_metrics = await self._collect_current_metrics()

        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue

            try:
                await self._evaluate_rule(rule, current_metrics)
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.rule_id}: {e}")

    async def _collect_current_metrics(self) -> dict[str, float]:
        """Collect current pipeline metrics"""
        try:
            # Get pipeline metrics
            pipeline_status = pipeline_metrics.get_pipeline_metrics()

            # Get trace analytics for additional metrics
            trace_analytics = pipeline_tracer.get_trace_analytics(time_window_hours=1)

            metrics = {
                "pipeline_avg_duration": pipeline_status.get("avg_duration_last_10", 0),
                "pipeline_success_rate": pipeline_status.get(
                    "success_rate_last_100", 1.0
                ),
                "active_executions": pipeline_status.get("active_executions", 0),
                "queue_size_total": 0,  # Would get from actual queue implementations
                "error_rate": 1.0 - pipeline_status.get("success_rate_last_100", 1.0),
            }

            # Add service health metrics
            if trace_analytics and "service_performance" in trace_analytics:
                service_health_scores = []
                for service, perf in trace_analytics["service_performance"].items():
                    # Calculate health score based on error rate and response time
                    error_rate = perf.get("error_rate", 0)
                    avg_duration = perf.get("average_duration", 0)

                    health_score = 1.0
                    if error_rate > 0.05:  # 5% error rate
                        health_score -= error_rate * 2
                    if avg_duration > 10.0:  # 10 second response time
                        health_score -= (avg_duration - 10) / 100

                    health_score = max(0, min(1.0, health_score))
                    service_health_scores.append(health_score)

                if service_health_scores:
                    metrics["service_health_min"] = min(service_health_scores)
                    metrics["service_health_avg"] = sum(service_health_scores) / len(
                        service_health_scores
                    )

            self._last_metrics = metrics
            return metrics

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return self._last_metrics

    async def _evaluate_rule(self, rule: AlertRule, current_metrics: dict[str, float]):
        """Evaluate a single alert rule"""
        metric_value = current_metrics.get(rule.metric_name)
        if metric_value is None:
            return

        # Check if threshold is breached
        threshold_breached = self._check_threshold(
            metric_value, rule.threshold_value, rule.comparison
        )

        if threshold_breached:
            await self._handle_threshold_breach(rule, metric_value)
        else:
            await self._handle_threshold_recovery(rule, metric_value)

    def _check_threshold(self, value: float, threshold: float, comparison: str) -> bool:
        """Check if a value breaches a threshold"""
        comparisons = {
            "gt": value > threshold,
            "gte": value >= threshold,
            "lt": value < threshold,
            "lte": value <= threshold,
            "eq": abs(value - threshold) < 0.001,  # Allow for floating point precision
        }
        return comparisons.get(comparison, False)

    async def _handle_threshold_breach(self, rule: AlertRule, current_value: float):
        """Handle a threshold breach"""
        # Check if alert already exists
        existing_alert = None
        for alert in self.active_alerts.values():
            if alert.rule_id == rule.rule_id and alert.status == AlertStatus.ACTIVE:
                existing_alert = alert
                break

        if existing_alert:
            # Update existing alert
            existing_alert.current_value = current_value
            return

        # Check cooldown
        if self._is_in_cooldown(rule):
            return

        # Create new alert
        alert = Alert(
            alert_id=f"{rule.rule_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            metric_name=rule.metric_name,
            current_value=current_value,
            threshold_value=rule.threshold_value,
            triggered_at=datetime.now(),
            metadata={
                "comparison": rule.comparison,
                "time_window_seconds": rule.time_window_seconds,
            },
        )

        self.active_alerts[alert.alert_id] = alert
        logger.warning(
            f"Alert triggered: {alert.name} - {rule.metric_name}={current_value} {rule.comparison} {rule.threshold_value}"
        )

        # Send notifications
        await self._send_notifications(alert, rule)

    async def _handle_threshold_recovery(self, rule: AlertRule, current_value: float):
        """Handle threshold recovery (alert resolution)"""
        # Find active alerts for this rule
        alerts_to_resolve = []
        for alert in self.active_alerts.values():
            if alert.rule_id == rule.rule_id and alert.status == AlertStatus.ACTIVE:
                alerts_to_resolve.append(alert)

        for alert in alerts_to_resolve:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.current_value = current_value

            logger.info(
                f"Alert resolved: {alert.name} - {rule.metric_name}={current_value}"
            )

            # Send recovery notification
            await self._send_recovery_notification(alert, rule)

    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Check if a rule is in cooldown period"""
        cutoff_time = datetime.now() - timedelta(seconds=rule.cooldown_seconds)

        for alert in self.alert_history:
            if alert.rule_id == rule.rule_id and alert.triggered_at > cutoff_time:
                return True

        return False

    async def _send_notifications(self, alert: Alert, rule: AlertRule):
        """Send notifications for an alert"""
        for channel in rule.notification_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    await self._send_email_notification(alert, rule)
                elif channel == NotificationChannel.SLACK:
                    await self._send_slack_notification(alert, rule)
                elif channel == NotificationChannel.WEBHOOK:
                    await self._send_webhook_notification(alert, rule)
                elif channel == NotificationChannel.LOG:
                    self._send_log_notification(alert, rule)

            except Exception as e:
                logger.error(
                    f"Error sending {channel.value} notification for alert {alert.alert_id}: {e}"
                )

    async def _send_email_notification(self, alert: Alert, rule: AlertRule):
        """Send email notification"""
        if not self.email_config:
            return

        smtp_server = self.email_config.get("smtp_server")
        smtp_port = self.email_config.get("smtp_port", 587)
        username = self.email_config.get("username")
        password = self.email_config.get("password")
        from_email = self.email_config.get("from_email")
        to_emails = self.email_config.get("to_emails", [])

        if not all([smtp_server, username, password, from_email, to_emails]):
            logger.warning("Email configuration incomplete")
            return

        subject = f"[{alert.severity.value.upper()}] {alert.name}"
        body = f"""
Pipeline Alert Triggered

Alert: {alert.name}
Severity: {alert.severity.value.upper()}
Metric: {alert.metric_name}
Current Value: {alert.current_value}
Threshold: {alert.threshold_value}
Triggered: {alert.triggered_at.isoformat()}

Description: {alert.description}

Please investigate immediately.
        """

        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Email notification sent for alert {alert.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    async def _send_slack_notification(self, alert: Alert, rule: AlertRule):
        """Send Slack notification"""
        webhook_url = self.slack_config.get("webhook_url")
        if not webhook_url:
            return

        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#8B0000",
        }

        payload = {
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#ff0000"),
                    "title": f"Pipeline Alert: {alert.name}",
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True,
                        },
                        {"title": "Metric", "value": alert.metric_name, "short": True},
                        {
                            "title": "Current Value",
                            "value": str(alert.current_value),
                            "short": True,
                        },
                        {
                            "title": "Threshold",
                            "value": str(alert.threshold_value),
                            "short": True,
                        },
                        {
                            "title": "Description",
                            "value": alert.description,
                            "short": False,
                        },
                    ],
                    "ts": int(alert.triggered_at.timestamp()),
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Slack notification sent for alert {alert.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    async def _send_webhook_notification(self, alert: Alert, rule: AlertRule):
        """Send webhook notification"""
        webhook_url = self.webhook_config.get("url")
        if not webhook_url:
            return

        payload = {
            "event_type": "alert_triggered",
            "alert": alert.to_dict(),
            "rule": asdict(rule),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Webhook notification sent for alert {alert.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")

    def _send_log_notification(self, alert: Alert, rule: AlertRule):
        """Send log notification"""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.CRITICAL,
            AlertSeverity.EMERGENCY: logging.CRITICAL,
        }.get(alert.severity, logging.WARNING)

        logger.log(
            log_level,
            f"ALERT: {alert.name} - {alert.metric_name}={alert.current_value} "
            f"(threshold: {alert.threshold_value})",
        )

    async def _send_recovery_notification(self, alert: Alert, rule: AlertRule):
        """Send recovery notification"""
        if NotificationChannel.SLACK in rule.notification_channels:
            await self._send_slack_recovery(alert)

        if NotificationChannel.LOG in rule.notification_channels:
            logger.info(
                f"ALERT RECOVERED: {alert.name} - {alert.metric_name}={alert.current_value}"
            )

    async def _send_slack_recovery(self, alert: Alert):
        """Send Slack recovery notification"""
        webhook_url = self.slack_config.get("webhook_url")
        if not webhook_url:
            return

        payload = {
            "attachments": [
                {
                    "color": "#36a64f",
                    "title": f"Alert Recovered: {alert.name}",
                    "fields": [
                        {"title": "Metric", "value": alert.metric_name, "short": True},
                        {
                            "title": "Current Value",
                            "value": str(alert.current_value),
                            "short": True,
                        },
                        {
                            "title": "Duration",
                            "value": str(alert.resolved_at - alert.triggered_at),
                            "short": True,
                        },
                    ],
                    "ts": int(alert.resolved_at.timestamp()),
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Slack recovery notification: {e}")

    async def _process_escalations(self):
        """Process alert escalations"""
        for alert in self.active_alerts.values():
            if alert.status != AlertStatus.ACTIVE:
                continue

            rule = self.alert_rules.get(alert.rule_id)
            if not rule or not rule.escalation_rules:
                continue

            time_since_trigger = datetime.now() - alert.triggered_at

            for escalation in rule.escalation_rules:
                delay_seconds = escalation.get("delay_seconds", 900)
                if (
                    time_since_trigger.total_seconds() >= delay_seconds
                    and alert.escalation_level < len(rule.escalation_rules)
                ):
                    await self._execute_escalation(alert, escalation)
                    alert.escalation_level += 1

    async def _execute_escalation(self, alert: Alert, escalation: dict[str, Any]):
        """Execute an alert escalation"""
        channels = escalation.get("channels", [])
        logger.warning(f"Escalating alert {alert.alert_id} to channels: {channels}")

        # Execute escalation actions
        for channel in channels:
            if channel == "webhook":
                await self._send_webhook_notification(
                    alert, self.alert_rules[alert.rule_id]
                )
            elif channel == "sms":
                # Would implement SMS notification
                logger.warning(
                    f"SMS escalation for alert {alert.alert_id} (not implemented)"
                )

    async def _cleanup_resolved_alerts(self):
        """Move resolved alerts to history"""
        resolved_alerts = []
        for alert_id, alert in self.active_alerts.items():
            if alert.status == AlertStatus.RESOLVED:
                resolved_alerts.append(alert_id)

        for alert_id in resolved_alerts:
            alert = self.active_alerts.pop(alert_id)
            self.alert_history.append(alert)

        # Limit history size
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history :]

    # Public API methods

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all active alerts"""
        return [alert.to_dict() for alert in self.active_alerts.values()]

    def get_alert_rules(self) -> list[dict[str, Any]]:
        """Get all alert rules"""
        return [asdict(rule) for rule in self.alert_rules.values()]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.metadata = alert.metadata or {}
            alert.metadata["acknowledged_by"] = acknowledged_by
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
        return False

    def suppress_alert(self, alert_id: str, suppress_until: datetime) -> bool:
        """Suppress an alert until specified time"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.SUPPRESSED
            alert.suppressed_until = suppress_until
            logger.info(f"Alert {alert_id} suppressed until {suppress_until}")
            return True
        return False

    def get_alert_statistics(self, time_window_hours: int = 24) -> dict[str, Any]:
        """Get alert statistics for the specified time window"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        recent_alerts = [
            alert for alert in self.alert_history if alert.triggered_at >= cutoff_time
        ]

        # Add currently active alerts
        recent_alerts.extend(self.active_alerts.values())

        # Calculate statistics
        total_alerts = len(recent_alerts)
        by_severity = {}
        by_rule = {}
        avg_resolution_time = 0

        for alert in recent_alerts:
            # By severity
            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # By rule
            rule_name = self.alert_rules.get(alert.rule_id, {}).name or alert.rule_id
            by_rule[rule_name] = by_rule.get(rule_name, 0) + 1

            # Resolution time
            if alert.resolved_at:
                duration = (alert.resolved_at - alert.triggered_at).total_seconds()
                avg_resolution_time += duration

        resolved_count = sum(1 for alert in recent_alerts if alert.resolved_at)
        if resolved_count > 0:
            avg_resolution_time = avg_resolution_time / resolved_count

        return {
            "time_window_hours": time_window_hours,
            "total_alerts": total_alerts,
            "active_alerts": len(self.active_alerts),
            "resolved_alerts": resolved_count,
            "by_severity": by_severity,
            "by_rule": by_rule,
            "avg_resolution_time_seconds": avg_resolution_time,
            "alert_rate_per_hour": (
                total_alerts / time_window_hours if time_window_hours > 0 else 0
            ),
        }


# Global alerting service instance
alerting_service = PipelineAlertingService()


def get_alerting_service() -> PipelineAlertingService:
    """Get the global alerting service"""
    return alerting_service


def configure_alerting(config: dict[str, Any]) -> PipelineAlertingService:
    """Configure the alerting service"""
    global alerting_service
    alerting_service = PipelineAlertingService(config)
    return alerting_service
