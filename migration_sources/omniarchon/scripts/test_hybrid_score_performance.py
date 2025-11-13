#!/usr/bin/env python3
"""
Performance Test Suite for Hybrid Score API

Tests the /api/pattern-learning/hybrid/score endpoint under various load scenarios
and measures performance against targets.

Performance Targets:
- Single pattern: <50ms target (expect <10ms actual)
- 10 patterns: <200ms target (expect <50ms actual)
- 150 patterns: <2000ms target (expect <500ms actual)

Author: Archon Intelligence Team
Date: 2025-11-03
"""

import asyncio
import json
import statistics
import time
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import httpx

# ============================================================================
# Configuration
# ============================================================================

INTELLIGENCE_SERVICE_URL = "http://localhost:8053"
HYBRID_SCORE_ENDPOINT = f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/hybrid/score"

# Performance targets (milliseconds)
TARGETS = {
    "single_pattern": 50.0,
    "10_patterns": 200.0,
    "150_patterns": 2000.0,
}

# Test scenarios
TEST_SCENARIOS = [
    {"name": "single_pattern", "count": 1, "iterations": 100},
    {"name": "10_patterns_sequential", "count": 10, "iterations": 20},
    {"name": "10_patterns_parallel", "count": 10, "iterations": 20},
    {"name": "150_patterns_sequential", "count": 150, "iterations": 5},
]


# ============================================================================
# Test Data Generators
# ============================================================================


def generate_pattern(index: int, quality_score: float = 0.8) -> Dict[str, Any]:
    """Generate a test pattern with metadata"""
    return {
        "name": f"test_pattern_{index}",
        "type": "onex",
        "keywords": [
            f"keyword{index}",
            "async",
            "compute",
            "node",
            "pattern",
        ],
        "metadata": {
            "quality_score": quality_score,
            "success_rate": 0.75 + (index % 10) * 0.02,
            "confidence_score": 0.7 + (index % 10) * 0.03,
            "semantic_score": 0.65 + (index % 10) * 0.035,
        },
    }


def generate_context(index: int) -> Dict[str, Any]:
    """Generate a test context"""
    return {
        "prompt": f"Test user prompt {index} for pattern matching",
        "keywords": ["async", "compute", f"keyword{index % 5}", "pattern"],
        "task_type": "pattern_matching",
        "complexity": "moderate",
    }


def generate_request(index: int) -> Dict[str, Any]:
    """Generate a complete hybrid score request"""
    return {
        "pattern": generate_pattern(index),
        "context": generate_context(index),
        "weights": None,  # Use default weights
        "include_tree_info": False,  # Don't include tree info for performance tests
    }


# ============================================================================
# HTTP Client
# ============================================================================


class PerformanceTestClient:
    """HTTP client for performance testing"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def calculate_hybrid_score(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call hybrid score API"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/pattern-learning/hybrid/score",
                json=request,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """Check if service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# Performance Measurement
# ============================================================================


class PerformanceMetrics:
    """Track and analyze performance metrics"""

    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.latencies: List[float] = []
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def add_latency(self, latency_ms: float):
        """Add a latency measurement"""
        self.latencies.append(latency_ms)

    def add_error(self, error: str):
        """Add an error"""
        self.errors.append(error)

    def calculate_percentiles(self) -> Dict[str, float]:
        """Calculate percentile statistics"""
        if not self.latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "p100": 0}

        sorted_latencies = sorted(self.latencies)
        return {
            "p50": statistics.median(sorted_latencies),
            "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
            "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
            "p100": max(sorted_latencies),
        }

    def calculate_summary(self) -> Dict[str, Any]:
        """Calculate comprehensive summary statistics"""
        if not self.latencies:
            return {
                "scenario": self.scenario_name,
                "total_requests": 0,
                "error_count": len(self.errors),
                "error_rate": 1.0,
            }

        percentiles = self.calculate_percentiles()
        total_time = self.end_time - self.start_time

        return {
            "scenario": self.scenario_name,
            "total_requests": len(self.latencies),
            "successful_requests": len(self.latencies),
            "error_count": len(self.errors),
            "error_rate": len(self.errors) / (len(self.latencies) + len(self.errors)),
            "latencies": {
                "min_ms": min(self.latencies),
                "max_ms": max(self.latencies),
                "mean_ms": statistics.mean(self.latencies),
                "median_ms": statistics.median(self.latencies),
                "stdev_ms": (
                    statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
                ),
                "p50_ms": percentiles["p50"],
                "p95_ms": percentiles["p95"],
                "p99_ms": percentiles["p99"],
                "p100_ms": percentiles["p100"],
            },
            "throughput": {
                "total_time_s": total_time,
                "requests_per_second": (
                    len(self.latencies) / total_time if total_time > 0 else 0
                ),
            },
        }


