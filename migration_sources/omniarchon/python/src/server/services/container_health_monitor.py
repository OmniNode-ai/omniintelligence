"""
Container Health Monitoring Service

Monitors Docker container health and sends Slack alerts when services fail.
Integrates with PipelineAlertingService for consistent alert management.

Features:
- Real-time container health monitoring via Docker SDK (with fallback)
- Error log pattern detection and alerting
- Slack notifications with container logs
- Cooldown to prevent alert spam
- Automatic recovery detection
- Health check status tracking
- Prometheus metrics
"""

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

try:
    from docker.errors import APIError, DockerException, NotFound

    import docker

    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False
    docker = None
    DockerException = Exception
    NotFound = Exception
    APIError = Exception
    logger = logging.getLogger(__name__)
    logger.warning("Docker SDK not available - will use subprocess fallback")

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from server.services.log_sanitizer import get_log_sanitizer
from server.services.pipeline_alerting_service import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
    PipelineAlertingService,
)

logger = logging.getLogger(__name__)


# Helper function to safely register metrics (idempotent)
def _get_or_create_metric(metric_class, name, description, labelnames=None, **kwargs):
    """
    Get an existing metric or create a new one if it doesn't exist.

    This prevents "Duplicated timeseries in CollectorRegistry" errors when
    modules are imported multiple times (e.g., in test suites).

    Args:
        metric_class: The Prometheus metric class (Gauge, Counter, Histogram)
        name: Metric name
        description: Metric description
        labelnames: List of label names (optional)
        **kwargs: Additional arguments passed to metric constructor

    Returns:
        The metric instance (existing or newly created)
    """
    try:
        # Try to create the metric
        if labelnames:
            return metric_class(name, description, labelnames, **kwargs)
        else:
            return metric_class(name, description, **kwargs)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            # Metric already registered, fetch it from registry
            for collector in REGISTRY._collector_to_names.keys():
                if hasattr(collector, "_name") and collector._name == name:
                    return collector
            # If we can't find it, re-raise
            raise
        else:
            raise


# Prometheus metrics for container health monitoring
# Using helper function to make registration idempotent
CONTAINER_HEALTH_STATUS = _get_or_create_metric(
    Gauge,
    "archon_container_health_status",
    "Container health status (1=healthy, 0=unhealthy, -1=starting, -2=no_healthcheck)",
    ["container_name"],
)

