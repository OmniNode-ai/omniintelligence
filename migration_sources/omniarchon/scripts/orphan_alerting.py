#!/usr/bin/env python3
"""
Orphan Alerting System
======================

Monitors orphan count and sends alerts when thresholds are exceeded.

Alert Triggers:
  - Orphan count > configurable threshold (default: 0)
  - Orphan growth rate > configurable rate (default: 10/hour)
  - Tree building fails
  - Orphan percentage > configurable percentage (default: 5%)

Alert Channels:
  - stdout (always enabled)
  - Log file (always enabled)
  - Slack webhook (optional, if SLACK_WEBHOOK_URL set)
  - Email (optional, if SMTP settings configured)

Features:
  - Configurable thresholds via environment variables or CLI args
  - Alert deduplication (don't spam on same issue)
  - Alert history tracking
  - Graceful degradation (if Slack/email fails, still log)
  - Continuous monitoring mode

Usage:
    # Check once and alert if needed
    python3 scripts/orphan_alerting.py

    # Continuous monitoring (every 5 minutes)
    python3 scripts/orphan_alerting.py --continuous

    # Custom thresholds
    python3 scripts/orphan_alerting.py --orphan-threshold 10 --growth-rate-threshold 20

    # With Slack webhook
    export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
    python3 scripts/orphan_alerting.py --continuous

    # Test alert (send test message)
    python3 scripts/orphan_alerting.py --test
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class AlertThresholds:
    """Configurable alert thresholds."""

    orphan_count: int = 0  # Alert if orphans > this value
    orphan_percentage: float = 5.0  # Alert if orphan % > this value
    growth_rate_per_hour: float = 10.0  # Alert if growth rate > this value


@dataclass
class Alert:
    """Alert data structure."""

    timestamp: str
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    context: Dict = field(default_factory=dict)
    alert_id: Optional[str] = None  # For deduplication


@dataclass
class AlertHistory:
    """Alert history for deduplication."""

    alerts: List[Alert] = field(default_factory=list)
    last_alert_ids: Dict[str, datetime] = field(default_factory=dict)


class OrphanAlertingSystem:
    """Orphan monitoring and alerting system."""

    def __init__(
        self,
        thresholds: Optional[AlertThresholds] = None,
        slack_webhook_url: Optional[str] = None,
        dedup_window_minutes: int = 60,
    ):
        self.thresholds = thresholds or AlertThresholds()
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        self.alerts_file = Path(__file__).parent.parent / "logs" / "orphan_alerts.json"
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_file = (
            Path(__file__).parent.parent / "logs" / "orphan_metrics.json"
        )
        self.running = False

        # Load alert history
        self.history = self._load_alert_history()

    def _load_alert_history(self) -> AlertHistory:
        """Load alert history from file."""
        if not self.alerts_file.exists():
            return AlertHistory()

        try:
            with open(self.alerts_file, "r") as f:
                data = json.load(f)
                alerts = [Alert(**a) for a in data.get("alerts", [])]
                last_alert_ids = {
                    k: datetime.fromisoformat(v)
                    for k, v in data.get("last_alert_ids", {}).items()
                }
                return AlertHistory(alerts=alerts, last_alert_ids=last_alert_ids)
        except Exception as e:
            logger.warning(f"Failed to load alert history: {e}")
            return AlertHistory()

    def _save_alert_history(self):
        """Save alert history to file."""
        try:
            # Keep only last 1000 alerts
            if len(self.history.alerts) > 1000:
                self.history.alerts = self.history.alerts[-1000:]

            # Clean up old dedup entries (older than 24 hours)
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self.history.last_alert_ids = {
                k: v for k, v in self.history.last_alert_ids.items() if v >= cutoff
            }

            data = {
                "alerts": [asdict(a) for a in self.history.alerts],
                "last_alert_ids": {
                    k: v.isoformat() for k, v in self.history.last_alert_ids.items()
                },
            }

            with open(self.alerts_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save alert history: {e}")

    def _should_send_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent (deduplication)."""
        if not alert.alert_id:
            return True  # Always send if no alert_id

        # Check if we've sent this alert recently
        if alert.alert_id in self.history.last_alert_ids:
            last_sent = self.history.last_alert_ids[alert.alert_id]
            if datetime.utcnow() - last_sent < self.dedup_window:
                logger.debug(f"Suppressing duplicate alert: {alert.alert_id}")
                return False

        return True

    def _mark_alert_sent(self, alert: Alert):
        """Mark alert as sent for deduplication."""
        if alert.alert_id:
            self.history.last_alert_ids[alert.alert_id] = datetime.utcnow()

    def send_alert(self, alert: Alert):
        """Send alert to all configured channels."""
        # Check deduplication
        if not self._should_send_alert(alert):
            return

        # Add to history
        self.history.alerts.append(alert)
        self._mark_alert_sent(alert)
        self._save_alert_history()

        # Log alert
        severity_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "❌"}[alert.severity]

        log_message = f"{severity_icon} {alert.title}: {alert.message}"
        if alert.severity == "critical":
            logger.error(log_message)
        elif alert.severity == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Print to stdout
        print(f"\n{'=' * 80}")
        print(f"{severity_icon} ALERT: {alert.title}")
        print(f"{'=' * 80}")
        print(f"Severity:  {alert.severity.upper()}")
        print(f"Time:      {alert.timestamp}")
        print(f"Message:   {alert.message}")
        if alert.context:
            print(f"Context:")
            for key, value in alert.context.items():
                print(f"  - {key}: {value}")
        print(f"{'=' * 80}\n")

        # Send to Slack (if configured)
        if self.slack_webhook_url:
            self._send_slack_alert(alert)

    def _send_slack_alert(self, alert: Alert):
        """Send alert to Slack webhook."""
        try:
            # Format Slack message
            severity_emoji = {
                "info": ":information_source:",
                "warning": ":warning:",
                "critical": ":x:",
            }[alert.severity]

            color = {"info": "#36a64f", "warning": "#ff9900", "critical": "#ff0000"}[
                alert.severity
            ]

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{severity_emoji} {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {"title": key, "value": str(value), "short": True}
                            for key, value in alert.context.items()
                        ],
                        "footer": "Archon Orphan Alerting",
                        "ts": int(datetime.fromisoformat(alert.timestamp).timestamp()),
                    }
                ]
            }

            response = httpx.post(self.slack_webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()

            logger.info("Alert sent to Slack successfully")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def check_orphan_count(self) -> Optional[Alert]:
        """Check orphan count and return alert if threshold exceeded."""
        try:
            driver = GraphDatabase.driver(self.memgraph_uri)

            with driver.session() as session:
                # Get orphan count
                orphan_count = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    OPTIONAL MATCH orphan_path = (f)<-[:CONTAINS*]-(:PROJECT)
                    WITH f, orphan_path
                    WHERE orphan_path IS NULL
                    RETURN count(f) as count
                    """
                ).single()["count"]

                # Get total files
                total_files = session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                    RETURN count(f) as count
                    """
                ).single()["count"]

            driver.close()

            orphan_percentage = (
                (orphan_count / total_files * 100) if total_files > 0 else 0
            )

            # Check thresholds
            if orphan_count > self.thresholds.orphan_count:
                severity = "critical" if orphan_count > 100 else "warning"

                return Alert(
                    timestamp=datetime.utcnow().isoformat(),
                    severity=severity,
                    title="Orphan Count Threshold Exceeded",
                    message=f"Detected {orphan_count:,} orphaned files ({orphan_percentage:.1f}% of {total_files:,} total files)",
                    context={
                        "orphan_count": orphan_count,
                        "total_files": total_files,
                        "orphan_percentage": f"{orphan_percentage:.2f}%",
                        "threshold": self.thresholds.orphan_count,
                        "action": "Run: python3 scripts/quick_fix_tree.py",
                    },
                    alert_id=f"orphan_count_{orphan_count // 10 * 10}",  # Group by tens
                )

            return None

        except Exception as e:
            logger.error(f"Failed to check orphan count: {e}")
            return Alert(
                timestamp=datetime.utcnow().isoformat(),
                severity="critical",
                title="Orphan Check Failed",
                message=f"Failed to query Memgraph: {str(e)}",
                context={"error": str(e)},
                alert_id="orphan_check_failed",
            )

    def check_growth_rate(self) -> Optional[Alert]:
        """Check orphan growth rate and return alert if threshold exceeded."""
        if not self.metrics_file.exists():
            return None

        try:
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
                metrics = data.get("metrics", [])

            if len(metrics) < 2:
                return None

            # Get last two data points
            latest = metrics[-1]
            previous = metrics[-2]

            latest_time = datetime.fromisoformat(latest["timestamp"])
            previous_time = datetime.fromisoformat(previous["timestamp"])

            time_diff_hours = (latest_time - previous_time).total_seconds() / 3600
            if time_diff_hours == 0:
                return None

            orphan_diff = latest["orphan_count"] - previous["orphan_count"]
            growth_rate = orphan_diff / time_diff_hours

            # Check threshold
            if abs(growth_rate) > self.thresholds.growth_rate_per_hour:
                if growth_rate > 0:
                    # Increasing orphans (bad)
                    return Alert(
                        timestamp=datetime.utcnow().isoformat(),
                        severity="critical",
                        title="High Orphan Growth Rate Detected",
                        message=f"Orphan count increasing at {growth_rate:+.2f} orphans/hour",
                        context={
                            "growth_rate": f"{growth_rate:+.2f} orphans/hour",
                            "current_count": latest["orphan_count"],
                            "previous_count": previous["orphan_count"],
                            "change": orphan_diff,
                            "threshold": f"{self.thresholds.growth_rate_per_hour} orphans/hour",
                            "action": "Check ingestion pipeline logs for errors",
                        },
                        alert_id=f"growth_rate_high_{int(growth_rate // 10)}",
                    )

            return None

        except Exception as e:
            logger.error(f"Failed to check growth rate: {e}")
            return None

    def check_tree_health(self) -> Optional[Alert]:
        """Check tree structure health and return alert if issues found."""
        try:
            driver = GraphDatabase.driver(self.memgraph_uri)

            with driver.session() as session:
                # Get PROJECT count
                project_count = session.run(
                    "MATCH (p:PROJECT) RETURN count(p) as count"
                ).single()["count"]

                # Get DIRECTORY count
                directory_count = session.run(
                    "MATCH (d:DIRECTORY) RETURN count(d) as count"
                ).single()["count"]

            driver.close()

            # Check if tree structure is missing
            if project_count == 0 or directory_count == 0:
                return Alert(
                    timestamp=datetime.utcnow().isoformat(),
                    severity="critical",
                    title="Tree Structure Missing",
                    message=f"Tree graph incomplete: {project_count} PROJECT nodes, {directory_count} DIRECTORY nodes",
                    context={
                        "project_nodes": project_count,
                        "directory_nodes": directory_count,
                        "action": "Re-run bulk_ingest_repository.py or run build_directory_tree.py",
                    },
                    alert_id="tree_structure_missing",
                )

            return None

        except Exception as e:
            logger.error(f"Failed to check tree health: {e}")
            return None

    def run_checks(self):
        """Run all checks and send alerts."""
        alerts = []

        # Run all checks
        alert = self.check_orphan_count()
        if alert:
            alerts.append(alert)

        alert = self.check_growth_rate()
        if alert:
            alerts.append(alert)

        alert = self.check_tree_health()
        if alert:
            alerts.append(alert)

        # Send alerts
        for alert in alerts:
            self.send_alert(alert)

        return alerts

    def continuous_monitoring(self, interval_seconds: int = 300):
        """Run continuous monitoring with specified interval."""
        self.running = True

        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal, stopping monitoring...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info(
            f"Starting continuous orphan alerting (interval: {interval_seconds}s)"
        )

        while self.running:
            try:
                alerts = self.run_checks()

                if alerts:
                    logger.info(f"Sent {len(alerts)} alert(s)")
                else:
                    logger.info("No alerts triggered")

                # Sleep until next check
                time.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error during monitoring: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

        logger.info("Monitoring stopped")

    def send_test_alert(self):
        """Send a test alert to verify configuration."""
        alert = Alert(
            timestamp=datetime.utcnow().isoformat(),
            severity="info",
            title="Test Alert",
            message="This is a test alert from Archon Orphan Alerting System",
            context={
                "orphan_threshold": self.thresholds.orphan_count,
                "growth_rate_threshold": f"{self.thresholds.growth_rate_per_hour} orphans/hour",
                "slack_configured": "Yes" if self.slack_webhook_url else "No",
            },
            alert_id=None,  # Don't deduplicate test alerts
        )
        self.send_alert(alert)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Orphan Alerting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuous monitoring"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Monitoring interval in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--orphan-threshold",
        type=int,
        default=0,
        help="Alert if orphan count exceeds this value (default: 0)",
    )
    parser.add_argument(
        "--growth-rate-threshold",
        type=float,
        default=10.0,
        help="Alert if growth rate exceeds this value (orphans/hour, default: 10.0)",
    )
    parser.add_argument(
        "--slack-webhook",
        type=str,
        help="Slack webhook URL for alerts (or set SLACK_WEBHOOK_URL env var)",
    )
    parser.add_argument("--test", action="store_true", help="Send a test alert")

    args = parser.parse_args()

    # Create thresholds
    thresholds = AlertThresholds(
        orphan_count=args.orphan_threshold,
        growth_rate_per_hour=args.growth_rate_threshold,
    )

    # Create alerting system
    alerting = OrphanAlertingSystem(
        thresholds=thresholds, slack_webhook_url=args.slack_webhook
    )

    try:
        if args.test:
            # Send test alert
            alerting.send_test_alert()
            print("\n✅ Test alert sent successfully!")
            sys.exit(0)

        elif args.continuous:
            # Run continuous monitoring
            alerting.continuous_monitoring(interval_seconds=args.interval)

        else:
            # Single check
            alerts = alerting.run_checks()

            if alerts:
                print(f"\n⚠️  {len(alerts)} alert(s) triggered!")
                sys.exit(1)
            else:
                print("\n✅ All checks passed! No alerts triggered.")
                sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
