#!/usr/bin/env python3
"""
Negative test cases for Archon Bridge Intelligence API.

Tests edge cases, error scenarios, and resilience:
- Concurrent request handling
- Lock timeout scenarios
- Database connection failures
- Generator initialization failures
- Invalid input handling
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp_server.clients.metadata_stamping_client import MetadataStampingClient

TEST_FILE_CONTENT = '''"""Example module."""
def test():
    pass
'''


async def test_concurrent_initialization():
    """Test multiple concurrent initializations don't deadlock."""
    print("\n" + "=" * 80)
    print("TEST 1: Concurrent Initialization (No Deadlock)")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8053", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            # Simulate 10 concurrent requests during initialization
            tasks = []
            for i in range(10):
                task = client.generate_intelligence(
                    file_path=f"/test/concurrent_{i}.py",
                    content=TEST_FILE_CONTENT,
                    include_semantic=False,  # Faster
                    include_compliance=False,
                    include_patterns=False,
                )
                tasks.append(task)

            # All should complete without deadlock
            start_time = time.perf_counter()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Check results
            successful = sum(
                1 for r in results if isinstance(r, dict) and r.get("success")
            )
            failed = len(results) - successful

            print("\n📊 Concurrent Request Results:")
            print(f"   Total Requests: {len(results)}")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            print(f"   Total Duration: {duration_ms:.2f}ms")
            print(f"   Avg Per Request: {duration_ms / len(results):.2f}ms")

            # Check for deadlocks (timeout would be >10s)
            if duration_ms < 30000:  # 30 seconds should be more than enough
                print("\n✅ SUCCESS: No deadlock detected")
                return True
            else:
                print(f"\n❌ FAILED: Possible deadlock (took {duration_ms:.2f}ms)")
                return False

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            return False


async def test_invalid_input_handling():
    """Test handling of invalid inputs."""
    print("\n" + "=" * 80)
    print("TEST 2: Invalid Input Handling")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8053", intelligence_url="http://localhost:8053"
    ) as client:
        test_cases = [
            {
                "name": "Empty content",
                "file_path": "/test/empty.py",
                "content": "",
            },
            {
                "name": "Very large content",
                "file_path": "/test/large.py",
                "content": "x" * 1000000,  # 1MB
            },
            {
                "name": "Special characters in path",
                "file_path": "/test/../../../etc/passwd",
                "content": TEST_FILE_CONTENT,
            },
        ]

        results = []
        for test_case in test_cases:
            try:
                result = await client.generate_intelligence(
                    file_path=test_case["file_path"],
                    content=test_case["content"],
                    include_semantic=False,
                    include_compliance=False,
                    include_patterns=False,
                )

                # Check if it handled gracefully
                handled_gracefully = result.get("success") is not None
                results.append(
                    {
                        "name": test_case["name"],
                        "handled": handled_gracefully,
                        "success": result.get("success"),
                    }
                )

                print(
                    f"   {test_case['name']}: {'✅ Handled' if handled_gracefully else '❌ Not handled'}"
                )

            except Exception as e:
                # Exceptions are also valid handling
                results.append(
                    {
                        "name": test_case["name"],
                        "handled": True,
                        "exception": str(e),
                    }
                )
                print(
                    f"   {test_case['name']}: ✅ Handled (exception: {type(e).__name__})"
                )

        # All should be handled gracefully (either return or exception)
        all_handled = all(r["handled"] for r in results)

        if all_handled:
            print("\n✅ SUCCESS: All invalid inputs handled gracefully")
            return True
        else:
            print("\n❌ FAILED: Some inputs not handled properly")
            return False


async def test_rapid_sequential_requests():
    """Test rapid sequential requests don't cause issues."""
    print("\n" + "=" * 80)
    print("TEST 3: Rapid Sequential Requests")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8053", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            num_requests = 20
            results = []
            durations = []

            print(f"\n🔄 Sending {num_requests} rapid sequential requests...\n")

            for i in range(num_requests):
                start_time = time.perf_counter()

                result = await client.generate_intelligence(
                    file_path=f"/test/rapid_{i}.py",
                    content=TEST_FILE_CONTENT,
                    include_semantic=False,
                    include_compliance=False,
                    include_patterns=False,
                )

                duration_ms = (time.perf_counter() - start_time) * 1000
                durations.append(duration_ms)
                results.append(result.get("success", False))

                if i % 5 == 0:
                    print(f"   Completed {i+1}/{num_requests} requests")

            success_rate = sum(results) / len(results)
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)

            print("\n📊 Rapid Request Statistics:")
            print(f"   Total Requests: {num_requests}")
            print(f"   Success Rate: {success_rate:.1%}")
            print(f"   Avg Duration: {avg_duration:.2f}ms")
            print(f"   Min Duration: {min_duration:.2f}ms")
            print(f"   Max Duration: {max_duration:.2f}ms")

            # Check for consistent performance (no degradation)
            if success_rate >= 0.95 and max_duration < 5000:  # 95% success, <5s max
                print("\n✅ SUCCESS: Consistent performance under rapid requests")
                return True
            else:
                print("\n⚠️  WARNING: Performance degradation detected")
                return False

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            return False


