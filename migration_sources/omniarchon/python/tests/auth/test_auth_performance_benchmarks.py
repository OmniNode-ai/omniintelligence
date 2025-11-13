"""
Authentication Performance Testing & Benchmarking Suite

This module implements comprehensive performance testing for authentication APIs
following performance engineering best practices and load testing methodologies.

Performance Test Categories:
1. Response Time Testing - Individual endpoint latency analysis
2. Throughput Testing - Maximum requests per second capacity
3. Concurrency Testing - Multiple simultaneous user behavior
4. Load Testing - Sustained load over time
5. Stress Testing - Breaking point identification
6. Spike Testing - Sudden load increase handling
7. Volume Testing - Large data set processing
8. Endurance Testing - Memory leaks and degradation

Benchmarking Standards:
- Authentication latency targets: <200ms (p95), <500ms (p99)
- Password hashing: 50-200ms per operation
- JWT generation/validation: <10ms per operation
- Concurrent users: Support 100+ simultaneous authentications
- Throughput: >500 auth requests per second

Architecture: Archon authentication system with performance metrics collection
Technology: pytest + asyncio + httpx + performance monitoring tools
"""

import asyncio
import gc
import json
import statistics
import threading
import time
from collections.abc import Callable
from typing import Any, Optional
from unittest.mock import patch

import httpx
import psutil
import pytest
from jose import jwt

# Performance monitoring imports
try:
    import memory_profiler

    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False

try:
    import line_profiler

    LINE_PROFILER_AVAILABLE = True
except ImportError:
    LINE_PROFILER_AVAILABLE = False


