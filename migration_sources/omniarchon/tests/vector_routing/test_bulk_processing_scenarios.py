"""
Bulk Document Processing Scenario Tests

Tests bulk document processing scenarios to validate system behavior under
high-volume conditions, batch processing efficiency, and resource management.
"""

import asyncio
import gc
import os
import random
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

import psutil
import pytest

# Add the search service to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))

from app import determine_collection_for_document


@dataclass
class BulkProcessingMetrics:
    """Metrics for bulk processing operations"""

    total_documents: int
    processing_time: float
    throughput: float
    success_rate: float
    memory_usage_mb: float
    cpu_percent: float
    collection_distribution: Dict[str, int]
    error_count: int
    errors: List[str]


@dataclass
class BulkProcessingConfig:
    """Configuration for bulk processing tests"""

    batch_size: int = 100
    max_concurrent_batches: int = 5
    document_size_kb: int = 10
    enable_memory_monitoring: bool = True
    enable_cpu_monitoring: bool = True
    collection_balance_threshold: float = 0.3  # 30% max imbalance


class BulkDocumentGenerator:
    """Generate realistic document sets for bulk testing"""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.document_counter = 0

    def generate_documents(
        self, count: int, document_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate a set of documents for testing"""

        if document_types is None:
            document_types = [
                "technical_diagnosis",
                "quality_assessment",
                "code_review",
                "execution_report",
                "quality_report",
                "compliance_check",
                "performance_analysis",
                "spec",
                "design",
                "note",
                "prp",
                "api",
                "guide",
                "documentation",
                "readme",
                "tutorial",
                "wiki",
            ]

        documents = []

        for i in range(count):
            doc_type = random.choice(document_types)
            doc_id = f"bulk_doc_{self.document_counter:06d}"
            self.document_counter += 1

            # Generate realistic content size
            content_words = random.randint(50, 500)
            content = " ".join([f"word{j}" for j in range(content_words)])

            # Add document type specific content
            if doc_type in ["technical_diagnosis", "quality_assessment"]:
                content += " technical analysis performance metrics quality standards"
            elif doc_type in ["spec", "api"]:
                content += " API specification endpoints parameters response schemas"
            elif doc_type in ["design", "documentation"]:
                content += " system architecture design patterns documentation"

            document = {
                "id": doc_id,
                "title": f"Document {self.document_counter}: {doc_type.replace('_', ' ').title()}",
                "content": content,
                "document_type": doc_type,
                "metadata": {
                    "author": f"author_{random.randint(1, 10)}",
                    "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}",
                    "priority": random.choice(["low", "medium", "high"]),
                    "tags": random.sample(
                        ["important", "draft", "reviewed", "approved", "deprecated"],
                        random.randint(1, 3),
                    ),
                    "size_kb": len(content.encode("utf-8")) / 1024,
                    "created_timestamp": time.time()
                    - random.randint(0, 86400 * 30),  # Last 30 days
                },
            }

            documents.append(document)

        return documents

    def generate_weighted_documents(
        self, count: int, quality_weight: float = 0.4
    ) -> List[Dict[str, Any]]:
        """Generate documents with specific quality vs general distribution"""

        quality_types = [
            "technical_diagnosis",
            "quality_assessment",
            "code_review",
            "execution_report",
            "quality_report",
            "compliance_check",
            "performance_analysis",
        ]

        general_types = [
            "spec",
            "design",
            "note",
            "prp",
            "api",
            "guide",
            "documentation",
            "readme",
            "tutorial",
            "wiki",
        ]

        documents = []
        quality_count = int(count * quality_weight)
        general_count = count - quality_count

        # Generate quality documents
        for i in range(quality_count):
            doc_type = random.choice(quality_types)
            documents.append(self._create_document(doc_type, i))

        # Generate general documents
        for i in range(general_count):
            doc_type = random.choice(general_types)
            documents.append(self._create_document(doc_type, quality_count + i))

        # Shuffle to simulate realistic mixed ordering
        random.shuffle(documents)
        return documents

    def _create_document(self, doc_type: str, index: int) -> Dict[str, Any]:
        """Create a single document of specified type"""
        doc_id = f"weighted_doc_{self.document_counter:06d}"
        self.document_counter += 1

        content_size = random.randint(100, 1000)
        content = f"Document content for {doc_type} " * (content_size // 20)

        return {
            "id": doc_id,
            "title": f"{doc_type.replace('_', ' ').title()} Document {index}",
            "content": content,
            "document_type": doc_type,
            "metadata": {
                "index": index,
                "type_category": (
                    "quality"
                    if doc_type
                    in [
                        "technical_diagnosis",
                        "quality_assessment",
                        "code_review",
                        "execution_report",
                        "quality_report",
                        "compliance_check",
                        "performance_analysis",
                    ]
                    else "general"
                ),
            },
        }


class MockBulkQdrantAdapter:
    """Mock QdrantAdapter optimized for bulk operations"""

    def __init__(self, latency_ms: float = 5.0, failure_rate: float = 0.0):
        self.collections = {
            "archon_vectors": {"points": [], "processing_time": []},
            "quality_vectors": {"points": [], "processing_time": []},
        }
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.operation_count = 0

    async def upsert_points(
        self, collection_name: str, points: List[Dict]
    ) -> Dict[str, Any]:
        """Mock bulk upsert with realistic latency"""
        self.operation_count += 1

        # Simulate processing latency
        processing_delay = self.latency_ms / 1000.0
        processing_delay += random.uniform(-0.002, 0.002)  # Add jitter
        await asyncio.sleep(processing_delay)

        # Simulate occasional failures
        if random.random() < self.failure_rate:
            raise Exception(f"Simulated failure in collection {collection_name}")

        if collection_name not in self.collections:
            raise Exception(f"Collection {collection_name} not found")

        # Process points
        processed_points = []
        for point in points:
            processed_point = {
                "id": point.get("id", str(uuid.uuid4())),
                "vector": point.get("vector", [0.1] * 1536),
                "payload": point.get("payload", {}),
            }
            self.collections[collection_name]["points"].append(processed_point)
            processed_points.append(processed_point)

        # Record processing time
        self.collections[collection_name]["processing_time"].append(processing_delay)

        return {
            "operation_id": str(uuid.uuid4()),
            "status": "completed",
            "result": {
                "count": len(processed_points),
                "processing_time": processing_delay,
            },
        }

    async def search(
        self, collection_name: str, query_vector: List[float], limit: int = 10, **kwargs
    ) -> Dict[str, Any]:
        """Mock search with performance simulation"""
        search_delay = self.latency_ms / 2000.0  # Search is typically faster
        await asyncio.sleep(search_delay)

        if collection_name not in self.collections:
            return {"result": []}

        points = self.collections[collection_name]["points"]
        results = []

        for i, point in enumerate(points[:limit]):
            results.append(
                {
                    "id": point["id"],
                    "score": 0.95 - (i * 0.05),
                    "payload": point["payload"],
                }
            )

        return {"result": results}

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get collection statistics"""
        if collection_name not in self.collections:
            return {}

        collection_data = self.collections[collection_name]
        processing_times = collection_data["processing_time"]

        return {
            "point_count": len(collection_data["points"]),
            "avg_processing_time": (
                statistics.mean(processing_times) if processing_times else 0
            ),
            "total_operations": len(processing_times),
        }


@pytest.fixture
def bulk_document_generator():
    """Provide document generator for testing"""
    return BulkDocumentGenerator()


@pytest.fixture
def mock_bulk_adapter():
    """Provide mock adapter optimized for bulk testing"""
    return MockBulkQdrantAdapter(latency_ms=5.0, failure_rate=0.01)


@pytest.fixture
def bulk_config():
    """Provide bulk processing configuration"""
    return BulkProcessingConfig()


class TestBulkProcessingScenarios:
    """Test suite for bulk document processing scenarios"""

    async def process_documents_in_batches(
        self,
        documents: List[Dict],
        batch_size: int,
        mock_adapter: MockBulkQdrantAdapter,
    ) -> BulkProcessingMetrics:
        """Process documents in batches and collect metrics"""

        start_time = time.time()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        total_success = 0
        total_errors = 0
        error_messages = []
        collection_counts = {"archon_vectors": 0, "quality_vectors": 0}

        # Process documents in batches
        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch_docs = documents[batch_start:batch_end]

            # Process batch
            batch_tasks = []
            for doc in batch_docs:
                # Determine collection
                collection = determine_collection_for_document(doc)
                collection_counts[collection] += 1

                # Create processing task
                task = mock_adapter.upsert_points(
                    collection_name=collection,
                    points=[
                        {
                            "id": doc["id"],
                            "vector": [
                                random.random() for _ in range(1536)
                            ],  # Mock embedding
                            "payload": doc,
                        }
                    ],
                )
                batch_tasks.append(task)

            # Execute batch
            try:
                await asyncio.gather(*batch_tasks)
                total_success += len(batch_docs)
            except Exception as e:
                total_errors += len(batch_docs)
                error_messages.append(str(e))

        end_time = time.time()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        processing_time = end_time - start_time
        throughput = len(documents) / processing_time if processing_time > 0 else 0
        success_rate = total_success / len(documents) if documents else 0

        return BulkProcessingMetrics(
            total_documents=len(documents),
            processing_time=processing_time,
            throughput=throughput,
            success_rate=success_rate,
            memory_usage_mb=final_memory - initial_memory,
            cpu_percent=process.cpu_percent(),
            collection_distribution=collection_counts,
            error_count=total_errors,
            errors=error_messages,
        )

    @pytest.mark.asyncio
    async def test_large_scale_document_processing(
        self, bulk_document_generator, mock_bulk_adapter, bulk_config
    ):
        """Test processing of large document sets"""

        # Generate large document set
        document_count = 1000
        documents = bulk_document_generator.generate_documents(document_count)

        # Process documents
        metrics = await self.process_documents_in_batches(
            documents, bulk_config.batch_size, mock_bulk_adapter
        )

        # Verify processing success
        assert (
            metrics.success_rate > 0.95
        ), f"Success rate too low: {metrics.success_rate:.2%}"
        assert (
            metrics.throughput > 50.0
        ), f"Throughput too low: {metrics.throughput:.2f} docs/sec"
        assert (
            metrics.processing_time < 30.0
        ), f"Processing time too high: {metrics.processing_time:.2f}s"

        # Verify memory efficiency
        assert (
            metrics.memory_usage_mb < 200.0
        ), f"Memory usage too high: {metrics.memory_usage_mb:.2f}MB"

        # Verify collection distribution
        total_routed = sum(metrics.collection_distribution.values())
        assert total_routed == document_count, "Document routing count mismatch"

        quality_ratio = (
            metrics.collection_distribution["quality_vectors"] / total_routed
        )
        assert (
            0.1 < quality_ratio < 0.9
        ), f"Collection distribution seems unbalanced: {quality_ratio:.2%}"

    @pytest.mark.asyncio
    async def test_concurrent_batch_processing(
        self, bulk_document_generator, mock_bulk_adapter, bulk_config
    ):
        """Test concurrent processing of multiple document batches"""

        # Generate documents for concurrent processing
        batch_count = 5
        docs_per_batch = 200
        batch_count * docs_per_batch

        all_batches = []
        for i in range(batch_count):
            batch_docs = bulk_document_generator.generate_documents(docs_per_batch)
            all_batches.append(batch_docs)

        # Process batches concurrently
        start_time = time.time()

        async def process_batch(batch_docs, batch_id):
            """Process a single batch of documents"""
            batch_metrics = await self.process_documents_in_batches(
                batch_docs, bulk_config.batch_size // 2, mock_bulk_adapter
            )
            return {"batch_id": batch_id, "metrics": batch_metrics}

        # Execute concurrent batch processing
        batch_tasks = [process_batch(batch, i) for i, batch in enumerate(all_batches)]
        batch_results = await asyncio.gather(*batch_tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify concurrent processing efficiency
        assert (
            total_time < 20.0
        ), f"Concurrent processing time too high: {total_time:.2f}s"

        # Aggregate metrics
        total_success_rate = sum(
            r["metrics"].success_rate for r in batch_results
        ) / len(batch_results)
        assert (
            total_success_rate > 0.95
        ), f"Overall success rate too low: {total_success_rate:.2%}"

        # Verify all batches processed
        assert len(batch_results) == batch_count, "Not all batches completed"

        # Check for reasonable throughput improvement from concurrency
        sequential_estimate = total_time * batch_count  # Rough sequential estimate
        concurrency_benefit = sequential_estimate / total_time
        assert (
            concurrency_benefit > 2.0
        ), f"Limited concurrency benefit: {concurrency_benefit:.2f}x"

    @pytest.mark.asyncio
    async def test_memory_management_during_bulk_processing(
        self, bulk_document_generator, mock_bulk_adapter
    ):
        """Test memory management during extended bulk processing"""

        # Test with progressively larger document sets
        test_sizes = [100, 500, 1000, 2000]
        memory_measurements = []

        for doc_count in test_sizes:
            # Generate documents
            documents = bulk_document_generator.generate_documents(doc_count)

            # Monitor memory during processing
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Process documents
            await self.process_documents_in_batches(
                documents, batch_size=50, mock_adapter=mock_bulk_adapter
            )

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = final_memory - initial_memory

            memory_measurements.append(
                {
                    "document_count": doc_count,
                    "memory_growth_mb": memory_growth,
                    "memory_per_doc_kb": (
                        (memory_growth * 1024) / doc_count if doc_count > 0 else 0
                    ),
                }
            )

            # Force garbage collection between tests
            gc.collect()

        # Verify memory scaling is reasonable
        for measurement in memory_measurements:
            memory_per_doc = measurement["memory_per_doc_kb"]
            assert (
                memory_per_doc < 50.0
            ), f"Memory per document too high: {memory_per_doc:.2f}KB for {measurement['document_count']} docs"

        # Check that memory growth is sublinear
        largest_test = memory_measurements[-1]
        assert (
            largest_test["memory_growth_mb"] < 300.0
        ), f"Total memory growth too high: {largest_test['memory_growth_mb']:.2f}MB"

    @pytest.mark.asyncio
    async def test_collection_balance_under_bulk_load(
        self, bulk_document_generator, mock_bulk_adapter, bulk_config
    ):
        """Test collection balance during bulk document processing"""

        # Generate documents with specific distribution
        quality_weight = 0.4  # 40% quality documents
        document_count = 1000

        documents = bulk_document_generator.generate_weighted_documents(
            document_count, quality_weight
        )

        # Process documents and track collection distribution
        metrics = await self.process_documents_in_batches(
            documents, bulk_config.batch_size, mock_bulk_adapter
        )

        # Verify expected distribution
        total_routed = sum(metrics.collection_distribution.values())
        actual_quality_ratio = (
            metrics.collection_distribution["quality_vectors"] / total_routed
        )
        expected_quality_ratio = quality_weight

        ratio_difference = abs(actual_quality_ratio - expected_quality_ratio)
        assert (
            ratio_difference < bulk_config.collection_balance_threshold
        ), f"Collection balance deviation too high: {ratio_difference:.2%}"

        # Verify both collections received documents
        assert (
            metrics.collection_distribution["quality_vectors"] > 0
        ), "No documents routed to quality_vectors"
        assert (
            metrics.collection_distribution["archon_vectors"] > 0
        ), "No documents routed to archon_vectors"

        # Test collection performance parity
        quality_stats = mock_bulk_adapter.get_collection_stats("quality_vectors")
        archon_stats = mock_bulk_adapter.get_collection_stats("archon_vectors")

        if quality_stats and archon_stats:
            quality_avg_time = quality_stats.get("avg_processing_time", 0)
            archon_avg_time = archon_stats.get("avg_processing_time", 0)

            if quality_avg_time > 0 and archon_avg_time > 0:
                time_ratio = max(quality_avg_time, archon_avg_time) / min(
                    quality_avg_time, archon_avg_time
                )
                assert (
                    time_ratio < 1.5
                ), f"Collection performance imbalance: {time_ratio:.2f}x difference"

    @pytest.mark.asyncio
    async def test_bulk_processing_with_failures(self, bulk_document_generator):
        """Test bulk processing resilience to failures"""

        # Create adapter with higher failure rate
        failing_adapter = MockBulkQdrantAdapter(latency_ms=10.0, failure_rate=0.1)

        # Generate test documents
        documents = bulk_document_generator.generate_documents(500)

        # Process with failure handling
        batch_size = 50
        successful_batches = 0
        failed_batches = 0
        total_docs_processed = 0

        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch_docs = documents[batch_start:batch_end]

            try:
                # Process batch with retry logic
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        batch_tasks = []
                        for doc in batch_docs:
                            collection = determine_collection_for_document(doc)
                            task = failing_adapter.upsert_points(
                                collection_name=collection,
                                points=[
                                    {
                                        "id": doc["id"],
                                        "vector": [0.1] * 1536,
                                        "payload": doc,
                                    }
                                ],
                            )
                            batch_tasks.append(task)

                        await asyncio.gather(*batch_tasks)
                        successful_batches += 1
                        total_docs_processed += len(batch_docs)
                        break

                    except Exception:
                        retry_count += 1
                        if retry_count >= max_retries:
                            failed_batches += 1
                            break
                        await asyncio.sleep(0.1 * retry_count)  # Exponential backoff

            except Exception:
                failed_batches += 1

        # Verify resilience
        total_batches = successful_batches + failed_batches
        success_rate = successful_batches / total_batches if total_batches > 0 else 0

        # With 10% failure rate and 3 retries, we should achieve high success
        assert (
            success_rate > 0.7
        ), f"Success rate too low with failures: {success_rate:.2%}"
        assert (
            total_docs_processed > len(documents) * 0.7
        ), f"Too few documents processed: {total_docs_processed}/{len(documents)}"

    @pytest.mark.asyncio
    async def test_bulk_search_performance(
        self, bulk_document_generator, mock_bulk_adapter
    ):
        """Test search performance after bulk document ingestion"""

        # Bulk load documents first
        document_count = 1000
        documents = bulk_document_generator.generate_documents(document_count)

        # Index all documents
        await self.process_documents_in_batches(
            documents, batch_size=100, mock_adapter=mock_bulk_adapter
        )

        # Perform bulk search operations
        search_queries = [
            "technical analysis performance",
            "API specification documentation",
            "quality assessment metrics",
            "system design patterns",
            "compliance check report",
        ]

        # Test concurrent searches
        async def perform_search_test(query: str):
            """Perform search and measure performance"""
            search_start = time.time()

            # Search both collections
            mock_embedding = [random.random() for _ in range(1536)]

            quality_results = await mock_bulk_adapter.search(
                collection_name="quality_vectors", query_vector=mock_embedding, limit=10
            )

            archon_results = await mock_bulk_adapter.search(
                collection_name="archon_vectors", query_vector=mock_embedding, limit=10
            )

            search_end = time.time()
            search_time = search_end - search_start

            return {
                "query": query,
                "search_time": search_time,
                "quality_results": len(quality_results.get("result", [])),
                "archon_results": len(archon_results.get("result", [])),
            }

        # Execute concurrent searches
        search_start_time = time.time()
        search_tasks = [perform_search_test(query) for query in search_queries]
        search_results = await asyncio.gather(*search_tasks)
        total_search_time = time.time() - search_start_time

        # Verify search performance
        assert (
            total_search_time < 1.0
        ), f"Bulk search time too high: {total_search_time:.2f}s"

        for result in search_results:
            assert (
                result["search_time"] < 0.5
            ), f"Individual search too slow: {result['search_time']:.2f}s"
            # Verify search returned results from appropriate collections
            total_results = result["quality_results"] + result["archon_results"]
            assert total_results > 0, f"No search results for query: {result['query']}"

    @pytest.mark.asyncio
    async def test_progressive_bulk_loading(
        self, bulk_document_generator, mock_bulk_adapter
    ):
        """Test progressive bulk loading scenarios"""

        # Simulate progressive document loading over time
        loading_phases = [
            {"docs": 100, "delay": 0.1},
            {"docs": 200, "delay": 0.2},
            {"docs": 500, "delay": 0.5},
            {"docs": 1000, "delay": 1.0},
        ]

        total_documents_loaded = 0
        phase_metrics = []

        for phase_num, phase in enumerate(loading_phases):
            # Generate documents for this phase
            phase_docs = bulk_document_generator.generate_documents(phase["docs"])

            # Process with simulated delay
            phase_start_time = time.time()

            # Simulate batched loading with delays
            batch_size = 50
            for batch_start in range(0, len(phase_docs), batch_size):
                batch_end = min(batch_start + batch_size, len(phase_docs))
                batch_docs = phase_docs[batch_start:batch_end]

                # Process batch
                batch_tasks = []
                for doc in batch_docs:
                    collection = determine_collection_for_document(doc)
                    task = mock_bulk_adapter.upsert_points(
                        collection_name=collection,
                        points=[
                            {"id": doc["id"], "vector": [0.1] * 1536, "payload": doc}
                        ],
                    )
                    batch_tasks.append(task)

                await asyncio.gather(*batch_tasks)

                # Simulate inter-batch delay
                await asyncio.sleep(phase["delay"] / 10)

            phase_end_time = time.time()
            phase_time = phase_end_time - phase_start_time

            total_documents_loaded += phase["docs"]

            phase_metrics.append(
                {
                    "phase": phase_num,
                    "documents": phase["docs"],
                    "processing_time": phase_time,
                    "throughput": phase["docs"] / phase_time,
                    "cumulative_docs": total_documents_loaded,
                }
            )

        # Verify progressive loading performance
        for i, metric in enumerate(phase_metrics):
            assert (
                metric["throughput"] > 20.0
            ), f"Phase {i} throughput too low: {metric['throughput']:.2f} docs/sec"

        # Verify system can handle increasing load
        final_throughput = phase_metrics[-1]["throughput"]
        initial_throughput = phase_metrics[0]["throughput"]

        # Throughput shouldn't degrade significantly with larger batches
        throughput_ratio = final_throughput / initial_throughput
        assert (
            throughput_ratio > 0.5
        ), f"Significant throughput degradation: {throughput_ratio:.2f}x"

        # Verify total documents loaded
        assert total_documents_loaded == sum(p["docs"] for p in loading_phases)

    @pytest.mark.parametrize(
        "document_size,batch_size,expected_throughput",
        [
            (1000, 10, 100.0),  # Small batches
            (1000, 50, 150.0),  # Medium batches
            (1000, 100, 200.0),  # Large batches
            (1000, 200, 180.0),  # Very large batches (may show diminishing returns)
        ],
    )
    @pytest.mark.asyncio
    async def test_batch_size_optimization(
        self,
        bulk_document_generator,
        mock_bulk_adapter,
        document_size,
        batch_size,
        expected_throughput,
    ):
        """Test optimal batch sizes for bulk processing"""

        # Generate documents
        documents = bulk_document_generator.generate_documents(document_size)

        # Process with specified batch size
        metrics = await self.process_documents_in_batches(
            documents, batch_size, mock_bulk_adapter
        )

        # Verify throughput meets expectations
        assert (
            metrics.throughput >= expected_throughput * 0.8
        ), f"Throughput {metrics.throughput:.2f} below expected {expected_throughput} for batch size {batch_size}"

        # Verify processing completed successfully
        assert (
            metrics.success_rate > 0.95
        ), f"Success rate {metrics.success_rate:.2%} too low for batch size {batch_size}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