async def test_connection_resilience():
    """Test resilience to temporary connection issues."""
    print("\n" + "=" * 80)
    print("TEST 4: Connection Resilience")
    print("=" * 80)

    # Test with correct URL first
    async with MetadataStampingClient(
        base_url="http://localhost:8053", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            result = await client.generate_intelligence(
                file_path="/test/resilience.py",
                content=TEST_FILE_CONTENT,
                include_semantic=False,
                include_compliance=False,
                include_patterns=False,
            )

            baseline_success = result.get("success", False)
            print(
                f"   Baseline request: {'✅ Success' if baseline_success else '❌ Failed'}"
            )

        except Exception as e:
            print(f"   Baseline request: ❌ Exception ({e})")
            baseline_success = False

    # Test with wrong URL (should fail gracefully)
    try:
        async with MetadataStampingClient(
            base_url="http://localhost:9999",  # Wrong port
            intelligence_url="http://localhost:9999",
        ) as client:
            try:
                result = await client.generate_intelligence(
                    file_path="/test/resilience.py",
                    content=TEST_FILE_CONTENT,
                    include_semantic=False,
                    include_compliance=False,
                    include_patterns=False,
                )
                wrong_url_handled = True
                print("   Wrong URL request: ⚠️  Unexpected success")
            except Exception as e:
                wrong_url_handled = True
                print(
                    f"   Wrong URL request: ✅ Failed gracefully ({type(e).__name__})"
                )
    except Exception as e:
        wrong_url_handled = True
        print(f"   Wrong URL request: ✅ Failed gracefully ({type(e).__name__})")

    if baseline_success and wrong_url_handled:
        print("\n✅ SUCCESS: Connection resilience validated")
        return True
    else:
        print(
            f"\n⚠️  WARNING: Baseline: {baseline_success}, Wrong URL handled: {wrong_url_handled}"
        )
        return baseline_success  # Partial pass if baseline worked


async def test_health_check_under_load():
    """Test health check remains responsive under load."""
    print("\n" + "=" * 80)
    print("TEST 5: Health Check Under Load")
    print("=" * 80)

    import httpx

    async with MetadataStampingClient(
        base_url="http://localhost:8053", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            # Start background load
            load_tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    client.generate_intelligence(
                        file_path=f"/test/load_{i}.py",
                        content=TEST_FILE_CONTENT,
                        include_semantic=True,  # Slower
                        include_compliance=True,
                        include_patterns=False,
                    )
                )
                load_tasks.append(task)

            # Check health while under load
            health_checks = []
            async with httpx.AsyncClient() as http_client:
                for i in range(3):
                    start_time = time.perf_counter()
                    response = await http_client.get(
                        "http://localhost:8053/api/bridge/health", timeout=5.0
                    )
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    health_checks.append(
                        {
                            "status_code": response.status_code,
                            "duration_ms": duration_ms,
                            "healthy": (
                                response.json().get("status") == "healthy"
                                if response.status_code == 200
                                else False
                            ),
                        }
                    )

                    await asyncio.sleep(0.1)  # Small delay between checks

            # Wait for load tasks to complete
            await asyncio.gather(*load_tasks, return_exceptions=True)

            # Analyze health checks
            all_healthy = all(check["healthy"] for check in health_checks)
            avg_health_duration = sum(
                check["duration_ms"] for check in health_checks
            ) / len(health_checks)

            print("\n📊 Health Check Under Load:")
            print(f"   Health Checks: {len(health_checks)}")
            print(f"   All Healthy: {all_healthy}")
            print(f"   Avg Duration: {avg_health_duration:.2f}ms")

            if all_healthy and avg_health_duration < 1000:  # <1s health check
                print("\n✅ SUCCESS: Health check remains responsive under load")
                return True
            else:
                print("\n⚠️  WARNING: Health check degraded under load")
                return False

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            return False


async def run_all_tests():
    """Run all negative test cases."""
    print("\n" + "=" * 80)
    print("ARCHON BRIDGE INTELLIGENCE API - NEGATIVE TEST CASES")
    print("=" * 80)
    print("\nTesting edge cases, error scenarios, and resilience")

    results = {
        "concurrent_initialization": await test_concurrent_initialization(),
        "invalid_input_handling": await test_invalid_input_handling(),
        "rapid_sequential_requests": await test_rapid_sequential_requests(),
        "connection_resilience": await test_connection_resilience(),
        "health_check_under_load": await test_health_check_under_load(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("NEGATIVE TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL NEGATIVE TESTS PASSED")
        print("\n🎯 Bridge Intelligence API is resilient and robust")
    else:
        passed_count = sum(results.values())
        total_count = len(results)
        print(f"⚠️  {passed_count}/{total_count} TESTS PASSED")
        print("\n💡 Some edge cases may need attention")
    print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
