"""
End-to-End Pipeline Tests for Vector Routing

Tests the complete document processing pipeline from ingestion through to search,
validating proper vector routing, collection assignment, and retrieval functionality.
"""

import asyncio
import os
import sys
import time
import uuid
from typing import Dict, List
from unittest.mock import AsyncMock, patch

import pytest

# Add services to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/intelligence"))

from app import determine_collection_for_document


class MockQdrantClient:
    """Mock Qdrant client for end-to-end testing"""

    def __init__(self):
        self.collections = {
            "archon_vectors": {"points": [], "metadata": {"status": "green"}},
            "quality_vectors": {"points": [], "metadata": {"status": "green"}},
        }
        self.next_point_id = 1

    async def upsert(self, collection_name: str, points: List[Dict]) -> Dict:
        """Mock upsert operation"""
        if collection_name not in self.collections:
            raise Exception(f"Collection {collection_name} not found")

        processed_points = []
        for point in points:
            point_data = {
                "id": point.get("id", str(self.next_point_id)),
                "vector": point.get("vector", [0.1] * 1536),
                "payload": point.get("payload", {}),
            }
            self.collections[collection_name]["points"].append(point_data)
            processed_points.append(point_data)
            self.next_point_id += 1

        return {
            "operation_id": str(uuid.uuid4()),
            "status": "completed",
            "result": {"count": len(processed_points)},
        }

    async def search(
        self, collection_name: str, query_vector: List[float], limit: int = 10, **kwargs
    ) -> Dict:
        """Mock search operation"""
        if collection_name not in self.collections:
            return {"result": []}

        points = self.collections[collection_name]["points"]
        # Simple mock search - return available points with mock scores
        results = []
        for i, point in enumerate(points[:limit]):
            results.append(
                {
                    "id": point["id"],
                    "score": 0.95 - (i * 0.1),  # Decreasing mock scores
                    "payload": point["payload"],
                }
            )

        return {"result": results}

    async def get_collection(self, collection_name: str) -> Dict:
        """Mock collection info"""
        if collection_name not in self.collections:
            raise Exception(f"Collection {collection_name} not found")

        return {
            "result": {
                "status": self.collections[collection_name]["metadata"]["status"],
                "vectors_count": len(self.collections[collection_name]["points"]),
                "config": {"params": {"vectors": {"size": 1536}}},
            }
        }


class MockEmbeddingService:
    """Mock embedding service for testing"""

    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """Generate mock embedding vector"""
        # Create deterministic mock embedding based on text hash
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()

        # Convert hex to floats and normalize to 1536 dimensions
        embedding = []
        for i in range(1536):
            hex_part = text_hash[
                (i * 2) % len(text_hash) : ((i * 2) + 2) % len(text_hash)
            ]
            if len(hex_part) == 2:
                embedding.append((int(hex_part, 16) / 255.0) - 0.5)
            else:
                embedding.append(0.1)

        return embedding


@pytest.fixture
def mock_qdrant_client():
    """Provide mock Qdrant client for testing"""
    return MockQdrantClient()


@pytest.fixture
def mock_embedding_service():
    """Provide mock embedding service for testing"""
    return MockEmbeddingService()


@pytest.fixture
def sample_documents():
    """Sample documents for pipeline testing"""
    return [
        {
            "id": "doc_quality_1",
            "title": "Code Review Guidelines",
            "content": "This document outlines the code review process and quality standards.",
            "document_type": "code_review",
            "metadata": {
                "author": "Engineering Team",
                "version": "1.0",
                "priority": "high",
            },
        },
        {
            "id": "doc_general_1",
            "title": "API Specification",
            "content": "REST API endpoints and documentation for the user service.",
            "document_type": "spec",
            "metadata": {
                "author": "API Team",
                "version": "2.1",
                "service": "user-service",
            },
        },
        {
            "id": "doc_quality_2",
            "title": "Performance Analysis Report",
            "content": "Analysis of system performance bottlenecks and optimization recommendations.",
            "document_type": "performance_analysis",
            "metadata": {"author": "Performance Team", "date": "2025-01-01"},
        },
        {
            "id": "doc_general_2",
            "title": "Design Document",
            "content": "System architecture design and component interactions.",
            "document_type": "design",
            "metadata": {"author": "Architecture Team", "complexity": "high"},
        },
        {
            "id": "doc_unknown",
            "title": "Unknown Document Type",
            "content": "Document with unrecognized type for fallback testing.",
            "document_type": "experimental_type",
            "metadata": {"author": "Research Team"},
        },
    ]


