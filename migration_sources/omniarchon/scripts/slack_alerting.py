#!/usr/bin/env python3
"""
ARCHON SLACK ALERTING SYSTEM
=============================

Comprehensive Slack alerting for Archon container infrastructure with
intelligent throttling to prevent alert flooding.

Features:
- Monitor all Archon containers (bridge, intelligence, search, consumers, etc.)
- Detect crashes, restarts, health failures, high error rates, consumer lag
- Intelligent throttling: aggregate similar errors, rate limit per service
- Escalation for repeated failures
- Recovery notifications
- Daemon mode for continuous monitoring

Usage:
    # One-shot check
    python scripts/slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK

    # Daemon mode (continuous monitoring)
    python scripts/slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK --daemon

    # Custom configuration
    export ALERT_THRESHOLD_CONSUMER_LAG_CRITICAL=1000
    export ALERT_THROTTLE_RATE_LIMIT_WINDOW_SECONDS=600
    python scripts/slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK --daemon
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, DefaultDict, Deque, Dict, List, Optional, Set

import httpx
from docker.errors import DockerException, NotFound

import docker

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.alerting_config import alerting_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    """Represents a single alert event."""

    timestamp: datetime
    service: str
    alert_type: str  # crash, restart, health_failure, high_errors, consumer_lag
    severity: str  # info, warning, critical
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    alert_id: Optional[str] = None  # For deduplication


@dataclass
class ServiceState:
    """Tracks state for a service to detect changes."""

    container_id: str = ""
    running: bool = False
    restart_count: int = 0
    last_restart_time: Optional[datetime] = None
    consecutive_health_failures: int = 0
    last_health_check: Optional[datetime] = None
    error_history: Deque[datetime] = field(default_factory=lambda: deque(maxlen=100))
    last_alert_time: Dict[str, datetime] = field(default_factory=dict)
    in_recovery: bool = False
    escalation_level: int = 0


class AlertThrottler:
    """Manages alert throttling, aggregation, and deduplication."""

    def __init__(self):
        self.config = alerting_config.throttling
        # Track alerts per service per type: service -> type -> list of timestamps
        self.alert_history: DefaultDict[str, DefaultDict[str, Deque[datetime]]] = (
            defaultdict(lambda: defaultdict(lambda: deque(maxlen=100)))
        )
        # Track error aggregation: service -> type -> count
        self.error_aggregation: DefaultDict[str, DefaultDict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        # Track last aggregation alert
        self.last_aggregation_alert: DefaultDict[str, Dict[str, datetime]] = (
            defaultdict(dict)
        )
        # Track recent alert IDs for deduplication
        self.recent_alert_ids: Deque[tuple[str, datetime]] = deque(maxlen=1000)

    def should_send_alert(self, event: AlertEvent) -> tuple[bool, Optional[str]]:
        """
        Determine if an alert should be sent based on throttling rules.

        Returns:
            tuple: (should_send, reason_if_suppressed)
        """
        now = datetime.now()
        service = event.service
        alert_type = event.alert_type

        # Check deduplication
        if event.alert_id:
            for alert_id, timestamp in self.recent_alert_ids:
                if alert_id == event.alert_id:
                    age = (now - timestamp).total_seconds()
                    if age < self.config.deduplication_window_seconds:
                        return False, f"Duplicate alert within {age:.0f}s"
            self.recent_alert_ids.append((event.alert_id, now))

        # Critical services bypass rate limiting
        if (
            event.severity == "critical"
            and service in alerting_config.services.critical_services
        ):
            return True, None

        # Check rate limiting
        alert_times = self.alert_history[service][alert_type]
        window_start = now - timedelta(seconds=self.config.rate_limit_window_seconds)

        # Remove old alerts outside window
        while alert_times and alert_times[0] < window_start:
            alert_times.popleft()

        # Check if we've exceeded rate limit
        if len(alert_times) >= self.config.max_alerts_per_window:
            oldest_alert = alert_times[0]
            wait_time = (
                oldest_alert
                + timedelta(seconds=self.config.rate_limit_window_seconds)
                - now
            ).total_seconds()
            return False, f"Rate limit exceeded, wait {wait_time:.0f}s"

        # Record this alert
        alert_times.append(now)

        return True, None

    def aggregate_errors(
        self, service: str, alert_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if errors should be aggregated and return aggregated message.

        Returns:
            Optional dict with aggregated alert info, or None if not ready
        """
        now = datetime.now()
        count = self.error_aggregation[service][alert_type]

        # Check if we have enough errors to aggregate
        if count < self.config.min_errors_for_aggregation:
            return None

        # Check if we've recently sent an aggregation alert
        last_alert = self.last_aggregation_alert[service].get(alert_type)
        if last_alert:
            time_since = (now - last_alert).total_seconds()
            if time_since < self.config.error_aggregation_window_seconds:
                return None

        # Reset counter and record alert time
        self.error_aggregation[service][alert_type] = 0
        self.last_aggregation_alert[service][alert_type] = now

        return {
            "count": count,
            "window_seconds": self.config.error_aggregation_window_seconds,
            "service": service,
            "type": alert_type,
        }

    def record_error(self, service: str, alert_type: str) -> None:
        """Record an error for aggregation."""
        self.error_aggregation[service][alert_type] += 1