class PerformanceMetrics:
    """Performance metrics collection and analysis"""

    def __init__(self):
        self.response_times: list[float] = []
        self.memory_usage: list[float] = []
        self.cpu_usage: list[float] = []
        self.error_count: int = 0
        self.success_count: int = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_time = time.time()
        gc.collect()  # Clean up before monitoring

    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.end_time = time.time()

    def record_request(
        self,
        response_time: float,
        success: bool,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
    ):
        """Record individual request metrics"""
        self.response_times.append(response_time)

        if memory_mb is not None:
            self.memory_usage.append(memory_mb)

        if cpu_percent is not None:
            self.cpu_usage.append(cpu_percent)

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def get_statistics(self) -> dict[str, Any]:
        """Calculate performance statistics"""
        if not self.response_times:
            return {"error": "No data recorded"}

        total_time = (
            (self.end_time - self.start_time)
            if self.start_time and self.end_time
            else 0
        )
        total_requests = len(self.response_times)

        stats = {
            # Response time statistics
            "response_time": {
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "min": min(self.response_times),
                "max": max(self.response_times),
                "std_dev": (
                    statistics.stdev(self.response_times)
                    if len(self.response_times) > 1
                    else 0
                ),
                "p95": self._percentile(self.response_times, 95),
                "p99": self._percentile(self.response_times, 99),
            },
            # Throughput statistics
            "throughput": {
                "total_requests": total_requests,
                "total_time": total_time,
                "requests_per_second": (
                    total_requests / total_time if total_time > 0 else 0
                ),
                "success_rate": (
                    (self.success_count / total_requests * 100)
                    if total_requests > 0
                    else 0
                ),
                "error_rate": (
                    (self.error_count / total_requests * 100)
                    if total_requests > 0
                    else 0
                ),
            },
            # Resource usage statistics
            "resources": {
                "memory": {
                    "mean_mb": (
                        statistics.mean(self.memory_usage) if self.memory_usage else 0
                    ),
                    "max_mb": max(self.memory_usage) if self.memory_usage else 0,
                    "min_mb": min(self.memory_usage) if self.memory_usage else 0,
                },
                "cpu": {
                    "mean_percent": (
                        statistics.mean(self.cpu_usage) if self.cpu_usage else 0
                    ),
                    "max_percent": max(self.cpu_usage) if self.cpu_usage else 0,
                },
            },
        }

        return stats

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile value"""
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        weight = index - lower_index

        return (
            sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
        )

    def print_summary(self, test_name: str = "Performance Test"):
        """Print performance summary"""
        stats = self.get_statistics()

        print(f"\n=== {test_name} Performance Summary ===")
        print("Response Time (ms):")
        print(f"  Mean: {stats['response_time']['mean']*1000:.2f}")
        print(f"  Median: {stats['response_time']['median']*1000:.2f}")
        print(f"  P95: {stats['response_time']['p95']*1000:.2f}")
        print(f"  P99: {stats['response_time']['p99']*1000:.2f}")
        print(f"  Max: {stats['response_time']['max']*1000:.2f}")

        print("\nThroughput:")
        print(f"  Requests/sec: {stats['throughput']['requests_per_second']:.2f}")
        print(f"  Success rate: {stats['throughput']['success_rate']:.2f}%")
        print(f"  Total requests: {stats['throughput']['total_requests']}")

        if stats["resources"]["memory"]["mean_mb"] > 0:
            print("\nResource Usage:")
            print(
                f"  Memory (MB): {stats['resources']['memory']['mean_mb']:.2f} avg, {stats['resources']['memory']['max_mb']:.2f} max"
            )
            print(
                f"  CPU: {stats['resources']['cpu']['mean_percent']:.1f}% avg, {stats['resources']['cpu']['max_percent']:.1f}% max"
            )


class AuthenticationLoadGenerator:
    """Generate realistic authentication load patterns"""

    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url
        self.session_count = 0
        self.lock = threading.Lock()

    async def simulate_login_flow(
        self, session: httpx.AsyncClient, user_id: int
    ) -> dict[str, Any]:
        """Simulate complete login flow for a user"""
        start_time = time.time()
        result = {
            "user_id": user_id,
            "success": False,
            "response_time": 0,
            "steps_completed": 0,
            "error": None,
        }

        try:
            # Step 1: Login
            login_start = time.time()
            login_response = await session.post(
                "/auth/login",
                json={
                    "email": f"loadtest-user-{user_id}@example.com",
                    "password": "LoadTestPassword123!",
                },
            )
            time.time() - login_start

            if login_response.status_code == 200:
                result["steps_completed"] = 1

                # Step 2: Access protected resource
                token = login_response.json().get("access_token")
                if token:
                    profile_start = time.time()
                    profile_response = await session.get(
                        "/auth/profile", headers={"Authorization": f"Bearer {token}"}
                    )
                    time.time() - profile_start

                    if profile_response.status_code == 200:
                        result["steps_completed"] = 2

                        # Step 3: Update profile (optional)
                        update_start = time.time()
                        update_response = await session.put(
                            "/auth/profile",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"full_name": f"Load Test User {user_id}"},
                        )
                        time.time() - update_start

                        if update_response.status_code in [200, 204]:
                            result["steps_completed"] = 3

                        # Step 4: Logout
                        logout_start = time.time()
                        logout_response = await session.post(
                            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
                        )
                        time.time() - logout_start

                        if logout_response.status_code in [200, 204]:
                            result["steps_completed"] = 4
                            result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        result["response_time"] = time.time() - start_time
        return result

    async def simulate_concurrent_logins(
        self, concurrent_users: int, duration_seconds: int = 60
    ) -> list[dict[str, Any]]:
        """Simulate concurrent user logins over time"""
        results = []
        end_time = time.time() + duration_seconds

        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            tasks = []
            user_id = 0

            while time.time() < end_time:
                # Launch concurrent users
                for _ in range(concurrent_users):
                    user_id += 1
                    task = asyncio.create_task(
                        self.simulate_login_flow(client, user_id)
                    )
                    tasks.append(task)

                # Wait for batch to complete
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, dict):
                        results.append(result)
                    else:
                        results.append(
                            {
                                "user_id": user_id,
                                "success": False,
                                "error": str(result),
                                "response_time": 0,
                                "steps_completed": 0,
                            }
                        )

                tasks.clear()

                # Brief pause between batches
                await asyncio.sleep(0.1)

        return results

    def generate_password_hashing_load(
        self, num_passwords: int = 100
    ) -> list[dict[str, Any]]:
        """Generate load for password hashing operations"""
        from tests.auth.test_auth_api_comprehensive import AuthenticationTestFixtures

        results = []
        passwords = [f"TestPassword{i}!" for i in range(num_passwords)]

        for i, password in enumerate(passwords):
            start_time = time.time()

            try:
                password_hash = AuthenticationTestFixtures.hash_password(password)
                hash_time = time.time() - start_time

                # Verify the hash works
                verify_start = time.time()
                is_valid = AuthenticationTestFixtures.verify_password(
                    password, password_hash
                )
                verify_time = time.time() - verify_start

                results.append(
                    {
                        "password_id": i,
                        "hash_time": hash_time,
                        "verify_time": verify_time,
                        "total_time": hash_time + verify_time,
                        "success": is_valid,
                        "hash_length": len(password_hash),
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "password_id": i,
                        "hash_time": 0,
                        "verify_time": 0,
                        "total_time": 0,
                        "success": False,
                        "error": str(e),
                        "hash_length": 0,
                    }
                )

        return results


@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationPerformance:
    """Core authentication performance tests"""

    async def test_login_endpoint_latency(self, auth_client):
        """Test login endpoint response time under normal conditions"""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()

        # Mock successful authentication
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": "perf-test-user",
                "email": "perf@example.com",
                "password_hash": "$2b$12$test.hash.value",  # Mock bcrypt hash
                "is_active": True,
            }

            with patch(
                "src.server.services.auth_service.verify_password", return_value=True
            ):
                # Warm up (JIT compilation, etc.)
                for _ in range(3):
                    auth_client.post(
                        "/auth/login",
                        json={"email": "perf@example.com", "password": "password123"},
                    )

                # Actual performance measurement
                for i in range(50):
                    start_time = time.time()
                    response = auth_client.post(
                        "/auth/login",
                        json={"email": "perf@example.com", "password": "password123"},
                    )
                    end_time = time.time()

                    response_time = end_time - start_time
                    success = response.status_code == 200

                    # Monitor system resources
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    cpu_percent = process.cpu_percent()

                    metrics.record_request(
                        response_time, success, memory_mb, cpu_percent
                    )

        metrics.stop_monitoring()
        stats = metrics.get_statistics()

        # Performance assertions
        assert (
            stats["response_time"]["p95"] < 0.2
        ), f"P95 response time should be <200ms, got {stats['response_time']['p95']*1000:.2f}ms"
        assert (
            stats["response_time"]["p99"] < 0.5
        ), f"P99 response time should be <500ms, got {stats['response_time']['p99']*1000:.2f}ms"
        assert (
            stats["response_time"]["mean"] < 0.1
        ), f"Mean response time should be <100ms, got {stats['response_time']['mean']*1000:.2f}ms"
        assert (
            stats["throughput"]["success_rate"] > 99.0
        ), f"Success rate should be >99%, got {stats['throughput']['success_rate']:.2f}%"

        metrics.print_summary("Login Endpoint Latency Test")

    async def test_jwt_token_performance(self, auth_client):
        """Test JWT token generation and validation performance"""
        from tests.auth.test_auth_api_comprehensive import AuthenticationTestFixtures

        metrics = PerformanceMetrics()
        metrics.start_monitoring()

        # Test JWT generation performance
        generation_times = []
        validation_times = []

        for i in range(100):
            # Generate JWT token
            start_time = time.time()
            token = AuthenticationTestFixtures.create_test_jwt_token(
                user_id=f"user-{i}", email=f"user{i}@example.com"
            )
            generation_time = time.time() - start_time
            generation_times.append(generation_time)

            # Validate JWT token
            start_time = time.time()
            try:
                decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
                validation_success = "sub" in decoded
            except (
                jwt.JWTError,
                jwt.ExpiredSignatureError,
                jwt.DecodeError,
                KeyError,
                ValueError,
            ) as e:
                validation_success = False
                print(f"⚠️  JWT validation failed: {type(e).__name__}: {e}")
            validation_time = time.time() - start_time
            validation_times.append(validation_time)

            total_time = generation_time + validation_time
            metrics.record_request(total_time, validation_success)

        metrics.stop_monitoring()
        stats = metrics.get_statistics()

        # JWT performance assertions
        avg_generation = statistics.mean(generation_times)
        avg_validation = statistics.mean(validation_times)

        assert (
            avg_generation < 0.01
        ), f"JWT generation should be <10ms, got {avg_generation*1000:.2f}ms"
        assert (
            avg_validation < 0.01
        ), f"JWT validation should be <10ms, got {avg_validation*1000:.2f}ms"
        assert (
            stats["throughput"]["success_rate"] == 100.0
        ), "JWT operations should have 100% success rate"

        print("\nJWT Performance:")
        print(f"  Generation: {avg_generation*1000:.2f}ms avg")
        print(f"  Validation: {avg_validation*1000:.2f}ms avg")
        print(f"  Total: {(avg_generation + avg_validation)*1000:.2f}ms avg")

    def test_password_hashing_performance(self):
        """Test password hashing and verification performance"""
        load_generator = AuthenticationLoadGenerator()
        results = load_generator.generate_password_hashing_load(50)

        # Analyze results
        hash_times = [r["hash_time"] for r in results if r["success"]]
        verify_times = [r["verify_time"] for r in results if r["success"]]
        total_times = [r["total_time"] for r in results if r["success"]]

        # Performance assertions
        avg_hash_time = statistics.mean(hash_times)
        avg_verify_time = statistics.mean(verify_times)
        avg_total_time = statistics.mean(total_times)

        # Password hashing should be slow enough to prevent brute force
        assert (
            avg_hash_time >= 0.05
        ), f"Password hashing should be ≥50ms for security, got {avg_hash_time*1000:.2f}ms"
        assert (
            avg_hash_time <= 0.5
        ), f"Password hashing should be ≤500ms for usability, got {avg_hash_time*1000:.2f}ms"

        # Verification should be consistently fast
        assert (
            avg_verify_time <= 0.05
        ), f"Password verification should be ≤50ms, got {avg_verify_time*1000:.2f}ms"

        # All operations should succeed
        success_rate = len([r for r in results if r["success"]]) / len(results) * 100
        assert (
            success_rate == 100.0
        ), f"Password hashing should have 100% success rate, got {success_rate:.2f}%"

        print("\nPassword Hashing Performance:")
        print(f"  Hashing: {avg_hash_time*1000:.2f}ms avg")
        print(f"  Verification: {avg_verify_time*1000:.2f}ms avg")
        print(f"  Total: {avg_total_time*1000:.2f}ms avg")
        print(f"  Success rate: {success_rate:.2f}%")


@pytest.mark.performance
@pytest.mark.load_testing
@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationLoadTesting:
    """Load testing for authentication system"""

    async def test_concurrent_authentication_load(self, auth_client):
        """Test system behavior under concurrent authentication load"""

        # Setup load generator
        load_generator = AuthenticationLoadGenerator()

        # Mock authentication service for load testing
        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            with patch(
                "src.server.services.auth_service.verify_password", return_value=True
            ):
                mock_get_user.return_value = {
                    "id": "load-test-user",
                    "email": "loadtest@example.com",
                    "password_hash": "$2b$12$test.hash.value",
                    "is_active": True,
                }

                # Test different concurrency levels
                concurrency_levels = [1, 5, 10, 25, 50]
                results_by_concurrency = {}

                for concurrency in concurrency_levels:
                    print(f"\nTesting concurrency level: {concurrency}")

                    # Run load test for 30 seconds
                    results = await load_generator.simulate_concurrent_logins(
                        concurrent_users=concurrency, duration_seconds=30
                    )

                    # Analyze results
                    successful_sessions = [r for r in results if r["success"]]
                    failed_sessions = [r for r in results if not r["success"]]

                    response_times = [r["response_time"] for r in successful_sessions]

                    if response_times:
                        stats = {
                            "concurrency": concurrency,
                            "total_sessions": len(results),
                            "successful_sessions": len(successful_sessions),
                            "failed_sessions": len(failed_sessions),
                            "success_rate": len(successful_sessions)
                            / len(results)
                            * 100,
                            "avg_response_time": statistics.mean(response_times),
                            "p95_response_time": self._percentile(response_times, 95),
                            "throughput": len(successful_sessions) / 30,  # per second
                        }

                        results_by_concurrency[concurrency] = stats

                        # Performance assertions
                        assert (
                            stats["success_rate"] >= 95.0
                        ), f"Success rate should be ≥95% at concurrency {concurrency}, got {stats['success_rate']:.2f}%"

                        assert (
                            stats["avg_response_time"] < 2.0
                        ), f"Average response time should be <2s at concurrency {concurrency}, got {stats['avg_response_time']:.3f}s"

                        print(f"  Success rate: {stats['success_rate']:.2f}%")
                        print(
                            f"  Avg response time: {stats['avg_response_time']*1000:.0f}ms"
                        )
                        print(
                            f"  P95 response time: {stats['p95_response_time']*1000:.0f}ms"
                        )
                        print(f"  Throughput: {stats['throughput']:.2f} sessions/sec")

                # Verify scalability - throughput should increase with concurrency (up to a point)
                throughputs = [
                    results_by_concurrency[c]["throughput"]
                    for c in sorted(concurrency_levels)
                    if c in results_by_concurrency
                ]

                if len(throughputs) > 1:
                    # Throughput should increase initially
                    assert (
                        throughputs[1] > throughputs[0]
                    ), "Throughput should increase with initial concurrency"

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile value"""
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        weight = index - lower_index

        return (
            sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
        )

    async def test_authentication_throughput_limits(self, auth_client):
        """Test maximum authentication throughput"""

        # Test rapid-fire authentication requests
        metrics = PerformanceMetrics()
        metrics.start_monitoring()

        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            with patch(
                "src.server.services.auth_service.verify_password", return_value=True
            ):
                mock_get_user.return_value = {
                    "id": "throughput-test-user",
                    "email": "throughput@example.com",
                    "password_hash": "$2b$12$test.hash.value",
                    "is_active": True,
                }

                # Rapid authentication attempts
                num_requests = 1000

                start_time = time.time()

                for i in range(num_requests):
                    request_start = time.time()
                    response = auth_client.post(
                        "/auth/login",
                        json={
                            "email": "throughput@example.com",
                            "password": "password123",
                        },
                    )
                    request_end = time.time()

                    response_time = request_end - request_start
                    success = response.status_code == 200

                    metrics.record_request(response_time, success)

                end_time = time.time()

        metrics.stop_monitoring()
        stats = metrics.get_statistics()

        total_time = end_time - start_time
        actual_throughput = num_requests / total_time

        # Throughput assertions
        assert (
            actual_throughput >= 100
        ), f"Should achieve ≥100 req/s throughput, got {actual_throughput:.2f} req/s"
        assert (
            stats["throughput"]["success_rate"] >= 99.0
        ), f"Should maintain ≥99% success rate, got {stats['throughput']['success_rate']:.2f}%"

        # Response time should remain reasonable under high throughput
        assert (
            stats["response_time"]["p95"] < 1.0
        ), f"P95 response time should be <1s under load, got {stats['response_time']['p95']*1000:.0f}ms"

        metrics.print_summary("Authentication Throughput Test")
        print(f"Actual throughput: {actual_throughput:.2f} requests/second")