class TestEndToEndPipeline:
    """End-to-end pipeline tests for vector routing"""

    @pytest.mark.asyncio
    async def test_document_ingestion_to_search_pipeline(
        self, mock_qdrant_client, mock_embedding_service, sample_documents
    ):
        """Test complete pipeline from document ingestion to search retrieval"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            # Setup mock adapter
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Configure mock responses
            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )
            mock_adapter.search = AsyncMock(side_effect=mock_qdrant_client.search)
            mock_adapter.get_collection_info = AsyncMock(
                side_effect=mock_qdrant_client.get_collection
            )

            # Process documents through the pipeline
            processing_results = []

            for doc in sample_documents:
                # Step 1: Document routing decision
                target_collection = determine_collection_for_document(doc)

                # Step 2: Generate embedding
                embedding = await mock_embedding_service.generate_embedding(
                    doc["content"]
                )

                # Step 3: Index document in appropriate collection
                index_result = await mock_adapter.upsert_points(
                    collection_name=target_collection,
                    points=[
                        {
                            "id": doc["id"],
                            "vector": embedding,
                            "payload": {
                                "title": doc["title"],
                                "content": doc["content"],
                                "document_type": doc["document_type"],
                                "metadata": doc["metadata"],
                            },
                        }
                    ],
                )

                processing_results.append(
                    {
                        "document_id": doc["id"],
                        "collection": target_collection,
                        "index_result": index_result,
                    }
                )

            # Verify processing results
            assert len(processing_results) == len(sample_documents)

            # Verify collection routing
            quality_docs = [
                r for r in processing_results if r["collection"] == "quality_vectors"
            ]
            general_docs = [
                r for r in processing_results if r["collection"] == "archon_vectors"
            ]

            assert len(quality_docs) == 2  # code_review and performance_analysis
            assert (
                len(general_docs) == 3
            )  # spec, design, and experimental_type (fallback)

            # Step 4: Test search functionality
            search_query = "performance optimization"
            search_embedding = await mock_embedding_service.generate_embedding(
                search_query
            )

            # Search in quality vectors
            quality_results = await mock_adapter.search(
                collection_name="quality_vectors",
                query_vector=search_embedding,
                limit=5,
            )

            # Search in archon vectors
            archon_results = await mock_adapter.search(
                collection_name="archon_vectors", query_vector=search_embedding, limit=5
            )

            # Verify search results
            assert "result" in quality_results
            assert "result" in archon_results
            assert len(quality_results["result"]) <= 2  # Max 2 quality docs indexed
            assert len(archon_results["result"]) <= 3  # Max 3 general docs indexed

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test pipeline error handling and recovery"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Test 1: Collection not found error
            mock_adapter.upsert_points = AsyncMock(
                side_effect=Exception("Collection not found")
            )

            error_doc = {
                "id": "error_doc",
                "content": "Test document for error handling",
                "document_type": "technical_diagnosis",
            }

            target_collection = determine_collection_for_document(error_doc)
            embedding = await mock_embedding_service.generate_embedding(
                error_doc["content"]
            )

            with pytest.raises(Exception, match="Collection not found"):
                await mock_adapter.upsert_points(
                    collection_name=target_collection,
                    points=[{"id": error_doc["id"], "vector": embedding}],
                )

            # Test 2: Recovery after error
            mock_adapter.upsert_points = AsyncMock(
                return_value={"operation_id": "recovery_op", "status": "completed"}
            )

            # Should succeed after recovery
            recovery_result = await mock_adapter.upsert_points(
                collection_name=target_collection,
                points=[{"id": error_doc["id"], "vector": embedding}],
            )

            assert recovery_result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_concurrent_document_processing(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test concurrent document processing through the pipeline"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )

            # Create multiple documents for concurrent processing
            concurrent_docs = []
            for i in range(20):
                doc_type = "technical_diagnosis" if i % 2 == 0 else "spec"
                concurrent_docs.append(
                    {
                        "id": f"concurrent_doc_{i}",
                        "content": f"Content for concurrent document {i}",
                        "document_type": doc_type,
                    }
                )

            async def process_document(doc):
                """Process a single document through the pipeline"""
                collection = determine_collection_for_document(doc)
                embedding = await mock_embedding_service.generate_embedding(
                    doc["content"]
                )

                result = await mock_adapter.upsert_points(
                    collection_name=collection,
                    points=[{"id": doc["id"], "vector": embedding, "payload": doc}],
                )

                return {"doc_id": doc["id"], "collection": collection, "result": result}

            # Process documents concurrently
            start_time = time.time()
            processing_tasks = [process_document(doc) for doc in concurrent_docs]
            results = await asyncio.gather(*processing_tasks)
            end_time = time.time()

            # Verify all documents processed successfully
            assert len(results) == len(concurrent_docs)

            # Verify processing time is reasonable for concurrent execution
            processing_time = end_time - start_time
            assert (
                processing_time < 5.0
            ), f"Concurrent processing took too long: {processing_time:.2f}s"

            # Verify routing distribution
            quality_count = sum(
                1 for r in results if r["collection"] == "quality_vectors"
            )
            archon_count = sum(
                1 for r in results if r["collection"] == "archon_vectors"
            )

            assert quality_count == 10  # Half should be technical_diagnosis
            assert archon_count == 10  # Half should be spec

    @pytest.mark.asyncio
    async def test_cross_collection_search_consistency(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test search consistency across different collections"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )
            mock_adapter.search = AsyncMock(side_effect=mock_qdrant_client.search)

            # Index similar documents in both collections
            similar_docs = [
                {
                    "id": "quality_doc",
                    "content": "Machine learning performance optimization techniques",
                    "document_type": "performance_analysis",
                },
                {
                    "id": "general_doc",
                    "content": "Machine learning system design patterns",
                    "document_type": "design",
                },
            ]

            # Process documents through pipeline
            for doc in similar_docs:
                collection = determine_collection_for_document(doc)
                embedding = await mock_embedding_service.generate_embedding(
                    doc["content"]
                )

                await mock_adapter.upsert_points(
                    collection_name=collection,
                    points=[{"id": doc["id"], "vector": embedding, "payload": doc}],
                )

            # Search for similar content across collections
            search_query = "machine learning optimization"
            search_embedding = await mock_embedding_service.generate_embedding(
                search_query
            )

            quality_results = await mock_adapter.search(
                collection_name="quality_vectors",
                query_vector=search_embedding,
                limit=5,
            )

            archon_results = await mock_adapter.search(
                collection_name="archon_vectors", query_vector=search_embedding, limit=5
            )

            # Verify both collections return relevant results
            assert len(quality_results["result"]) > 0
            assert len(archon_results["result"]) > 0

            # Verify document routing was correct
            quality_doc_ids = [r["id"] for r in quality_results["result"]]
            archon_doc_ids = [r["id"] for r in archon_results["result"]]

            assert "quality_doc" in quality_doc_ids
            assert "general_doc" in archon_doc_ids

    @pytest.mark.asyncio
    async def test_pipeline_with_malformed_documents(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test pipeline handling of malformed or invalid documents"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )

            malformed_docs = [
                # Missing document_type
                {"id": "missing_type", "content": "Content without type"},
                # Empty document_type
                {"id": "empty_type", "content": "Content", "document_type": ""},
                # None document_type
                {"id": "none_type", "content": "Content", "document_type": None},
                # Missing content
                {"id": "missing_content", "document_type": "spec"},
                # Empty content
                {"id": "empty_content", "content": "", "document_type": "spec"},
                # Very long content
                {"id": "long_content", "content": "x" * 10000, "document_type": "note"},
            ]

            processing_results = []

            for doc in malformed_docs:
                try:
                    # Document routing should handle malformed docs gracefully
                    collection = determine_collection_for_document(doc)

                    # Generate embedding for available content
                    content = doc.get("content", "default content")
                    if not content:
                        content = "default content"

                    embedding = await mock_embedding_service.generate_embedding(content)

                    # Try to index document
                    result = await mock_adapter.upsert_points(
                        collection_name=collection,
                        points=[{"id": doc["id"], "vector": embedding, "payload": doc}],
                    )

                    processing_results.append(
                        {
                            "doc_id": doc["id"],
                            "collection": collection,
                            "status": "success",
                            "result": result,
                        }
                    )

                except Exception as e:
                    processing_results.append(
                        {"doc_id": doc["id"], "status": "error", "error": str(e)}
                    )

            # Verify malformed documents were handled appropriately
            successful_processing = [
                r for r in processing_results if r["status"] == "success"
            ]
            assert (
                len(successful_processing) > 0
            ), "Pipeline should handle some malformed documents"

            # Verify default routing for malformed document types
            for result in successful_processing:
                if result["doc_id"] in ["missing_type", "empty_type", "none_type"]:
                    assert (
                        result["collection"] == "archon_vectors"
                    ), f"Malformed document {result['doc_id']} should default to archon_vectors"

    @pytest.mark.asyncio
    async def test_pipeline_data_integrity(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test data integrity throughout the pipeline"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )
            mock_adapter.search = AsyncMock(side_effect=mock_qdrant_client.search)

            # Test document with rich metadata
            test_doc = {
                "id": "integrity_test_doc",
                "title": "Data Integrity Test Document",
                "content": "This document tests data integrity through the pipeline.",
                "document_type": "technical_diagnosis",
                "metadata": {
                    "author": "Test Suite",
                    "version": "1.0",
                    "tags": ["testing", "integrity", "pipeline"],
                    "numeric_field": 42,
                    "boolean_field": True,
                    "nested_object": {"level1": {"level2": "deep_value"}},
                },
            }

            # Process document through pipeline
            collection = determine_collection_for_document(test_doc)
            embedding = await mock_embedding_service.generate_embedding(
                test_doc["content"]
            )

            # Index document
            index_result = await mock_adapter.upsert_points(
                collection_name=collection,
                points=[
                    {"id": test_doc["id"], "vector": embedding, "payload": test_doc}
                ],
            )

            assert index_result["status"] == "completed"

            # Search for the document
            search_embedding = await mock_embedding_service.generate_embedding(
                "data integrity"
            )
            search_results = await mock_adapter.search(
                collection_name=collection, query_vector=search_embedding, limit=5
            )

            # Verify document was found and data is intact
            assert len(search_results["result"]) > 0

            found_doc = None
            for result in search_results["result"]:
                if result["id"] == test_doc["id"]:
                    found_doc = result
                    break

            assert found_doc is not None, "Document not found in search results"

            # Verify all metadata preserved
            payload = found_doc["payload"]
            assert payload["title"] == test_doc["title"]
            assert payload["content"] == test_doc["content"]
            assert payload["document_type"] == test_doc["document_type"]

            # Verify complex metadata structure
            assert payload["metadata"]["author"] == "Test Suite"
            assert payload["metadata"]["numeric_field"] == 42
            assert payload["metadata"]["boolean_field"] is True
            assert (
                payload["metadata"]["nested_object"]["level1"]["level2"] == "deep_value"
            )

    @pytest.mark.asyncio
    async def test_pipeline_performance_under_load(
        self, mock_qdrant_client, mock_embedding_service
    ):
        """Test pipeline performance under realistic load conditions"""

        with patch("engines.qdrant_adapter.QdrantAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            mock_adapter.upsert_points = AsyncMock(
                side_effect=mock_qdrant_client.upsert
            )
            mock_adapter.search = AsyncMock(side_effect=mock_qdrant_client.search)

            # Generate load test documents
            load_test_docs = []
            doc_types = [
                "technical_diagnosis",
                "spec",
                "quality_assessment",
                "design",
                "note",
            ]

            for i in range(100):
                doc_type = doc_types[i % len(doc_types)]
                load_test_docs.append(
                    {
                        "id": f"load_test_doc_{i}",
                        "content": f"Load test document content {i} with unique identifier",
                        "document_type": doc_type,
                        "metadata": {"batch": i // 10, "sequence": i},
                    }
                )

            # Process documents in batches to simulate realistic load
            batch_size = 10
            processing_times = []

            for batch_start in range(0, len(load_test_docs), batch_size):
                batch_docs = load_test_docs[batch_start : batch_start + batch_size]

                batch_start_time = time.time()

                # Process batch concurrently
                async def process_batch_doc(doc):
                    collection = determine_collection_for_document(doc)
                    embedding = await mock_embedding_service.generate_embedding(
                        doc["content"]
                    )
                    return await mock_adapter.upsert_points(
                        collection_name=collection,
                        points=[{"id": doc["id"], "vector": embedding, "payload": doc}],
                    )

                batch_tasks = [process_batch_doc(doc) for doc in batch_docs]
                await asyncio.gather(*batch_tasks)

                batch_end_time = time.time()
                batch_time = batch_end_time - batch_start_time
                processing_times.append(batch_time)

            # Verify load performance
            avg_batch_time = sum(processing_times) / len(processing_times)
            max_batch_time = max(processing_times)

            assert (
                avg_batch_time < 1.0
            ), f"Average batch processing time too high: {avg_batch_time:.2f}s"
            assert (
                max_batch_time < 2.0
            ), f"Maximum batch processing time too high: {max_batch_time:.2f}s"

            # Test search performance under load
            search_queries = [
                "technical diagnosis",
                "specification document",
                "quality assessment",
                "design patterns",
                "documentation notes",
            ]

            search_start_time = time.time()

            # Perform concurrent searches
            async def perform_search(query):
                search_embedding = await mock_embedding_service.generate_embedding(
                    query
                )
                quality_results = await mock_adapter.search(
                    collection_name="quality_vectors",
                    query_vector=search_embedding,
                    limit=5,
                )
                archon_results = await mock_adapter.search(
                    collection_name="archon_vectors",
                    query_vector=search_embedding,
                    limit=5,
                )
                return {"quality": quality_results, "archon": archon_results}

            search_tasks = [perform_search(query) for query in search_queries]
            search_results = await asyncio.gather(*search_tasks)

            search_end_time = time.time()
            total_search_time = search_end_time - search_start_time

            assert (
                total_search_time < 1.0
            ), f"Concurrent search time too high: {total_search_time:.2f}s"
            assert len(search_results) == len(search_queries)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