# ============================================================================
# Test Scenarios
# ============================================================================


async def test_single_pattern(
    client: PerformanceTestClient, iterations: int
) -> PerformanceMetrics:
    """Test single pattern scoring"""
    metrics = PerformanceMetrics("single_pattern")
    metrics.start_time = time.time()

    print(f"\n🔍 Testing single pattern scoring ({iterations} iterations)...")

    for i in range(iterations):
        try:
            request = generate_request(i)
            start = time.time()
            result = await client.calculate_hybrid_score(request)
            latency_ms = (time.time() - start) * 1000

            # Validate response
            if "data" not in result or "hybrid_score" not in result["data"]:
                raise ValueError(f"Invalid response: {result}")

            metrics.add_latency(latency_ms)

            if (i + 1) % 20 == 0:
                print(f"  ✓ Completed {i + 1}/{iterations} iterations")

        except Exception as e:
            metrics.add_error(str(e))
            print(f"  ✗ Error on iteration {i + 1}: {e}")

    metrics.end_time = time.time()
    return metrics


async def test_sequential_batch(
    client: PerformanceTestClient, count: int, iterations: int
) -> PerformanceMetrics:
    """Test sequential batch scoring"""
    metrics = PerformanceMetrics(f"{count}_patterns_sequential")
    metrics.start_time = time.time()

    print(f"\n🔍 Testing {count} patterns sequential ({iterations} batches)...")

    for iteration in range(iterations):
        try:
            # Time the entire batch
            batch_start = time.time()

            for i in range(count):
                request = generate_request(iteration * count + i)
                await client.calculate_hybrid_score(request)

            batch_latency_ms = (time.time() - batch_start) * 1000
            metrics.add_latency(batch_latency_ms)

            if (iteration + 1) % 5 == 0:
                print(f"  ✓ Completed {iteration + 1}/{iterations} batches")

        except Exception as e:
            metrics.add_error(str(e))
            print(f"  ✗ Error on batch {iteration + 1}: {e}")

    metrics.end_time = time.time()
    return metrics


async def test_parallel_batch(
    client: PerformanceTestClient, count: int, iterations: int
) -> PerformanceMetrics:
    """Test parallel batch scoring"""
    metrics = PerformanceMetrics(f"{count}_patterns_parallel")
    metrics.start_time = time.time()

    print(f"\n🔍 Testing {count} patterns parallel ({iterations} batches)...")

    for iteration in range(iterations):
        try:
            # Time the entire parallel batch
            batch_start = time.time()

            # Create all requests for this batch
            requests = [generate_request(iteration * count + i) for i in range(count)]

            # Execute all in parallel
            tasks = [client.calculate_hybrid_score(req) for req in requests]
            await asyncio.gather(*tasks)

            batch_latency_ms = (time.time() - batch_start) * 1000
            metrics.add_latency(batch_latency_ms)

            if (iteration + 1) % 5 == 0:
                print(f"  ✓ Completed {iteration + 1}/{iterations} batches")

        except Exception as e:
            metrics.add_error(str(e))
            print(f"  ✗ Error on batch {iteration + 1}: {e}")

    metrics.end_time = time.time()
    return metrics


# ============================================================================
# Cache Performance Testing
# ============================================================================