@pytest.mark.performance
@pytest.mark.stress_testing
@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Auth API endpoints not yet implemented - waiting for /auth/login, /auth/register, etc."
)
class TestAuthenticationStressTesting:
    """Stress testing to find breaking points"""

    async def test_memory_usage_under_load(self, auth_client):
        """Test memory usage under sustained authentication load"""

        # Get baseline memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_measurements = []

        with patch(
            "src.server.services.auth_service.get_user_by_email"
        ) as mock_get_user:
            with patch(
                "src.server.services.auth_service.verify_password", return_value=True
            ):
                mock_get_user.return_value = {
                    "id": "memory-test-user",
                    "email": "memory@example.com",
                    "password_hash": "$2b$12$test.hash.value",
                    "is_active": True,
                }

                # Sustained load for memory testing
                for batch in range(10):  # 10 batches
                    # Process batch of requests
                    for i in range(100):  # 100 requests per batch
                        response = auth_client.post(
                            "/auth/login",
                            json={
                                "email": "memory@example.com",
                                "password": "password123",
                            },
                        )

                        # Should still respond successfully
                        assert (
                            response.status_code == 200
                        ), f"Request failed during memory stress test: batch {batch}, request {i}"

                    # Measure memory after each batch
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_measurements.append(current_memory)

                    # Force garbage collection
                    gc.collect()

                    print(f"Batch {batch+1}/10: Memory usage {current_memory:.1f}MB")

        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory

        # Memory usage assertions
        assert (
            memory_increase < 100
        ), f"Memory increase should be <100MB, got {memory_increase:.1f}MB"

        # Check for memory leaks (memory should not continuously grow)
        if len(memory_measurements) > 5:
            # Compare first half vs second half
            first_half = memory_measurements[: len(memory_measurements) // 2]
            second_half = memory_measurements[len(memory_measurements) // 2 :]

            avg_first_half = statistics.mean(first_half)
            avg_second_half = statistics.mean(second_half)

            memory_growth_rate = (
                (avg_second_half - avg_first_half) / avg_first_half * 100
            )

            assert (
                memory_growth_rate < 50
            ), f"Memory growth rate should be <50%, got {memory_growth_rate:.1f}%"

            print(f"Memory growth rate: {memory_growth_rate:.1f}%")

        print(f"Initial memory: {initial_memory:.1f}MB")
        print(f"Final memory: {final_memory:.1f}MB")
        print(f"Memory increase: {memory_increase:.1f}MB")

    async def test_error_handling_under_stress(self, auth_client):
        """Test error handling under stress conditions"""

        error_scenarios = [
            # Database connection errors
            {
                "mock_error": Exception("Database connection lost"),
                "expected_status": [500, 503],
            },
            # Service timeouts
            {
                "mock_error": TimeoutError("Service timeout"),
                "expected_status": [408, 503, 500],
            },
            # Memory pressure scenarios
            {"mock_error": MemoryError("Out of memory"), "expected_status": [500, 503]},
        ]

        for scenario in error_scenarios:
            print(f"\nTesting error scenario: {type(scenario['mock_error']).__name__}")

            with patch(
                "src.server.services.auth_service.get_user_by_email"
            ) as mock_get_user:
                # Configure mock to raise error intermittently
                call_count = 0

                def side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count % 5 == 0:  # Every 5th call fails
                        raise scenario["mock_error"]
                    return {
                        "id": "stress-test-user",
                        "email": "stress@example.com",
                        "password_hash": "$2b$12$test.hash.value",
                        "is_active": True,
                    }

                mock_get_user.side_effect = side_effect

                # Send requests during error conditions
                error_responses = []
                success_responses = []

                for i in range(20):
                    try:
                        response = auth_client.post(
                            "/auth/login",
                            json={
                                "email": "stress@example.com",
                                "password": "password123",
                            },
                        )

                        if response.status_code == 200:
                            success_responses.append(response)
                        else:
                            error_responses.append(response)

                        # Should not crash completely
                        assert (
                            response.status_code != 0
                        ), "Server should not crash completely"

                        # Error responses should be in expected range
                        if response.status_code >= 400:
                            assert response.status_code in scenario[
                                "expected_status"
                            ] + [
                                400,
                                401,
                                422,
                            ], f"Unexpected error status code: {response.status_code}"

                    except Exception as e:
                        # Client-side exceptions should be handled gracefully
                        print(f"Client exception (expected): {e}")

                # Should have some successful responses despite errors
                assert (
                    len(success_responses) > 0
                ), "Should have some successful responses even during errors"

                # Error responses should be properly formatted
                for error_response in error_responses[:5]:  # Check first few
                    try:
                        error_data = error_response.json()
                        assert (
                            "detail" in error_data or "message" in error_data
                        ), "Error responses should be properly formatted"
                    except json.JSONDecodeError:
                        # Some errors might return non-JSON responses, which is acceptable
                        pass

                print(f"  Success responses: {len(success_responses)}")
                print(f"  Error responses: {len(error_responses)}")

    async def test_extreme_payload_sizes(self, auth_client):
        """Test handling of extreme payload sizes"""

        payload_tests = [
            # Extremely long email
            {
                "email": "x" * 10000 + "@example.com",
                "password": "password123",
                "expected_status": [400, 413, 422],
            },
            # Extremely long password
            {
                "email": "test@example.com",
                "password": "x" * 100000,
                "expected_status": [400, 413, 422],
            },
            # Empty strings
            {"email": "", "password": "", "expected_status": [400, 422]},
            # Null bytes
            {
                "email": "test\x00@example.com",
                "password": "password\x00123",
                "expected_status": [400, 422],
            },
            # Unicode stress test
            {
                "email": "测试用户@example.com",
                "password": "пароль123",
                "expected_status": [200, 400, 401, 422],  # May be valid or invalid
            },
        ]

        for i, payload in enumerate(payload_tests):
            print(
                f"Testing payload {i+1}: {type(payload['email'])} email, {type(payload['password'])} password"
            )

            try:
                response = auth_client.post(
                    "/auth/login",
                    json={"email": payload["email"], "password": payload["password"]},
                )

                # Should not crash the server
                assert response.status_code != 0, "Server should not crash"
                assert (
                    response.status_code < 600
                ), "Should return valid HTTP status code"

                # Should be in expected status codes
                assert (
                    response.status_code in payload["expected_status"]
                ), f"Unexpected status {response.status_code} for payload {i+1}, expected one of {payload['expected_status']}"

                print(f"  Status: {response.status_code}")

            except Exception as e:
                # Should handle gracefully
                print(f"  Exception (should be handled): {type(e).__name__}: {e}")

                # Should not be unhandled exceptions
                assert (
                    "unhandled" not in str(e).lower()
                ), "Should not have unhandled exceptions"


# Performance benchmarking utilities
def run_performance_benchmark(
    test_name: str, test_function: Callable, iterations: int = 10
) -> dict[str, Any]:
    """Run performance benchmark for a test function"""

    results = []

    for i in range(iterations):
        start_time = time.time()

        try:
            test_function()
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)

        end_time = time.time()
        execution_time = end_time - start_time

        results.append(
            {
                "iteration": i + 1,
                "execution_time": execution_time,
                "success": success,
                "error": error,
            }
        )

    # Calculate statistics
    successful_results = [r for r in results if r["success"]]
    execution_times = [r["execution_time"] for r in successful_results]

    if execution_times:
        benchmark_stats = {
            "test_name": test_name,
            "total_iterations": iterations,
            "successful_iterations": len(successful_results),
            "success_rate": len(successful_results) / iterations * 100,
            "execution_time": {
                "mean": statistics.mean(execution_times),
                "median": statistics.median(execution_times),
                "min": min(execution_times),
                "max": max(execution_times),
                "std_dev": (
                    statistics.stdev(execution_times) if len(execution_times) > 1 else 0
                ),
            },
            "errors": [r["error"] for r in results if not r["success"]],
        }
    else:
        benchmark_stats = {
            "test_name": test_name,
            "total_iterations": iterations,
            "successful_iterations": 0,
            "success_rate": 0,
            "execution_time": None,
            "errors": [r["error"] for r in results],
        }

    return benchmark_stats


if __name__ == "__main__":
    """
    Run authentication performance tests

    Usage:
    python -m pytest tests/auth/test_auth_performance_benchmarks.py -v
    python -m pytest tests/auth/test_auth_performance_benchmarks.py -m performance -v
    python -m pytest tests/auth/test_auth_performance_benchmarks.py -m load_testing -v
    python -m pytest tests/auth/test_auth_performance_benchmarks.py -m stress_testing -v

    For detailed performance analysis:
    python -m pytest tests/auth/test_auth_performance_benchmarks.py -v -s
    """
    pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])
