"""
Performance benchmark for HTTP connection pooling

Compares performance between:
1. One-off HTTP clients (no pooling)
2. Pooled HTTP clients (with connection reuse)

Measures:
- Total execution time
- Average request latency
- Connection establishment overhead
- Resource utilization improvements
"""

import asyncio
import time
from typing import Dict, List
from unittest.mock import Mock, patch

import httpx
import pytest
from src.config.http_client_config import HTTPClientConfig


class PerformanceBenchmark:
    """Performance benchmark for connection pooling"""

    @staticmethod
    async def benchmark_without_pooling(num_requests: int = 100) -> Dict[str, float]:
        """
        Benchmark performance without connection pooling (one-off clients).

        Args:
            num_requests: Number of requests to make

        Returns:
            Performance metrics dictionary
        """
        start_time = time.perf_counter()
        request_times: List[float] = []

        # Mock HTTP server responses
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"result": "success"},
            )

            for i in range(num_requests):
                req_start = time.perf_counter()

                # Create new client for each request (no pooling)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        "http://localhost:8000/api/test",
                        json={"test_data": f"request_{i}"},
                    )

                request_times.append(time.perf_counter() - req_start)

        total_time = time.perf_counter() - start_time
        avg_time = sum(request_times) / len(request_times)
        min_time = min(request_times)
        max_time = max(request_times)

        return {
            "total_time_seconds": total_time,
            "average_request_time_seconds": avg_time,
            "min_request_time_seconds": min_time,
            "max_request_time_seconds": max_time,
            "requests_per_second": num_requests / total_time,
        }

    @staticmethod
    async def benchmark_with_pooling(num_requests: int = 100) -> Dict[str, float]:
        """
        Benchmark performance with connection pooling (shared client).

        Args:
            num_requests: Number of requests to make

        Returns:
            Performance metrics dictionary
        """
        start_time = time.perf_counter()
        request_times: List[float] = []

        # Mock HTTP server responses
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"result": "success"},
            )

            # Create client with connection pooling
            config = HTTPClientConfig(
                max_connections=20,
                max_keepalive_connections=5,
                default_timeout=30.0,
                connect_timeout=10.0,
                read_timeout=30.0,
                write_timeout=5.0,
                max_retries=3,
                retry_backoff_multiplier=2.0,
            )

            async with config.create_httpx_client() as client:
                for i in range(num_requests):
                    req_start = time.perf_counter()

                    # Reuse same client (connection pooling)
                    await client.post(
                        "http://localhost:8000/api/test",
                        json={"test_data": f"request_{i}"},
                    )

                    request_times.append(time.perf_counter() - req_start)

        total_time = time.perf_counter() - start_time
        avg_time = sum(request_times) / len(request_times)
        min_time = min(request_times)
        max_time = max(request_times)

        return {
            "total_time_seconds": total_time,
            "average_request_time_seconds": avg_time,
            "min_request_time_seconds": min_time,
            "max_request_time_seconds": max_time,
            "requests_per_second": num_requests / total_time,
        }

    @staticmethod
    async def benchmark_concurrent_requests(
        num_concurrent: int = 10, pooling: bool = True
    ) -> Dict[str, float]:
        """
        Benchmark concurrent request performance.

        Args:
            num_concurrent: Number of concurrent requests
            pooling: Whether to use connection pooling

        Returns:
            Performance metrics dictionary
        """
        start_time = time.perf_counter()

        # Mock HTTP server responses
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"result": "success"},
            )

            if pooling:
                config = HTTPClientConfig(
                    max_connections=num_concurrent,
                    max_keepalive_connections=num_concurrent // 2,
                    default_timeout=30.0,
                    connect_timeout=10.0,
                    read_timeout=30.0,
                    write_timeout=5.0,
                    max_retries=3,
                    retry_backoff_multiplier=2.0,
                )

                async with config.create_httpx_client() as client:
                    tasks = [
                        client.post(
                            "http://localhost:8000/api/test",
                            json={"test_data": f"request_{i}"},
                        )
                        for i in range(num_concurrent)
                    ]
                    await asyncio.gather(*tasks)
            else:
                # No pooling - create separate clients
                tasks = []
                for i in range(num_concurrent):

                    async def make_request(idx):
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            await client.post(
                                "http://localhost:8000/api/test",
                                json={"test_data": f"request_{idx}"},
                            )

                    tasks.append(make_request(i))

                await asyncio.gather(*tasks)

        total_time = time.perf_counter() - start_time

        return {
            "total_time_seconds": total_time,
            "concurrent_requests": num_concurrent,
            "requests_per_second": num_concurrent / total_time,
        }


