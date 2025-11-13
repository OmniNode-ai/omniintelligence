"""
Performance Testing Framework for Enhanced Search Capabilities

Comprehensive performance testing for the integrated Knowledge feature
search capabilities, including benchmarking, load testing, and regression detection.
"""

import asyncio
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pytest


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""

    operation: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    throughput_ops_per_sec: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    error_rate: float
    timestamp: str
    test_session: str
    dataset_size: int
    concurrency_level: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PerformanceBenchmark:
    """Performance benchmark thresholds"""

    operation: str
    max_duration_ms: float
    max_memory_mb: float
    min_throughput_ops_per_sec: float
    max_latency_p95_ms: float
    max_error_rate: float

    def validate(self, metrics: PerformanceMetrics) -> dict[str, bool]:
        """Validate metrics against benchmark thresholds"""
        return {
            "duration": metrics.duration_ms <= self.max_duration_ms,
            "memory": metrics.memory_usage_mb <= self.max_memory_mb,
            "throughput": metrics.throughput_ops_per_sec
            >= self.min_throughput_ops_per_sec,
            "latency": metrics.latency_p95 <= self.max_latency_p95_ms,
            "error_rate": metrics.error_rate <= self.max_error_rate,
        }


class PerformanceTestDataGenerator:
    """Generate test data for performance testing"""

    def __init__(self, session_id: str):
        self.session_id = session_id

    def generate_search_queries(self, count: int) -> list[str]:
        """Generate diverse search queries for testing"""
        query_templates = [
            "machine learning algorithms",
            "database optimization techniques",
            "FastAPI REST API development",
            "vector embeddings similarity search",
            "microservices architecture patterns",
            "Python asyncio programming",
            "neural network training methods",
            "cloud infrastructure deployment",
            "data pipeline processing",
            "authentication security protocols",
        ]

        queries = []
        for i in range(count):
            base_query = query_templates[i % len(query_templates)]
            # Add variations to make queries unique
            variations = [
                f"{base_query} tutorial",
                f"{base_query} best practices",
                f"{base_query} performance optimization",
                f"advanced {base_query}",
                f"{base_query} implementation guide",
            ]
            variation = variations[i % len(variations)]
            queries.append(f"{variation} test_{self.session_id}_{i}")

        return queries

    def generate_test_documents(self, count: int) -> list[dict[str, Any]]:
        """Generate test documents for indexing performance tests"""
        documents = []

        for i in range(count):
            doc = {
                "id": f"perf_doc_{self.session_id}_{i}",
                "title": f"Performance Test Document {i}",
                "content": f"""
This is performance test document {i} for session {self.session_id}.

Content includes:
- Technical documentation about software development
- Code examples and implementation patterns
- Best practices and optimization techniques
- Architecture diagrams and system design
- Performance metrics and benchmarking data

Document metadata:
- Document ID: {i}
- Session: {self.session_id}
- Generated at: {datetime.now().isoformat()}
- Content length: Variable for testing different sizes
- Category: Performance testing data

Additional content to vary document sizes:
{'Lorem ipsum dolor sit amet. ' * (i % 10 + 1)}

Technical details:
- Vector embedding dimensions: 1536
- Search relevance score: Variable
- Last updated: {datetime.now().isoformat()}
                """.strip(),
                "metadata": {
                    "session_id": self.session_id,
                    "doc_index": i,
                    "category": "performance_test",
                    "size_category": (
                        "small" if i % 3 == 0 else "medium" if i % 3 == 1 else "large"
                    ),
                    "created_for": "performance_testing",
                },
                "url": f"https://perf-test-{self.session_id}.example.com/doc/{i}",
                "source_id": f"perf_source_{self.session_id}",
            }
            documents.append(doc)

        return documents


