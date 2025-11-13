"""
Performance Regression Tests for Vector Routing

Tests the performance characteristics of the vector routing system to detect
regressions and ensure optimal performance under various conditions.
"""

import asyncio
import gc
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import psutil
import pytest

# Add the search service to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))

from app import determine_collection_for_document
from engines.qdrant_adapter import QdrantAdapter


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results"""

    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    p95_time: float
    p99_time: float
    throughput: float
    memory_delta: float
    cpu_percent: float


@dataclass
class PerformanceBenchmark:
    """Performance benchmark thresholds"""

    max_avg_routing_time: float = 0.001  # 1ms average routing time
    max_p95_routing_time: float = 0.005  # 5ms 95th percentile
    max_search_time: float = 0.100  # 100ms search time
    min_throughput: float = 1000.0  # 1000 operations/second
    max_memory_growth: float = 100.0  # 100MB max memory growth
    max_cpu_percent: float = 80.0  # 80% max CPU utilization


class TestPerformanceRegression:
    """Performance regression test suite for vector routing"""

    @pytest.fixture
    def performance_benchmark(self):
        """Standard performance benchmark thresholds"""
        return PerformanceBenchmark()

    @pytest.fixture
    def mock_qdrant_adapter(self):
        """Mock QdrantAdapter for performance testing"""
        adapter = Mock(spec=QdrantAdapter)

        # Mock vector operation methods with realistic timing
        async def mock_search(*args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate 10ms search time
            return {
                "points": [
                    {"id": "test-1", "score": 0.95, "payload": {"content": "test"}},
                    {"id": "test-2", "score": 0.89, "payload": {"content": "test2"}},
                ]
            }

        async def mock_upsert(*args, **kwargs):
            await asyncio.sleep(0.005)  # Simulate 5ms upsert time
            return {"status": "completed", "points_count": 1}

        adapter.search = AsyncMock(side_effect=mock_search)
        adapter.upsert_points = AsyncMock(side_effect=mock_upsert)
        adapter.get_collection_info = AsyncMock(
            return_value={
                "status": "green",
                "points_count": 1000,
                "disk_usage": 1024 * 1024,  # 1MB
            }
        )

        return adapter

    def measure_performance(
        self, operation_func, iterations: int = 100
    ) -> PerformanceMetrics:
        """
        Measure performance metrics for a given operation.

        Args:
            operation_func: Function to measure
            iterations: Number of iterations to run

        Returns:
            PerformanceMetrics with timing and resource usage data
        """
        # Initial memory measurement
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Warm up
        for _ in range(5):
            operation_func()

        # Collect garbage before measurement
        gc.collect()

        # Performance measurement
        times = []
        cpu_percentages = []

        start_time = time.time()

        for _ in range(iterations):
            cpu_before = process.cpu_percent()
            op_start = time.perf_counter()
            operation_func()
            op_end = time.perf_counter()
            cpu_after = process.cpu_percent()

            times.append(op_end - op_start)
            cpu_percentages.append(max(cpu_before, cpu_after))

        total_time = time.time() - start_time

        # Final memory measurement
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_delta = final_memory - initial_memory

        # Calculate metrics
        times.sort()
        avg_cpu = statistics.mean(cpu_percentages) if cpu_percentages else 0.0

        return PerformanceMetrics(
            min_time=min(times),
            max_time=max(times),
            avg_time=statistics.mean(times),
            median_time=statistics.median(times),
            p95_time=times[int(0.95 * len(times))],
            p99_time=times[int(0.99 * len(times))],
            throughput=iterations / total_time,
            memory_delta=memory_delta,
            cpu_percent=avg_cpu,
        )

    def test_routing_decision_performance(self, performance_benchmark):
        """Test performance of document type routing decisions"""

        test_documents = [
            {"document_type": "technical_diagnosis"},
            {"document_type": "quality_assessment"},
            {"document_type": "code_review"},
            {"document_type": "spec"},
            {"document_type": "design"},
            {"document_type": "unknown_type"},
            {"document_type": ""},
            {},
        ]

        def routing_operation():
            for metadata in test_documents:
                determine_collection_for_document(metadata)

        metrics = self.measure_performance(routing_operation, iterations=1000)

        # Verify performance thresholds
        assert (
            metrics.avg_time < performance_benchmark.max_avg_routing_time
        ), f"Average routing time {metrics.avg_time:.6f}s exceeds threshold {performance_benchmark.max_avg_routing_time}s"

        assert (
            metrics.p95_time < performance_benchmark.max_p95_routing_time
        ), f"95th percentile routing time {metrics.p95_time:.6f}s exceeds threshold {performance_benchmark.max_p95_routing_time}s"

        assert (
            metrics.throughput > performance_benchmark.min_throughput
        ), f"Throughput {metrics.throughput:.2f} ops/sec below threshold {performance_benchmark.min_throughput}"

        assert (
            metrics.memory_delta < performance_benchmark.max_memory_growth
        ), f"Memory growth {metrics.memory_delta:.2f}MB exceeds threshold {performance_benchmark.max_memory_growth}MB"

    def test_routing_consistency_under_load(self):
        """Test that routing decisions remain consistent under high load"""

        test_metadata = {"document_type": "technical_diagnosis"}
        expected_collection = "quality_vectors"

        def concurrent_routing(iterations: int = 100):
            results = []
            for _ in range(iterations):
                result = determine_collection_for_document(test_metadata)
                results.append(result)
            return results

        # Test concurrent routing decisions
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(concurrent_routing, 50) for _ in range(10)]
            all_results = []

            for future in as_completed(futures):
                all_results.extend(future.result())

        # Verify all results are consistent
        assert len(set(all_results)) == 1, "Routing decisions inconsistent under load"
        assert (
            all_results[0] == expected_collection
        ), f"Expected {expected_collection}, got {all_results[0]}"

    @pytest.mark.asyncio
    async def test_vector_search_performance_parity(
        self, mock_qdrant_adapter, performance_benchmark
    ):
        """Test that search performance is similar across collections"""

        collections = ["archon_vectors", "quality_vectors"]
        search_metrics = {}

        for collection in collections:

            def search_operation():
                # Synchronous wrapper for async operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        mock_qdrant_adapter.search(
                            collection_name=collection,
                            query_vector=[0.1] * 1536,
                            limit=10,
                        )
                    )
                finally:
                    loop.close()

            metrics = self.measure_performance(search_operation, iterations=50)
            search_metrics[collection] = metrics

            # Verify individual collection performance
            assert (
                metrics.avg_time < performance_benchmark.max_search_time
            ), f"Search time for {collection} exceeds threshold: {metrics.avg_time:.4f}s"

        # Verify performance parity between collections (within 20%)
        archon_avg = search_metrics["archon_vectors"].avg_time
        quality_avg = search_metrics["quality_vectors"].avg_time

        performance_ratio = abs(archon_avg - quality_avg) / min(archon_avg, quality_avg)
        assert (
            performance_ratio < 0.20
        ), f"Performance difference between collections too large: {performance_ratio:.2%}"

    @pytest.mark.asyncio
    async def test_bulk_document_routing_performance(
        self, mock_qdrant_adapter, performance_benchmark
    ):
        """Test performance of bulk document routing operations"""

        # Generate diverse document types for bulk processing
        bulk_documents = []
        quality_types = [
            "technical_diagnosis",
            "quality_assessment",
            "code_review",
            "execution_report",
            "quality_report",
            "compliance_check",
            "performance_analysis",
        ]
        general_types = ["spec", "design", "note", "prp", "api", "guide"]

        for i in range(100):
            if i % 3 == 0:
                doc_type = quality_types[i % len(quality_types)]
            elif i % 3 == 1:
                doc_type = general_types[i % len(general_types)]
            else:
                doc_type = f"custom_type_{i}"

            bulk_documents.append(
                {
                    "id": f"doc_{i}",
                    "document_type": doc_type,
                    "content": f"Sample content for document {i}",
                    "metadata": {"priority": i % 5},
                }
            )

        async def bulk_routing_operation():
            """Simulate bulk document processing with routing"""
            routing_results = []
            indexing_tasks = []

            for doc in bulk_documents:
                # Route document
                collection = determine_collection_for_document(doc)
                routing_results.append((doc["id"], collection))

                # Simulate vector indexing
                indexing_task = mock_qdrant_adapter.upsert_points(
                    collection_name=collection,
                    points=[{"id": doc["id"], "vector": [0.1] * 1536, "payload": doc}],
                )
                indexing_tasks.append(indexing_task)

            # Wait for all indexing operations
            await asyncio.gather(*indexing_tasks)
            return routing_results

        # Measure bulk processing performance
        start_time = time.perf_counter()
        routing_results = await bulk_routing_operation()
        end_time = time.perf_counter()

        total_time = end_time - start_time
        throughput = len(bulk_documents) / total_time

        # Verify bulk processing performance
        assert (
            throughput > 50.0
        ), f"Bulk processing throughput too low: {throughput:.2f} docs/sec"
        assert total_time < 5.0, f"Bulk processing time too high: {total_time:.2f}s"

        # Verify routing distribution
        quality_docs = sum(
            1 for _, collection in routing_results if collection == "quality_vectors"
        )
        archon_docs = sum(
            1 for _, collection in routing_results if collection == "archon_vectors"
        )

        assert quality_docs > 0, "No documents routed to quality_vectors"
        assert archon_docs > 0, "No documents routed to archon_vectors"

    def test_memory_efficiency_during_routing(self, performance_benchmark):
        """Test memory efficiency during extended routing operations"""

        # Create a large dataset for memory testing
        large_dataset = []
        for i in range(1000):
            large_dataset.append(
                {
                    "document_type": f"type_{i % 20}",
                    "content": f"Document content {i}" * 100,  # Larger content
                    "metadata": {"index": i, "category": f"cat_{i % 5}"},
                }
            )

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Process documents in batches to simulate real usage
        batch_size = 50
        for i in range(0, len(large_dataset), batch_size):
            batch = large_dataset[i : i + batch_size]

            for doc in batch:
                determine_collection_for_document(doc)

            # Force garbage collection between batches
            gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        assert (
            memory_growth < performance_benchmark.max_memory_growth
        ), f"Memory growth {memory_growth:.2f}MB exceeds threshold {performance_benchmark.max_memory_growth}MB"

    def test_cpu_efficiency_during_routing(self, performance_benchmark):
        """Test CPU efficiency during intensive routing operations"""

        process = psutil.Process()

        # CPU-intensive routing test
        def cpu_intensive_routing():
            for _ in range(10000):
                metadata = {
                    "document_type": "technical_diagnosis",
                    "complex_field": {"nested": {"data": list(range(100))}},
                }
                determine_collection_for_document(metadata)

        # Monitor CPU usage during operation
        cpu_measurements = []

        def monitor_cpu():
            for _ in range(20):  # Monitor for 2 seconds
                cpu_measurements.append(process.cpu_percent(interval=0.1))

        # Run CPU monitoring in background
        import threading

        cpu_thread = threading.Thread(target=monitor_cpu)
        cpu_thread.start()

        # Execute CPU-intensive routing
        start_time = time.perf_counter()
        cpu_intensive_routing()
        end_time = time.perf_counter()

        cpu_thread.join()

        if cpu_measurements:
            avg_cpu = statistics.mean(cpu_measurements)
            max(cpu_measurements)

            assert (
                avg_cpu < performance_benchmark.max_cpu_percent
            ), f"Average CPU usage {avg_cpu:.2f}% exceeds threshold {performance_benchmark.max_cpu_percent}%"

            # Ensure operation completed in reasonable time
            total_time = end_time - start_time
            assert (
                total_time < 2.0
            ), f"CPU-intensive routing took too long: {total_time:.2f}s"

    @pytest.mark.parametrize(
        "document_count,expected_max_time",
        [(10, 0.001), (100, 0.005), (1000, 0.050), (10000, 0.500)],
    )
    def test_scaling_characteristics(self, document_count, expected_max_time):
        """Test that routing performance scales appropriately with document count"""

        # Generate documents for scaling test
        documents = []
        doc_types = [
            "technical_diagnosis",
            "spec",
            "design",
            "quality_assessment",
            "note",
        ]

        for i in range(document_count):
            documents.append(
                {"document_type": doc_types[i % len(doc_types)], "id": f"doc_{i}"}
            )

        def scaling_operation():
            for doc in documents:
                determine_collection_for_document(doc)

        start_time = time.perf_counter()
        scaling_operation()
        end_time = time.perf_counter()

        total_time = end_time - start_time

        assert (
            total_time < expected_max_time
        ), f"Routing {document_count} documents took {total_time:.4f}s, expected < {expected_max_time}s"

        # Verify linear or better scaling
        time_per_document = total_time / document_count
        assert (
            time_per_document < 0.001
        ), f"Time per document {time_per_document:.6f}s suggests poor scaling"

    def test_performance_regression_detection(self):
        """Test framework for detecting performance regressions"""

        # Baseline performance measurement
        baseline_iterations = 1000

        def baseline_operation():
            test_docs = [
                {"document_type": "technical_diagnosis"},
                {"document_type": "spec"},
                {"document_type": "unknown"},
            ]
            for doc in test_docs:
                determine_collection_for_document(doc)

        baseline_metrics = self.measure_performance(
            baseline_operation, baseline_iterations
        )

        # Store baseline for comparison (in real implementation, this would be persisted)
        baseline_data = {
            "avg_time": baseline_metrics.avg_time,
            "p95_time": baseline_metrics.p95_time,
            "throughput": baseline_metrics.throughput,
            "timestamp": time.time(),
        }

        # Simulate current performance measurement
        current_metrics = self.measure_performance(
            baseline_operation, baseline_iterations
        )

        # Regression detection thresholds (20% degradation)
        regression_threshold = 1.20

        avg_time_ratio = current_metrics.avg_time / baseline_data["avg_time"]
        p95_time_ratio = current_metrics.p95_time / baseline_data["p95_time"]
        throughput_ratio = baseline_data["throughput"] / current_metrics.throughput

        # Check for regressions
        assert (
            avg_time_ratio < regression_threshold
        ), f"Average time regression detected: {avg_time_ratio:.2f}x slower"

        assert (
            p95_time_ratio < regression_threshold
        ), f"P95 time regression detected: {p95_time_ratio:.2f}x slower"

        assert (
            throughput_ratio < regression_threshold
        ), f"Throughput regression detected: {throughput_ratio:.2f}x lower"

        # Performance improvement detection (optional validation)
        improvement_threshold = 0.90  # 10% improvement

        if avg_time_ratio < improvement_threshold:
            print(
                f"Performance improvement detected: {(1 - avg_time_ratio) * 100:.1f}% faster"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
