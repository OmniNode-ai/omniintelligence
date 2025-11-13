#!/usr/bin/env python3
"""
Performance Testing Script for Connection Pool Improvements

This script validates the performance improvements made to the pattern tracking
system by comparing the original vs optimized connection pooling infrastructure.

Tests:
1. Baseline performance (original client)
2. Optimized performance (new client)
3. Load testing under various concurrency levels
4. Memory usage analysis
5. Connection leak testing

Usage:
    python test_connection_pool_performance.py
    python test_connection_pool_performance.py --target-ops-sec 200
    python test_connection_pool_performance.py --max-concurrency 100
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Add the services directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """Run comprehensive performance tests for connection pooling"""

    def __init__(self, base_url: str = "http://localhost:8053"):
        self.base_url = base_url
        self.results = []

    async def run_comprehensive_test(
        self, target_ops_sec: int = 200, max_concurrency: int = 100
    ):
        """Run comprehensive performance test suite"""
        print("🚀 Starting comprehensive connection pool performance test...")
        print(
            f"📋 Target: {target_ops_sec} ops/sec, Max concurrency: {max_concurrency}"
        )

        # Test 1: Original client baseline
        print("\n📊 Test 1: Original Client Baseline")
        baseline_result = await self.test_original_client()
        self.results.append(("baseline", baseline_result))
        self.print_test_results("Original Client", baseline_result)

        # Test 2: Optimized client
        print("\n📊 Test 2: Optimized Client")
        optimized_result = await self.test_optimized_client()
        self.results.append(("optimized", optimized_result))
        self.print_test_results("Optimized Client", optimized_result)

        # Test 3: Load testing
        print("\n📊 Test 3: Load Testing (Progressive Concurrency)")
        load_results = await self.test_load_progressive(max_concurrency)
        self.results.append(("load_test", load_results))
        self.print_load_test_results(load_results)

        # Test 4: Sustained load test
        print("\n📊 Test 4: Sustained Load Test")
        sustained_result = await self.test_sustained_load(target_ops_sec)
        self.results.append(("sustained", sustained_result))
        self.print_sustained_results(sustained_result)

        # Test 5: Memory usage analysis
        print("\n📊 Test 5: Memory Usage Analysis")
        memory_result = await self.test_memory_usage()
        self.results.append(("memory", memory_result))
        self.print_memory_results(memory_result)

        # Generate final report
        await self.generate_performance_report()

    async def test_original_client(self) -> Dict[str, Any]:
        """Test original ResilientAPIClient performance"""
        try:
            from hooks.lib.resilience import ResilientAPIClient

            client = ResilientAPIClient(
                base_url=self.base_url,
                enable_caching=False,  # Disable caching for pure performance test
                enable_circuit_breaker=False,
            )

            return await self._run_client_test(client, "Original Client")

        except Exception as e:
            logger.error(f"Original client test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "throughput_ops_sec": 0,
                "avg_latency_ms": 0,
                "success_rate": 0,
            }

    async def test_optimized_client(self) -> Dict[str, Any]:
        """Test optimized ResilientAPIClient performance"""
        try:
            from hooks.lib.resilience_optimized import OptimizedResilientAPIClient

            client = OptimizedResilientAPIClient(
                base_url=self.base_url,
                enable_caching=False,  # Disable caching for pure performance test
                enable_circuit_breaker=False,
                enable_request_batching=True,
                pool_initial_size=20,
                pool_max_size=100,
                enable_adaptive_scaling=True,
            )

            return await self._run_client_test(client, "Optimized Client")

        except Exception as e:
            logger.error(f"Optimized client test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "throughput_ops_sec": 0,
                "avg_latency_ms": 0,
                "success_rate": 0,
            }

    async def _run_client_test(self, client, client_name: str) -> Dict[str, Any]:
        """Run standard test with given client"""
        num_requests = 500
        concurrency = 50

        print(
            f"   Running {num_requests} requests with {concurrency} concurrent workers..."
        )

        async def make_request(i: int) -> Dict[str, Any]:
            start_time = time.time()
            try:
                result = await client.track_pattern_resilient(
                    event_type="pattern_created",
                    pattern_id=f"test_{client_name.lower()}_{i}",
                    pattern_name=f"Test Pattern {i}",
                    pattern_type="test",
                    pattern_data={"index": i, "client": client_name},
                )
                latency_ms = (time.time() - start_time) * 1000
                return {
                    "success": result.get("success", False),
                    "latency_ms": latency_ms,
                    "cached": result.get("cached", False),
                }
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                return {"success": False, "latency_ms": latency_ms, "error": str(e)}

        # Run concurrent requests
        start_time = time.time()
        tasks = [make_request(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Process results
        successful = [r for r in results if isinstance(r, dict) and r["success"]]
        failed = [r for r in results if isinstance(r, dict) and not r["success"]]
        exceptions = [r for r in results if isinstance(r, Exception)]

        latencies = [r["latency_ms"] for r in successful]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = (
            sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else 0
        )

        throughput = len(successful) / total_time if total_time > 0 else 0
        success_rate = len(successful) / num_requests

        try:
            await client.close()
        except:
            pass

        return {
            "success": True,
            "client_name": client_name,
            "num_requests": num_requests,
            "concurrency": concurrency,
            "total_time_seconds": total_time,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "exceptions": len(exceptions),
            "throughput_ops_sec": throughput,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
        }

    async def test_load_progressive(self, max_concurrency: int) -> Dict[str, Any]:
        """Test performance with progressive concurrency increase"""
        try:
            from hooks.lib.resilience_optimized import OptimizedResilientAPIClient

            client = OptimizedResilientAPIClient(
                base_url=self.base_url,
                enable_caching=False,
                enable_circuit_breaker=False,
                enable_request_batching=True,
                pool_initial_size=30,
                pool_max_size=150,
                enable_adaptive_scaling=True,
            )

            results = []
            concurrency_levels = [10, 25, 50, 75, 100, max_concurrency]

            for concurrency in concurrency_levels:
                print(f"   Testing concurrency level: {concurrency}...")

                num_requests = concurrency * 10  # 10 requests per worker

                async def make_request(i: int):
                    start_time = time.time()
                    try:
                        result = await client.track_pattern_resilient(
                            event_type="pattern_created",
                            pattern_id=f"load_test_{concurrency}_{i}",
                            pattern_name=f"Load Test {concurrency}-{i}",
                            pattern_data={"concurrency": concurrency, "index": i},
                        )
                        latency_ms = (time.time() - start_time) * 1000
                        return result.get("success", False), latency_ms
                    except Exception:
                        latency_ms = (time.time() - start_time) * 1000
                        return False, latency_ms

                start_time = time.time()
                tasks = [make_request(i) for i in range(num_requests)]
                request_results = await asyncio.gather(*tasks, return_exceptions=True)
                total_time = time.time() - start_time

                successful = [
                    r for r in request_results if isinstance(r, tuple) and r[0]
                ]
                latencies = [r[1] for r in successful]

                result = {
                    "concurrency": concurrency,
                    "num_requests": num_requests,
                    "total_time_seconds": total_time,
                    "successful_requests": len(successful),
                    "throughput_ops_sec": (
                        len(successful) / total_time if total_time > 0 else 0
                    ),
                    "avg_latency_ms": (
                        sum(latencies) / len(latencies) if latencies else 0
                    ),
                    "p95_latency_ms": (
                        sorted(latencies)[int(len(latencies) * 0.95)]
                        if len(latencies) >= 20
                        else 0
                    ),
                    "success_rate": len(successful) / num_requests,
                }
                results.append(result)

                print(
                    f"     {concurrency} workers: {result['throughput_ops_sec']:.1f} ops/sec, "
                    f"{result['avg_latency_ms']:.1f}ms avg, {result['success_rate']:.1%} success"
                )

            await client.close()
            return {"success": True, "results": results}

        except Exception as e:
            logger.error(f"Load test failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_sustained_load(self, target_ops_sec: int) -> Dict[str, Any]:
        """Test sustained load over time"""
        try:
            from hooks.lib.resilience_optimized import OptimizedResilientAPIClient

            client = OptimizedResilientAPIClient(
                base_url=self.base_url,
                enable_caching=False,
                enable_circuit_breaker=False,
                enable_request_batching=True,
            )

            # Run sustained test for 30 seconds
            duration_seconds = 30
            concurrency = min(
                50, target_ops_sec // 4
            )  # Adjust concurrency based on target

            print(
                f"   Running sustained load test for {duration_seconds}s with {concurrency} workers..."
            )

            request_count = 0
            success_count = 0
            latencies = []
            start_time = time.time()
            end_time = start_time + duration_seconds

            async def worker():
                nonlocal request_count, success_count, latencies
                worker_id = id(asyncio.current_task())

                while time.time() < end_time:
                    try:
                        req_start = time.time()
                        result = await client.track_pattern_resilient(
                            event_type="pattern_created",
                            pattern_id=f"sustained_{worker_id}_{request_count}",
                            pattern_name=f"Sustained Test {request_count}",
                            pattern_data={
                                "worker": worker_id,
                                "request": request_count,
                            },
                        )
                        latency_ms = (time.time() - req_start) * 1000

                        request_count += 1
                        if result.get("success", False):
                            success_count += 1
                            latencies.append(latency_ms)

                        # Small delay to prevent overwhelming
                        await asyncio.sleep(0.01)

                    except Exception as e:
                        request_count += 1
                        logger.warning(f"Worker {worker_id} error: {e}")

            # Start workers
            workers = [asyncio.create_task(worker()) for _ in range(concurrency)]

            # Wait for duration
            await asyncio.sleep(duration_seconds)

            # Cancel workers
            for worker in workers:
                worker.cancel()

            # Wait for workers to finish
            await asyncio.gather(*workers, return_exceptions=True)

            actual_duration = time.time() - start_time
            throughput = success_count / actual_duration if actual_duration > 0 else 0

            await client.close()

            return {
                "success": True,
                "duration_seconds": actual_duration,
                "target_throughput": target_ops_sec,
                "actual_throughput": throughput,
                "total_requests": request_count,
                "successful_requests": success_count,
                "success_rate": (
                    success_count / request_count if request_count > 0 else 0
                ),
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                "p95_latency_ms": (
                    sorted(latencies)[int(len(latencies) * 0.95)]
                    if len(latencies) >= 20
                    else 0
                ),
                "throughput_achievement": (
                    (throughput / target_ops_sec) if target_ops_sec > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Sustained load test failed: {e}")
            return {"success": False, "error": str(e)}

    async def test_memory_usage(self) -> Dict[str, Any]:
        """Test memory usage patterns"""
        try:
            import gc

            import psutil

            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            from hooks.lib.resilience_optimized import OptimizedResilientAPIClient

            print(f"   Initial memory usage: {initial_memory:.1f} MB")

            # Create multiple client instances
            clients = []
            for i in range(10):
                client = OptimizedResilientAPIClient(
                    base_url=self.base_url,
                    enable_caching=False,
                    enable_circuit_breaker=False,
                )
                clients.append(client)

                # Make some requests
                for j in range(10):
                    await client.track_pattern_resilient(
                        event_type="pattern_created",
                        pattern_id=f"memory_test_{i}_{j}",
                        pattern_name=f"Memory Test {i}-{j}",
                        pattern_data={"i": i, "j": j},
                    )

                if i % 3 == 0:
                    memory = process.memory_info().rss / 1024 / 1024
                    print(f"   After {i+1} clients: {memory:.1f} MB")

            peak_memory = process.memory_info().rss / 1024 / 1024

            # Close all clients
            for client in clients:
                await client.close()

            # Force garbage collection
            gc.collect()
            await asyncio.sleep(1)

            final_memory = process.memory_info().rss / 1024 / 1024

            return {
                "success": True,
                "initial_memory_mb": initial_memory,
                "peak_memory_mb": peak_memory,
                "final_memory_mb": final_memory,
                "memory_growth_mb": peak_memory - initial_memory,
                "memory_leaked_mb": final_memory - initial_memory,
                "clients_created": len(clients),
                "total_requests": len(clients) * 10,
            }

        except ImportError:
            return {"success": False, "error": "psutil not available"}
        except Exception as e:
            logger.error(f"Memory test failed: {e}")
            return {"success": False, "error": str(e)}

    def print_test_results(self, test_name: str, result: Dict[str, Any]):
        """Print individual test results"""
        if not result["success"]:
            print(f"   ❌ {test_name} failed: {result.get('error', 'Unknown error')}")
            return

        print(f"   ✅ {test_name} Results:")
        print(f"      Throughput: {result['throughput_ops_sec']:.1f} ops/sec")
        print(f"      Success Rate: {result['success_rate']:.1%}")
        print(f"      Avg Latency: {result['avg_latency_ms']:.1f}ms")
        print(f"      P95 Latency: {result['p95_latency_ms']:.1f}ms")
        print(f"      Total Time: {result['total_time_seconds']:.1f}s")

    def print_load_test_results(self, result: Dict[str, Any]):
        """Print load test results"""
        if not result["success"]:
            print(f"   ❌ Load test failed: {result.get('error', 'Unknown error')}")
            return

        print("   ✅ Load Test Results:")
        max_throughput = max(r["throughput_ops_sec"] for r in result["results"])
        max(r["throughput_ops_sec"] for r in result["results"])
        print(f"      Peak Throughput: {max_throughput:.1f} ops/sec")

        for r in result["results"]:
            marker = "🏆" if r["throughput_ops_sec"] == max_throughput else "   "
            print(
                f"      {marker} {r['concurrency']:3d} workers: "
                f"{r['throughput_ops_sec']:6.1f} ops/sec, "
                f"{r['avg_latency_ms']:5.1f}ms avg, "
                f"{r['success_rate']:5.1%} success"
            )

    def print_sustained_results(self, result: Dict[str, Any]):
        """Print sustained load test results"""
        if not result["success"]:
            print(
                f"   ❌ Sustained load test failed: {result.get('error', 'Unknown error')}"
            )
            return

        print("   ✅ Sustained Load Test Results:")
        print(f"      Duration: {result['duration_seconds']:.1f}s")
        print(f"      Target: {result['target_throughput']} ops/sec")
        print(f"      Actual: {result['actual_throughput']:.1f} ops/sec")
        print(f"      Achievement: {result['throughput_achievement']:.1%}")
        print(f"      Success Rate: {result['success_rate']:.1%}")
        print(f"      Avg Latency: {result['avg_latency_ms']:.1f}ms")

    def print_memory_results(self, result: Dict[str, Any]):
        """Print memory test results"""
        if not result["success"]:
            print(f"   ❌ Memory test failed: {result.get('error', 'Unknown error')}")
            return

        print("   ✅ Memory Usage Results:")
        print(f"      Initial: {result['initial_memory_mb']:.1f} MB")
        print(f"      Peak: {result['peak_memory_mb']:.1f} MB")
        print(f"      Final: {result['final_memory_mb']:.1f} MB")
        print(f"      Growth: {result['memory_growth_mb']:.1f} MB")
        print(f"      Leaked: {result['memory_leaked_mb']:.1f} MB")

        if result["memory_leaked_mb"] > 10:
            print("      ⚠️  Possible memory leak detected!")
        elif result["memory_leaked_mb"] > 1:
            print("      ℹ️  Minor memory growth within acceptable limits")
        else:
            print("      ✅ No significant memory leak detected")

    async def generate_performance_report(self):
        """Generate comprehensive performance report"""
        print("\n📋 PERFORMANCE TEST SUMMARY")
        print("=" * 60)

        # Calculate improvements
        baseline = next((r[1] for r in self.results if r[0] == "baseline"), None)
        optimized = next((r[1] for r in self.results if r[0] == "optimized"), None)

        if baseline and optimized and baseline["success"] and optimized["success"]:
            throughput_improvement = (
                (
                    (
                        optimized["throughput_ops_sec"] / baseline["throughput_ops_sec"]
                        - 1
                    )
                    * 100
                )
                if baseline["throughput_ops_sec"] > 0
                else 0
            )
            latency_improvement = (
                ((baseline["avg_latency_ms"] / optimized["avg_latency_ms"] - 1) * 100)
                if optimized["avg_latency_ms"] > 0
                else 0
            )

            print("🎯 Performance Improvements:")
            print(
                f"   Throughput: {throughput_improvement:+.1f}% ({baseline['throughput_ops_sec']:.1f} → {optimized['throughput_ops_sec']:.1f} ops/sec)"
            )
            print(
                f"   Latency: {latency_improvement:+.1f}% ({baseline['avg_latency_ms']:.1f} → {optimized['avg_latency_ms']:.1f}ms)"
            )
            print(
                f"   Success Rate: {((optimized['success_rate'] - baseline['success_rate']) * 100):+.1f}% ({baseline['success_rate']:.1%} → {optimized['success_rate']:.1%})"
            )

        # Check target achievement
        sustained = next((r[1] for r in self.results if r[0] == "sustained"), None)
        if sustained and sustained["success"]:
            target_met = sustained["throughput_achievement"] >= 0.9  # 90% of target
            print("\n🎯 Target Achievement:")
            print(
                f"   {'✅' if target_met else '❌'} {sustained['throughput_achievement']:.1%} of target 200 ops/sec"
            )
            print(f"   Actual: {sustained['actual_throughput']:.1f} ops/sec sustained")

        # Memory check
        memory = next((r[1] for r in self.results if r[0] == "memory"), None)
        if memory and memory["success"]:
            memory_ok = memory["memory_leaked_mb"] < 5  # Less than 5MB leaked
            print("\n💾 Memory Management:")
            print(
                f"   {'✅' if memory_ok else '❌'} {memory['memory_leaked_mb']:.1f} MB memory growth"
            )

        print("\n📝 Recommendations:")

        if not baseline or not baseline["success"]:
            print("   - Fix baseline client implementation for comparison")

        if optimized and optimized["success"]:
            if optimized["throughput_ops_sec"] < 150:
                print("   - Further optimize connection pool configuration")
            if optimized["avg_latency_ms"] > 100:
                print("   - Investigate latency bottlenecks")
            if optimized["success_rate"] < 0.95:
                print("   - Improve error handling and retry logic")

        if sustained and sustained["success"]:
            if sustained["throughput_achievement"] < 0.8:
                print(
                    "   - Scale up connection pool size or investigate resource constraints"
                )

        if memory and memory["success"]:
            if memory["memory_leaked_mb"] > 5:
                print("   - Investigate and fix memory leaks")

        # Save detailed report
        report_path = Path("performance_test_report.json")
        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": {name: data for name, data in self.results},
        }
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_path}")


async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Connection Pool Performance Test")
    parser.add_argument(
        "--target-ops-sec", type=int, default=200, help="Target operations per second"
    )
    parser.add_argument(
        "--max-concurrency", type=int, default=100, help="Maximum concurrency level"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8053",
        help="Base URL for Phase 4 API",
    )

    args = parser.parse_args()

    runner = PerformanceTestRunner(args.base_url)
    await runner.run_comprehensive_test(args.target_ops_sec, args.max_concurrency)


if __name__ == "__main__":
    asyncio.run(main())
