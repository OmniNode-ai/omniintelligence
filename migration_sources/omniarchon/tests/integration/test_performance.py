#!/usr/bin/env python3
"""
Performance Benchmark Tests for MCP Document Indexing Pipeline

Comprehensive performance testing including:
1. Latency benchmarks (response times)
2. Throughput testing (requests per second)
3. Memory usage monitoring
4. Scalability testing (increasing load)
5. Stress testing (system limits)
6. Performance regression detection
7. Resource utilization monitoring

These tests ensure the system meets performance requirements and
can handle expected production loads without degradation.
"""

import asyncio
import gc
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil
import pytest

from .conftest import IntegrationTestClient, TestProject

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance measurement"""

    operation: str
    duration: float
    success: bool
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBenchmark:
    """Performance benchmark results"""

    operation: str
    metrics: List[PerformanceMetric]
    min_duration: float
    max_duration: float
    avg_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    success_rate: float
    throughput: float  # operations per second


class PerformanceMonitor:
    """Monitor system resources during performance tests"""

    def __init__(self):
        self.start_time = None
        self.measurements = []
        self.monitoring = False

    async def start_monitoring(self, interval: float = 1.0):
        """Start resource monitoring"""
        self.start_time = time.time()
        self.monitoring = True
        self.measurements = []

        while self.monitoring:
            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")

                measurement = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used / 1024 / 1024,
                    "disk_percent": disk.percent,
                    "process_count": len(psutil.pids()),
                }

                self.measurements.append(measurement)

            except Exception as e:
                logger.warning(f"Error collecting system metrics: {e}")

            await asyncio.sleep(interval)

    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return summary"""
        self.monitoring = False

        if not self.measurements:
            return {}

        # Calculate statistics
        cpu_values = [m["cpu_percent"] for m in self.measurements]
        memory_values = [m["memory_percent"] for m in self.measurements]

        return {
            "duration": time.time() - self.start_time if self.start_time else 0,
            "measurements_count": len(self.measurements),
            "cpu": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": statistics.mean(cpu_values),
                "median": statistics.median(cpu_values),
            },
            "memory": {
                "min": min(memory_values),
                "max": max(memory_values),
                "avg": statistics.mean(memory_values),
                "median": statistics.median(memory_values),
            },
            "peak_memory_mb": max(m["memory_used_mb"] for m in self.measurements),
        }


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
class TestLatencyBenchmarks:
    """
    Latency benchmark tests for individual operations

    These tests measure response times for critical operations
    and ensure they meet performance SLAs.
    """

    async def test_document_creation_latency(
        self, test_client: IntegrationTestClient, test_project: TestProject, benchmark
    ):
        """Benchmark document creation latency"""
        logger.info("📊 Benchmarking document creation latency")

        num_iterations = 20
        metrics = []

        for i in range(num_iterations):
            start_time = time.time()

            try:
                await test_client.create_test_document(
                    test_project,
                    f"Latency Test Doc {i}",
                    content_override={
                        "test_scenario": "latency_benchmark",
                        "iteration": i,
                        "content": f"Latency test content for iteration {i}",
                    },
                )

                duration = time.time() - start_time
                success = True

                logger.debug(f"Document {i} created in {duration:.3f}s")

            except Exception as e:
                duration = time.time() - start_time
                success = False
                logger.warning(f"Document creation {i} failed: {e}")

            metrics.append(
                PerformanceMetric(
                    operation="document_creation",
                    duration=duration,
                    success=success,
                    timestamp=datetime.now(timezone.utc),
                    metadata={"iteration": i},
                )
            )

        # Calculate benchmark statistics
        durations = [m.duration for m in metrics if m.success]
        successful_operations = len(durations)

        if durations:
            benchmark_result = PerformanceBenchmark(
                operation="document_creation",
                metrics=metrics,
                min_duration=min(durations),
                max_duration=max(durations),
                avg_duration=statistics.mean(durations),
                median_duration=statistics.median(durations),
                p95_duration=(
                    statistics.quantiles(durations, n=20)[18]
                    if len(durations) >= 20
                    else max(durations)
                ),
                p99_duration=(
                    statistics.quantiles(durations, n=100)[98]
                    if len(durations) >= 100
                    else max(durations)
                ),
                success_rate=successful_operations / num_iterations,
                throughput=(
                    successful_operations / sum(durations) if sum(durations) > 0 else 0
                ),
            )

            logger.info("📈 Document Creation Latency Results:")
            logger.info(f"  Average: {benchmark_result.avg_duration:.3f}s")
            logger.info(f"  Median: {benchmark_result.median_duration:.3f}s")
            logger.info(f"  P95: {benchmark_result.p95_duration:.3f}s")
            logger.info(f"  Success Rate: {benchmark_result.success_rate:.1%}")
            logger.info(f"  Throughput: {benchmark_result.throughput:.2f} ops/sec")

            # Performance assertions (SLA requirements)
            assert (
                benchmark_result.avg_duration <= 5.0
            ), f"Average latency too high: {benchmark_result.avg_duration:.3f}s"
            assert (
                benchmark_result.p95_duration <= 10.0
            ), f"P95 latency too high: {benchmark_result.p95_duration:.3f}s"
            assert (
                benchmark_result.success_rate >= 0.95
            ), f"Success rate too low: {benchmark_result.success_rate:.1%}"

            # Use pytest-benchmark if available
            if benchmark:
                benchmark.extra_info.update(
                    {
                        "avg_duration": benchmark_result.avg_duration,
                        "p95_duration": benchmark_result.p95_duration,
                        "success_rate": benchmark_result.success_rate,
                    }
                )
        else:
            pytest.fail("No successful document creations for latency benchmark")

        logger.info("🎉 Document creation latency benchmark passed")

    async def test_rag_query_latency(
        self, test_client: IntegrationTestClient, test_project: TestProject, benchmark
    ):
        """Benchmark RAG query latency"""
        logger.info("📊 Benchmarking RAG query latency")

        # First create a document to ensure we have something to query
        document = await test_client.create_test_document(
            test_project,
            "RAG Query Latency Test Document",
            content_override={
                "test_scenario": "rag_query_latency",
                "searchable_content": "This document contains content for RAG query latency testing. "
                "It includes various keywords and phrases that should be retrievable "
                "through semantic search and vector similarity matching.",
            },
        )

        # Wait for indexing
        await test_client.wait_for_indexing(document, max_wait_seconds=30.0)

        # Test queries
        test_queries = [
            "RAG query latency testing",
            "semantic search performance",
            "vector similarity matching",
            f"document {document.id}",
            f"session {test_client.session.session_id}",
        ]

        num_iterations = 15
        all_metrics = []

        for query in test_queries:
            logger.info(f"Testing query: '{query[:30]}...'")

            for i in range(num_iterations):
                start_time = time.time()

                try:
                    mcp_request = {
                        "method": "perform_rag_query",
                        "params": {"query": query, "match_count": 5},
                    }

                    response = await test_client.http_client.post(
                        f"{test_client.session.services.mcp_server}/mcp",
                        json=mcp_request,
                        timeout=10.0,
                    )

                    duration = time.time() - start_time
                    success = response.status_code == 200

                    if success:
                        result = response.json()
                        results_count = len(result.get("result", {}).get("results", []))
                        metadata = {
                            "query": query,
                            "iteration": i,
                            "results_count": results_count,
                        }
                    else:
                        metadata = {
                            "query": query,
                            "iteration": i,
                            "error_status": response.status_code,
                        }

                except Exception as e:
                    duration = time.time() - start_time
                    success = False
                    metadata = {"query": query, "iteration": i, "error": str(e)}

                all_metrics.append(
                    PerformanceMetric(
                        operation="rag_query",
                        duration=duration,
                        success=success,
                        timestamp=datetime.now(timezone.utc),
                        metadata=metadata,
                    )
                )

        # Calculate benchmark statistics
        durations = [m.duration for m in all_metrics if m.success]
        successful_operations = len(durations)

        if durations:
            benchmark_result = PerformanceBenchmark(
                operation="rag_query",
                metrics=all_metrics,
                min_duration=min(durations),
                max_duration=max(durations),
                avg_duration=statistics.mean(durations),
                median_duration=statistics.median(durations),
                p95_duration=(
                    statistics.quantiles(durations, n=20)[18]
                    if len(durations) >= 20
                    else max(durations)
                ),
                p99_duration=(
                    statistics.quantiles(durations, n=100)[98]
                    if len(durations) >= 100
                    else max(durations)
                ),
                success_rate=successful_operations / len(all_metrics),
                throughput=(
                    successful_operations / sum(durations) if sum(durations) > 0 else 0
                ),
            )

            logger.info("📈 RAG Query Latency Results:")
            logger.info(f"  Average: {benchmark_result.avg_duration:.3f}s")
            logger.info(f"  Median: {benchmark_result.median_duration:.3f}s")
            logger.info(f"  P95: {benchmark_result.p95_duration:.3f}s")
            logger.info(f"  Success Rate: {benchmark_result.success_rate:.1%}")
            logger.info(f"  Throughput: {benchmark_result.throughput:.2f} queries/sec")

            # Performance assertions (SLA requirements)
            assert (
                benchmark_result.avg_duration <= 2.0
            ), f"Average query latency too high: {benchmark_result.avg_duration:.3f}s"
            assert (
                benchmark_result.p95_duration <= 5.0
            ), f"P95 query latency too high: {benchmark_result.p95_duration:.3f}s"
            assert (
                benchmark_result.success_rate >= 0.90
            ), f"Query success rate too low: {benchmark_result.success_rate:.1%}"

            # Use pytest-benchmark if available
            if benchmark:
                benchmark.extra_info.update(
                    {
                        "avg_duration": benchmark_result.avg_duration,
                        "p95_duration": benchmark_result.p95_duration,
                        "success_rate": benchmark_result.success_rate,
                    }
                )
        else:
            pytest.fail("No successful RAG queries for latency benchmark")

        logger.info("🎉 RAG query latency benchmark passed")

    async def test_indexing_pipeline_latency(
        self, test_client: IntegrationTestClient, test_project: TestProject, benchmark
    ):
        """Benchmark complete indexing pipeline latency (creation to searchability)"""
        logger.info("📊 Benchmarking complete indexing pipeline latency")

        num_iterations = 10
        metrics = []

        for i in range(num_iterations):
            pipeline_start = time.time()

            try:
                # Step 1: Create document
                creation_start = time.time()
                document = await test_client.create_test_document(
                    test_project,
                    f"Pipeline Latency Test {i}",
                    content_override={
                        "test_scenario": "pipeline_latency",
                        "iteration": i,
                        "pipeline_test": True,
                        "unique_content": f"Pipeline test document {i} with unique content for searching",
                    },
                )
                creation_time = time.time() - creation_start

                # Step 2: Wait for indexing
                indexing_start = time.time()
                indexing_success = await test_client.wait_for_indexing(
                    document, max_wait_seconds=45.0
                )
                indexing_time = time.time() - indexing_start

                # Step 3: Test retrievability
                rag_start = time.time()
                rag_success = await test_client.test_rag_retrievability(document)
                rag_time = time.time() - rag_start

                total_duration = time.time() - pipeline_start
                success = indexing_success and rag_success

                logger.debug(
                    f"Pipeline {i}: creation={creation_time:.2f}s, indexing={indexing_time:.2f}s, "
                    f"rag={rag_time:.2f}s, total={total_duration:.2f}s"
                )

            except Exception as e:
                total_duration = time.time() - pipeline_start
                success = False
                creation_time = indexing_time = rag_time = 0
                logger.warning(f"Pipeline test {i} failed: {e}")

            metrics.append(
                PerformanceMetric(
                    operation="indexing_pipeline",
                    duration=total_duration,
                    success=success,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "iteration": i,
                        "creation_time": creation_time,
                        "indexing_time": indexing_time,
                        "rag_time": rag_time,
                    },
                )
            )

        # Calculate benchmark statistics
        durations = [m.duration for m in metrics if m.success]
        successful_operations = len(durations)

        if durations:
            benchmark_result = PerformanceBenchmark(
                operation="indexing_pipeline",
                metrics=metrics,
                min_duration=min(durations),
                max_duration=max(durations),
                avg_duration=statistics.mean(durations),
                median_duration=statistics.median(durations),
                p95_duration=(
                    statistics.quantiles(durations, n=20)[18]
                    if len(durations) >= 20
                    else max(durations)
                ),
                p99_duration=(
                    statistics.quantiles(durations, n=100)[98]
                    if len(durations) >= 100
                    else max(durations)
                ),
                success_rate=successful_operations / num_iterations,
                throughput=(
                    successful_operations / sum(durations) if sum(durations) > 0 else 0
                ),
            )

            # Calculate sub-operation averages
            creation_times = [m.metadata["creation_time"] for m in metrics if m.success]
            indexing_times = [m.metadata["indexing_time"] for m in metrics if m.success]
            rag_times = [m.metadata["rag_time"] for m in metrics if m.success]

            logger.info("📈 Complete Pipeline Latency Results:")
            logger.info(f"  Average Total: {benchmark_result.avg_duration:.3f}s")
            logger.info(f"  Average Creation: {statistics.mean(creation_times):.3f}s")
            logger.info(f"  Average Indexing: {statistics.mean(indexing_times):.3f}s")
            logger.info(f"  Average RAG: {statistics.mean(rag_times):.3f}s")
            logger.info(f"  P95: {benchmark_result.p95_duration:.3f}s")
            logger.info(f"  Success Rate: {benchmark_result.success_rate:.1%}")
            logger.info(
                f"  Throughput: {benchmark_result.throughput:.2f} pipelines/sec"
            )

            # Performance assertions (SLA requirements)
            assert (
                benchmark_result.avg_duration <= 30.0
            ), f"Average pipeline latency too high: {benchmark_result.avg_duration:.3f}s"
            assert (
                benchmark_result.p95_duration <= 45.0
            ), f"P95 pipeline latency too high: {benchmark_result.p95_duration:.3f}s"
            assert (
                benchmark_result.success_rate >= 0.80
            ), f"Pipeline success rate too low: {benchmark_result.success_rate:.1%}"

            # Use pytest-benchmark if available
            if benchmark:
                benchmark.extra_info.update(
                    {
                        "avg_duration": benchmark_result.avg_duration,
                        "p95_duration": benchmark_result.p95_duration,
                        "success_rate": benchmark_result.success_rate,
                    }
                )
        else:
            pytest.fail("No successful pipeline operations for latency benchmark")

        logger.info("🎉 Complete pipeline latency benchmark passed")


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
class TestThroughputBenchmarks:
    """
    Throughput benchmark tests for system capacity

    These tests measure how many operations the system can handle
    per unit time under various load conditions.
    """

    async def test_document_creation_throughput(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Benchmark document creation throughput"""
        logger.info("📊 Benchmarking document creation throughput")

        # Start resource monitoring
        monitor = PerformanceMonitor()
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        try:
            # Test parameters
            test_duration = 30.0  # seconds
            concurrent_workers = 5

            # Statistics tracking
            successful_operations = 0
            failed_operations = 0
            total_operations = 0
            start_time = time.time()

            async def worker(worker_id: int):
                nonlocal successful_operations, failed_operations, total_operations
                worker_operations = 0

                while time.time() - start_time < test_duration:
                    try:
                        await test_client.create_test_document(
                            test_project,
                            f"Throughput Test W{worker_id} Doc{worker_operations}",
                            content_override={
                                "test_scenario": "throughput_test",
                                "worker_id": worker_id,
                                "worker_operations": worker_operations,
                                "timestamp": time.time(),
                            },
                        )

                        successful_operations += 1
                        worker_operations += 1

                    except Exception as e:
                        failed_operations += 1
                        logger.warning(f"Worker {worker_id} operation failed: {e}")

                    total_operations += 1

                return worker_operations

            # Run workers concurrently
            workers = [worker(i) for i in range(concurrent_workers)]
            await asyncio.gather(*workers, return_exceptions=True)

            actual_duration = time.time() - start_time

        finally:
            # Stop monitoring
            monitor.stop_monitoring()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Calculate results
        resource_stats = monitor.stop_monitoring()
        throughput = successful_operations / actual_duration
        error_rate = failed_operations / total_operations if total_operations > 0 else 0

        logger.info("📈 Document Creation Throughput Results:")
        logger.info(f"  Duration: {actual_duration:.2f}s")
        logger.info(f"  Successful Operations: {successful_operations}")
        logger.info(f"  Failed Operations: {failed_operations}")
        logger.info(f"  Throughput: {throughput:.2f} docs/sec")
        logger.info(f"  Error Rate: {error_rate:.1%}")
        logger.info(f"  Concurrent Workers: {concurrent_workers}")

        if resource_stats:
            logger.info(f"  Peak CPU: {resource_stats['cpu']['max']:.1f}%")
            logger.info(f"  Peak Memory: {resource_stats['memory']['max']:.1f}%")

        # Performance assertions
        assert throughput >= 1.0, f"Throughput too low: {throughput:.2f} docs/sec"
        assert error_rate <= 0.05, f"Error rate too high: {error_rate:.1%}"
        assert (
            successful_operations >= 20
        ), f"Too few successful operations: {successful_operations}"

        logger.info("🎉 Document creation throughput benchmark passed")

    async def test_rag_query_throughput(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Benchmark RAG query throughput"""
        logger.info("📊 Benchmarking RAG query throughput")

        # First create documents to query
        logger.info("Creating test documents for throughput testing...")
        for i in range(5):
            await test_client.create_test_document(
                test_project,
                f"Throughput Query Test Doc {i}",
                content_override={
                    "test_scenario": "query_throughput",
                    "document_number": i,
                    "searchable_content": f"Throughput test document {i} with unique searchable content "
                    f"for performance benchmarking and load testing purposes.",
                },
            )

        # Wait for all documents to be indexed
        await asyncio.sleep(30.0)  # Give time for indexing

        # Start resource monitoring
        monitor = PerformanceMonitor()
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        try:
            # Test parameters
            test_duration = 20.0  # seconds
            concurrent_workers = 8

            # Query variations
            test_queries = [
                "throughput test",
                "performance benchmarking",
                "load testing",
                "searchable content",
                f"session {test_client.session.session_id}",
            ]

            # Statistics tracking
            successful_queries = 0
            failed_queries = 0
            total_queries = 0
            start_time = time.time()

            async def query_worker(worker_id: int):
                nonlocal successful_queries, failed_queries, total_queries
                worker_queries = 0
                query_index = 0

                while time.time() - start_time < test_duration:
                    try:
                        query = test_queries[query_index % len(test_queries)]

                        mcp_request = {
                            "method": "perform_rag_query",
                            "params": {
                                "query": f"{query} worker{worker_id}",
                                "match_count": 3,
                            },
                        }

                        response = await test_client.http_client.post(
                            f"{test_client.session.services.mcp_server}/mcp",
                            json=mcp_request,
                            timeout=5.0,
                        )

                        if response.status_code == 200:
                            successful_queries += 1
                        else:
                            failed_queries += 1

                        worker_queries += 1
                        query_index += 1

                    except Exception as e:
                        failed_queries += 1
                        logger.debug(f"Query worker {worker_id} operation failed: {e}")

                    total_queries += 1

                return worker_queries

            # Run query workers concurrently
            workers = [query_worker(i) for i in range(concurrent_workers)]
            await asyncio.gather(*workers, return_exceptions=True)

            actual_duration = time.time() - start_time

        finally:
            # Stop monitoring
            monitor.stop_monitoring()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Calculate results
        resource_stats = monitor.stop_monitoring()
        throughput = successful_queries / actual_duration
        error_rate = failed_queries / total_queries if total_queries > 0 else 0

        logger.info("📈 RAG Query Throughput Results:")
        logger.info(f"  Duration: {actual_duration:.2f}s")
        logger.info(f"  Successful Queries: {successful_queries}")
        logger.info(f"  Failed Queries: {failed_queries}")
        logger.info(f"  Throughput: {throughput:.2f} queries/sec")
        logger.info(f"  Error Rate: {error_rate:.1%}")
        logger.info(f"  Concurrent Workers: {concurrent_workers}")

        if resource_stats:
            logger.info(f"  Peak CPU: {resource_stats['cpu']['max']:.1f}%")
            logger.info(f"  Peak Memory: {resource_stats['memory']['max']:.1f}%")

        # Performance assertions
        assert (
            throughput >= 5.0
        ), f"Query throughput too low: {throughput:.2f} queries/sec"
        assert error_rate <= 0.10, f"Query error rate too high: {error_rate:.1%}"
        assert (
            successful_queries >= 50
        ), f"Too few successful queries: {successful_queries}"

        logger.info("🎉 RAG query throughput benchmark passed")


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
class TestScalabilityAndStress:
    """
    Scalability and stress tests to determine system limits

    These tests push the system to its limits to understand
    maximum capacity and identify performance bottlenecks.
    """

    async def test_increasing_load_scalability(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test system behavior under increasing load"""
        logger.info("📊 Testing scalability under increasing load")

        # Test with increasing number of concurrent operations
        load_levels = [1, 2, 5, 10, 15, 20]
        results = []

        for load_level in load_levels:
            logger.info(f"Testing with {load_level} concurrent operations")

            # Start resource monitoring
            monitor = PerformanceMonitor()
            monitor_task = asyncio.create_task(monitor.start_monitoring())

            try:
                # Test parameters
                operations_per_worker = 5

                async def load_worker(worker_id: int):
                    successful = 0
                    failed = 0
                    start_time = time.time()

                    for i in range(operations_per_worker):
                        try:
                            await test_client.create_test_document(
                                test_project,
                                f"Load Test L{load_level} W{worker_id} D{i}",
                                content_override={
                                    "test_scenario": "scalability_test",
                                    "load_level": load_level,
                                    "worker_id": worker_id,
                                    "operation": i,
                                },
                            )
                            successful += 1

                        except Exception as e:
                            failed += 1
                            logger.debug(f"Load test operation failed: {e}")

                    duration = time.time() - start_time
                    return {
                        "successful": successful,
                        "failed": failed,
                        "duration": duration,
                    }

                # Run workers concurrently
                start_time = time.time()
                workers = [load_worker(i) for i in range(load_level)]
                worker_results = await asyncio.gather(*workers, return_exceptions=True)
                total_duration = time.time() - start_time

            finally:
                # Stop monitoring
                monitor.stop_monitoring()
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

            # Aggregate results
            resource_stats = monitor.stop_monitoring()
            total_successful = sum(
                r.get("successful", 0) for r in worker_results if isinstance(r, dict)
            )
            total_failed = sum(
                r.get("failed", 0) for r in worker_results if isinstance(r, dict)
            )
            total_operations = total_successful + total_failed

            throughput = total_successful / total_duration if total_duration > 0 else 0
            error_rate = total_failed / total_operations if total_operations > 0 else 0

            result = {
                "load_level": load_level,
                "total_operations": total_operations,
                "successful_operations": total_successful,
                "failed_operations": total_failed,
                "duration": total_duration,
                "throughput": throughput,
                "error_rate": error_rate,
                "resource_stats": resource_stats,
            }

            results.append(result)

            logger.info(
                f"  Load {load_level}: {throughput:.2f} ops/sec, {error_rate:.1%} error rate"
            )

            if resource_stats:
                logger.info(
                    f"  CPU: {resource_stats['cpu']['avg']:.1f}%, Memory: {resource_stats['memory']['avg']:.1f}%"
                )

            # Brief pause between load levels
            await asyncio.sleep(5.0)

        # Analyze scalability trends
        logger.info("📈 Scalability Analysis:")
        for result in results:
            logger.info(
                f"  Load {result['load_level']:2d}: "
                f"{result['throughput']:6.2f} ops/sec, "
                f"{result['error_rate']:5.1%} errors"
            )

        # Performance assertions
        # Throughput should not degrade drastically with reasonable load
        low_load_throughput = next(
            (r["throughput"] for r in results if r["load_level"] == 2), 0
        )
        high_load_throughput = next(
            (r["throughput"] for r in results if r["load_level"] == 10), 0
        )

        if low_load_throughput > 0:
            throughput_degradation = (
                low_load_throughput - high_load_throughput
            ) / low_load_throughput
            assert (
                throughput_degradation <= 0.5
            ), f"Throughput degraded too much under load: {throughput_degradation:.1%}"

        # Error rates should remain reasonable
        max_error_rate = max(r["error_rate"] for r in results)
        assert (
            max_error_rate <= 0.20
        ), f"Error rate too high under load: {max_error_rate:.1%}"

        logger.info("🎉 Scalability test passed")

    async def test_memory_usage_patterns(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test memory usage patterns under sustained load"""
        logger.info("📊 Testing memory usage patterns")

        # Start memory monitoring
        monitor = PerformanceMonitor()
        monitor_task = asyncio.create_task(monitor.start_monitoring(interval=0.5))

        try:
            # Create documents with varying sizes to test memory usage
            document_sizes = [1000, 5000, 10000, 50000, 100000]  # Characters
            operations_per_size = 3

            for size in document_sizes:
                logger.info(f"Testing memory usage with {size} character documents")

                for i in range(operations_per_size):
                    large_content = {
                        "test_scenario": "memory_usage_test",
                        "content_size": size,
                        "large_field": "X" * size,
                        "metadata": {
                            "size_category": (
                                "large"
                                if size > 20000
                                else "medium" if size > 5000 else "small"
                            ),
                            "iteration": i,
                        },
                    }

                    try:
                        await test_client.create_test_document(
                            test_project,
                            f"Memory Test {size} chars #{i}",
                            content_override=large_content,
                        )

                        logger.debug(f"Created document with {size} characters")

                        # Force garbage collection to see actual memory usage
                        gc.collect()

                        # Small delay to allow memory monitoring
                        await asyncio.sleep(1.0)

                    except Exception as e:
                        logger.warning(
                            f"Failed to create {size} character document: {e}"
                        )

            # Keep monitoring for a bit longer to see memory behavior
            await asyncio.sleep(10.0)

        finally:
            # Stop monitoring
            monitor.stop_monitoring()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Analyze memory usage
        resource_stats = monitor.stop_monitoring()

        if resource_stats:
            logger.info("📈 Memory Usage Analysis:")
            logger.info(f"  Peak Memory: {resource_stats['peak_memory_mb']:.1f} MB")
            logger.info(f"  Average Memory: {resource_stats['memory']['avg']:.1f}%")
            logger.info(
                f"  Memory Range: {resource_stats['memory']['min']:.1f}% - {resource_stats['memory']['max']:.1f}%"
            )

            # Memory usage assertions
            assert (
                resource_stats["memory"]["max"] <= 90.0
            ), f"Memory usage too high: {resource_stats['memory']['max']:.1f}%"
            assert (
                resource_stats["peak_memory_mb"] <= 2048.0
            ), f"Peak memory too high: {resource_stats['peak_memory_mb']:.1f} MB"

        logger.info("🎉 Memory usage patterns test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])
