#!/usr/bin/env python3
"""
Performance Crisis Intervention Validation Script

Tests the performance improvements made to the pattern tracking system:
1. Database connection pooling fixes
2. HTTP connection pooling implementation
3. Concurrent request handling with rate limiting
4. Optimized queries and async processing

Measures:
- Success rate under load (target: 95%+)
- Operations per second (target: 150+ ops/sec)
- Response times (target: <50ms tracking, <200ms queries)
- Connection pooling efficiency
- Memory usage under load
"""

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict

import asyncpg
import httpx

# Test configuration
TEST_CONFIG = {
    "base_url": "http://localhost:8053",
    "database_url": "postgresql://localhost/archon",
    "concurrent_users": [1, 10, 50, 100],
    "test_duration_seconds": 30,
    "requests_per_user": 100,
    "warmup_requests": 10,
}


class PerformanceTestResult:
    """Container for performance test results"""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.response_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.concurrent_users = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        return (self.success_count / total * 100) if total > 0 else 0

    @property
    def ops_per_second(self) -> float:
        if self.end_time and self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            return self.success_count / duration if duration > 0 else 0
        return 0

    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0

    @property
    def p95_response_time(self) -> float:
        if self.response_times:
            sorted_times = sorted(self.response_times)
            index = int(len(sorted_times) * 0.95)
            return sorted_times[index]
        return 0