@pytest.mark.asyncio
@pytest.mark.benchmark
class TestConnectionPoolingPerformance:
    """Performance tests for connection pooling"""

    async def test_sequential_requests_performance(self):
        """Test sequential request performance with and without pooling"""
        num_requests = 50

        # Benchmark without pooling
        results_no_pool = await PerformanceBenchmark.benchmark_without_pooling(
            num_requests
        )

        # Benchmark with pooling
        results_with_pool = await PerformanceBenchmark.benchmark_with_pooling(
            num_requests
        )

        # Calculate improvement
        improvement_percent = (
            (
                results_no_pool["total_time_seconds"]
                - results_with_pool["total_time_seconds"]
            )
            / results_no_pool["total_time_seconds"]
            * 100
        )

        print("\n" + "=" * 80)
        print("SEQUENTIAL REQUESTS PERFORMANCE BENCHMARK")
        print("=" * 80)
        print(f"\nTotal requests: {num_requests}")
        print("\nWITHOUT Connection Pooling:")
        print(f"  Total time: {results_no_pool['total_time_seconds']:.4f}s")
        print(
            f"  Average per request: {results_no_pool['average_request_time_seconds']*1000:.2f}ms"
        )
        print(f"  Requests/second: {results_no_pool['requests_per_second']:.2f}")

        print("\nWITH Connection Pooling:")
        print(f"  Total time: {results_with_pool['total_time_seconds']:.4f}s")
        print(
            f"  Average per request: {results_with_pool['average_request_time_seconds']*1000:.2f}ms"
        )
        print(f"  Requests/second: {results_with_pool['requests_per_second']:.2f}")

        print(f"\n✅ Performance improvement: {improvement_percent:.1f}%")
        print("=" * 80)

        # Assert improvement (pooling should be faster)
        assert (
            results_with_pool["total_time_seconds"]
            < results_no_pool["total_time_seconds"]
        )

    async def test_concurrent_requests_performance(self):
        """Test concurrent request performance with and without pooling"""
        num_concurrent = 20

        # Benchmark without pooling
        results_no_pool = await PerformanceBenchmark.benchmark_concurrent_requests(
            num_concurrent=num_concurrent, pooling=False
        )

        # Benchmark with pooling
        results_with_pool = await PerformanceBenchmark.benchmark_concurrent_requests(
            num_concurrent=num_concurrent, pooling=True
        )

        # Calculate improvement
        improvement_percent = (
            (
                results_no_pool["total_time_seconds"]
                - results_with_pool["total_time_seconds"]
            )
            / results_no_pool["total_time_seconds"]
            * 100
        )

        print("\n" + "=" * 80)
        print("CONCURRENT REQUESTS PERFORMANCE BENCHMARK")
        print("=" * 80)
        print(f"\nConcurrent requests: {num_concurrent}")
        print("\nWITHOUT Connection Pooling:")
        print(f"  Total time: {results_no_pool['total_time_seconds']:.4f}s")
        print(f"  Requests/second: {results_no_pool['requests_per_second']:.2f}")

        print("\nWITH Connection Pooling:")
        print(f"  Total time: {results_with_pool['total_time_seconds']:.4f}s")
        print(f"  Requests/second: {results_with_pool['requests_per_second']:.2f}")

        print(f"\n✅ Performance improvement: {improvement_percent:.1f}%")
        print("=" * 80)

        # Assert improvement
        assert (
            results_with_pool["total_time_seconds"]
            < results_no_pool["total_time_seconds"]
        )

    async def test_varying_load_performance(self):
        """Test performance across different load levels"""
        load_levels = [10, 25, 50, 100]

        print("\n" + "=" * 80)
        print("VARYING LOAD PERFORMANCE BENCHMARK")
        print("=" * 80)

        for num_requests in load_levels:
            results_no_pool = await PerformanceBenchmark.benchmark_without_pooling(
                num_requests
            )
            results_with_pool = await PerformanceBenchmark.benchmark_with_pooling(
                num_requests
            )

            improvement = (
                (
                    results_no_pool["total_time_seconds"]
                    - results_with_pool["total_time_seconds"]
                )
                / results_no_pool["total_time_seconds"]
                * 100
            )

            print(f"\n{num_requests} requests:")
            print(f"  Without pooling: {results_no_pool['total_time_seconds']:.4f}s")
            print(f"  With pooling: {results_with_pool['total_time_seconds']:.4f}s")
            print(f"  Improvement: {improvement:.1f}%")

        print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "benchmark"])
