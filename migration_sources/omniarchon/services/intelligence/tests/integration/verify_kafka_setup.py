#!/usr/bin/env python3
"""
Kafka Test Infrastructure Verification Script

Quick verification script to test Kafka test infrastructure setup.
Run this to verify connectivity and fixture functionality before running full test suite.

Usage:
    python tests/integration/verify_kafka_setup.py

Author: Archon Intelligence Team
Version: 1.0.0
Created: 2025-10-15 (MVP Phase 4 - Workflow 1)
"""

import sys
from pathlib import Path

from integration.kafka_test_config import KafkaTestConfig
from integration.kafka_utils import create_test_topics, verify_kafka_connectivity

# Add tests directory to path


def print_section(title: str):
    """Print section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def verify_configuration():
    """Verify configuration is loaded correctly."""
    print_section("Configuration Verification")

    print(f"✓ Bootstrap Servers: {KafkaTestConfig.BOOTSTRAP_SERVERS}")
    print(f"✓ Consumer Group Prefix: {KafkaTestConfig.CONSUMER_GROUP_PREFIX}")
    print(f"✓ Default Topics: {len(KafkaTestConfig.DEFAULT_TOPICS)}")

    print("\nTopics:")
    for key, topic in KafkaTestConfig.DEFAULT_TOPICS.items():
        print(f"  - {key}: {topic}")

    print("\n✅ Configuration loaded successfully")
    return True


def verify_connectivity():
    """Verify Kafka connectivity."""
    print_section("Connectivity Verification")

    print("Testing Kafka connectivity...")
    if verify_kafka_connectivity():
        print("✅ Kafka is available and accessible")
        return True
    else:
        print("❌ Kafka is not available")
        print("\nTroubleshooting:")
        print("  1. Check if Redpanda/Kafka is running:")
        print("     docker ps | grep redpanda")
        print("  2. Verify bootstrap servers:")
        print(f"     kafkacat -b {KafkaTestConfig.BOOTSTRAP_SERVERS} -L")
        print("  3. Check environment variables:")
        print("     echo $TEST_KAFKA_BOOTSTRAP_SERVERS")
        return False


def verify_topic_creation():
    """Verify topic creation works."""
    print_section("Topic Creation Verification")

    print("Attempting to create test topics...")
    if create_test_topics():
        print("✅ Topics created successfully")
        print("\nVerify topics exist:")
        print(
            f"  kafkacat -b {KafkaTestConfig.BOOTSTRAP_SERVERS} -L | grep omninode.codegen"
        )
        return True
    else:
        print("❌ Topic creation failed")
        print("\nTroubleshooting:")
        print("  1. Check admin client permissions")
        print("  2. Verify Kafka allows auto-creation")
        print("  3. Check Kafka logs for errors")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("  Kafka Test Infrastructure Verification")
    print("  MVP Phase 4 - Workflow 1")
    print("=" * 60)

    results = {
        "configuration": False,
        "connectivity": False,
        "topic_creation": False,
    }

    # Run checks
    try:
        results["configuration"] = verify_configuration()
        results["connectivity"] = verify_connectivity()

        if results["connectivity"]:
            results["topic_creation"] = verify_topic_creation()

    except Exception as e:
        print(f"\n❌ Verification failed with exception: {e}")
        import traceback

        traceback.print_exc()

    # Print summary
    print_section("Verification Summary")

    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {check.replace('_', ' ').title()}")

    all_passed = all(results.values())

    print()
    if all_passed:
        print("🎉 All checks passed! Kafka test infrastructure is ready.")
        print("\nNext Steps:")
        print("  1. Run Kafka integration tests:")
        print("     pytest -m kafka -v")
        print("  2. Proceed to Workflow 2: Enable Kafka tests")
        return 0
    else:
        print("⚠️  Some checks failed. Review output above for troubleshooting.")
        print("\nCommon Issues:")
        print("  - Kafka not running: Start Redpanda/Kafka container")
        print("  - Wrong bootstrap servers: Check TEST_KAFKA_BOOTSTRAP_SERVERS")
        print("  - Network issues: Verify container networking")
        return 1


if __name__ == "__main__":
    sys.exit(main())