CONTAINER_HEALTH_CHECK_DURATION = _get_or_create_metric(
    Histogram,
    "archon_container_health_check_duration_seconds",
    "Duration of container health checks",
    ["container_name"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

CONTAINER_UNHEALTHY_COUNT = _get_or_create_metric(
    Gauge,
    "archon_container_unhealthy_count",
    "Number of unhealthy containers",
)

CONTAINER_ALERTS_TOTAL = _get_or_create_metric(
    Counter,
    "archon_container_alerts_total",
    "Total number of container health alerts sent",
    ["container_name", "alert_type", "severity"],
)

CONTAINER_ERROR_PATTERNS_DETECTED = _get_or_create_metric(
    Counter,
    "archon_container_error_patterns_total",
    "Total number of error patterns detected in logs",
    ["container_name", "severity", "pattern_type"],
)

CONTAINER_RECOVERY_TOTAL = _get_or_create_metric(
    Counter,
    "archon_container_recovery_total",
    "Total number of container recoveries",
    ["container_name"],
)


# Container name validation
CONTAINER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
# Docker naming conventions recommend max 128 chars
# (though Docker itself allows up to 255)
MAX_CONTAINER_NAME_LENGTH = 128


class InvalidContainerNameError(ValueError):
    """Raised when a container name fails validation"""

    pass


def validate_container_name(name: str) -> str:
    """
    Validate container name to prevent command injection.

    Security rules:
    - Only alphanumeric, underscore, hyphen, and dot allowed
    - Maximum length: 128 characters (Docker convention)
    - Cannot be empty

    Args:
        name: Container name to validate

    Returns:
        Validated container name (same as input if valid)

    Raises:
        InvalidContainerNameError: If container name is invalid

    Examples:
        >>> validate_container_name("archon-mcp")
        'archon-mcp'
        >>> validate_container_name("archon_server.1")
        'archon_server.1'
        >>> validate_container_name("evil; rm -rf /")  # doctest: +SKIP
        InvalidContainerNameError: Invalid container name
    """
    if not name:
        raise InvalidContainerNameError("Container name cannot be empty")

    if len(name) > MAX_CONTAINER_NAME_LENGTH:
        raise InvalidContainerNameError(
            f"Container name too long (max {MAX_CONTAINER_NAME_LENGTH} chars): {len(name)}"
        )

    if not CONTAINER_NAME_PATTERN.match(name):
        logger.warning(
            f"Rejected invalid container name: {name!r} "
            "(contains invalid characters)"
        )
        raise InvalidContainerNameError(
            f"Invalid container name: {name!r}. "
            "Only alphanumeric, underscore, hyphen, and dot allowed."
        )

    return name


# Error patterns to detect in container logs
ERROR_PATTERNS = [
    (r"ERROR", AlertSeverity.WARNING),
    (r"CRITICAL", AlertSeverity.CRITICAL),
    (r"FATAL", AlertSeverity.CRITICAL),
    (r"Exception", AlertSeverity.WARNING),
    (r"Traceback \(most recent call last\)", AlertSeverity.WARNING),
    (r"ServiceUnavailable", AlertSeverity.CRITICAL),
    (r"ConnectionError", AlertSeverity.CRITICAL),
    (r"TimeoutError", AlertSeverity.WARNING),
    (r"Cannot resolve address", AlertSeverity.CRITICAL),
    (r"Connection refused", AlertSeverity.CRITICAL),
    (r"Failed to connect", AlertSeverity.CRITICAL),
]


class ContainerHealthStatus(Enum):
    """Container health status from Docker"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    NONE = "none"  # No health check configured


@dataclass
class ContainerHealth:
    """Container health information"""

    name: str
    status: ContainerHealthStatus
    timestamp: datetime
    logs: Optional[str] = None
    exit_code: Optional[int] = None


class ContainerHealthMonitor:
    """
    Monitors Docker container health and sends alerts via Slack.

    Uses Docker Python SDK for better performance and type safety, with
    subprocess fallback if SDK is unavailable.

    Checks container health every ALERT_CHECK_INTERVAL_SECONDS and sends
    Slack notifications when containers become unhealthy. Includes container
    logs in alerts for faster debugging.
    """

    def __init__(self):
        self.check_interval = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "60"))
        self.cooldown_seconds = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
        self.enable_slack = os.getenv("ENABLE_SLACK_ALERTS", "true").lower() == "true"
        self.enable_email = os.getenv("ENABLE_EMAIL_ALERTS", "false").lower() == "true"

        # Initialize Docker client if SDK is available
        self.docker_client: Optional[docker.DockerClient] = None
        self.use_docker_sdk = DOCKER_SDK_AVAILABLE

        if DOCKER_SDK_AVAILABLE:
            try:
                self.docker_client = docker.from_env(timeout=10)
                # Test connection
                self.docker_client.ping()
                logger.info("Docker SDK initialized successfully")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Docker SDK: {e}. Falling back to subprocess."
                )
                self.docker_client = None
                self.use_docker_sdk = False
        else:
            logger.info("Docker SDK not available - using subprocess fallback")
            self.use_docker_sdk = False

        # Error monitoring configuration (must be before _register_alert_rules)
        self.enable_error_monitoring = (
            os.getenv("ENABLE_ERROR_MONITORING", "true").lower() == "true"
        )
        self.error_log_window = int(
            os.getenv("ERROR_LOG_WINDOW_SECONDS", "300")  # Check last 5 minutes
        )
        self.error_cooldown_seconds = int(
            os.getenv("ERROR_COOLDOWN_SECONDS", "900")
        )  # 15 minutes

        # Initialize alerting service
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.alerting_service = PipelineAlertingService(
            config={
                "notifications": {
                    "slack": {"webhook_url": slack_webhook} if slack_webhook else {},
                    "email": (
                        {
                            "smtp_server": os.getenv("ALERT_EMAIL_SMTP_SERVER", ""),
                            "smtp_port": int(os.getenv("ALERT_EMAIL_SMTP_PORT", "587")),
                            "from": os.getenv("ALERT_EMAIL_FROM", ""),
                            "to": os.getenv("ALERT_EMAIL_TO", "").split(","),
                            "username": os.getenv("ALERT_EMAIL_USERNAME", ""),
                            "password": os.getenv("ALERT_EMAIL_PASSWORD", ""),
                        }
                        if self.enable_email
                        else {}
                    ),
                }
            }
        )

        # Register container health alert rules
        self._register_alert_rules()

        # Track last alert times for cooldown
        self.last_alert_times: dict[str, datetime] = {}

        # Track known unhealthy containers to detect recovery
        self.unhealthy_containers: set[str] = set()

        # Track recent errors to prevent spam (hash of error -> last alert time)
        self.recent_errors: dict[str, datetime] = {}

        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None

        # Initialize log sanitizer
        self.log_sanitizer = get_log_sanitizer()

    def _register_alert_rules(self):
        """Register alert rules for container health monitoring"""
        # Critical: Container unhealthy
        self.alerting_service.add_alert_rule(
            AlertRule(
                rule_id="container_unhealthy",
                name="Container Unhealthy",
                description="Docker container failed health check",
                metric_name="container_health",
                comparison="lt",
                threshold_value=1.0,
                time_window_seconds=0,  # Immediate alert
                severity=AlertSeverity.CRITICAL,
                notification_channels=[
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ]
                + ([NotificationChannel.EMAIL] if self.enable_email else []),
                cooldown_seconds=self.cooldown_seconds,
            )
        )

        # Info: Container recovered
        self.alerting_service.add_alert_rule(
            AlertRule(
                rule_id="container_recovered",
                name="Container Recovered",
                description="Docker container health check passed after failure",
                metric_name="container_health",
                comparison="gt",
                threshold_value=0.0,
                time_window_seconds=0,
                severity=AlertSeverity.INFO,
                notification_channels=[
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=self.cooldown_seconds,
            )
        )

        # Warning: Container errors detected
        self.alerting_service.add_alert_rule(
            AlertRule(
                rule_id="container_errors_warning",
                name="Container Errors Detected",
                description="Warning-level errors detected in container logs",
                metric_name="container_errors",
                comparison="gt",
                threshold_value=0.0,
                time_window_seconds=0,
                severity=AlertSeverity.WARNING,
                notification_channels=[
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ],
                cooldown_seconds=self.error_cooldown_seconds,
            )
        )

        # Critical: Container critical errors
        self.alerting_service.add_alert_rule(
            AlertRule(
                rule_id="container_errors_critical",
                name="Container Critical Errors",
                description="Critical errors detected in container logs",
                metric_name="container_errors",
                comparison="gt",
                threshold_value=0.0,
                time_window_seconds=0,
                severity=AlertSeverity.CRITICAL,
                notification_channels=[
                    NotificationChannel.SLACK,
                    NotificationChannel.LOG,
                ]
                + ([NotificationChannel.EMAIL] if self.enable_email else []),
                cooldown_seconds=self.error_cooldown_seconds,
            )
        )

    def _get_container_health_sdk(
        self, container_name: str
    ) -> Optional[ContainerHealth]:
        """
        Get container health using Docker SDK.

        Args:
            container_name: Name of the Docker container

        Returns:
            ContainerHealth object or None if container not found
        """
        if not self.docker_client:
            return None

        try:
            # Get container
            container = self.docker_client.containers.get(container_name)

            # Get health status from container attributes
            health_status = (
                container.attrs.get("State", {}).get("Health", {}).get("Status", "")
            )

            # Map Docker status to our enum
            status_map = {
                "healthy": ContainerHealthStatus.HEALTHY,
                "unhealthy": ContainerHealthStatus.UNHEALTHY,
                "starting": ContainerHealthStatus.STARTING,
                "": ContainerHealthStatus.NONE,  # No health check
            }

            status = status_map.get(health_status.lower(), ContainerHealthStatus.NONE)

            # Get container logs if unhealthy
            logs = None
            if status == ContainerHealthStatus.UNHEALTHY:
                try:
                    logs_bytes = container.logs(tail=50, stdout=True, stderr=True)
                    logs = logs_bytes.decode("utf-8", errors="replace")
                except Exception as e:
                    logger.warning(
                        f"Failed to get logs for {container_name} via SDK: {e}"
                    )

            return ContainerHealth(
                name=container_name,
                status=status,
                timestamp=datetime.now(),
                logs=logs,
            )

        except NotFound:
            logger.warning(f"Container {container_name} not found or not running")
            return None
        except (DockerException, APIError) as e:
            logger.error(f"Docker SDK error getting health for {container_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting health for {container_name}: {e}")
            return None

    def _get_container_health_subprocess(
        self, container_name: str
    ) -> Optional[ContainerHealth]:
        """
        Get container health using subprocess (fallback).

        Args:
            container_name: Name of the Docker container

        Returns:
            ContainerHealth object or None if container not found
        """
        import subprocess

        try:
            # Get container health status
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning(f"Container {container_name} not found or not running")
                return None

            status_str = result.stdout.strip()

            # Map Docker status to our enum
            status_map = {
                "healthy": ContainerHealthStatus.HEALTHY,
                "unhealthy": ContainerHealthStatus.UNHEALTHY,
                "starting": ContainerHealthStatus.STARTING,
                "": ContainerHealthStatus.NONE,  # No health check
            }

            status = status_map.get(status_str.lower(), ContainerHealthStatus.NONE)

            # Get container logs if unhealthy
            logs = None
            if status == ContainerHealthStatus.UNHEALTHY:
                logs_result = subprocess.run(
                    ["docker", "logs", "--tail", "50", container_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if logs_result.returncode == 0:
                    logs = logs_result.stdout + logs_result.stderr

            return ContainerHealth(
                name=container_name,
                status=status,
                timestamp=datetime.now(),
                logs=logs,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout getting health for {container_name}")
            return None
        except Exception as e:
            logger.error(f"Error getting health for {container_name}: {e}")
            return None

    def get_container_health(self, container_name: str) -> Optional[ContainerHealth]:
        """
        Get health status for a specific container.

        Uses Docker SDK if available, falls back to subprocess.

        Args:
            container_name: Name of the Docker container

        Returns:
            ContainerHealth object or None if container not found

        Raises:
            InvalidContainerNameError: If container name is invalid
        """
        # Validate container name to prevent command injection
        validate_container_name(container_name)

        # Use Docker SDK if available, otherwise subprocess
        if self.use_docker_sdk and self.docker_client:
            return self._get_container_health_sdk(container_name)
        else:
            return self._get_container_health_subprocess(container_name)

    def _get_all_containers_sdk(self) -> list[str]:
        """
        Get all container names using Docker SDK.

        Returns:
            List of container names
        """
        if not self.docker_client:
            return []

        try:
            containers = self.docker_client.containers.list(filters={"name": "archon-"})
            return [c.name for c in containers]
        except (DockerException, APIError) as e:
            logger.error(f"Docker SDK error listing containers: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing containers: {e}")
            return []

    def _get_all_containers_subprocess(self) -> list[str]:
        """
        Get all container names using subprocess (fallback).

        Returns:
            List of container names
        """
        import subprocess

        try:
            # Get all running containers with archon prefix
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=archon-",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.error("Failed to list Docker containers")
                return []

            container_names = [
                name.strip() for name in result.stdout.split("\n") if name.strip()
            ]

            return container_names

        except Exception as e:
            logger.error(f"Error getting all containers: {e}")
            return []

    def get_all_containers_health(self) -> list[ContainerHealth]:
        """
        Get health status for all running Archon containers.

        Uses Docker SDK if available, falls back to subprocess.

        Returns:
            List of ContainerHealth objects
        """
        # Get container names using appropriate method
        if self.use_docker_sdk and self.docker_client:
            container_names = self._get_all_containers_sdk()
        else:
            container_names = self._get_all_containers_subprocess()

        health_statuses = []
        for name in container_names:
            # Validate container name before use
            try:
                validate_container_name(name)
                health = self.get_container_health(name)
                if health:
                    health_statuses.append(health)
            except InvalidContainerNameError as e:
                logger.warning(f"Skipping invalid container name from docker ps: {e}")
                continue

        return health_statuses

    def _get_container_logs_sdk(
        self, container_name: str, since_seconds: int = 300
    ) -> Optional[str]:
        """
        Get container logs using Docker SDK.

        Args:
            container_name: Name of the Docker container
            since_seconds: Get logs from last N seconds

        Returns:
            Container logs as string, or None if error
        """
        if not self.docker_client:
            return None

        try:
            container = self.docker_client.containers.get(container_name)

            # Calculate since timestamp
            since = datetime.now() - timedelta(seconds=since_seconds)

            # Get logs
            logs_bytes = container.logs(since=since, tail=100, stdout=True, stderr=True)

            return logs_bytes.decode("utf-8", errors="replace")

        except NotFound:
            logger.warning(f"Container {container_name} not found")
            return None
        except (DockerException, APIError) as e:
            logger.error(f"Docker SDK error getting logs for {container_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting logs for {container_name}: {e}")
            return None

    def _get_container_logs_subprocess(
        self, container_name: str, since_seconds: int = 300
    ) -> Optional[str]:
        """
        Get container logs using subprocess (fallback).

        Args:
            container_name: Name of the Docker container
            since_seconds: Get logs from last N seconds

        Returns:
            Container logs as string, or None if error
        """
        import subprocess

        try:
            result = subprocess.run(
                [
                    "docker",
                    "logs",
                    "--since",
                    f"{since_seconds}s",
                    "--tail",
                    "100",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to get logs for {container_name}")
                return None

            raw_logs = result.stdout + result.stderr
            # Sanitize logs before returning
            return self.log_sanitizer.sanitize(raw_logs)

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout getting logs for {container_name}")
            return None
        except Exception as e:
            logger.error(f"Error getting logs for {container_name}: {e}")
            return None

    def get_container_logs(
        self, container_name: str, since_seconds: int = 300
    ) -> Optional[str]:
        """
        Get recent logs for a container.

        Uses Docker SDK if available, falls back to subprocess.

        Args:
            container_name: Name of the Docker container
            since_seconds: Get logs from last N seconds

        Returns:
            Container logs as string, or None if error

        Raises:
            InvalidContainerNameError: If container name is invalid
        """
        # Validate container name to prevent command injection
        validate_container_name(container_name)

        # Use Docker SDK if available, otherwise subprocess
        if self.use_docker_sdk and self.docker_client:
            return self._get_container_logs_sdk(container_name, since_seconds)
        else:
            return self._get_container_logs_subprocess(container_name, since_seconds)

    def detect_errors_in_logs(
        self, logs: str, container_name: str
    ) -> list[tuple[str, AlertSeverity, str]]:
        """
        Detect errors in container logs using pattern matching.

        Args:
            logs: Container log content
            container_name: Name of the container

        Returns:
            List of (error_line, severity, pattern) tuples for detected errors
        """
        if not logs:
            return []

        detected_errors = []
        lines = logs.split("\n")

        for line in lines:
            for pattern, severity in ERROR_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Sanitize the error line before hashing/storing
                    sanitized_line = self.log_sanitizer.sanitize(line.strip())

                    # Hash the error line for deduplication
                    error_hash = hashlib.md5(
                        f"{container_name}:{sanitized_line}".encode()
                    ).hexdigest()

                    # Check if we've alerted on this error recently
                    now = datetime.now()
                    last_alert = self.recent_errors.get(error_hash)

                    if (
                        last_alert
                        and (now - last_alert).total_seconds()
                        < self.error_cooldown_seconds
                    ):
                        continue  # Skip this error (cooldown active)

                    detected_errors.append((sanitized_line, severity, pattern))
                    self.recent_errors[error_hash] = now
                    break  # Only match first pattern per line

        return detected_errors

    async def _send_error_alert(
        self,
        container_name: str,
        errors: list[tuple[str, AlertSeverity, str]],
    ):
        """
        Send alert for detected errors in container logs.

        Args:
            container_name: Name of the container with errors
            errors: List of (error_line, severity, pattern) tuples
        """
        if not errors:
            return

        now = datetime.now()

        # Group errors by severity
        critical_errors = [e for e in errors if e[1] == AlertSeverity.CRITICAL]
        warning_errors = [e for e in errors if e[1] == AlertSeverity.WARNING]

        # Send critical errors first
        if critical_errors:
            # Format error lines for display
            error_lines = "\n".join(
                [f"• {e[0]}" for e in critical_errors[:5]]
            )  # Limit to 5 lines
            if len(critical_errors) > 5:
                error_lines += f"\n... and {len(critical_errors) - 5} more"

            alert = Alert(
                alert_id=f"container_errors_critical_{container_name}_{int(now.timestamp())}",
                rule_id="container_errors_critical",
                name=f"Critical Errors: {container_name}",
                description=f"Container {container_name} has critical errors\n\n"
                f"**Detected Errors ({len(critical_errors)}):**\n```\n{error_lines}\n```",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                metric_name="container_errors",
                current_value=float(len(critical_errors)),
                threshold_value=0.0,
                triggered_at=now,
                metadata={
                    "container_name": container_name,
                    "error_count": len(critical_errors),
                    "error_type": "critical",
                },
            )

            rule = self.alerting_service.alert_rules.get(alert.rule_id)
            if rule:
                await self.alerting_service._send_notifications(alert, rule)
                logger.warning(
                    f"Sent critical error alert for {container_name} "
                    f"({len(critical_errors)} errors)"
                )

        # Send warning errors
        elif warning_errors:
            error_lines = "\n".join([f"• {e[0]}" for e in warning_errors[:5]])
            if len(warning_errors) > 5:
                error_lines += f"\n... and {len(warning_errors) - 5} more"

            alert = Alert(
                alert_id=f"container_errors_warning_{container_name}_{int(now.timestamp())}",
                rule_id="container_errors_warning",
                name=f"Errors Detected: {container_name}",
                description=f"Container {container_name} has warnings/errors\n\n"
                f"**Detected Errors ({len(warning_errors)}):**\n```\n{error_lines}\n```",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                metric_name="container_errors",
                current_value=float(len(warning_errors)),
                threshold_value=0.0,
                triggered_at=now,
                metadata={
                    "container_name": container_name,
                    "error_count": len(warning_errors),
                    "error_type": "warning",
                },
            )

            rule = self.alerting_service.alert_rules.get(alert.rule_id)
            if rule:
                await self.alerting_service._send_notifications(alert, rule)
                logger.info(
                    f"Sent warning error alert for {container_name} "
                    f"({len(warning_errors)} errors)"
                )

    async def _send_alert(self, container: ContainerHealth, is_recovery: bool = False):
        """
        Send alert via PipelineAlertingService.

        Args:
            container: Container health information
            is_recovery: True if this is a recovery alert
        """
        # Check cooldown
        now = datetime.now()
        last_alert = self.last_alert_times.get(container.name)
        if last_alert and (now - last_alert).total_seconds() < self.cooldown_seconds:
            logger.debug(f"Skipping alert for {container.name} (cooldown active)")
            return

        # Create alert
        if is_recovery:
            alert = Alert(
                alert_id=f"container_recovered_{container.name}_{int(now.timestamp())}",
                rule_id="container_recovered",
                name=f"Container Recovered: {container.name}",
                description=f"Container {container.name} is now healthy",
                severity=AlertSeverity.INFO,
                status=AlertStatus.ACTIVE,
                metric_name="container_health",
                current_value=1.0,
                threshold_value=0.0,
                triggered_at=now,
                metadata={
                    "container_name": container.name,
                    "status": container.status.value,
                },
            )
        else:
            # Include logs in alert description
            log_snippet = ""
            if container.logs:
                # Get last 10 lines of logs
                log_lines = container.logs.strip().split("\n")
                log_snippet = "\n".join(log_lines[-10:])

            alert = Alert(
                alert_id=f"container_unhealthy_{container.name}_{int(now.timestamp())}",
                rule_id="container_unhealthy",
                name=f"Container Unhealthy: {container.name}",
                description=(
                    f"Container {container.name} failed health check\n\n"
                    f"**Recent Logs:**\n```\n{log_snippet}\n```"
                    if log_snippet
                    else f"Container {container.name} failed health check"
                ),
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                metric_name="container_health",
                current_value=0.0,
                threshold_value=1.0,
                triggered_at=now,
                metadata={
                    "container_name": container.name,
                    "status": container.status.value,
                    "has_logs": bool(container.logs),
                },
            )

        # Get alert rule
        rule = self.alerting_service.alert_rules.get(alert.rule_id)
        if not rule:
            logger.error(f"Alert rule {alert.rule_id} not found")
            return

        # Send notifications
        await self.alerting_service._send_notifications(alert, rule)

        # Update last alert time
        self.last_alert_times[container.name] = now

        logger.info(
            f"Sent {'recovery' if is_recovery else 'unhealthy'} alert for {container.name}"
        )

    async def check_health_once(self):
        """
        Check container health once and send alerts if needed.
        """
        containers = self.get_all_containers_health()

        for container in containers:
            # Skip containers without health checks
            if container.status == ContainerHealthStatus.NONE:
                continue

            # Skip containers that are still starting
            if container.status == ContainerHealthStatus.STARTING:
                logger.debug(f"Container {container.name} is starting...")
                continue

            # Check if container is unhealthy
            if container.status == ContainerHealthStatus.UNHEALTHY:
                if container.name not in self.unhealthy_containers:
                    # New unhealthy container
                    logger.warning(f"Container {container.name} is unhealthy")
                    await self._send_alert(container, is_recovery=False)
                    self.unhealthy_containers.add(container.name)
            else:
                # Container is healthy
                if container.name in self.unhealthy_containers:
                    # Container recovered
                    logger.info(f"Container {container.name} recovered")
                    await self._send_alert(container, is_recovery=True)
                    self.unhealthy_containers.remove(container.name)

            # Check for errors in logs (if error monitoring enabled)
            if self.enable_error_monitoring:
                logs = self.get_container_logs(
                    container.name, since_seconds=self.error_log_window
                )
                if logs:
                    errors = self.detect_errors_in_logs(logs, container.name)
                    if errors:
                        logger.debug(
                            f"Detected {len(errors)} errors in {container.name} logs"
                        )
                        await self._send_error_alert(container.name, errors)

    async def start_monitoring(self):
        """
        Start continuous health monitoring.
        """
        if not self.enable_slack:
            logger.warning("Slack alerts disabled (ENABLE_SLACK_ALERTS=false)")
            return

        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.warning(
                "Slack webhook URL not configured (SLACK_WEBHOOK_URL not set)"
            )
            return

        logger.info(
            f"Starting container health monitoring (interval: {self.check_interval}s, "
            f"using {'Docker SDK' if self.use_docker_sdk else 'subprocess fallback'})"
        )

        while True:
            try:
                await self.check_health_once()
            except Exception as e:
                logger.error(f"Error during health check: {e}")

            await asyncio.sleep(self.check_interval)

    async def stop_monitoring(self):
        """
        Stop continuous health monitoring.
        """
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped container health monitoring")

        # Close Docker client if it exists
        if self.docker_client:
            try:
                self.docker_client.close()
                logger.info("Docker client closed")
            except Exception as e:
                logger.warning(f"Error closing Docker client: {e}")


# Global monitor instance
_monitor: Optional[ContainerHealthMonitor] = None


def get_health_monitor() -> ContainerHealthMonitor:
    """Get or create global health monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = ContainerHealthMonitor()
    return _monitor


async def start_health_monitoring():
    """Start health monitoring (call from application startup)"""
    monitor = get_health_monitor()
    await monitor.start_monitoring()


async def stop_health_monitoring():
    """Stop health monitoring (call from application shutdown)"""
    monitor = get_health_monitor()
    await monitor.stop_monitoring()
