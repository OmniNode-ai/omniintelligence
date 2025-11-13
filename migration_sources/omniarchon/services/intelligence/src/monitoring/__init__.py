"""
Monitoring and Alerting Module

Provides Slack alerting and monitoring capabilities for the Intelligence service.
"""

from monitoring.slack_alerting import (
    AlertSeverity,
    SlackAlertingService,
    get_slack_alerting_service,
)

__all__ = [
    "SlackAlertingService",
    "AlertSeverity",
    "get_slack_alerting_service",
]
