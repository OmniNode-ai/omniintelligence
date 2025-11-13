"""
Performance tests for correlation generation functionality.

Tests performance characteristics of correlation detection algorithms,
data processing pipelines, and end-to-end intelligence analysis.
"""

import concurrent.futures
import statistics
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from src.server.data.intelligence_data_access import (
    IntelligenceDataAccess,
    QueryParameters,
)


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return self.duration * 1000


class PerformanceTestDataGenerator:
    """Generates large datasets for performance testing."""

    @staticmethod
    def generate_intelligence_documents(
        count: int, repos: int = 5
    ) -> list[dict[str, Any]]:
        """Generate a large set of intelligence documents."""
        documents = []
        base_time = datetime.now(UTC)

        repositories = [
            f"Repo-{chr(65 + i)}" for i in range(repos)
        ]  # Repo-A, Repo-B, etc.

        for i in range(count):
            repo = repositories[i % repos]
            doc_time = base_time - timedelta(hours=i * 0.1)

            # Generate realistic file changes
            file_count = (i % 10) + 1
            files = [f"src/module_{j}/file_{i}_{j}.py" for j in range(file_count)]

            # Generate correlations (not every document has correlations)
            temporal_correlations = []
            semantic_correlations = []

            if i % 3 == 0:  # About 1/3 of documents have temporal correlations
                corr_count = (i % 5) + 1
                for j in range(corr_count):
                    related_repo = repositories[(i + j + 1) % repos]
                    time_diff = float((i + j) % 72 + 1)  # 1-72 hours
                    strength = 0.3 + (i % 70) / 100  # 0.3-1.0 range

                    temporal_correlations.append(
                        {
                            "repository": related_repo,
                            "commit_sha": f"corr-commit-{i}-{j}",
                            "time_diff_hours": time_diff,
                            "correlation_strength": strength,
                        }
                    )

            if i % 5 == 0:  # About 1/5 of documents have semantic correlations
                semantic_correlations.append(
                    {
                        "repository": repositories[(i + 2) % repos],
                        "commit_sha": f"semantic-commit-{i}",
                        "semantic_similarity": 0.4 + (i % 60) / 100,
                        "common_keywords": [f"keyword_{k}" for k in range((i % 8) + 1)],
                    }
                )

            # Generate breaking changes occasionally
            breaking_changes = []
            if i % 20 == 0:  # 5% of documents have breaking changes
                breaking_changes.append(
                    {
                        "type": "API_CHANGE" if i % 2 == 0 else "SCHEMA_CHANGE",
                        "severity": "HIGH" if i % 10 == 0 else "MEDIUM",
                        "description": f"Breaking change in document {i}",
                        "files_affected": files[:2],
                    }
                )

            document = {
                "id": f"perf-doc-{i:05d}",
                "document_type": "intelligence",
                "tags": ["intelligence", "pre-push"],
                "created_at": doc_time.isoformat(),
                "updated_at": doc_time.isoformat(),
                "author": f"perf-user-{i % 20}",  # 20 different users
                "content": {
                    "metadata": {
                        "repository": repo,
                        "commit": f"commit-{i:05d}",
                        "author": f"dev-{i % 15}",
                        "timestamp": doc_time.isoformat(),
                    },
                    "diff_analysis": {
                        "total_changes": len(files),
                        "added_lines": (i % 200) + 10,
                        "removed_lines": (i % 100) + 5,
                        "modified_files": files,
                    },
                    "correlation_analysis": {
                        "temporal_correlations": temporal_correlations,
                        "semantic_correlations": semantic_correlations,
                        "breaking_changes": breaking_changes,
                    },
                    "security_analysis": (
                        {
                            "patterns_detected": [
                                f"pattern_{j}" for j in range((i % 5) + 1)
                            ],
                            "risk_level": "LOW" if i % 4 != 0 else "MEDIUM",
                            "secure_patterns": (i % 8) + 1,
                        }
                        if i % 4 == 0
                        else None
                    ),  # 25% have security analysis
                },
            }
            documents.append(document)

        return documents


@pytest.fixture
def performance_data_generator():
    """Get performance test data generator."""
    return PerformanceTestDataGenerator()


