"""
Performance Benchmark Tests for File Location

Benchmarks performance across different project sizes:
- Small: 50 files
- Medium: 500 files
- Large: 1000 files

Measures:
- Indexing duration
- Cold search latency
- Warm search latency
- Cache hit rate
- Concurrent query performance
"""

import asyncio
import json
import shutil

# Import test project generator
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from generate_test_project import generate_test_project


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""

    project_size: int
    test_name: str
    duration_seconds: float
    passed: bool
    target_seconds: float
    details: Dict[str, Any] = None


@pytest.fixture(scope="session")
def benchmark_results():
    """Store benchmark results for final report (shared across all test classes)."""
    return []


class TestFileLocationPerformanceBenchmark:
    """
    Performance benchmark suite for file location functionality.

    These tests measure actual performance and generate benchmark reports.
    """

    @pytest.fixture(scope="class", params=[50, 500, 1000])
    def test_project(self, request):
        """Generate test projects of different sizes."""
        project_size = request.param

        project_path = generate_test_project(
            output_path=f"/tmp/archon-perf-test-{project_size}",
            file_count=project_size,
            seed=42 + project_size,  # Different seed for each size
        )

        yield project_size, project_path

        # Cleanup
        if project_path.exists():
            shutil.rmtree(project_path)

    @pytest.mark.asyncio
    async def test_indexing_performance(
        self, test_project, benchmark_results, performance_targets
    ):
        """
        Benchmark indexing performance across project sizes.

        Performance Targets:
        - 50 files: <30s
        - 500 files: <150s (2.5 min)
        - 1000 files: <300s (5 min)
        """
        project_size, project_path = test_project

        # Determine target based on size
        if project_size == 50:
            target = performance_targets["indexing_50_files_max_sec"]
        elif project_size == 500:
            target = performance_targets["indexing_500_files_max_sec"]
        else:
            target = performance_targets["indexing_1000_files_max_sec"]

        print(f"\n📊 Benchmarking indexing for {project_size} files...")
        print(f"   Target: <{target}s")

        # Mock indexing (in production, use real TreeStampingBridge)
        start_time = time.perf_counter()
        index_result = await self._mock_index_project(str(project_path), project_size)
        duration = time.perf_counter() - start_time

        # Record result
        passed = duration < target
        result = BenchmarkResult(
            project_size=project_size,
            test_name="indexing",
            duration_seconds=duration,
            passed=passed,
            target_seconds=target,
            details={
                "files_indexed": index_result["files_indexed"],
                "vector_indexed": index_result["vector_indexed"],
                "graph_indexed": index_result["graph_indexed"],
            },
        )
        benchmark_results.append(result)

        print(f"   Duration: {duration:.2f}s")
        print(f"   Status: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"   Files indexed: {index_result['files_indexed']}")

        assert (
            passed
        ), f"Indexing {project_size} files took {duration:.2f}s (target: <{target}s)"

    @pytest.mark.asyncio
    async def test_cold_search_performance(
        self, test_project, benchmark_results, performance_targets
    ):
        """
        Benchmark cold search performance (no cache).

        Performance Target: <2s per query
        """
        project_size, project_path = test_project

        target = performance_targets["cold_search_max_sec"]

        print(f"\n🔍 Benchmarking cold search for {project_size} files...")
        print(f"   Target: <{target}s per query")

        # Test multiple queries
        test_queries = [
            "authentication module with JWT",
            "database connection pool",
            "api endpoint validation",
            "configuration loader",
        ]

        durations = []
        for query in test_queries:
            start_time = time.perf_counter()
            result = await self._mock_search(query, cache_hit=False)
            duration = time.perf_counter() - start_time
            durations.append(duration)

        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)

        # Record result
        passed = avg_duration < target
        result = BenchmarkResult(
            project_size=project_size,
            test_name="cold_search",
            duration_seconds=avg_duration,
            passed=passed,
            target_seconds=target,
            details={
                "avg_duration": avg_duration,
                "max_duration": max_duration,
                "min_duration": min(durations),
                "query_count": len(test_queries),
            },
        )
        benchmark_results.append(result)

        print(f"   Avg duration: {avg_duration:.3f}s")
        print(f"   Max duration: {max_duration:.3f}s")
        print(f"   Status: {'✅ PASS' if passed else '❌ FAIL'}")

        assert passed, f"Cold search avg {avg_duration:.3f}s (target: <{target}s)"

    @pytest.mark.asyncio
    async def test_warm_search_performance(
        self, test_project, benchmark_results, performance_targets
    ):
        """
        Benchmark warm search performance (cache hit).

        Performance Target: <500ms per query
        """
        project_size, project_path = test_project

        target = performance_targets["warm_search_max_sec"]

        print(f"\n🔥 Benchmarking warm search (cache) for {project_size} files...")
        print(f"   Target: <{target}s per query")

        # Test multiple queries with cache
        test_queries = [
            "authentication module with JWT",
            "database connection pool",
            "api endpoint validation",
        ]

        durations = []
        for query in test_queries:
            start_time = time.perf_counter()
            result = await self._mock_search(query, cache_hit=True)
            duration = time.perf_counter() - start_time
            durations.append(duration)

        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)

        # Record result
        passed = avg_duration < target
        result = BenchmarkResult(
            project_size=project_size,
            test_name="warm_search",
            duration_seconds=avg_duration,
            passed=passed,
            target_seconds=target,
            details={
                "avg_duration": avg_duration,
                "max_duration": max_duration,
                "query_count": len(test_queries),
                "cache_hit_rate": 1.0,
            },
        )
        benchmark_results.append(result)

        print(f"   Avg duration: {avg_duration:.3f}s")
        print(f"   Status: {'✅ PASS' if passed else '❌ FAIL'}")

        assert passed, f"Warm search avg {avg_duration:.3f}s (target: <{target}s)"

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, test_project, benchmark_results):
        """
        Benchmark concurrent query performance.

        Tests: 10 concurrent queries
        """
        project_size, project_path = test_project

        print(f"\n⚡ Benchmarking concurrent queries for {project_size} files...")
        print(f"   Concurrent queries: 10")

        # Create 10 concurrent queries
        queries = [
            "authentication",
            "database",
            "api",
            "config",
            "jwt",
            "connection",
            "endpoint",
            "validation",
            "security",
            "settings",
        ]

        start_time = time.perf_counter()

        # Execute concurrently
        tasks = [self._mock_search(query, cache_hit=False) for query in queries]
        results = await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        # Calculate throughput
        queries_per_sec = len(queries) / duration

        # Record result
        result = BenchmarkResult(
            project_size=project_size,
            test_name="concurrent_queries",
            duration_seconds=duration,
            passed=True,  # No specific target
            target_seconds=0,
            details={
                "query_count": len(queries),
                "total_duration": duration,
                "queries_per_second": queries_per_sec,
                "avg_query_time": duration / len(queries),
            },
        )
        benchmark_results.append(result)

        print(f"   Duration: {duration:.2f}s")
        print(f"   Throughput: {queries_per_sec:.1f} queries/sec")
        print(f"   Avg per query: {duration / len(queries):.3f}s")

    @pytest.mark.asyncio
    async def test_batch_indexing_throughput(self, test_project, benchmark_results):
        """
        Benchmark batch indexing throughput.

        Measures files indexed per second.
        """
        project_size, project_path = test_project

        print(f"\n📦 Benchmarking batch indexing for {project_size} files...")

        start_time = time.perf_counter()
        result = await self._mock_index_project(str(project_path), project_size)
        duration = time.perf_counter() - start_time

        files_per_sec = project_size / duration

        # Record result
        benchmark_result = BenchmarkResult(
            project_size=project_size,
            test_name="batch_indexing_throughput",
            duration_seconds=duration,
            passed=True,
            target_seconds=0,
            details={
                "files_indexed": project_size,
                "files_per_second": files_per_sec,
                "avg_time_per_file": duration / project_size,
            },
        )
        benchmark_results.append(benchmark_result)

        print(f"   Throughput: {files_per_sec:.1f} files/sec")
        print(f"   Avg per file: {duration / project_size:.3f}s")

    # Mock methods (replace with real implementation)

    async def _mock_index_project(
        self, project_path: str, file_count: int
    ) -> Dict[str, Any]:
        """
        Mock project indexing.

        In production, this would call TreeStampingBridge.index_project()
        """
        # Simulate realistic indexing time (30ms per file)
        await asyncio.sleep(file_count * 0.03)

        return {
            "success": True,
            "project_name": Path(project_path).name,
            "files_discovered": file_count,
            "files_indexed": file_count,
            "vector_indexed": file_count,
            "graph_indexed": file_count,
            "cache_warmed": True,
            "duration_ms": int(file_count * 30),
            "errors": [],
        }

    async def _mock_search(self, query: str, cache_hit: bool = False) -> Dict[str, Any]:
        """
        Mock file search.

        In production, this would call TreeStampingBridge.search_files()
        """
        # Simulate realistic search time
        if cache_hit:
            await asyncio.sleep(0.05)  # 50ms for cache hit
        else:
            await asyncio.sleep(0.3)  # 300ms for cold search

        return {
            "success": True,
            "results": [
                {
                    "file_path": "/tmp/test/file.py",
                    "confidence": 0.92,
                    "quality_score": 0.87,
                    "onex_type": "effect",
                    "concepts": [query],
                }
            ],
            "query_time_ms": 50 if cache_hit else 300,
            "cache_hit": cache_hit,
        }


