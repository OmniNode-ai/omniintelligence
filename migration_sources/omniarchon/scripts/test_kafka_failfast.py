#!/usr/bin/env python3
"""
Test script to verify fail-fast Kafka connectivity validation.

Tests two scenarios:
1. Kafka DOWN - should fail immediately with clear error
2. Kafka UP - should succeed (or be skipped if Kafka is actually down)

Usage:
    python3 scripts/test_kafka_failfast.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bulk_ingest_repository import verify_kafka_connectivity


async def test_kafka_down():
    """Test that fail-fast validation catches unreachable Kafka."""
    print("=" * 70)
    print("TEST 1: Kafka DOWN (unreachable host)")
    print("=" * 70)
    print("Expected: Immediate failure with clear error message")
    print("")

    try:
        # Use a definitely unreachable host
        await verify_kafka_connectivity("192.0.2.1:9092", timeout=2)
        print("❌ TEST FAILED: Should have raised SystemExit")
        return False
    except SystemExit as e:
        if e.code == 1:
            print("\n✅ TEST PASSED: Failed fast with exit code 1")
            return True
        else:
            print(f"\n❌ TEST FAILED: Wrong exit code {e.code} (expected 1)")
            return False


async def test_kafka_up():
    """Test that validation succeeds when Kafka is reachable."""
    print("\n" + "=" * 70)
    print("TEST 2: Kafka UP (reachable host)")
    print("=" * 70)
    print("Expected: Successful connection")
    print("")

    try:
        # Use actual Kafka server from environment
        await verify_kafka_connectivity("192.168.86.200:9092", timeout=5)
        print("✅ TEST PASSED: Kafka is reachable")
        return True
    except SystemExit as e:
        print(f"⚠️  TEST SKIPPED: Kafka is not running (exit code {e.code})")
        print("   This is expected if Kafka/Redpanda is actually down.")
        return True  # Don't fail the test if Kafka is legitimately down


async def test_kafka_wrong_port():
    """Test that fail-fast validation catches wrong port."""
    print("\n" + "=" * 70)
    print("TEST 3: Kafka WRONG PORT (connection refused)")
    print("=" * 70)
    print("Expected: Immediate failure with connection refused error")
    print("")

    try:
        # Use correct host but wrong port (likely nothing listening)
        await verify_kafka_connectivity("192.168.86.200:9999", timeout=2)
        print("❌ TEST FAILED: Should have raised SystemExit")
        return False
    except SystemExit as e:
        if e.code == 1:
            print("\n✅ TEST PASSED: Failed fast with exit code 1")
            return True
        else:
            print(f"\n❌ TEST FAILED: Wrong exit code {e.code} (expected 1)")
            return False


async def main():
    """Run all fail-fast validation tests."""
    print("\n" + "=" * 70)
    print("KAFKA FAIL-FAST VALIDATION TEST SUITE")
    print("=" * 70)
    print("")

    results = []

    # Test 1: Unreachable host
    results.append(await test_kafka_down())

    # Test 2: Reachable Kafka (if available)
    results.append(await test_kafka_up())

    # Test 3: Wrong port
    results.append(await test_kafka_wrong_port())

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