class SlackAlerter:
    """Handles sending alerts to Slack with formatting."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.config = alerting_config.notification
        self.client = httpx.Client(timeout=10.0)

    def format_alert(self, event: AlertEvent) -> Dict[str, Any]:
        """Format alert event as Slack message."""
        # Determine emoji based on severity
        emoji_map = {
            "critical": self.config.emoji_critical,
            "warning": self.config.emoji_warning,
            "info": self.config.emoji_info,
        }
        emoji = emoji_map.get(event.severity, self.config.emoji_info)

        # Build message
        title = f"{emoji} {self.config.alert_prefix} {event.alert_type.replace('_', ' ').title()}"

        fields = [
            {"title": "Service", "value": event.service, "short": True},
            {"title": "Severity", "value": event.severity.upper(), "short": True},
            {
                "title": "Time",
                "value": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "short": True,
            },
        ]

        # Add metrics if configured
        if self.config.include_metrics and event.details:
            for key, value in event.details.items():
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                fields.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": value_str,
                        "short": True,
                    }
                )

        # Color based on severity
        color_map = {"critical": "danger", "warning": "warning", "info": "#36a64f"}
        color = color_map.get(event.severity, "#36a64f")

        return {
            "attachments": [
                {
                    "title": title,
                    "text": event.message,
                    "color": color,
                    "fields": fields,
                    "footer": "Archon Alerting System",
                    "ts": int(event.timestamp.timestamp()),
                }
            ]
        }

    def format_recovery_alert(
        self, service: str, recovery_type: str, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format recovery alert."""
        emoji = self.config.emoji_recovery
        title = f"{emoji} {self.config.alert_prefix} Service Recovered"

        fields = [
            {"title": "Service", "value": service, "short": True},
            {"title": "Recovery Type", "value": recovery_type, "short": True},
            {
                "title": "Time",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "short": True,
            },
        ]

        if details:
            for key, value in details.items():
                fields.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True,
                    }
                )

        return {
            "attachments": [
                {
                    "title": title,
                    "text": f"{service} has recovered from {recovery_type}",
                    "color": "good",
                    "fields": fields,
                    "footer": "Archon Alerting System",
                    "ts": int(datetime.now().timestamp()),
                }
            ]
        }

    def send_alert(self, payload: Dict[str, Any]) -> bool:
        """Send alert to Slack webhook."""
        try:
            response = self.client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.debug(f"Alert sent successfully: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def close(self):
        """Close HTTP client."""
        self.client.close()


class ArchonMonitor:
    """Main monitoring class for Archon services."""

    def __init__(self, webhook_url: str):
        self.docker_client = docker.from_env()
        self.alerter = SlackAlerter(webhook_url)
        self.throttler = AlertThrottler()
        self.config = alerting_config
        self.service_states: Dict[str, ServiceState] = {}
        self.running = False
        self.state_file = Path(self.config.monitoring.state_file_path)

        # Load previous state if exists
        self.load_state()

    def load_state(self):
        """Load previous monitoring state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    for service, state_data in data.get("service_states", {}).items():
                        # Reconstruct state (simplified, only essential fields)
                        self.service_states[service] = ServiceState(
                            container_id=state_data.get("container_id", ""),
                            running=state_data.get("running", False),
                            restart_count=state_data.get("restart_count", 0),
                        )
                logger.info(f"Loaded state from {self.state_file}")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def save_state(self):
        """Save current monitoring state to disk."""
        try:
            data = {
                "service_states": {
                    service: {
                        "container_id": state.container_id,
                        "running": state.running,
                        "restart_count": state.restart_count,
                    }
                    for service, state in self.service_states.items()
                },
                "timestamp": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def check_container_health(self, container_name: str) -> Optional[AlertEvent]:
        """Check container health and detect issues."""
        try:
            container = self.docker_client.containers.get(container_name)
        except NotFound:
            # Container doesn't exist
            if container_name in self.service_states:
                del self.service_states[container_name]
            logger.debug(f"Container {container_name} not found")
            return None
        except Exception as e:
            logger.error(f"Error checking container {container_name}: {e}")
            return None

        # Initialize state if new
        if container_name not in self.service_states:
            self.service_states[container_name] = ServiceState()

        state = self.service_states[container_name]
        now = datetime.now()

        # Check if container is running
        is_running = container.status == "running"
        container_id = container.id
        restart_count = int(container.attrs.get("RestartCount", 0))

        # Detect state changes
        events: List[AlertEvent] = []

        # Container crash detection
        if state.running and not is_running:
            events.append(
                AlertEvent(
                    timestamp=now,
                    service=container_name,
                    alert_type="crash",
                    severity="critical",
                    message=f"{container_name} has crashed (status: {container.status})",
                    details={
                        "status": container.status,
                        "container_id": container_id[:12],
                    },
                    alert_id=f"crash-{container_name}-{container_id[:12]}",
                )
            )

        # Container restart detection
        if restart_count > state.restart_count:
            restarts_since_last = restart_count - state.restart_count
            severity = (
                "critical"
                if restart_count >= self.config.thresholds.container_restart_count
                else "warning"
            )
            events.append(
                AlertEvent(
                    timestamp=now,
                    service=container_name,
                    alert_type="restart",
                    severity=severity,
                    message=f"{container_name} has restarted ({restarts_since_last} time(s))",
                    details={
                        "restart_count": restart_count,
                        "new_restarts": restarts_since_last,
                    },
                    alert_id=f"restart-{container_name}-{restart_count}",
                )
            )
            state.last_restart_time = now

        # Recovery detection
        if not state.running and is_running and state.in_recovery:
            if self.config.notification.include_recovery_alerts:
                recovery_payload = self.alerter.format_recovery_alert(
                    container_name,
                    "container_start",
                    {"restart_count": restart_count},
                )
                self.alerter.send_alert(recovery_payload)
            state.in_recovery = False
            state.consecutive_health_failures = 0
            state.escalation_level = 0

        # Update state
        state.running = is_running
        state.container_id = container_id
        state.restart_count = restart_count

        # Return first event if any
        return events[0] if events else None

    def check_resource_usage(self, container_name: str) -> Optional[AlertEvent]:
        """Check container resource usage."""
        try:
            container = self.docker_client.containers.get(container_name)
            if container.status != "running":
                return None

            stats = container.stats(stream=False)

            # CPU usage
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            num_cpus = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
            cpu_percent = (
                (cpu_delta / system_delta) * num_cpus * 100.0
                if system_delta > 0
                else 0.0
            )

            # Memory usage
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_mb = memory_usage / (1024 * 1024)

            # Check thresholds
            if cpu_percent >= self.config.thresholds.cpu_percent_critical:
                return AlertEvent(
                    timestamp=datetime.now(),
                    service=container_name,
                    alert_type="high_cpu",
                    severity="critical",
                    message=f"{container_name} CPU usage critical: {cpu_percent:.1f}%",
                    details={"cpu_percent": cpu_percent},
                    alert_id=f"cpu-{container_name}-critical",
                )
            elif cpu_percent >= self.config.thresholds.cpu_percent_warning:
                return AlertEvent(
                    timestamp=datetime.now(),
                    service=container_name,
                    alert_type="high_cpu",
                    severity="warning",
                    message=f"{container_name} CPU usage high: {cpu_percent:.1f}%",
                    details={"cpu_percent": cpu_percent},
                    alert_id=f"cpu-{container_name}-warning",
                )

            if memory_mb >= self.config.thresholds.memory_mb_critical:
                return AlertEvent(
                    timestamp=datetime.now(),
                    service=container_name,
                    alert_type="high_memory",
                    severity="critical",
                    message=f"{container_name} memory usage critical: {memory_mb:.0f}MB",
                    details={"memory_mb": memory_mb},
                    alert_id=f"memory-{container_name}-critical",
                )
            elif memory_mb >= self.config.thresholds.memory_mb_warning:
                return AlertEvent(
                    timestamp=datetime.now(),
                    service=container_name,
                    alert_type="high_memory",
                    severity="warning",
                    message=f"{container_name} memory usage high: {memory_mb:.0f}MB",
                    details={"memory_mb": memory_mb},
                    alert_id=f"memory-{container_name}-warning",
                )

        except Exception as e:
            logger.error(f"Error checking resources for {container_name}: {e}")

        return None

    def check_health_endpoint(self, container_name: str) -> Optional[AlertEvent]:
        """Check service health endpoint."""
        health_url = self.config.services.health_endpoints.get(container_name)
        if not health_url:
            return None

        state = self.service_states.get(container_name)
        if not state:
            return None

        try:
            with httpx.Client() as client:
                response = client.get(
                    health_url,
                    timeout=self.config.thresholds.health_check_timeout_seconds,
                )
                if response.status_code == 200:
                    # Healthy - reset failure count
                    if state.consecutive_health_failures > 0:
                        if self.config.notification.include_recovery_alerts:
                            recovery_payload = self.alerter.format_recovery_alert(
                                container_name,
                                "health_check",
                                {
                                    "previous_failures": state.consecutive_health_failures
                                },
                            )
                            self.alerter.send_alert(recovery_payload)
                        state.consecutive_health_failures = 0
                        state.escalation_level = 0
                    state.last_health_check = datetime.now()
                    return None
                else:
                    # Unhealthy response
                    state.consecutive_health_failures += 1
        except Exception as e:
            # Health check failed
            state.consecutive_health_failures += 1
            logger.debug(f"Health check failed for {container_name}: {e}")

        state.last_health_check = datetime.now()

        # Check if we should alert
        if (
            state.consecutive_health_failures
            >= self.config.thresholds.consecutive_health_failures
        ):
            # Escalate if repeated failures
            if (
                state.consecutive_health_failures
                >= self.config.throttling.escalation_threshold
            ):
                state.escalation_level = min(state.escalation_level + 1, 3)
                severity = "critical"
            else:
                severity = "warning"

            return AlertEvent(
                timestamp=datetime.now(),
                service=container_name,
                alert_type="health_failure",
                severity=severity,
                message=f"{container_name} health check failing ({state.consecutive_health_failures} consecutive failures)",
                details={
                    "consecutive_failures": state.consecutive_health_failures,
                    "escalation_level": state.escalation_level,
                },
                alert_id=f"health-{container_name}-{state.consecutive_health_failures}",
            )

        return None

    def process_alert(self, event: AlertEvent) -> None:
        """Process alert through throttling and send if approved."""
        # Check if we should send
        should_send, reason = self.throttler.should_send_alert(event)

        if should_send:
            # Format and send alert
            payload = self.alerter.format_alert(event)
            success = self.alerter.send_alert(payload)
            if success:
                logger.info(
                    f"Alert sent: {event.service} - {event.alert_type} ({event.severity})"
                )
                # Mark service as in recovery
                if event.service in self.service_states:
                    self.service_states[event.service].in_recovery = True
            else:
                logger.error(
                    f"Failed to send alert: {event.service} - {event.alert_type}"
                )
        else:
            logger.debug(
                f"Alert suppressed: {event.service} - {event.alert_type} - {reason}"
            )

            # Record for aggregation
            self.throttler.record_error(event.service, event.alert_type)

            # Check if we should send aggregated alert
            aggregated = self.throttler.aggregate_errors(
                event.service, event.alert_type
            )
            if aggregated:
                agg_event = AlertEvent(
                    timestamp=datetime.now(),
                    service=event.service,
                    alert_type=f"{event.alert_type}_aggregated",
                    severity="warning",
                    message=f"{event.service} had {aggregated['count']} {event.alert_type} errors in the last {aggregated['window_seconds']}s",
                    details=aggregated,
                )
                payload = self.alerter.format_alert(agg_event)
                self.alerter.send_alert(payload)
                logger.info(
                    f"Aggregated alert sent: {event.service} - {aggregated['count']} errors"
                )

    def monitor_once(self) -> None:
        """Run one monitoring cycle."""
        logger.info("Running monitoring cycle...")

        for container_name in self.config.services.monitored_containers:
            # Check container health
            event = self.check_container_health(container_name)
            if event:
                self.process_alert(event)

            # Check resource usage
            event = self.check_resource_usage(container_name)
            if event:
                self.process_alert(event)

            # Check health endpoint
            event = self.check_health_endpoint(container_name)
            if event:
                self.process_alert(event)

        # Save state
        self.save_state()

        logger.info("Monitoring cycle complete")

    def run_daemon(self) -> None:
        """Run continuous monitoring in daemon mode."""
        logger.info("Starting daemon mode...")
        self.running = True

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while self.running:
            try:
                self.monitor_once()
                time.sleep(self.config.monitoring.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(10)  # Brief pause before retry

        logger.info("Daemon stopped")
        self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        self.save_state()
        self.alerter.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Archon Slack Alerting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--webhook",
        type=str,
        help="Slack webhook URL (or set ALERT_NOTIFICATION_SLACK_WEBHOOK_URL env var)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode (continuous monitoring)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Monitoring interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Get webhook URL
    webhook_url = args.webhook or alerting_config.notification.slack_webhook_url

    if not webhook_url:
        logger.error(
            "Slack webhook URL required. Use --webhook or set ALERT_NOTIFICATION_SLACK_WEBHOOK_URL"
        )
        sys.exit(1)

    # Override config if needed
    if args.interval:
        alerting_config.monitoring.check_interval_seconds = args.interval

    # Initialize monitor
    try:
        monitor = ArchonMonitor(webhook_url)
    except DockerException as e:
        logger.error(f"Failed to connect to Docker: {e}")
        logger.error("Make sure Docker is running and accessible")
        sys.exit(1)

    # Run monitoring
    try:
        if args.daemon:
            monitor.run_daemon()
        else:
            monitor.monitor_once()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        monitor.cleanup()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