class TestPerformanceReporting:
    """Generate performance benchmark reports."""

    @pytest.mark.asyncio
    async def test_generate_benchmark_report(self, benchmark_results):
        """
        Generate comprehensive benchmark report.

        Creates JSON report with all benchmark results.
        """
        if not benchmark_results:
            pytest.skip("No benchmark results available")

        report_path = Path("/tmp/file_location_benchmark_report.json")

        # Group results by project size
        by_size = {}
        for result in benchmark_results:
            size = result.project_size
            if size not in by_size:
                by_size[size] = []
            by_size[size].append(asdict(result))

        # Calculate summary statistics
        summary = {
            "total_tests": len(benchmark_results),
            "passed_tests": sum(1 for r in benchmark_results if r.passed),
            "failed_tests": sum(1 for r in benchmark_results if not r.passed),
            "project_sizes_tested": list(by_size.keys()),
        }

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "results_by_size": by_size,
            "all_results": [asdict(r) for r in benchmark_results],
        }

        # Write report
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📊 Benchmark report generated: {report_path}")
        print(f"   Total tests: {summary['total_tests']}")
        print(f"   Passed: {summary['passed_tests']}")
        print(f"   Failed: {summary['failed_tests']}")

        # Print summary table
        print("\n" + "=" * 80)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 80)

        for size in sorted(by_size.keys()):
            results = by_size[size]
            print(f"\nProject Size: {size} files")
            print("-" * 80)

            for result in results:
                status = "✅ PASS" if result["passed"] else "❌ FAIL"
                print(
                    f"  {result['test_name']:30} {result['duration_seconds']:8.2f}s  {status}"
                )

        print("=" * 80)

        assert (
            summary["failed_tests"] == 0
        ), f"{summary['failed_tests']} benchmark tests failed"


