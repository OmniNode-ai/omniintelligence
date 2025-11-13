#!/usr/bin/env python3
"""
Corrected test for Archon Bridge Intelligence API.

Uses correct port: 8053 (archon-intelligence service)
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp_server.clients.metadata_stamping_client import MetadataStampingClient

TEST_FILE_CONTENT = '''"""Example ONEX module."""
from typing import Dict, Any

class DataTransformer:
    async def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"transformed": True, "data": data}
'''


async def run_tests():
    """Run all Bridge Intelligence API tests."""
    print("\n" + "=" * 80)
    print("ARCHON BRIDGE INTELLIGENCE API - CORRECTED TESTS")
    print("=" * 80)
    print("\nUsing Port 8053 (archon-intelligence service)")

    async with MetadataStampingClient(
        base_url="http://localhost:8053",  # CORRECTED: Use intelligence service port
        intelligence_url="http://localhost:8053",
    ) as client:

        # Test 1: Intelligence Generation
        print("\n" + "=" * 80)
        print("TEST 1: Intelligence Generation")
        print("=" * 80)

        start_time = time.perf_counter()
        result = await client.generate_intelligence(
            file_path="/test/example.py",
            content=TEST_FILE_CONTENT,
            include_semantic=True,
            include_compliance=True,
            include_patterns=True,
        )
        duration_ms = (time.perf_counter() - start_time) * 1000

        print(f"\n✅ Response Time: {duration_ms:.2f}ms")
        print(f"   Success: {result.get('success')}")
        print(f"   Sources: {', '.join(result.get('intelligence_sources', []))}")

        metadata = result.get("metadata", {})
        if metadata:
            quality = metadata.get("quality_metrics", {})
            print("\n📊 Quality Metrics:")
            print(f"   Quality: {quality.get('quality_score', 0):.2f}")
            print(f"   ONEX: {quality.get('onex_compliance', 0):.2f}")
            print(f"   Complexity: {quality.get('complexity_score', 0):.2f}")

        test1_pass = result.get("success") and duration_ms < 2000

        # Test 2: Health Check (using httpx directly)
        print("\n" + "=" * 80)
        print("TEST 2: Health Check")
        print("=" * 80)

        import httpx

        start_time = time.perf_counter()
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                "http://localhost:8053/api/bridge/health", timeout=5.0
            )
        duration_ms = (time.perf_counter() - start_time) * 1000

        health = response.json()
        print(f"\n✅ Response Time: {duration_ms:.2f}ms")
        print(f"   Status: {health.get('status')}")
        print(f"   Service: {health.get('service')}")

        components = health.get("components", {})
        print("\n📊 Components:")
        for name, status in components.items():
            print(f"   {name}: {status}")

        test2_pass = response.status_code == 200 and health.get("status") == "healthy"

        # Test 3: Performance (5 requests)
        print("\n" + "=" * 80)
        print("TEST 3: Performance Consistency (5 requests)")
        print("=" * 80)

        durations = []
        for i in range(5):
            start_time = time.perf_counter()
            result = await client.generate_intelligence(
                file_path=f"/test/perf_{i}.py",
                content=TEST_FILE_CONTENT,
                include_semantic=False,  # Faster
                include_compliance=True,
                include_patterns=False,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            durations.append(duration_ms)
            print(f"   Request {i+1}: {duration_ms:.2f}ms")

        avg = sum(durations) / len(durations)
        min_d = min(durations)
        max_d = max(durations)

        print("\n📊 Statistics:")
        print(f"   Average: {avg:.2f}ms")
        print(f"   Min: {min_d:.2f}ms")
        print(f"   Max: {max_d:.2f}ms")
        print("   Target: <2000ms")

        test3_pass = all(d < 2000 for d in durations)

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    tests = {
        "Intelligence Generation": test1_pass,
        "Health Check": test2_pass,
        "Performance Consistency": test3_pass,
    }

    for name, passed in tests.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")

    all_passed = all(tests.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\n🎯 Bridge Intelligence API is fully operational")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