class MockPerformanceAwareSearchService:
    """Mock search service with performance simulation"""

    def __init__(self):
        self.base_latency_ms = 50
        self.latency_variance = 0.2  # 20% variance
        self.memory_usage_base_mb = 100
        self.cpu_usage_base = 20
        self.error_rate = 0.0  # No simulated errors for deterministic performance tests
        self.indexed_documents = 0
        self.concurrent_requests = 0

    async def vector_search(
        self, query: str, limit: int = 10
    ) -> tuple[dict[str, Any], PerformanceMetrics]:
        """Simulate vector search with performance tracking"""
        start_time = time.time()
        self.concurrent_requests += 1

        try:
            # Simulate realistic latency based on query complexity and system load
            query_complexity = len(query.split()) / 10.0  # Normalize by words
            load_factor = min(
                2.0, self.concurrent_requests / 10.0
            )  # Load increases latency

            simulated_latency = (
                self.base_latency_ms
                * (1 + query_complexity)
                * (1 + load_factor)
                * (1 + (hash(query) % 100) / 100 * self.latency_variance)
            ) / 1000.0

            await asyncio.sleep(simulated_latency)

            # Simulate occasional errors
            if (hash(query) % 100) / 100 < self.error_rate:
                raise Exception("Simulated search service error")

            duration_ms = (time.time() - start_time) * 1000

            # Generate realistic results
            results = [
                {
                    "id": f"result_{i}_{hash(query) % 1000}",
                    "content": f"Search result {i} for query: {query[:50]}...",
                    "similarity_score": max(0.1, 1.0 - (i * 0.1)),
                    "metadata": {"result_index": i},
                }
                for i in range(min(limit, 10))
            ]

            metrics = PerformanceMetrics(
                operation="vector_search",
                duration_ms=duration_ms,
                memory_usage_mb=self.memory_usage_base_mb + (len(results) * 2),
                cpu_usage_percent=self.cpu_usage_base + (query_complexity * 10),
                throughput_ops_per_sec=1000.0 / duration_ms if duration_ms > 0 else 0,
                latency_p50=duration_ms,
                latency_p95=duration_ms * 1.5,
                latency_p99=duration_ms * 2.0,
                error_rate=0.0,
                timestamp=datetime.now().isoformat(),
                test_session="",
                dataset_size=self.indexed_documents,
                concurrency_level=self.concurrent_requests,
            )

            return {
                "success": True,
                "query": query,
                "results": results,
                "total_results": len(results),
            }, metrics

        finally:
            self.concurrent_requests -= 1

    async def hybrid_search(
        self, query: str, limit: int = 10
    ) -> tuple[dict[str, Any], PerformanceMetrics]:
        """Simulate hybrid search (vector + keyword) with performance tracking"""
        start_time = time.time()

        # Hybrid search is typically 2-3x slower than vector search
        base_result, base_metrics = await self.vector_search(query, limit)

        # Additional processing time for keyword search and result merging
        additional_latency = 0.1 + (len(query.split()) * 0.02)
        await asyncio.sleep(additional_latency)

        duration_ms = (time.time() - start_time) * 1000

        # Enhanced results with keyword matching
        enhanced_results = []
        for i, result in enumerate(base_result["results"]):
            enhanced_result = {
                **result,
                "keyword_score": max(0.1, 1.0 - (i * 0.08)),
                "combined_score": (
                    result["similarity_score"] + max(0.1, 1.0 - (i * 0.08))
                )
                / 2,
                "search_type": "hybrid",
            }
            enhanced_results.append(enhanced_result)

        metrics = PerformanceMetrics(
            operation="hybrid_search",
            duration_ms=duration_ms,
            memory_usage_mb=base_metrics.memory_usage_mb
            * 1.3,  # More memory for hybrid
            cpu_usage_percent=base_metrics.cpu_usage_percent
            * 1.5,  # More CPU for hybrid
            throughput_ops_per_sec=1000.0 / duration_ms if duration_ms > 0 else 0,
            latency_p50=duration_ms,
            latency_p95=duration_ms * 1.4,
            latency_p99=duration_ms * 1.8,
            error_rate=0.0,
            timestamp=datetime.now().isoformat(),
            test_session="",
            dataset_size=self.indexed_documents,
            concurrency_level=self.concurrent_requests,
        )

        return {
            "success": True,
            "query": query,
            "results": enhanced_results,
            "total_results": len(enhanced_results),
            "search_type": "hybrid",
        }, metrics

    async def graph_traversal_search(
        self, query: str, max_depth: int = 3
    ) -> tuple[dict[str, Any], PerformanceMetrics]:
        """Simulate graph traversal search with performance tracking"""
        start_time = time.time()

        # Graph traversal complexity grows with depth
        base_latency = 0.2  # Higher base latency for graph operations
        depth_factor = max_depth**1.5  # Exponential growth with depth
        complexity_latency = base_latency * depth_factor

        await asyncio.sleep(complexity_latency)

        duration_ms = (time.time() - start_time) * 1000

        # Generate graph traversal results
        results = []
        for depth in range(max_depth):
            for i in range(max(1, 3 - depth)):  # Fewer results at greater depth
                result = {
                    "id": f"graph_result_{depth}_{i}_{hash(query) % 100}",
                    "content": f"Graph result at depth {depth} for query: {query[:30]}...",
                    "depth": depth,
                    "path_length": depth + 1,
                    "relationship_type": ["references", "contains", "related_to"][
                        i % 3
                    ],
                    "graph_score": max(0.1, 1.0 - (depth * 0.2) - (i * 0.1)),
                }
                results.append(result)

        metrics = PerformanceMetrics(
            operation="graph_traversal_search",
            duration_ms=duration_ms,
            memory_usage_mb=self.memory_usage_base_mb * (1 + max_depth * 0.5),
            cpu_usage_percent=self.cpu_usage_base * (1 + max_depth * 0.3),
            throughput_ops_per_sec=1000.0 / duration_ms if duration_ms > 0 else 0,
            latency_p50=duration_ms,
            latency_p95=duration_ms * 1.6,
            latency_p99=duration_ms * 2.2,
            error_rate=0.0,
            timestamp=datetime.now().isoformat(),
            test_session="",
            dataset_size=self.indexed_documents,
            concurrency_level=self.concurrent_requests,
        )

        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results),
            "max_depth": max_depth,
            "search_type": "graph_traversal",
        }, metrics