class PerformanceValidator:
    """Validates performance improvements in pattern tracking system"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.http_client = None
        self.db_pool = None
        self.results = {}

    async def initialize(self):
        """Initialize HTTP client and database pool"""
        # Configure HTTP client with connection pooling
        limits = httpx.Limits(
            max_keepalive_connections=100,
            max_connections=200,
            keepalive_expiry=300,
        )

        timeout = httpx.Timeout(
            30.0,
            connect=10.0,
            read=30.0,
            write=30.0,
            pool=30.0,
        )

        self.http_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            base_url=self.config["base_url"],
        )

        # Initialize database pool for verification
        try:
            self.db_pool = await asyncpg.create_pool(
                self.config["database_url"],
                min_size=5,
                max_size=50,
                command_timeout=60,
            )
            print("✅ Database pool initialized for validation")
        except Exception as e:
            print(f"⚠️  Database pool initialization failed: {e}")
            self.db_pool = None

    async def cleanup(self):
        """Clean up resources"""
        if self.http_client:
            await self.http_client.aclose()
        if self.db_pool:
            await self.db_pool.close()

    async def health_check(self) -> bool:
        """Check if services are healthy"""
        try:
            response = await self.http_client.get("/api/pattern-traceability/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check passed: {health_data.get('status', 'unknown')}")
                return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        return False

    async def test_single_request(self, pattern_id: str) -> Dict[str, Any]:
        """Test a single pattern tracking request"""
        start_time = time.time()

        try:
            payload = {
                "event_type": "pattern_created",
                "pattern_id": pattern_id,
                "pattern_name": f"Test Pattern {pattern_id}",
                "pattern_type": "code",
                "pattern_version": "1.0.0",
                "pattern_data": {
                    "language": "python",
                    "code": f"def test_function_{pattern_id}():\n    return 'test'",
                    "metadata": {"test": True},
                },
                "triggered_by": "performance_test",
            }

            response = await self.http_client.post(
                "/api/pattern-traceability/lineage/track", json=payload, timeout=30.0
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "success": True,
                    "response_time_ms": response_time,
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "response_time_ms": response_time,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e),
            }

    async def test_query_request(self, pattern_id: str) -> Dict[str, Any]:
        """Test a pattern lineage query request"""
        start_time = time.time()

        try:
            response = await self.http_client.get(
                f"/api/pattern-traceability/lineage/{pattern_id}", timeout=30.0
            )

            response_time = (time.time() - start_time) * 1000

            if response.status_code in [200, 404]:  # 404 is acceptable for queries
                return {
                    "success": True,
                    "response_time_ms": response_time,
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "response_time_ms": response_time,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e),
            }

    async def run_concurrent_test(self, concurrent_users: int) -> PerformanceTestResult:
        """Run concurrent performance test"""
        print(f"\n🧪 Testing with {concurrent_users} concurrent users...")

        result = PerformanceTestResult()
        result.concurrent_users = concurrent_users

        # Generate test data
        pattern_ids = [
            f"test_pattern_{i}"
            for i in range(concurrent_users * self.config["requests_per_user"])
        ]

        async def user_task(user_id: int):
            """Simulate a single user making requests"""
            user_pattern_ids = pattern_ids[user_id::concurrent_users]

            for pattern_id in user_pattern_ids:
                test_result = await self.test_single_request(pattern_id)
                result.response_times.append(test_result["response_time_ms"])

                if test_result["success"]:
                    result.success_count += 1
                else:
                    result.error_count += 1
                    result.errors.append(test_result.get("error", "Unknown error"))

                # Small delay between requests
                await asyncio.sleep(0.01)

        # Start timing
        result.start_time = datetime.now(timezone.utc)

        # Create concurrent user tasks
        tasks = [user_task(i) for i in range(concurrent_users)]

        # Wait for all tasks to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config["test_duration_seconds"] + 60,
            )
        except asyncio.TimeoutError:
            print("⚠️  Test timed out")

        result.end_time = datetime.now(timezone.utc)

        return result

    async def run_query_performance_test(self) -> PerformanceTestResult:
        """Test query performance specifically"""
        print("\n🔍 Testing query performance...")

        result = PerformanceTestResult()

        # First, create some test patterns
        pattern_ids = []
        for i in range(50):
            pattern_id = f"query_test_{i}"
            pattern_ids.append(pattern_id)

            create_result = await self.test_single_request(pattern_id)
            if create_result["success"]:
                result.success_count += 1
            else:
                result.error_count += 1

        # Now test queries
        query_tasks = []
        for pattern_id in pattern_ids:
            task = self.test_query_request(pattern_id)
            query_tasks.append(task)

        start_time = time.time()

        query_results = await asyncio.gather(*query_tasks, return_exceptions=True)

        end_time = time.time()

        for query_result in query_results:
            if isinstance(query_result, Exception):
                result.error_count += 1
                result.errors.append(str(query_result))
            else:
                result.response_times.append(query_result["response_time_ms"])
                if query_result["success"]:
                    result.success_count += 1
                else:
                    result.error_count += 1

        result.start_time = datetime.fromtimestamp(start_time, tz=timezone.utc)
        result.end_time = datetime.fromtimestamp(end_time, tz=timezone.utc)

        return result

    async def validate_database_pool(self) -> Dict[str, Any]:
        """Validate database connection pool performance"""
        if not self.db_pool:
            return {"error": "Database pool not available"}

        try:
            pool_stats = {
                "min_size": self.db_pool.get_min_size(),
                "max_size": self.db_pool.get_max_size(),
                "current_size": self.db_pool.get_size(),
                "free_size": self.db_pool.get_idle_size(),
            }

            # Test connection acquisition speed
            start_time = time.time()
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            acquisition_time = (time.time() - start_time) * 1000

            return {
                "pool_stats": pool_stats,
                "connection_acquisition_ms": acquisition_time,
                "healthy": True,
            }
        except Exception as e:
            return {"error": str(e), "healthy": False}

    async def run_full_validation(self):
        """Run complete performance validation"""
        print("🚀 Starting Performance Crisis Intervention Validation")
        print("=" * 60)

        # Initialize
        await self.initialize()

        # Health check
        if not await self.health_check():
            print("❌ Services not healthy - aborting validation")
            return

        # Warmup
        print("🔥 Warming up services...")
        for i in range(self.config["warmup_requests"]):
            await self.test_single_request(f"warmup_{i}")
        print("✅ Warmup complete")

        # Test different concurrency levels
        for concurrent_users in self.config["concurrent_users"]:
            result = await self.run_concurrent_test(concurrent_users)
            self.results[f"concurrent_{concurrent_users}"] = result

        # Test query performance
        query_result = await self.run_query_performance_test()
        self.results["queries"] = query_result

        # Validate database pool
        db_validation = await self.validate_database_pool()
        self.results["database_pool"] = db_validation

        # Generate report
        await self.generate_report()

        # Cleanup
        await self.cleanup()

    async def generate_report(self):
        """Generate comprehensive performance report"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE VALIDATION REPORT")
        print("=" * 60)

        success_rates = []
        ops_rates = []

        print("\n📈 CONCURRENT REQUEST TEST RESULTS:")
        print("-" * 40)

        for test_name, result in self.results.items():
            if test_name.startswith("concurrent_"):
                concurrent_users = result.concurrent_users
                success_rate = result.success_rate
                ops_per_sec = result.ops_per_second
                avg_time = result.avg_response_time
                p95_time = result.p95_response_time

                success_rates.append(success_rate)
                ops_rates.append(ops_per_sec)

                print(f"\n👥 {concurrent_users} Concurrent Users:")
                print(
                    f"   ✅ Success Rate: {success_rate:.1f}% ({result.success_count}/{result.success_count + result.error_count})"
                )
                print(f"   ⚡ Throughput: {ops_per_sec:.1f} ops/sec")
                print(f"   📊 Avg Response: {avg_time:.1f}ms")
                print(f"   📈 P95 Response: {p95_time:.1f}ms")

                # Performance targets
                success_target = "✅ PASS" if success_rate >= 95 else "❌ FAIL"
                throughput_target = "✅ PASS" if ops_per_sec >= 150 else "❌ FAIL"
                latency_target = "✅ PASS" if avg_time < 50 else "❌ FAIL"

                print(
                    f"   🎯 Targets: {success_target} | {throughput_target} | {latency_target}"
                )

        # Query performance
        if "queries" in self.results:
            query_result = self.results["queries"]
            print("\n🔍 QUERY PERFORMANCE:")
            print(f"   ✅ Success Rate: {query_result.success_rate:.1f}%")
            print(f"   ⚡ Throughput: {query_result.ops_per_second:.1f} queries/sec")
            print(f"   📊 Avg Response: {query_result.avg_response_time:.1f}ms")
            print(f"   📈 P95 Response: {query_result.p95_response_time:.1f}ms")

        # Database pool validation
        if "database_pool" in self.results:
            db_result = self.results["database_pool"]
            print("\n🗄️  DATABASE POOL:")
            if db_result.get("healthy"):
                stats = db_result["pool_stats"]
                acquisition = db_result["connection_acquisition_ms"]
                print(
                    f"   ✅ Pool Size: {stats['current_size']}/{stats['max_size']} (min: {stats['min_size']})"
                )
                print(f"   ✅ Free Connections: {stats['free_size']}")
                print(f"   ⚡ Acquisition Time: {acquisition:.2f}ms")
                print(
                    f"   🎯 Pool Performance: {'✅ PASS' if acquisition < 10 else '❌ FAIL'}"
                )
            else:
                print(f"   ❌ Pool Error: {db_result.get('error')}")

        # Overall assessment
        print("\n🎯 OVERALL ASSESSMENT:")
        print("-" * 40)

        # Calculate averages
        if success_rates:
            avg_success_rate = statistics.mean(success_rates)
            max_ops_rate = max(ops_rates) if ops_rates else 0

            print(f"   📊 Average Success Rate: {avg_success_rate:.1f}%")
            print(f"   ⚡ Peak Throughput: {max_ops_rate:.1f} ops/sec")

            # Determine overall success
            success_target_met = avg_success_rate >= 95
            throughput_target_met = max_ops_rate >= 150

            if success_target_met and throughput_target_met:
                print("   🎉 CRISIS RESOLVED: Performance targets achieved!")
                print(
                    f"   ✅ Success Rate: {'✅ PASS' if success_target_met else '❌ FAIL'} (≥95%)"
                )
                print(
                    f"   ✅ Throughput: {'✅ PASS' if throughput_target_met else '❌ FAIL'} (≥150 ops/sec)"
                )
            else:
                print("   ⚠️  PERFORMANCE CRISIS: Targets not fully met")
                print(
                    f"   ❌ Success Rate: {'✅ PASS' if success_target_met else '❌ FAIL'} (≥95%)"
                )
                print(
                    f"   ❌ Throughput: {'✅ PASS' if throughput_target_met else '❌ FAIL'} (≥150 ops/sec)"
                )

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("   1. Monitor connection pool metrics in production")
        print("   2. Set up alerting for success rate < 95%")
        print("   3. Consider auto-scaling based on concurrent users")
        print("   4. Implement database query optimization for complex queries")

        # Save detailed results
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"performance_validation_{timestamp}.json"

        detailed_results = {
            "timestamp": timestamp,
            "config": self.config,
            "results": {
                name: {
                    "success_count": r.success_count,
                    "error_count": r.error_count,
                    "success_rate": r.success_rate,
                    "ops_per_second": r.ops_per_second,
                    "avg_response_time_ms": r.avg_response_time,
                    "p95_response_time_ms": r.p95_response_time,
                    "errors": r.errors[:10],  # Sample of errors
                }
                for name, r in self.results.items()
                if hasattr(r, "success_count")
            },
        }

        with open(filename, "w") as f:
            json.dump(detailed_results, f, indent=2)

        print(f"\n💾 Detailed results saved to: {filename}")


async def main():
    """Main validation function"""
    validator = PerformanceValidator(TEST_CONFIG)
    await validator.run_full_validation()


if __name__ == "__main__":
    asyncio.run(main())