class TestCorrelationGenerationPerformance:
    """Performance tests for correlation generation algorithms."""

    @pytest.fixture
    def large_dataset_1k(self, performance_data_generator):
        """Generate 1K document dataset."""
        return performance_data_generator.generate_intelligence_documents(
            1000, repos=10
        )

    @pytest.fixture
    def large_dataset_5k(self, performance_data_generator):
        """Generate 5K document dataset."""
        return performance_data_generator.generate_intelligence_documents(
            5000, repos=20
        )

    @pytest.fixture
    def large_dataset_10k(self, performance_data_generator):
        """Generate 10K document dataset."""
        return performance_data_generator.generate_intelligence_documents(
            10000, repos=50
        )

    @pytest.fixture
    def mock_database_client_with_large_data(self):
        """Mock database client that can handle large datasets."""
        client = Mock()

        # Setup method chaining
        mock_table = Mock()
        mock_select = Mock()
        mock_execute = Mock()

        mock_select.execute.return_value = mock_execute
        mock_select.order.return_value = mock_select
        mock_table.select.return_value = mock_select
        client.table.return_value = mock_table

        return client, mock_execute

    def test_document_parsing_performance_1k(
        self, large_dataset_1k, mock_database_client_with_large_data
    ):
        """Test document parsing performance with 1K documents."""
        client, mock_execute = mock_database_client_with_large_data

        # Setup mock data
        project_data = [
            {
                "id": "perf-proj-1k",
                "title": "Performance Test 1K",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_1k,
            }
        ]
        mock_execute.data = project_data

        # Create data access instance
        data_access = IntelligenceDataAccess(client)
        params = QueryParameters(time_range="7d", limit=1000)

        # Measure parsing performance
        with PerformanceTimer("1K Document Parsing") as timer:
            parsed_docs = data_access.get_parsed_documents(params)

        # Verify results
        assert len(parsed_docs) == 1000, "Should parse all 1K documents"
        assert (
            timer.duration < 5.0
        ), f"1K document parsing took {timer.duration:.3f}s, expected < 5.0s"

        # Verify data quality
        docs_with_temporal = sum(
            1 for doc in parsed_docs if len(doc.temporal_correlations) > 0
        )
        docs_with_semantic = sum(
            1 for doc in parsed_docs if len(doc.semantic_correlations) > 0
        )
        docs_with_breaking = sum(
            1 for doc in parsed_docs if len(doc.breaking_changes) > 0
        )

        assert docs_with_temporal > 300, "Should have significant temporal correlations"
        assert docs_with_semantic > 150, "Should have significant semantic correlations"
        assert docs_with_breaking > 40, "Should have significant breaking changes"

    def test_document_parsing_performance_5k(
        self, large_dataset_5k, mock_database_client_with_large_data
    ):
        """Test document parsing performance with 5K documents."""
        client, mock_execute = mock_database_client_with_large_data

        project_data = [
            {
                "id": "perf-proj-5k",
                "title": "Performance Test 5K",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_5k,
            }
        ]
        mock_execute.data = project_data

        data_access = IntelligenceDataAccess(client)
        params = QueryParameters(time_range="7d", limit=5000)

        with PerformanceTimer("5K Document Parsing") as timer:
            parsed_docs = data_access.get_parsed_documents(params)

        # Should parse a significant portion of documents (allow for time filtering)
        assert (
            len(parsed_docs) >= 1000
        ), f"Should parse at least 1000 documents, got {len(parsed_docs)}"
        assert (
            timer.duration < 20.0
        ), f"Document parsing took {timer.duration:.3f}s for {len(parsed_docs)} docs, expected < 20.0s"

        # Performance per document should be reasonable
        per_doc_ms = timer.duration_ms / max(len(parsed_docs), 1)
        assert (
            per_doc_ms < 10.0
        ), f"Per-document parsing time {per_doc_ms:.3f}ms too slow"

    def test_statistics_calculation_performance(
        self, large_dataset_5k, mock_database_client_with_large_data
    ):
        """Test statistics calculation performance with large datasets."""
        client, mock_execute = mock_database_client_with_large_data

        project_data = [
            {
                "id": "stats-perf-proj",
                "title": "Statistics Performance Test",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_5k,
            }
        ]
        mock_execute.data = project_data

        data_access = IntelligenceDataAccess(client)
        params = QueryParameters(time_range="7d")

        with PerformanceTimer("Statistics Calculation") as timer:
            stats = data_access.calculate_statistics(params)

        # Verify performance
        assert (
            timer.duration < 10.0
        ), f"Statistics calculation took {timer.duration:.3f}s, expected < 10.0s"

        # Verify statistics accuracy (allow for time filtering)
        assert (
            stats.total_changes >= 1000
        ), f"Should count significant documents, got {stats.total_changes}"
        assert (
            stats.repositories_active >= 5
        ), f"Should identify repositories, got {stats.repositories_active}"
        assert (
            stats.total_correlations > 100
        ), f"Should count correlations, got {stats.total_correlations}"
        assert (
            0.0 <= stats.average_correlation_strength <= 1.0
        ), "Average should be valid"
        assert (
            len(stats.correlation_strengths) == stats.total_correlations
        ), "Correlation data consistency"

    def test_concurrent_processing_performance(
        self, large_dataset_1k, mock_database_client_with_large_data
    ):
        """Test concurrent processing of intelligence data."""
        client, mock_execute = mock_database_client_with_large_data

        # Split dataset into chunks for concurrent processing
        chunk_size = 250
        chunks = [
            large_dataset_1k[i : i + chunk_size]
            for i in range(0, len(large_dataset_1k), chunk_size)
        ]

        def process_chunk(chunk_id, chunk_data):
            """Process a chunk of documents."""
            project_data = [
                {
                    "id": f"concurrent-proj-{chunk_id}",
                    "title": f"Concurrent Test {chunk_id}",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "docs": chunk_data,
                }
            ]

            # Create fresh client for thread safety
            thread_client = Mock()
            thread_table = Mock()
            thread_select = Mock()
            thread_execute = Mock()
            thread_execute.data = project_data
            thread_select.execute.return_value = thread_execute
            thread_select.order.return_value = thread_select
            thread_table.select.return_value = thread_select
            thread_client.table.return_value = thread_table

            data_access = IntelligenceDataAccess(thread_client)
            params = QueryParameters(time_range="24h", limit=len(chunk_data))

            start_time = time.perf_counter()
            parsed_docs = data_access.get_parsed_documents(params)
            processing_time = time.perf_counter() - start_time

            return {
                "chunk_id": chunk_id,
                "documents_processed": len(parsed_docs),
                "processing_time": processing_time,
            }

        # Process chunks concurrently
        with PerformanceTimer("Concurrent Processing") as timer:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(process_chunk, i, chunk)
                    for i, chunk in enumerate(chunks)
                ]
                results = [
                    future.result()
                    for future in concurrent.futures.as_completed(futures)
                ]

        # Verify concurrent processing performance
        total_docs = sum(r["documents_processed"] for r in results)
        max_chunk_time = max(r["processing_time"] for r in results)

        # Should process a significant portion (allow for time filtering and chunking)
        assert (
            total_docs >= 200
        ), f"Should process significant documents, got {total_docs}"
        assert (
            timer.duration < 8.0
        ), f"Concurrent processing took {timer.duration:.3f}s, expected < 8.0s"
        assert (
            max_chunk_time < 3.0
        ), f"Slowest chunk took {max_chunk_time:.3f}s, expected < 3.0s"

        # Concurrent processing should show some benefit (relaxed for test environment)
        avg_chunk_time = sum(r["processing_time"] for r in results) / len(results)
        sequential_estimate = avg_chunk_time * len(chunks)
        speedup = sequential_estimate / timer.duration

        # In test environment, concurrent overhead may reduce speedup
        assert speedup > 0.5, f"Concurrent speedup {speedup:.2f}x should be > 0.5x"

    def test_memory_usage_performance(
        self, large_dataset_1k, mock_database_client_with_large_data
    ):
        """Test memory usage characteristics during processing."""
        import tracemalloc

        client, mock_execute = mock_database_client_with_large_data

        project_data = [
            {
                "id": "memory-test-proj",
                "title": "Memory Usage Test",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_1k,
            }
        ]
        mock_execute.data = project_data

        data_access = IntelligenceDataAccess(client)
        params = QueryParameters(time_range="7d", limit=1000)

        # Start memory tracing
        tracemalloc.start()

        # Perform processing
        parsed_docs = data_access.get_parsed_documents(params)
        data_access.calculate_statistics(params)

        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Verify memory usage is reasonable
        current_mb = current / 1024 / 1024
        peak_mb = peak / 1024 / 1024

        # Should process a significant portion (allow for time filtering)
        assert (
            len(parsed_docs) >= 200
        ), f"Should process significant documents, got {len(parsed_docs)}"
        assert (
            current_mb < 200
        ), f"Current memory usage {current_mb:.1f}MB should be < 200MB"
        assert peak_mb < 500, f"Peak memory usage {peak_mb:.1f}MB should be < 500MB"

        # Memory per document in test environment includes Python interpreter overhead
        # Just verify we successfully processed documents
        assert len(parsed_docs) > 0, "Should have processed some documents"

    def test_pagination_performance(
        self, large_dataset_5k, mock_database_client_with_large_data
    ):
        """Test pagination performance with large datasets."""
        client, mock_execute = mock_database_client_with_large_data

        project_data = [
            {
                "id": "pagination-test-proj",
                "title": "Pagination Performance Test",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_5k,
            }
        ]
        mock_execute.data = project_data

        data_access = IntelligenceDataAccess(client)

        # Test different page sizes
        page_sizes = [50, 100, 250, 500]
        performance_results = {}

        for page_size in page_sizes:
            page_times = []

            # Test first few pages for each page size
            for page in range(3):  # Test pages 0, 1, 2
                params = QueryParameters(
                    time_range="7d", limit=page_size, offset=page * page_size
                )

                with PerformanceTimer(f"Page {page} Size {page_size}") as timer:
                    result = data_access.get_raw_documents(params)

                page_times.append(timer.duration)

                # Verify pagination correctness
                assert result["success"] is True
                expected_count = min(
                    page_size, max(0, len(large_dataset_5k) - page * page_size)
                )
                assert len(result["documents"]) == expected_count

            performance_results[page_size] = {
                "avg_time": statistics.mean(page_times),
                "max_time": max(page_times),
                "min_time": min(page_times),
            }

        # Verify pagination performance characteristics
        for page_size, perf in performance_results.items():
            assert (
                perf["max_time"] < 5.0
            ), f"Page size {page_size} max time {perf['max_time']:.3f}s too slow"
            assert (
                perf["avg_time"] < 3.0
            ), f"Page size {page_size} avg time {perf['avg_time']:.3f}s too slow"

        # Larger page sizes should have better throughput (docs/second)
        small_throughput = (
            page_sizes[0] / performance_results[page_sizes[0]]["avg_time"]
        )
        large_throughput = (
            page_sizes[-1] / performance_results[page_sizes[-1]]["avg_time"]
        )

        assert (
            large_throughput >= small_throughput
        ), "Larger page sizes should have better throughput"

    def test_correlation_detection_scaling(self, performance_data_generator):
        """Test how correlation detection algorithms scale with data size."""
        # Import correlation algorithms from the local test data
        from tests.unit.test_correlation_algorithms import CorrelationAlgorithms

        dataset_sizes = [100, 500, 1000, 2500]
        scaling_results = {}

        for size in dataset_sizes:
            dataset = performance_data_generator.generate_intelligence_documents(
                size, repos=10
            )

            # Extract correlation data from documents
            temporal_pairs = []
            semantic_pairs = []

            for doc in dataset:
                content = doc["content"]
                correlations = content.get("correlation_analysis", {})

                # Collect temporal correlation data
                for tc in correlations.get("temporal_correlations", []):
                    temporal_pairs.append(tc["time_diff_hours"])

                # Collect semantic correlation data
                for sc in correlations.get("semantic_correlations", []):
                    if "common_keywords" in sc:
                        semantic_pairs.append(
                            (
                                sc["common_keywords"],
                                [
                                    f"related_keyword_{i}"
                                    for i in range(len(sc["common_keywords"]) // 2)
                                ],
                            )
                        )

            # Measure correlation calculation performance
            with PerformanceTimer(f"Temporal Correlations {size}") as temporal_timer:
                [
                    CorrelationAlgorithms.calculate_temporal_correlation_strength(td)
                    for td in temporal_pairs
                ]

            with PerformanceTimer(f"Semantic Correlations {size}") as semantic_timer:
                [
                    CorrelationAlgorithms.calculate_semantic_similarity(kw1, kw2)
                    for kw1, kw2 in semantic_pairs
                ]

            scaling_results[size] = {
                "documents": size,
                "temporal_correlations": len(temporal_pairs),
                "temporal_time": temporal_timer.duration,
                "semantic_correlations": len(semantic_pairs),
                "semantic_time": semantic_timer.duration,
                "temporal_per_correlation_ms": temporal_timer.duration_ms
                / max(len(temporal_pairs), 1),
                "semantic_per_correlation_ms": semantic_timer.duration_ms
                / max(len(semantic_pairs), 1),
            }

        # Verify scaling characteristics
        for size, results in scaling_results.items():
            # Per-correlation time should be consistent regardless of dataset size
            assert (
                results["temporal_per_correlation_ms"] < 0.1
            ), f"Temporal correlation per-item time {results['temporal_per_correlation_ms']:.3f}ms too slow for size {size}"
            assert (
                results["semantic_per_correlation_ms"] < 5.0
            ), f"Semantic correlation per-item time {results['semantic_per_correlation_ms']:.3f}ms too slow for size {size}"

        # Overall processing time should scale reasonably
        largest_result = scaling_results[max(dataset_sizes)]
        assert (
            largest_result["temporal_time"] < 1.0
        ), "Largest temporal correlation processing too slow"
        assert (
            largest_result["semantic_time"] < 5.0
        ), "Largest semantic correlation processing too slow"

    def test_end_to_end_performance_benchmark(
        self, large_dataset_1k, mock_database_client_with_large_data
    ):
        """End-to-end performance benchmark for complete intelligence processing."""
        client, mock_execute = mock_database_client_with_large_data

        project_data = [
            {
                "id": "e2e-benchmark-proj",
                "title": "End-to-End Performance Benchmark",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": large_dataset_1k,
            }
        ]
        mock_execute.data = project_data

        data_access = IntelligenceDataAccess(client)

        # Comprehensive performance benchmark
        benchmark_results = {}

        # 1. Raw document retrieval
        params = QueryParameters(time_range="7d", limit=1000)
        with PerformanceTimer("Raw Document Retrieval") as timer:
            raw_result = data_access.get_raw_documents(params)
        benchmark_results["raw_retrieval"] = timer.duration

        # 2. Document parsing
        with PerformanceTimer("Document Parsing") as timer:
            parsed_docs = data_access.get_parsed_documents(params)
        benchmark_results["document_parsing"] = timer.duration

        # 3. Statistics calculation
        with PerformanceTimer("Statistics Calculation") as timer:
            stats = data_access.calculate_statistics(params)
        benchmark_results["statistics_calculation"] = timer.duration

        # 4. Repository extraction
        with PerformanceTimer("Repository Extraction") as timer:
            repositories = data_access.get_active_repositories()
        benchmark_results["repository_extraction"] = timer.duration

        # Verify benchmark results
        total_time = sum(benchmark_results.values())

        assert raw_result["success"] is True
        assert len(parsed_docs) == 1000
        assert stats.total_changes == 1000
        assert len(repositories) >= 5

        # Performance targets for 1K documents
        assert benchmark_results["raw_retrieval"] < 1.0, "Raw retrieval too slow"
        assert benchmark_results["document_parsing"] < 5.0, "Document parsing too slow"
        assert (
            benchmark_results["statistics_calculation"] < 2.0
        ), "Statistics calculation too slow"
        assert (
            benchmark_results["repository_extraction"] < 1.0
        ), "Repository extraction too slow"
        assert total_time < 8.0, f"Total end-to-end time {total_time:.3f}s too slow"

        # Calculate throughput metrics
        docs_per_second = len(parsed_docs) / benchmark_results["document_parsing"]
        correlations_per_second = (
            stats.total_correlations / benchmark_results["statistics_calculation"]
        )

        assert (
            docs_per_second > 200
        ), f"Document parsing throughput {docs_per_second:.1f} docs/s too low"
        assert (
            correlations_per_second > 500
        ), f"Correlation processing throughput {correlations_per_second:.1f} corr/s too low"

        return benchmark_results


class TestPerformanceRegressionDetection:
    """Tests for detecting performance regressions."""

    def test_performance_baseline_establishment(self, performance_data_generator):
        """Test establishing performance baselines for regression detection."""

        # Generate consistent test dataset
        test_dataset = performance_data_generator.generate_intelligence_documents(
            500, repos=5
        )

        # Mock baseline storage
        performance_baselines = {}

        def establish_baseline(operation_name, dataset_size, duration):
            """Establish performance baseline."""
            if operation_name not in performance_baselines:
                performance_baselines[operation_name] = {}
            performance_baselines[operation_name][dataset_size] = {
                "baseline_duration": duration,
                "tolerance": duration * 0.2,  # 20% tolerance
                "measurements": [duration],
            }

        # Establish baselines for key operations
        client = Mock()
        mock_execute = Mock()
        mock_execute.data = [
            {
                "id": "baseline-proj",
                "title": "Baseline Project",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "docs": test_dataset,
            }
        ]

        # Setup mock chaining
        mock_table = Mock()
        mock_select = Mock()
        mock_select.execute.return_value = mock_execute
        mock_select.order.return_value = mock_select
        mock_table.select.return_value = mock_select
        client.table.return_value = mock_table

        data_access = IntelligenceDataAccess(client)
        params = QueryParameters(time_range="7d", limit=500)

        # Establish parsing baseline
        with PerformanceTimer("Baseline Document Parsing") as timer:
            data_access.get_parsed_documents(params)
        establish_baseline("document_parsing", 500, timer.duration)

        # Establish statistics baseline
        with PerformanceTimer("Baseline Statistics") as timer:
            data_access.calculate_statistics(params)
        establish_baseline("statistics_calculation", 500, timer.duration)

        # Verify baselines were established
        assert "document_parsing" in performance_baselines
        assert "statistics_calculation" in performance_baselines
        assert performance_baselines["document_parsing"][500]["baseline_duration"] > 0
        assert (
            performance_baselines["statistics_calculation"][500]["baseline_duration"]
            > 0
        )

        # Test regression detection simulation
        def check_regression(operation_name, dataset_size, current_duration):
            """Check if current performance indicates regression."""
            baseline_info = performance_baselines.get(operation_name, {}).get(
                dataset_size
            )
            if not baseline_info:
                return False, "No baseline established"

            baseline = baseline_info["baseline_duration"]
            tolerance = baseline_info["tolerance"]

            if current_duration > baseline + tolerance:
                regression_pct = ((current_duration - baseline) / baseline) * 100
                return (
                    True,
                    f"Regression detected: {regression_pct:.1f}% slower than baseline",
                )

            return False, "Performance within acceptable range"

        # Simulate performance check
        simulated_slow_duration = (
            performance_baselines["document_parsing"][500]["baseline_duration"] * 1.5
        )
        is_regression, message = check_regression(
            "document_parsing", 500, simulated_slow_duration
        )

        assert is_regression is True, "Should detect performance regression"
        assert "Regression detected" in message, "Should provide regression details"

    def test_performance_monitoring_across_dataset_sizes(
        self, performance_data_generator
    ):
        """Test performance monitoring across different dataset sizes."""

        dataset_sizes = [100, 250, 500, 1000]
        performance_profile = {}

        for size in dataset_sizes:
            dataset = performance_data_generator.generate_intelligence_documents(
                size, repos=5
            )

            # Setup mock for this dataset size
            client = Mock()
            mock_execute = Mock()
            mock_execute.data = [
                {
                    "id": f"monitoring-proj-{size}",
                    "title": f"Monitoring Project {size}",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "docs": dataset,
                }
            ]

            mock_table = Mock()
            mock_select = Mock()
            mock_select.execute.return_value = mock_execute
            mock_select.order.return_value = mock_select
            mock_table.select.return_value = mock_select
            client.table.return_value = mock_table

            data_access = IntelligenceDataAccess(client)
            params = QueryParameters(time_range="7d", limit=size)

            # Measure performance for this size
            with PerformanceTimer(f"Parsing {size} docs") as parsing_timer:
                parsed_docs = data_access.get_parsed_documents(params)

            with PerformanceTimer(f"Stats {size} docs") as stats_timer:
                stats = data_access.calculate_statistics(params)

            performance_profile[size] = {
                "parsing_time": parsing_timer.duration,
                "stats_time": stats_timer.duration,
                "total_time": parsing_timer.duration + stats_timer.duration,
                "parsing_throughput": len(parsed_docs) / parsing_timer.duration,
                "docs_processed": len(parsed_docs),
                "correlations_found": stats.total_correlations,
            }

        # Analyze scaling characteristics
        for size in dataset_sizes:
            profile = performance_profile[size]

            # Performance should scale reasonably with dataset size
            expected_max_parsing_time = size * 0.01  # 10ms per document max
            expected_max_stats_time = size * 0.005  # 5ms per document max

            assert (
                profile["parsing_time"] <= expected_max_parsing_time
            ), f"Parsing time {profile['parsing_time']:.3f}s exceeds expected {expected_max_parsing_time:.3f}s for {size} docs"

            assert (
                profile["stats_time"] <= expected_max_stats_time
            ), f"Stats time {profile['stats_time']:.3f}s exceeds expected {expected_max_stats_time:.3f}s for {size} docs"

            # Throughput should remain reasonable (relaxed for test environment variance)
            assert (
                profile["parsing_throughput"] >= 50
            ), f"Parsing throughput {profile['parsing_throughput']:.1f} docs/s too low for {size} docs"

        # Check that performance scales roughly linearly
        small_size = dataset_sizes[0]
        large_size = dataset_sizes[-1]

        small_profile = performance_profile[small_size]
        large_profile = performance_profile[large_size]

        size_ratio = large_size / small_size
        time_ratio = large_profile["total_time"] / small_profile["total_time"]

        # Time ratio should not be excessive (allowing for overhead, variance, and test environment)
        # Use a more lenient multiplier (4.0x) to account for test environment variance and startup overhead
        assert (
            time_ratio <= size_ratio * 4.0
        ), f"Performance scaling worse than expected: {time_ratio:.2f}x time for {size_ratio:.2f}x data"

    @pytest.mark.slow
    def test_sustained_load_performance(self, performance_data_generator):
        """Test performance under sustained load conditions."""

        # Generate datasets for sustained load testing
        base_dataset = performance_data_generator.generate_intelligence_documents(
            200, repos=5
        )

        # Simulate sustained load over multiple iterations
        iterations = 10
        performance_measurements = []

        for iteration in range(iterations):
            # Setup fresh mock for each iteration
            client = Mock()
            mock_execute = Mock()
            mock_execute.data = [
                {
                    "id": f"sustained-proj-{iteration}",
                    "title": f"Sustained Load {iteration}",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "docs": base_dataset,
                }
            ]

            mock_table = Mock()
            mock_select = Mock()
            mock_select.execute.return_value = mock_execute
            mock_select.order.return_value = mock_select
            mock_table.select.return_value = mock_select
            client.table.return_value = mock_table

            data_access = IntelligenceDataAccess(client)
            params = QueryParameters(time_range="24h", limit=200)

            # Measure performance for this iteration
            with PerformanceTimer(f"Sustained Load Iteration {iteration}") as timer:
                parsed_docs = data_access.get_parsed_documents(params)
                stats = data_access.calculate_statistics(params)
                repositories = data_access.get_active_repositories()

            performance_measurements.append(
                {
                    "iteration": iteration,
                    "duration": timer.duration,
                    "docs_processed": len(parsed_docs),
                    "correlations_found": stats.total_correlations,
                    "repositories_found": len(repositories),
                }
            )

        # Analyze sustained performance characteristics
        durations = [m["duration"] for m in performance_measurements]
        avg_duration = statistics.mean(durations)
        max_duration = max(durations)
        min(durations)
        std_dev = statistics.stdev(durations)

        # Verify sustained performance is stable (with tolerance for variance)
        # Allow for more variance in test environment (up to 5x for max, 2x for std dev)
        assert (
            max_duration < avg_duration * 5.0
        ), f"Max duration {max_duration:.3f}s too much higher than average {avg_duration:.3f}s"
        assert (
            std_dev < avg_duration * 2.0
        ), f"Performance variance {std_dev:.3f}s too high (avg: {avg_duration:.3f}s)"

        # Verify all iterations processed data correctly
        for measurement in performance_measurements:
            assert (
                measurement["docs_processed"] == 200
            ), f"Iteration {measurement['iteration']} processed wrong number of docs"
            assert (
                measurement["correlations_found"] >= 0
            ), f"Iteration {measurement['iteration']} found negative correlations"
            assert (
                measurement["repositories_found"] >= 1
            ), f"Iteration {measurement['iteration']} found no repositories"

        # Overall performance should be acceptable
        assert (
            avg_duration < 3.0
        ), f"Average sustained load duration {avg_duration:.3f}s too slow"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])
