#!/usr/bin/env python3
"""
Test Slack Alerting Configuration

Validates Slack webhook configuration and sends test alerts.
Useful for verifying alerting setup before deploying to production.

Usage:
    python scripts/test_slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    python scripts/test_slack_alerting.py  # Uses ALERT_NOTIFICATION_SLACK_WEBHOOK_URL env var
"""

import argparse
import sys
from pathlib import Path

import httpx

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.alerting_config import alerting_config


def test_webhook_connectivity(webhook_url: str) -> bool:
    """Test if webhook URL is reachable and valid."""
    print("Testing webhook connectivity...")

    try:
        client = httpx.Client(timeout=10.0)
        response = client.post(
            webhook_url,
            json={
                "text": "🧪 Test message from Archon alerting configuration validation"
            },
        )
        response.raise_for_status()
        print("✅ Webhook connectivity test PASSED")
        print(f"   Response: {response.status_code} {response.reason_phrase}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"❌ Webhook connectivity test FAILED")
        print(f"   HTTP Error: {e.response.status_code} {e.response.reason_phrase}")
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Webhook connectivity test FAILED")
        print(f"   Error: {e}")
        return False
    finally:
        client.close()


def test_alert_formatting() -> bool:
    """Test alert formatting."""
    print("\nTesting alert formatting...")

    try:
        from datetime import datetime

        from scripts.slack_alerting import AlertEvent, SlackAlerter

        # Create test alerter (won't actually send)
        alerter = SlackAlerter("https://example.com/webhook")

        # Test critical alert
        event = AlertEvent(
            timestamp=datetime.now(),
            service="test-service",
            alert_type="test_alert",
            severity="critical",
            message="This is a test critical alert",
            details={"cpu_percent": 95.5, "memory_mb": 3800.0},
        )

        payload = alerter.format_alert(event)

        # Validate payload structure
        assert "attachments" in payload
        assert len(payload["attachments"]) > 0
        attachment = payload["attachments"][0]
        assert "title" in attachment
        assert "text" in attachment
        assert "color" in attachment
        assert "fields" in attachment
        assert attachment["color"] == "danger"  # Critical = danger

        print("✅ Alert formatting test PASSED")
        print(
            f"   Generated valid Slack attachment with {len(attachment['fields'])} fields"
        )

        alerter.close()
        return True
    except Exception as e:
        print(f"❌ Alert formatting test FAILED")
        print(f"   Error: {e}")
        return False


def test_configuration() -> bool:
    """Test configuration loading."""
    print("\nTesting configuration...")

    try:
        # Validate thresholds
        assert alerting_config.thresholds.container_restart_count > 0
        assert alerting_config.thresholds.cpu_percent_warning < 100.0
        assert alerting_config.thresholds.memory_mb_warning > 0

        # Validate throttling
        assert alerting_config.throttling.rate_limit_window_seconds > 0
        assert alerting_config.throttling.max_alerts_per_window > 0

        # Validate services
        assert len(alerting_config.services.monitored_containers) > 0
        assert len(alerting_config.services.critical_services) > 0

        # Validate monitoring
        assert alerting_config.monitoring.check_interval_seconds > 0

        print("✅ Configuration test PASSED")
        print(
            f"   Monitoring {len(alerting_config.services.monitored_containers)} containers"
        )
        print(
            f"   Critical services: {', '.join(alerting_config.services.critical_services)}"
        )
        print(
            f"   Check interval: {alerting_config.monitoring.check_interval_seconds}s"
        )
        return True
    except Exception as e:
        print(f"❌ Configuration test FAILED")
        print(f"   Error: {e}")
        return False


def test_docker_connectivity() -> bool:
    """Test Docker connectivity."""
    print("\nTesting Docker connectivity...")

    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list()

        # Find Archon containers
        archon_containers = [c for c in containers if c.name.startswith("archon-")]

        print("✅ Docker connectivity test PASSED")
        print(f"   Found {len(containers)} running containers")
        print(f"   Found {len(archon_containers)} Archon containers")

        if archon_containers:
            print(
                f"   Archon containers: {', '.join(c.name for c in archon_containers[:5])}"
            )
            if len(archon_containers) > 5:
                print(f"   ... and {len(archon_containers) - 5} more")
        else:
            print("   ⚠️  No Archon containers found (this is OK if not running)")

        return True
    except Exception as e:
        print(f"❌ Docker connectivity test FAILED")
        print(f"   Error: {e}")
        print("   Make sure Docker is running and you have permission to access it")
        return False


def send_test_alert(webhook_url: str) -> bool:
    """Send a comprehensive test alert."""
    print("\nSending comprehensive test alert...")

    try:
        from datetime import datetime

        from scripts.slack_alerting import AlertEvent, SlackAlerter

        alerter = SlackAlerter(webhook_url)

        # Create comprehensive test alert
        event = AlertEvent(
            timestamp=datetime.now(),
            service="archon-alerting-test",
            alert_type="configuration_test",
            severity="info",
            message="✅ Archon alerting system test successful! All components working correctly.",
            details={
                "test_timestamp": datetime.now().isoformat(),
                "webhook_configured": "Yes",
                "docker_accessible": "Yes",
                "config_valid": "Yes",
            },
        )

        payload = alerter.format_alert(event)
        success = alerter.send_alert(payload)

        if success:
            print("✅ Test alert sent successfully")
            print("   Check your Slack channel for the test message")
        else:
            print("❌ Failed to send test alert")

        alerter.close()
        return success
    except Exception as e:
        print(f"❌ Test alert sending FAILED")
        print(f"   Error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Slack alerting configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--webhook",
        type=str,
        help="Slack webhook URL (or set ALERT_NOTIFICATION_SLACK_WEBHOOK_URL env var)",
    )
    parser.add_argument(
        "--skip-send",
        action="store_true",
        help="Skip sending test alert (only validate configuration)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("ARCHON SLACK ALERTING CONFIGURATION TEST")
    print("=" * 70)

    # Get webhook URL
    webhook_url = args.webhook or alerting_config.notification.slack_webhook_url

    results = []

    # Run tests
    results.append(("Configuration Loading", test_configuration()))
    results.append(("Docker Connectivity", test_docker_connectivity()))
    results.append(("Alert Formatting", test_alert_formatting()))

    if webhook_url:
        results.append(("Webhook Connectivity", test_webhook_connectivity(webhook_url)))
        if not args.skip_send:
            results.append(("Send Test Alert", send_test_alert(webhook_url)))
    else:
        print("\n⚠️  Skipping webhook tests (no webhook URL configured)")
        print("   Set ALERT_NOTIFICATION_SLACK_WEBHOOK_URL or use --webhook flag")

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("-" * 70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! Your alerting system is ready to use.")
        print("\nNext steps:")
        print("  1. Run daemon mode: python scripts/slack_alerting.py --daemon")
        print("  2. Monitor logs: tail -f /tmp/archon_alerting_state.json")
        print("  3. Check Slack channel for alerts")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review the errors above.")
        print("\nCommon issues:")
        print("  - Docker not running: start Docker Desktop or dockerd")
        print("  - Invalid webhook URL: check Slack webhook configuration")
        print("  - Permission issues: add your user to docker group")
        return 1


if __name__ == "__main__":
    sys.exit(main())