class PerformanceTestSuite:
    """Comprehensive performance test suite for enhanced search"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.search_service = MockPerformanceAwareSearchService()
        self.data_generator = PerformanceTestDataGenerator(session_id)
        self.metrics_history = []

        # Performance benchmarks
        self.benchmarks = {
            "vector_search": PerformanceBenchmark(
                operation="vector_search",
                max_duration_ms=200.0,
                max_memory_mb=150.0,
                min_throughput_ops_per_sec=5.0,
                max_latency_p95_ms=300.0,
                max_error_rate=0.02,
            ),
            "hybrid_search": PerformanceBenchmark(
                operation="hybrid_search",
                max_duration_ms=500.0,
                max_memory_mb=200.0,
                min_throughput_ops_per_sec=2.0,
                max_latency_p95_ms=750.0,
                max_error_rate=0.02,
            ),
            "graph_traversal_search": PerformanceBenchmark(
                operation="graph_traversal_search",
                max_duration_ms=1000.0,
                max_memory_mb=300.0,
                min_throughput_ops_per_sec=1.0,
                max_latency_p95_ms=1500.0,
                max_error_rate=0.05,
            ),
        }

    async def run_single_operation_benchmark(
        self, operation: str, query: str, **kwargs
    ) -> PerformanceMetrics:
        """Run benchmark for a single operation"""

        if operation == "vector_search":
            result, metrics = await self.search_service.vector_search(query, **kwargs)
        elif operation == "hybrid_search":
            result, metrics = await self.search_service.hybrid_search(query, **kwargs)
        elif operation == "graph_traversal_search":
            result, metrics = await self.search_service.graph_traversal_search(
                query, **kwargs
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")

        metrics.test_session = self.session_id
        self.metrics_history.append(metrics)

        return metrics

    async def run_load_test(
        self, operation: str, concurrent_users: int, duration_seconds: int
    ) -> list[PerformanceMetrics]:
        """Run load test with concurrent users"""

        print(
            f"🚀 Starting load test: {operation} with {concurrent_users} users for {duration_seconds}s"
        )

        queries = self.data_generator.generate_search_queries(concurrent_users * 10)
        results = []

        async def user_simulation(user_id: int):
            """Simulate a single user's search behavior"""
            user_results = []
            start_time = time.time()

            while time.time() - start_time < duration_seconds:
                query = queries[user_id % len(queries)]
                try:
                    metrics = await self.run_single_operation_benchmark(
                        operation, query
                    )
                    user_results.append(metrics)
                except Exception:
                    # Record error metrics
                    error_metrics = PerformanceMetrics(
                        operation=operation,
                        duration_ms=0,
                        memory_usage_mb=0,
                        cpu_usage_percent=0,
                        throughput_ops_per_sec=0,
                        latency_p50=0,
                        latency_p95=0,
                        latency_p99=0,
                        error_rate=1.0,
                        timestamp=datetime.now().isoformat(),
                        test_session=self.session_id,
                        dataset_size=0,
                        concurrency_level=concurrent_users,
                    )
                    user_results.append(error_metrics)

                # Realistic user think time
                await asyncio.sleep(0.5 + (hash(str(user_id)) % 100) / 100.0)

            return user_results

        # Run concurrent user simulations
        tasks = [user_simulation(i) for i in range(concurrent_users)]
        user_results = await asyncio.gather(*tasks)

        # Flatten results
        for user_result in user_results:
            results.extend(user_result)

        return results

    def calculate_aggregate_metrics(
        self, metrics_list: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Calculate aggregate performance metrics"""

        if not metrics_list:
            return {}

        durations = [m.duration_ms for m in metrics_list if m.error_rate == 0]
        error_count = sum(1 for m in metrics_list if m.error_rate > 0)

        if not durations:
            return {"error": "All requests failed"}

        return {
            "total_requests": len(metrics_list),
            "successful_requests": len(durations),
            "failed_requests": error_count,
            "error_rate": error_count / len(metrics_list),
            "avg_duration_ms": statistics.mean(durations),
            "median_duration_ms": statistics.median(durations),
            "p95_duration_ms": (
                sorted(durations)[int(len(durations) * 0.95)] if durations else 0
            ),
            "p99_duration_ms": (
                sorted(durations)[int(len(durations) * 0.99)] if durations else 0
            ),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "throughput_ops_per_sec": (
                len(durations) / (max(durations) / 1000.0) if durations else 0
            ),
            "avg_memory_mb": statistics.mean(
                [m.memory_usage_mb for m in metrics_list if m.error_rate == 0]
            ),
            "avg_cpu_percent": statistics.mean(
                [m.cpu_usage_percent for m in metrics_list if m.error_rate == 0]
            ),
        }

    def validate_performance(
        self, operation: str, metrics: PerformanceMetrics
    ) -> dict[str, Any]:
        """Validate performance against benchmarks"""

        if operation not in self.benchmarks:
            return {"error": f"No benchmark defined for operation: {operation}"}

        benchmark = self.benchmarks[operation]
        validation_results = benchmark.validate(metrics)

        return {
            "operation": operation,
            "passed": all(validation_results.values()),
            "individual_checks": validation_results,
            "metrics": metrics.to_dict(),
            "benchmark": asdict(benchmark),
        }


@pytest.fixture
async def performance_test_suite():
    """Fixture providing performance test suite"""
    session_id = f"perf_test_{uuid.uuid4().hex[:8]}"
    suite = PerformanceTestSuite(session_id)
    yield suite

    # Cleanup and summary
    print(f"✅ Performance test session {session_id} completed")
    print(f"📊 Total metrics collected: {len(suite.metrics_history)}")


class TestSearchPerformanceBenchmarks:
    """Test performance benchmarks for different search types"""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_vector_search_performance(self, performance_test_suite):
        """Test vector search performance benchmarks"""

        queries = performance_test_suite.data_generator.generate_search_queries(10)

        metrics_list = []
        for query in queries:
            metrics = await performance_test_suite.run_single_operation_benchmark(
                "vector_search", query, limit=10
            )
            metrics_list.append(metrics)

        # Calculate aggregate metrics
        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # Performance assertions
        assert (
            aggregate["error_rate"] <= 0.02
        ), f"Error rate too high: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 200
        ), f"Average duration too high: {aggregate['avg_duration_ms']:.2f}ms"
        assert (
            aggregate["p95_duration_ms"] <= 300
        ), f"P95 duration too high: {aggregate['p95_duration_ms']:.2f}ms"

        print(
            f"✅ Vector search: {aggregate['avg_duration_ms']:.2f}ms avg, {aggregate['p95_duration_ms']:.2f}ms p95"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_hybrid_search_performance(self, performance_test_suite):
        """Test hybrid search performance benchmarks"""

        queries = performance_test_suite.data_generator.generate_search_queries(10)

        metrics_list = []
        for query in queries:
            metrics = await performance_test_suite.run_single_operation_benchmark(
                "hybrid_search", query, limit=10
            )
            metrics_list.append(metrics)

        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # Hybrid search should be slower but still reasonable
        assert (
            aggregate["error_rate"] <= 0.02
        ), f"Error rate too high: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 500
        ), f"Average duration too high: {aggregate['avg_duration_ms']:.2f}ms"
        assert (
            aggregate["p95_duration_ms"] <= 750
        ), f"P95 duration too high: {aggregate['p95_duration_ms']:.2f}ms"

        print(
            f"✅ Hybrid search: {aggregate['avg_duration_ms']:.2f}ms avg, {aggregate['p95_duration_ms']:.2f}ms p95"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_graph_traversal_performance(self, performance_test_suite):
        """Test graph traversal search performance benchmarks"""

        queries = performance_test_suite.data_generator.generate_search_queries(
            5
        )  # Fewer queries for slower operation

        metrics_list = []
        for query in queries:
            for max_depth in [1, 2, 3]:
                metrics = await performance_test_suite.run_single_operation_benchmark(
                    "graph_traversal_search", query, max_depth=max_depth
                )
                metrics_list.append(metrics)

        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # Graph traversal is the slowest operation
        assert (
            aggregate["error_rate"] <= 0.05
        ), f"Error rate too high: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 1000
        ), f"Average duration too high: {aggregate['avg_duration_ms']:.2f}ms"
        assert (
            aggregate["p95_duration_ms"] <= 1500
        ), f"P95 duration too high: {aggregate['p95_duration_ms']:.2f}ms"

        print(
            f"✅ Graph traversal: {aggregate['avg_duration_ms']:.2f}ms avg, {aggregate['p95_duration_ms']:.2f}ms p95"
        )


class TestConcurrentPerformance:
    """Test performance under concurrent load"""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_low_concurrency_performance(self, performance_test_suite):
        """Test performance with low concurrency (2-5 users)"""

        concurrent_users = 3
        duration_seconds = 10

        metrics_list = await performance_test_suite.run_load_test(
            "vector_search", concurrent_users, duration_seconds
        )

        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # Performance should be good with low concurrency
        assert (
            aggregate["error_rate"] <= 0.02
        ), f"Error rate under low load: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 250
        ), f"Avg duration under low load: {aggregate['avg_duration_ms']:.2f}ms"

        print(
            f"✅ Low concurrency ({concurrent_users} users): {aggregate['total_requests']} requests, "
            f"{aggregate['avg_duration_ms']:.2f}ms avg"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_medium_concurrency_performance(self, performance_test_suite):
        """Test performance with medium concurrency (10-20 users)"""

        concurrent_users = 15
        duration_seconds = 15

        metrics_list = await performance_test_suite.run_load_test(
            "vector_search", concurrent_users, duration_seconds
        )

        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # Allow some degradation under medium load
        assert (
            aggregate["error_rate"] <= 0.05
        ), f"Error rate under medium load: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 400
        ), f"Avg duration under medium load: {aggregate['avg_duration_ms']:.2f}ms"

        print(
            f"✅ Medium concurrency ({concurrent_users} users): {aggregate['total_requests']} requests, "
            f"{aggregate['avg_duration_ms']:.2f}ms avg"
        )

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_high_concurrency_performance(self, performance_test_suite):
        """Test performance with high concurrency (50+ users)"""

        concurrent_users = 50
        duration_seconds = 20

        metrics_list = await performance_test_suite.run_load_test(
            "vector_search", concurrent_users, duration_seconds
        )

        aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)

        # System should handle high load with graceful degradation
        assert (
            aggregate["error_rate"] <= 0.10
        ), f"Error rate under high load: {aggregate['error_rate']}"
        assert (
            aggregate["avg_duration_ms"] <= 1000
        ), f"Avg duration under high load: {aggregate['avg_duration_ms']:.2f}ms"

        # Should maintain reasonable throughput
        assert (
            aggregate["throughput_ops_per_sec"] >= 10
        ), f"Throughput too low: {aggregate['throughput_ops_per_sec']:.2f} ops/sec"

        print(
            f"✅ High concurrency ({concurrent_users} users): {aggregate['total_requests']} requests, "
            f"{aggregate['avg_duration_ms']:.2f}ms avg, {aggregate['throughput_ops_per_sec']:.2f} ops/sec"
        )


class TestPerformanceRegression:
    """Test for performance regression detection"""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_performance_baseline_comparison(self, performance_test_suite):
        """Test performance against baseline measurements"""

        # Simulate baseline metrics (would normally be loaded from previous runs)
        baseline_metrics = {
            "vector_search": {"avg_duration_ms": 150.0, "p95_duration_ms": 250.0},
            "hybrid_search": {"avg_duration_ms": 350.0, "p95_duration_ms": 500.0},
            "graph_traversal_search": {
                "avg_duration_ms": 600.0,
                "p95_duration_ms": 900.0,
            },
        }

        # Test each operation type
        for operation in ["vector_search", "hybrid_search", "graph_traversal_search"]:
            queries = performance_test_suite.data_generator.generate_search_queries(5)

            metrics_list = []
            for query in queries:
                kwargs = (
                    {"max_depth": 2} if operation == "graph_traversal_search" else {}
                )
                metrics = await performance_test_suite.run_single_operation_benchmark(
                    operation, query, **kwargs
                )
                metrics_list.append(metrics)

            aggregate = performance_test_suite.calculate_aggregate_metrics(metrics_list)
            baseline = baseline_metrics[operation]

            # Check for regression (allow 20% degradation)
            avg_regression = (
                aggregate["avg_duration_ms"] - baseline["avg_duration_ms"]
            ) / baseline["avg_duration_ms"]
            p95_regression = (
                aggregate["p95_duration_ms"] - baseline["p95_duration_ms"]
            ) / baseline["p95_duration_ms"]

            assert (
                avg_regression <= 0.20
            ), f"{operation} avg duration regression: {avg_regression:.2%}"
            assert (
                p95_regression <= 0.25
            ), f"{operation} p95 duration regression: {p95_regression:.2%}"

            if avg_regression > 0:
                print(
                    f"⚠️  {operation} performance change: avg +{avg_regression:.1%}, p95 +{p95_regression:.1%}"
                )
            else:
                print(
                    f"✅ {operation} performance: avg {avg_regression:.1%}, p95 {p95_regression:.1%}"
                )


class TestResourceUtilization:
    """Test resource utilization during search operations"""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self, performance_test_suite):
        """Test memory usage scales appropriately with query complexity"""

        # Test with different query complexities
        simple_query = "test"
        complex_query = (
            "complex machine learning optimization techniques implementation patterns"
        )

        simple_metrics = await performance_test_suite.run_single_operation_benchmark(
            "vector_search", simple_query
        )
        complex_metrics = await performance_test_suite.run_single_operation_benchmark(
            "vector_search", complex_query
        )

        # Complex queries should use more memory but not excessively
        memory_increase = (
            complex_metrics.memory_usage_mb - simple_metrics.memory_usage_mb
        ) / simple_metrics.memory_usage_mb

        assert (
            0 <= memory_increase <= 0.5
        ), f"Memory usage increase too high: {memory_increase:.2%}"

        print(f"✅ Memory scaling: {memory_increase:.1%} increase for complex queries")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_cpu_usage_patterns(self, performance_test_suite):
        """Test CPU usage patterns across different operations"""

        query = "performance testing query"

        vector_metrics = await performance_test_suite.run_single_operation_benchmark(
            "vector_search", query
        )
        hybrid_metrics = await performance_test_suite.run_single_operation_benchmark(
            "hybrid_search", query
        )
        graph_metrics = await performance_test_suite.run_single_operation_benchmark(
            "graph_traversal_search", query, max_depth=2
        )

        # CPU usage should increase with operation complexity (with some tolerance for variance)
        # Allow 10% tolerance due to query complexity variations
        assert (
            vector_metrics.cpu_usage_percent <= hybrid_metrics.cpu_usage_percent * 1.1
        )
        assert hybrid_metrics.cpu_usage_percent <= graph_metrics.cpu_usage_percent * 1.2

        # But should remain reasonable
        assert (
            graph_metrics.cpu_usage_percent <= 80
        ), f"CPU usage too high: {graph_metrics.cpu_usage_percent}%"

        print(
            f"✅ CPU usage scaling: vector={vector_metrics.cpu_usage_percent:.1f}%, "
            f"hybrid={hybrid_metrics.cpu_usage_percent:.1f}%, "
            f"graph={graph_metrics.cpu_usage_percent:.1f}%"
        )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_comprehensive_performance_suite(performance_test_suite):
    """Comprehensive performance test combining all aspects"""

    print("🚀 Starting comprehensive performance test suite")

    # 1. Baseline single-operation performance
    operations = ["vector_search", "hybrid_search", "graph_traversal_search"]
    baseline_results = {}

    for operation in operations:
        query = f"comprehensive test {operation}"
        kwargs = {"max_depth": 2} if operation == "graph_traversal_search" else {}

        metrics = await performance_test_suite.run_single_operation_benchmark(
            operation, query, **kwargs
        )

        validation = performance_test_suite.validate_performance(operation, metrics)
        assert validation["passed"], f"{operation} failed performance validation"

        baseline_results[operation] = metrics.duration_ms
        print(f"  {operation}: {metrics.duration_ms:.2f}ms")

    # 2. Concurrent performance test
    concurrent_metrics = await performance_test_suite.run_load_test(
        "vector_search", concurrent_users=10, duration_seconds=10
    )

    concurrent_aggregate = performance_test_suite.calculate_aggregate_metrics(
        concurrent_metrics
    )
    assert concurrent_aggregate["error_rate"] <= 0.05, "Concurrent error rate too high"

    print(
        f"  Concurrent (10 users): {concurrent_aggregate['avg_duration_ms']:.2f}ms avg, "
        f"{concurrent_aggregate['error_rate']:.2%} error rate"
    )

    # 3. Performance consistency test
    consistency_metrics = []
    for i in range(20):
        metrics = await performance_test_suite.run_single_operation_benchmark(
            "vector_search", f"consistency test {i}"
        )
        consistency_metrics.append(metrics.duration_ms)

    # Check for consistency (coefficient of variation should be < 0.5)
    mean_duration = statistics.mean(consistency_metrics)
    std_duration = statistics.stdev(consistency_metrics)
    coefficient_of_variation = std_duration / mean_duration

    assert (
        coefficient_of_variation <= 0.5
    ), f"Performance too inconsistent: CV={coefficient_of_variation:.2f}"

    print(f"  Consistency: CV={coefficient_of_variation:.2f}, std={std_duration:.2f}ms")

    # 4. Overall system health
    total_metrics = len(performance_test_suite.metrics_history)
    error_metrics = sum(
        1 for m in performance_test_suite.metrics_history if m.error_rate > 0
    )
    overall_error_rate = error_metrics / total_metrics if total_metrics > 0 else 0

    assert (
        overall_error_rate <= 0.05
    ), f"Overall error rate too high: {overall_error_rate:.2%}"

    print("✅ Comprehensive performance test completed")
    print(f"📊 Total operations: {total_metrics}, Error rate: {overall_error_rate:.2%}")
    print("🎯 All performance benchmarks passed")


if __name__ == "__main__":
    # Demo performance testing
    async def demo_performance_testing():
        print("🚀 Performance Testing Demo")

        suite = PerformanceTestSuite("demo_session")

        # Test vector search performance
        query = "machine learning algorithms performance test"
        metrics = await suite.run_single_operation_benchmark("vector_search", query)

        print("Vector Search Performance:")
        print(f"  Duration: {metrics.duration_ms:.2f}ms")
        print(f"  Memory: {metrics.memory_usage_mb:.1f}MB")
        print(f"  CPU: {metrics.cpu_usage_percent:.1f}%")
        print(f"  Throughput: {metrics.throughput_ops_per_sec:.2f} ops/sec")

        # Validate against benchmark
        validation = suite.validate_performance("vector_search", metrics)
        print(
            f"  Benchmark validation: {'✅ PASSED' if validation['passed'] else '❌ FAILED'}"
        )

        if not validation["passed"]:
            for check, result in validation["individual_checks"].items():
                if not result:
                    print(f"    Failed: {check}")

        # Test concurrent performance
        print("\nConcurrent Load Test:")
        concurrent_metrics = await suite.run_load_test("vector_search", 5, 5)
        aggregate = suite.calculate_aggregate_metrics(concurrent_metrics)

        print(f"  Total requests: {aggregate['total_requests']}")
        print(f"  Success rate: {100 * (1 - aggregate['error_rate']):.1f}%")
        print(f"  Average duration: {aggregate['avg_duration_ms']:.2f}ms")
        print(f"  P95 duration: {aggregate['p95_duration_ms']:.2f}ms")

        print("✅ Performance testing demo completed")

    # Run demo if called directly
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_performance_testing())