async def test_cache_performance(
    client: PerformanceTestClient,
) -> Dict[str, PerformanceMetrics]:
    """Test cache performance with cold, warm, and hot scenarios"""
    results = {}

    print("\n" + "=" * 70)
    print("📊 CACHE PERFORMANCE TESTING")
    print("=" * 70)

    # Cold cache - unique patterns (0% hit rate)
    print("\n❄️  Cold Cache Test (unique patterns, 0% hit rate)...")
    cold_metrics = PerformanceMetrics("cache_cold")
    cold_metrics.start_time = time.time()

    for i in range(50):
        try:
            request = generate_request(10000 + i)  # Unique patterns
            start = time.time()
            await client.calculate_hybrid_score(request)
            latency_ms = (time.time() - start) * 1000
            cold_metrics.add_latency(latency_ms)
        except Exception as e:
            cold_metrics.add_error(str(e))

    cold_metrics.end_time = time.time()
    results["cold"] = cold_metrics
    print(f"  ✓ Cold cache: median={cold_metrics.calculate_percentiles()['p50']:.2f}ms")

    # Warm cache - 50% repeat patterns
    print("\n🌡️  Warm Cache Test (50% repeated patterns)...")
    warm_metrics = PerformanceMetrics("cache_warm")
    warm_metrics.start_time = time.time()

    for i in range(50):
        try:
            # Alternate between new and repeated patterns
            pattern_id = (i // 2) if i % 2 == 0 else (20000 + i)
            request = generate_request(pattern_id)
            start = time.time()
            await client.calculate_hybrid_score(request)
            latency_ms = (time.time() - start) * 1000
            warm_metrics.add_latency(latency_ms)
        except Exception as e:
            warm_metrics.add_error(str(e))

    warm_metrics.end_time = time.time()
    results["warm"] = warm_metrics
    print(f"  ✓ Warm cache: median={warm_metrics.calculate_percentiles()['p50']:.2f}ms")

    # Hot cache - 90% repeat patterns
    print("\n🔥 Hot Cache Test (90% repeated patterns)...")
    hot_metrics = PerformanceMetrics("cache_hot")
    hot_metrics.start_time = time.time()

    for i in range(50):
        try:
            # 90% use same 5 patterns, 10% unique
            pattern_id = (i % 5) if i % 10 != 0 else (30000 + i)
            request = generate_request(pattern_id)
            start = time.time()
            await client.calculate_hybrid_score(request)
            latency_ms = (time.time() - start) * 1000
            hot_metrics.add_latency(latency_ms)
        except Exception as e:
            hot_metrics.add_error(str(e))

    hot_metrics.end_time = time.time()
    results["hot"] = hot_metrics
    print(f"  ✓ Hot cache: median={hot_metrics.calculate_percentiles()['p50']:.2f}ms")

    return results


# ============================================================================
# Results Analysis and Reporting
# ============================================================================


def compare_to_targets(metrics: PerformanceMetrics, target_ms: float) -> Dict[str, Any]:
    """Compare results to performance targets"""
    summary = metrics.calculate_summary()
    latencies = summary["latencies"]

    # Compare median to target
    median_ms = latencies["median_ms"]
    target_met = median_ms <= target_ms
    improvement_pct = ((target_ms - median_ms) / target_ms) * 100

    return {
        "target_ms": target_ms,
        "actual_median_ms": median_ms,
        "target_met": target_met,
        "improvement_pct": improvement_pct,
        "performance_ratio": median_ms / target_ms if target_ms > 0 else 0,
    }


def print_performance_summary(all_results: Dict[str, PerformanceMetrics]):
    """Print comprehensive performance summary"""
    print("\n" + "=" * 70)
    print("📊 PERFORMANCE TEST RESULTS")
    print("=" * 70)

    for scenario_name, metrics in all_results.items():
        if "cache" in scenario_name:
            continue  # Skip cache scenarios for main summary

        summary = metrics.calculate_summary()
        latencies = summary["latencies"]

        print(f"\n{scenario_name.upper()}")
        print("-" * 70)
        print(f"Total Requests:      {summary['total_requests']}")
        print(f"Successful:          {summary['successful_requests']}")
        print(f"Error Rate:          {summary['error_rate']:.2%}")
        print(f"")
        print(f"Latency Statistics (ms):")
        print(f"  Min:               {latencies['min_ms']:.2f}")
        print(f"  Median (p50):      {latencies['median_ms']:.2f}")
        print(f"  p95:               {latencies['p95_ms']:.2f}")
        print(f"  p99:               {latencies['p99_ms']:.2f}")
        print(f"  Max:               {latencies['max_ms']:.2f}")
        print(f"  Std Dev:           {latencies['stdev_ms']:.2f}")
        print(f"")
        print(f"Throughput:")
        print(f"  Total Time:        {summary['throughput']['total_time_s']:.2f}s")
        print(
            f"  Requests/sec:      {summary['throughput']['requests_per_second']:.2f}"
        )

        # Compare to target if available
        if "single" in scenario_name:
            target = TARGETS["single_pattern"]
        elif "10_patterns" in scenario_name:
            target = TARGETS["10_patterns"]
        elif "150_patterns" in scenario_name:
            target = TARGETS["150_patterns"]
        else:
            target = None

        if target:
            comparison = compare_to_targets(metrics, target)
            print(f"")
            print(f"Target Comparison:")
            print(f"  Target:            {comparison['target_ms']:.2f}ms")
            print(f"  Actual (median):   {comparison['actual_median_ms']:.2f}ms")
            print(
                f"  Status:            {'✅ MET' if comparison['target_met'] else '❌ MISSED'}"
            )
            print(f"  Improvement:       {comparison['improvement_pct']:.1f}%")
            print(f"  Performance Ratio: {comparison['performance_ratio']:.2f}x target")


def print_cache_summary(cache_results: Dict[str, PerformanceMetrics]):
    """Print cache performance summary"""
    print("\n" + "=" * 70)
    print("📊 CACHE PERFORMANCE RESULTS")
    print("=" * 70)

    for cache_type, metrics in cache_results.items():
        summary = metrics.calculate_summary()
        latencies = summary["latencies"]

        print(f"\n{cache_type.upper()} CACHE")
        print("-" * 70)
        print(f"Median Latency:      {latencies['median_ms']:.2f}ms")
        print(f"p95 Latency:         {latencies['p95_ms']:.2f}ms")
        print(f"p99 Latency:         {latencies['p99_ms']:.2f}ms")
        print(f"Error Rate:          {summary['error_rate']:.2%}")

    # Calculate cache effectiveness
    if "cold" in cache_results and "hot" in cache_results:
        cold_median = cache_results["cold"].calculate_percentiles()["p50"]
        hot_median = cache_results["hot"].calculate_percentiles()["p50"]
        speedup = cold_median / hot_median if hot_median > 0 else 0

        print(f"\n" + "-" * 70)
        print(f"Cache Effectiveness:")
        print(f"  Cold → Hot Speedup: {speedup:.2f}x")
        print(
            f"  Improvement:        {((cold_median - hot_median) / cold_median * 100):.1f}%"
        )


def save_results_to_json(
    all_results: Dict[str, PerformanceMetrics],
    cache_results: Dict[str, PerformanceMetrics],
    output_file: str,
):
    """Save results to JSON file"""
    results_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "scenarios": {
            name: metrics.calculate_summary() for name, metrics in all_results.items()
        },
        "cache_tests": {
            name: metrics.calculate_summary() for name, metrics in cache_results.items()
        },
        "targets": TARGETS,
    }

    with open(output_file, "w") as f:
        json.dump(results_data, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")


# ============================================================================
# Main Test Runner
# ============================================================================


async def main():
    """Run all performance tests"""
    print("=" * 70)
    print("🚀 HYBRID SCORE API PERFORMANCE TEST SUITE")
    print("=" * 70)
    print(f"Service URL: {INTELLIGENCE_SERVICE_URL}")
    print(f"Test Time: {datetime.utcnow().isoformat()}")
    print("=" * 70)

    # Initialize client
    client = PerformanceTestClient(INTELLIGENCE_SERVICE_URL)

    # Health check
    print("\n🏥 Health check...")
    if not await client.health_check():
        print("❌ Service is not healthy. Please start the service first.")
        return

    print("✅ Service is healthy")

    # Run test scenarios
    all_results = {}

    # Single pattern test
    single_metrics = await test_single_pattern(client, 100)
    all_results["single_pattern"] = single_metrics

    # 10 patterns sequential
    seq_10_metrics = await test_sequential_batch(client, 10, 20)
    all_results["10_patterns_sequential"] = seq_10_metrics

    # 10 patterns parallel
    par_10_metrics = await test_parallel_batch(client, 10, 20)
    all_results["10_patterns_parallel"] = par_10_metrics

    # 150 patterns sequential
    seq_150_metrics = await test_sequential_batch(client, 150, 5)
    all_results["150_patterns_sequential"] = seq_150_metrics

    # Cache performance tests
    cache_results = await test_cache_performance(client)

    # Print summaries
    print_performance_summary(all_results)
    print_cache_summary(cache_results)

    # Save results
    output_file = f"/Volumes/PRO-G40/Code/omniarchon/performance_test_results_{int(time.time())}.json"
    save_results_to_json(all_results, cache_results, output_file)

    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
