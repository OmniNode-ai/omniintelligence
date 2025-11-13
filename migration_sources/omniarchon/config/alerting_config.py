"""
Alerting Configuration Module

Configuration for Slack alerting system with intelligent throttling,
rate limiting, and alert aggregation to prevent alert flooding.

Environment variables can override any default value.
All time values are in seconds unless otherwise specified.
"""

import os
import threading
from pathlib import Path
from typing import ClassVar, Dict, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_webhook_from_credentials() -> str:
    """
    Load Slack webhook URL from systemd credential directory.

    Returns:
        Webhook URL if found in credentials, empty string otherwise.

    Note:
        When systemd LoadCredential is used, the credential is available at:
        $CREDENTIALS_DIRECTORY/slack_webhook

        This provides secure credential management without exposing URLs
        in environment variables that are visible via /proc/<pid>/environ
    """
    credentials_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if not credentials_dir:
        return ""

    webhook_file = Path(credentials_dir) / "slack_webhook"
    if not webhook_file.exists():
        return ""

    try:
        with open(webhook_file, "r") as f:
            webhook_url = f.read().strip()
            if webhook_url:
                return webhook_url
    except Exception:
        # Silently fail if credential file can't be read
        pass

    return ""


class AlertThresholdConfig(BaseSettings):
    """Threshold configuration for triggering alerts."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_THRESHOLD_", env_file=".env", extra="ignore"
    )

    # Container health thresholds
    container_restart_count: int = Field(
        default=3,
        description="Number of restarts before alerting",
        ge=1,
        le=20,
    )

    # Resource usage thresholds
    cpu_percent_warning: float = Field(
        default=80.0,
        description="CPU usage percentage for warning alerts",
        ge=50.0,
        le=100.0,
    )

    cpu_percent_critical: float = Field(
        default=95.0,
        description="CPU usage percentage for critical alerts",
        ge=80.0,
        le=100.0,
    )

    memory_mb_warning: float = Field(
        default=3072.0,  # 3GB
        description="Memory usage (MB) for warning alerts",
        ge=512.0,
        le=16384.0,
    )

    memory_mb_critical: float = Field(
        default=3686.4,  # 3.6GB
        description="Memory usage (MB) for critical alerts",
        ge=1024.0,
        le=16384.0,
    )

    # Consumer lag thresholds
    consumer_lag_warning: int = Field(
        default=100,
        description="Consumer lag messages for warning",
        ge=10,
        le=10000,
    )

    consumer_lag_critical: int = Field(
        default=500,
        description="Consumer lag messages for critical alert",
        ge=50,
        le=10000,
    )

    # Error rate thresholds
    error_rate_window_seconds: int = Field(
        default=300,  # 5 minutes
        description="Time window for error rate calculation",
        ge=60,
        le=3600,
    )

    error_rate_warning: int = Field(
        default=10,
        description="Number of errors in window for warning",
        ge=5,
        le=1000,
    )

    error_rate_critical: int = Field(
        default=50,
        description="Number of errors in window for critical alert",
        ge=10,
        le=1000,
    )

    # Health check thresholds
    health_check_timeout_seconds: float = Field(
        default=10.0,
        description="Health check timeout before considering unhealthy",
        ge=1.0,
        le=60.0,
    )

    consecutive_health_failures: int = Field(
        default=3,
        description="Consecutive health check failures before alerting",
        ge=1,
        le=10,
    )


class AlertThrottlingConfig(BaseSettings):
    """Throttling configuration to prevent alert flooding."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_THROTTLE_", env_file=".env", extra="ignore"
    )

    # Rate limiting per service per error type
    rate_limit_window_seconds: int = Field(
        default=300,  # 5 minutes
        description="Time window for rate limiting alerts",
        ge=60,
        le=3600,
    )

    max_alerts_per_window: int = Field(
        default=1,
        description="Maximum alerts per window per service per error type",
        ge=1,
        le=10,
    )

    # Error aggregation
    error_aggregation_window_seconds: int = Field(
        default=300,  # 5 minutes
        description="Time window for aggregating similar errors",
        ge=60,
        le=3600,
    )

    min_errors_for_aggregation: int = Field(
        default=10,
        description="Minimum errors before sending aggregated alert",
        ge=2,
        le=1000,
    )

    # Escalation for repeated failures
    escalation_threshold: int = Field(
        default=3,
        description="Number of consecutive failures before escalation",
        ge=2,
        le=10,
    )

    escalation_multiplier: float = Field(
        default=2.0,
        description="Multiplier for escalation severity",
        ge=1.0,
        le=5.0,
    )

    # Cooldown periods
    recovery_cooldown_seconds: int = Field(
        default=300,  # 5 minutes
        description="Cooldown after recovery before new alerts",
        ge=60,
        le=3600,
    )

    # Deduplication
    deduplication_window_seconds: int = Field(
        default=60,
        description="Window for deduplicating identical alerts",
        ge=10,
        le=300,
    )


