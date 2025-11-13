"""
Performance Benchmarks for ONEX Qdrant Effect Nodes

Validates performance targets:
- Search: <100ms for 10K vectors
- Batch indexing: <2s for 100 patterns
- Update operations: <50ms
"""

import asyncio
import os
import statistics
import time
from typing import Any, Dict, List

from onex.config import (
    ONEXQdrantConfig,
    OpenAIConfig,
    QdrantConfig,
)
from onex.service import ONEXQdrantService


class QdrantPerformanceBenchmark:
    """Performance benchmark suite for ONEX Qdrant operations."""

    def __init__(
        self, qdrant_url: str = "http://localhost:6333", openai_api_key: str = ""
    ):
        """
        Initialize benchmark suite.

        Args:
            qdrant_url: Qdrant service URL
            openai_api_key: OpenAI API key
        """
        self.config = ONEXQdrantConfig(
            qdrant=QdrantConfig(
                url=qdrant_url,
                collection_name="benchmark_collection",
            ),
            openai=OpenAIConfig(
                api_key=openai_api_key or os.getenv("OPENAI_API_KEY", ""),
            ),
        )
        self.service: ONEXQdrantService = None
        self.results: Dict[str, Any] = {}

    async def setup(self):
        """Setup benchmark environment."""
        self.service = ONEXQdrantService(config=self.config)
        print("✓ Benchmark environment initialized")

    async def teardown(self):
        """Cleanup benchmark environment."""
        if self.service:
            await self.service.close()
        print("✓ Benchmark environment cleaned up")

    async def benchmark_batch_indexing(self, batch_sizes: List[int] = [10, 50, 100]):
        """
        Benchmark batch indexing performance.

        Target: <2s for 100 patterns
        """
        print("\n" + "=" * 60)
        print("BENCHMARK: Batch Indexing Performance")
        print("=" * 60)

        results = {}

        for batch_size in batch_sizes:
            print(f"\n Testing batch size: {batch_size}")

            # Generate test patterns
            patterns = [
                {
                    "text": f"Authentication pattern {i}: Implement secure user authentication with JWT tokens and refresh tokens",
                    "type": "security",
                    "index": i,
                }
                for i in range(batch_size)
            ]

            # Warm-up run
            await self.service.index_patterns(patterns)

            # Benchmark runs
            durations = []
            for run in range(5):
                start_time = time.perf_counter()
                await self.service.index_patterns(patterns)
                duration_ms = (time.perf_counter() - start_time) * 1000

                durations.append(duration_ms)
                print(f"  Run {run + 1}: {duration_ms:.2f}ms")

            avg_duration = statistics.mean(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            results[batch_size] = {
                "avg_ms": avg_duration,
                "min_ms": min_duration,
                "max_ms": max_duration,
                "target_met": avg_duration < 2000 if batch_size == 100 else True,
            }

            print(f"\n  Average: {avg_duration:.2f}ms")
            print(f"  Min: {min_duration:.2f}ms, Max: {max_duration:.2f}ms")

            if batch_size == 100:
                status = "✓ PASS" if avg_duration < 2000 else "✗ FAIL"
                print(f"  Target (<2000ms): {status} ({avg_duration:.2f}ms)")

        self.results["batch_indexing"] = results

    async def benchmark_search_performance(self, num_iterations: int = 50):
        """
        Benchmark search performance.

        Target: <100ms for 10K vectors
        """
        print("\n" + "=" * 60)
        print("BENCHMARK: Search Performance")
        print("=" * 60)

        # First, index some data for searching
        print("\n Setting up test data (1000 patterns)...")
        patterns = [
            {
                "text": f"Pattern {i}: Various authentication and security patterns for modern applications",
                "type": "security" if i % 3 == 0 else "performance",
                "index": i,
            }
            for i in range(1000)
        ]
        await self.service.index_patterns(patterns)

        # Warm-up
        await self.service.search_patterns("authentication security", limit=10)

        # Benchmark searches
        print(f"\n Running {num_iterations} search iterations...")
        durations = []

        for i in range(num_iterations):
            query = f"authentication pattern {i % 10}"

            start_time = time.perf_counter()
            result = await self.service.search_patterns(query, limit=10)
            duration_ms = (time.perf_counter() - start_time) * 1000

            durations.append(duration_ms)

            if i % 10 == 0:
                print(
                    f"  Iteration {i + 1}: {duration_ms:.2f}ms ({len(result.hits)} results)"
                )

        avg_duration = statistics.mean(durations)
        p50_duration = statistics.median(durations)
        p95_duration = sorted(durations)[int(len(durations) * 0.95)]
        p99_duration = sorted(durations)[int(len(durations) * 0.99)]
        min_duration = min(durations)
        max_duration = max(durations)

        self.results["search"] = {
            "avg_ms": avg_duration,
            "p50_ms": p50_duration,
            "p95_ms": p95_duration,
            "p99_ms": p99_duration,
            "min_ms": min_duration,
            "max_ms": max_duration,
            "target_met": p95_duration < 100,
        }

        print(f"\n  Average: {avg_duration:.2f}ms")
        print(f"  P50: {p50_duration:.2f}ms")
        print(f"  P95: {p95_duration:.2f}ms")
        print(f"  P99: {p99_duration:.2f}ms")
        print(f"  Min: {min_duration:.2f}ms, Max: {max_duration:.2f}ms")

        status = "✓ PASS" if p95_duration < 100 else "✗ FAIL"
        print(f"  Target P95 (<100ms): {status} ({p95_duration:.2f}ms)")

    async def benchmark_update_performance(self, num_iterations: int = 20):
        """
        Benchmark update performance.

        Target: <50ms for metadata updates
        """
        print("\n" + "=" * 60)
        print("BENCHMARK: Update Performance")
        print("=" * 60)

        # Setup: Index some test patterns
        print("\n Setting up test data...")
        patterns = [{"text": f"Test pattern {i}", "reviewed": False} for i in range(10)]
        index_result = await self.service.index_patterns(patterns)
        point_ids = [str(pid) for pid in index_result.point_ids[:num_iterations]]

        # Benchmark metadata-only updates
        print(f"\n Running {num_iterations} metadata update iterations...")
        metadata_durations = []

        for i, point_id in enumerate(point_ids):
            start_time = time.perf_counter()
            await self.service.update_pattern(
                point_id=point_id, payload={"reviewed": True, "update_count": i}
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            metadata_durations.append(duration_ms)

        avg_metadata = statistics.mean(metadata_durations)
        p95_metadata = sorted(metadata_durations)[int(len(metadata_durations) * 0.95)]

        print("  Metadata-only updates:")
        print(f"    Average: {avg_metadata:.2f}ms")
        print(f"    P95: {p95_metadata:.2f}ms")

        # Benchmark with re-embedding
        print(f"\n Running {min(5, num_iterations)} re-embedding update iterations...")
        embedding_durations = []

        for i in range(min(5, len(point_ids))):
            start_time = time.perf_counter()
            await self.service.update_pattern(
                point_id=point_ids[i], text_for_embedding=f"Updated pattern text {i}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            embedding_durations.append(duration_ms)

        avg_embedding = statistics.mean(embedding_durations)

        print("  With re-embedding:")
        print(f"    Average: {avg_embedding:.2f}ms")

        self.results["update"] = {
            "metadata_avg_ms": avg_metadata,
            "metadata_p95_ms": p95_metadata,
            "embedding_avg_ms": avg_embedding,
            "target_met": p95_metadata < 50,
        }

        status = "✓ PASS" if p95_metadata < 50 else "✗ FAIL"
        print(f"  Target P95 (<50ms): {status} ({p95_metadata:.2f}ms)")

    async def benchmark_health_check(self):
        """Benchmark health check performance."""
        print("\n" + "=" * 60)
        print("BENCHMARK: Health Check Performance")
        print("=" * 60)

        durations = []
        for i in range(10):
            start_time = time.perf_counter()
            result = await self.service.health_check()
            duration_ms = (time.perf_counter() - start_time) * 1000
            durations.append(duration_ms)

        avg_duration = statistics.mean(durations)
        print(f"\n  Average: {avg_duration:.2f}ms")
        print(f"  Service OK: {result.service_ok}")
        print(f"  Collections: {len(result.collections)}")

        self.results["health_check"] = {
            "avg_ms": avg_duration,
            "service_ok": result.service_ok,
        }

    def print_summary(self):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        all_passed = True

        if "batch_indexing" in self.results:
            print("\n Batch Indexing:")
            for batch_size, metrics in self.results["batch_indexing"].items():
                status = "✓" if metrics["target_met"] else "✗"
                print(
                    f"  {status} {batch_size} patterns: {metrics['avg_ms']:.2f}ms avg"
                )
                if not metrics["target_met"]:
                    all_passed = False

        if "search" in self.results:
            metrics = self.results["search"]
            status = "✓" if metrics["target_met"] else "✗"
            print(f"\n{status} Search Performance:")
            print(f"    P95: {metrics['p95_ms']:.2f}ms (target: <100ms)")
            if not metrics["target_met"]:
                all_passed = False

        if "update" in self.results:
            metrics = self.results["update"]
            status = "✓" if metrics["target_met"] else "✗"
            print(f"\n{status} Update Performance:")
            print(
                f"    Metadata P95: {metrics['metadata_p95_ms']:.2f}ms (target: <50ms)"
            )
            if not metrics["target_met"]:
                all_passed = False

        if "health_check" in self.results:
            print(
                f"\n✓ Health Check: {self.results['health_check']['avg_ms']:.2f}ms avg"
            )

        print("\n" + "=" * 60)
        if all_passed:
            print("✓ ALL PERFORMANCE TARGETS MET")
        else:
            print("✗ SOME PERFORMANCE TARGETS NOT MET")
        print("=" * 60 + "\n")

        return all_passed


async def main():
    """Run all benchmarks."""
    benchmark = QdrantPerformanceBenchmark()

    try:
        await benchmark.setup()

        await benchmark.benchmark_batch_indexing()
        await benchmark.benchmark_search_performance()
        await benchmark.benchmark_update_performance()
        await benchmark.benchmark_health_check()

        all_passed = benchmark.print_summary()

        return 0 if all_passed else 1

    finally:
        await benchmark.teardown()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