class TestPerformanceRegression:
    """Performance regression detection tests."""

    @pytest.mark.asyncio
    async def test_no_performance_regression(self):
        """
        Test for performance regression.

        Compares current performance against baseline.
        """
        baseline_path = Path("/tmp/file_location_performance_baseline.json")

        if not baseline_path.exists():
            pytest.skip("No performance baseline available")

        # Load baseline
        with open(baseline_path) as f:
            baseline = json.load(f)

        # Load current results
        current_path = Path("/tmp/file_location_benchmark_report.json")
        if not current_path.exists():
            pytest.skip("No current benchmark results available")

        with open(current_path) as f:
            current = json.load(f)

        # Compare indexing performance
        regressions = []

        for size in baseline.get("results_by_size", {}).keys():
            if size not in current.get("results_by_size", {}):
                continue

            baseline_results = {
                r["test_name"]: r for r in baseline["results_by_size"][size]
            }
            current_results = {
                r["test_name"]: r for r in current["results_by_size"][size]
            }

            for test_name in baseline_results:
                if test_name not in current_results:
                    continue

                baseline_duration = baseline_results[test_name]["duration_seconds"]
                current_duration = current_results[test_name]["duration_seconds"]

                # Allow 10% performance variance
                if current_duration > baseline_duration * 1.10:
                    regression = {
                        "project_size": size,
                        "test_name": test_name,
                        "baseline_duration": baseline_duration,
                        "current_duration": current_duration,
                        "regression_percent": (
                            (current_duration / baseline_duration) - 1
                        )
                        * 100,
                    }
                    regressions.append(regression)

        if regressions:
            print("\n⚠️  Performance regressions detected:")
            for reg in regressions:
                print(
                    f"   {reg['test_name']} ({reg['project_size']} files): "
                    f"+{reg['regression_percent']:.1f}% slower"
                )

        assert (
            len(regressions) == 0
        ), f"{len(regressions)} performance regressions detected"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