class AlertServiceConfig(BaseSettings):
    """Configuration for monitored services."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_SERVICE_", env_file=".env", extra="ignore"
    )

    # Services to monitor (container names)
    monitored_containers: List[str] = Field(
        default=[
            "archon-intelligence",
            "archon-bridge",
            "archon-search",
            "archon-langextract",
            "archon-kafka-consumer",
            "archon-intelligence-consumer-1",
            "archon-intelligence-consumer-2",
            "archon-intelligence-consumer-3",
            "archon-intelligence-consumer-4",
            "archon-qdrant",
            "archon-memgraph",
            "archon-valkey",
        ],
        description="List of container names to monitor",
    )

    # Critical services (failures trigger immediate alerts)
    critical_services: List[str] = Field(
        default=[
            "archon-intelligence",
            "archon-bridge",
            "archon-qdrant",
            "archon-memgraph",
        ],
        description="Critical services that trigger immediate alerts",
    )

    # Health check endpoints (service_name: endpoint)
    health_endpoints: Dict[str, str] = Field(
        default={
            "archon-intelligence": "http://localhost:8053/health",
            "archon-bridge": "http://localhost:8054/health",
            "archon-search": "http://localhost:8055/health",
            "archon-langextract": "http://localhost:8156/health",
            "archon-kafka-consumer": "http://localhost:8059/health",
        },
        description="Health check endpoints for services",
    )


class AlertNotificationConfig(BaseSettings):
    """Notification configuration for alerts."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_NOTIFICATION_", env_file=".env", extra="ignore"
    )

    # Slack webhook URL with systemd credential support
    # Priority order:
    # 1. Environment variable: ALERT_NOTIFICATION_SLACK_WEBHOOK_URL
    # 2. Systemd credential: $CREDENTIALS_DIRECTORY/slack_webhook
    # 3. Default: empty string
    slack_webhook_url: str = Field(
        default_factory=lambda: os.environ.get(
            "ALERT_NOTIFICATION_SLACK_WEBHOOK_URL", ""
        )
        or _load_webhook_from_credentials(),
        description="Slack webhook URL for sending alerts (supports systemd credentials)",
    )

    # Alert formatting
    include_metrics: bool = Field(
        default=True,
        description="Include detailed metrics in alerts",
    )

    include_recovery_alerts: bool = Field(
        default=True,
        description="Send alerts when services recover",
    )

    # Emoji configuration for alert severity
    emoji_critical: str = Field(default="🚨", description="Emoji for critical alerts")
    emoji_warning: str = Field(default="⚠️", description="Emoji for warning alerts")
    emoji_info: str = Field(default="ℹ️", description="Emoji for info alerts")
    emoji_recovery: str = Field(default="✅", description="Emoji for recovery alerts")

    # Alert message prefixes
    alert_prefix: str = Field(
        default="[Archon Alert]",
        description="Prefix for alert messages",
    )


class MonitoringConfig(BaseSettings):
    """Main monitoring loop configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MONITORING_", env_file=".env", extra="ignore"
    )

    # Monitoring intervals
    check_interval_seconds: int = Field(
        default=30,
        description="Interval between monitoring checks",
        ge=5,
        le=300,
    )

    health_check_interval_seconds: int = Field(
        default=60,
        description="Interval for health check tests",
        ge=10,
        le=300,
    )

    metrics_collection_interval_seconds: int = Field(
        default=120,
        description="Interval for collecting detailed metrics",
        ge=30,
        le=600,
    )

    # State persistence
    state_file_path: str = Field(
        default="/var/lib/archon/alerting_state.json",
        description="Path to state persistence file",
    )

    max_history_entries: int = Field(
        default=1000,
        description="Maximum alert history entries to keep",
        ge=100,
        le=10000,
    )

    # Daemon mode
    daemon_mode: bool = Field(
        default=False,
        description="Run as daemon (continuous monitoring)",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )


class AlertingConfig(BaseSettings):
    """Master alerting configuration aggregating all categories."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sub-configurations
    thresholds: AlertThresholdConfig = Field(default_factory=AlertThresholdConfig)
    throttling: AlertThrottlingConfig = Field(default_factory=AlertThrottlingConfig)
    services: AlertServiceConfig = Field(default_factory=AlertServiceConfig)
    notification: AlertNotificationConfig = Field(
        default_factory=AlertNotificationConfig
    )
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    # Thread-safe singleton lock
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @field_validator("notification")
    @classmethod
    def validate_slack_webhook(
        cls, v: AlertNotificationConfig
    ) -> AlertNotificationConfig:
        """Validate Slack webhook URL is configured."""
        if v.slack_webhook_url and not v.slack_webhook_url.startswith("https://"):
            raise ValueError("Slack webhook URL must start with https://")
        return v

    @classmethod
    def get_instance(cls) -> "AlertingConfig":
        """Get singleton instance of alerting configuration (thread-safe)."""
        # First check without lock (fast path)
        if not hasattr(cls, "_instance"):
            # Acquire lock for instance creation
            with cls._lock:
                # Double-check after acquiring lock
                if not hasattr(cls, "_instance"):
                    cls._instance = cls()
        return cls._instance


# Global singleton instance
alerting_config = AlertingConfig.get_instance()


# Export all for easy importing
__all__ = [
    "AlertingConfig",
    "AlertThresholdConfig",
    "AlertThrottlingConfig",
    "AlertServiceConfig",
    "AlertNotificationConfig",
    "MonitoringConfig",
    "alerting_config",
]
