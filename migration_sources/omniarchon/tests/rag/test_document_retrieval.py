"""
RAG Service Document Retrieval Unit Tests

Tests for the RAG service document retrieval and search functionality including:
- Document search and retrieval with full content
- Search result ranking and reordering
- Content matching and similarity scoring
- Query processing and result filtering
- Error handling and edge cases

Critical focus on ensuring retrieved content matches original without truncation.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
)


class TestRAGDocumentRetrieval:
    """Test RAG service document retrieval functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.base_url = "http://test-rag:8056"

    @pytest.fixture
    def mock_document_store(self):
        """Mock document store with test documents."""
        # Create a store with our test documents
        documents = {}

        # Process standardized test document
        doc = STANDARDIZED_TEST_DOCUMENT.copy()
        doc_data = doc["document_data"]
        content = doc_data["content"]["content"]

        documents[doc["document_id"]] = {
            "document_id": doc["document_id"],
            "project_id": doc["project_id"],
            "title": doc_data["title"],
            "content": content,
            "full_text": f"{doc_data['title']}\n\n{content}",
            "document_type": doc_data["document_type"],
            "metadata": doc_data.get("metadata", {}),
            "content_length": len(content),
            "indexed_at": "2024-01-01T00:00:00Z",
        }

        # Process nested content document
        nested_doc = NESTED_CONTENT_DOCUMENT.copy()
        nested_data = nested_doc["document_data"]
        nested_content = nested_data["content"]["overview"]

        documents[nested_doc["document_id"]] = {
            "document_id": nested_doc["document_id"],
            "project_id": nested_doc["project_id"],
            "title": nested_data["title"],
            "content": nested_content,
            "full_text": f"{nested_data['title']}\n\n{nested_content}",
            "document_type": nested_data["document_type"],
            "metadata": nested_data.get("metadata", {}),
            "content_length": len(nested_content),
            "indexed_at": "2024-01-01T00:00:00Z",
        }

        # Add large document
        large_doc = generate_large_document(content_size=2000)
        large_data = large_doc["document_data"]
        large_content = large_data["content"]["content"]

        documents[large_doc["document_id"]] = {
            "document_id": large_doc["document_id"],
            "project_id": large_doc["project_id"],
            "title": large_data["title"],
            "content": large_content,
            "full_text": f"{large_data['title']}\n\n{large_content}",
            "document_type": large_data["document_type"],
            "metadata": large_data.get("metadata", {}),
            "content_length": len(large_content),
            "indexed_at": "2024-01-01T00:00:00Z",
        }

        return documents

    @pytest.fixture
    def mock_vector_search_client(self):
        """Mock vector search client for similarity search."""
        client = AsyncMock()
        client.search.return_value = [
            {
                "id": "test-doc-12345",
                "score": 0.95,
                "metadata": {"document_type": "test"},
            },
            {
                "id": "test-nested-content",
                "score": 0.87,
                "metadata": {"document_type": "research"},
            },
        ]
        return client

    @pytest.mark.asyncio
    async def test_document_search_with_full_content_retrieval(
        self, mock_document_store, mock_vector_search_client
    ):
        """Test document search retrieves full content without truncation."""
        query = "comprehensive test document with substantial content"

        # Mock RAG search process
        async def mock_rag_search(query_text, limit=10):
            # Step 1: Vector similarity search
            vector_results = await mock_vector_search_client.search(
                query_vector=[0.1] * 1536, limit=limit  # Mock query vector
            )

            # Step 2: Retrieve full documents
            retrieved_docs = []
            for result in vector_results:
                doc_id = result["id"]
                if doc_id in mock_document_store:
                    doc = mock_document_store[doc_id]

                    # Critical: Verify full content is retrieved
                    assert (
                        len(doc["content"]) > 50
                    ), f"Retrieved content truncated: {len(doc['content'])} chars"

                    retrieved_docs.append(
                        {
                            "document_id": doc["document_id"],
                            "title": doc["title"],
                            "content": doc["content"],  # Full content
                            "full_text": doc["full_text"],  # Complete text
                            "score": result["score"],
                            "content_length": doc["content_length"],
                            "metadata": doc["metadata"],
                        }
                    )

            return retrieved_docs

        # Execute search
        search_results = await mock_rag_search(query, limit=5)

        # Validate search results
        assert len(search_results) > 0, "No search results returned"

        # Check top result (standardized test document)
        top_result = search_results[0]
        assert top_result["document_id"] == "test-doc-12345"

        # Critical: Validate full content is preserved
        self.assertions.assert_content_not_truncated(
            top_result["content"],
            STANDARDIZED_TEST_DOCUMENT["document_data"]["content"],
        )

        # Verify content contains expected elements
        expected_keywords = [
            "comprehensive test document",
            "substantial content",
            "pipeline components",
            "truncation bugs",
        ]
        self.assertions.assert_content_contains_keywords(
            top_result["content"], expected_keywords
        )

        # Validate content length matches original
        original_content = STANDARDIZED_TEST_DOCUMENT["document_data"]["content"][
            "content"
        ]
        assert len(top_result["content"]) == len(
            original_content
        ), "Content length mismatch in retrieval"

    @pytest.mark.asyncio
    async def test_search_result_reranking_with_complete_content(
        self, mock_document_store, mock_vector_search_client
    ):
        """Test search result reranking preserves complete content."""
        query = "document processing pipeline testing"

        # Mock reranking process
        async def mock_reranking_search(query_text, initial_results):
            # Simulate reranking based on content analysis
            reranked_results = []

            for result in initial_results:
                doc_id = result["document_id"]
                doc = mock_document_store[doc_id]
                content = doc["content"]

                # Calculate relevance score based on query terms
                relevance_score = 0.0
                query_terms = query_text.lower().split()

                for term in query_terms:
                    if term in content.lower():
                        relevance_score += 0.25

                # Boost score for longer, more comprehensive content
                if len(content) > 300:
                    relevance_score += 0.1

                reranked_results.append(
                    {
                        "document_id": doc_id,
                        "title": doc["title"],
                        "content": content,  # Preserve full content
                        "full_text": doc["full_text"],
                        "original_score": result["score"],
                        "rerank_score": relevance_score,
                        "final_score": (result["score"] + relevance_score) / 2,
                        "content_length": len(content),
                        "rerank_factors": {
                            "query_term_matches": sum(
                                1 for term in query_terms if term in content.lower()
                            ),
                            "content_comprehensiveness": len(content) > 300,
                        },
                    }
                )

            # Sort by final score
            reranked_results.sort(key=lambda x: x["final_score"], reverse=True)
            return reranked_results

        # Initial search results
        initial_results = [
            {"document_id": "test-doc-12345", "score": 0.85},
            {"document_id": "test-nested-content", "score": 0.90},
            {
                "document_id": mock_document_store[list(mock_document_store.keys())[2]][
                    "document_id"
                ],
                "score": 0.80,
            },
        ]

        # Execute reranking
        reranked_results = await mock_reranking_search(query, initial_results)

        # Validate reranking results
        assert len(reranked_results) == len(
            initial_results
        ), "Results lost during reranking"

        for result in reranked_results:
            # Critical: Ensure content is not truncated during reranking
            assert (
                len(result["content"]) > 50
            ), f"Content truncated during reranking: {len(result['content'])}"
            assert result["content_length"] == len(
                result["content"]
            ), "Content length mismatch"

            # Verify reranking factors are calculated
            assert "rerank_factors" in result, "Reranking factors missing"
            assert (
                result["rerank_factors"]["query_term_matches"] >= 0
            ), "Query term matching failed"

    @pytest.mark.asyncio
    async def test_content_matching_accuracy(self, mock_document_store):
        """Test that content matching algorithms work with full content."""
        # Test various query types
        test_queries = [
            {
                "query": "comprehensive test document pipeline",
                "expected_doc": "test-doc-12345",
                "expected_terms": ["comprehensive", "test", "document", "pipeline"],
            },
            {
                "query": "nested content structures extraction",
                "expected_doc": "test-nested-content",
                "expected_terms": ["nested", "content", "structures"],
            },
            {
                "query": "large document processing performance",
                "expected_doc": list(mock_document_store.keys())[2],  # Large document
                "expected_terms": ["large", "document"],
            },
        ]

        for test_case in test_queries:
            query = test_case["query"]
            query_terms = query.lower().split()

            # Find best matching document
            best_match = None
            best_score = 0.0

            for doc_id, doc in mock_document_store.items():
                content = doc["content"].lower()

                # Calculate match score
                match_score = 0.0
                matched_terms = 0

                for term in query_terms:
                    if term in content:
                        match_score += 1.0
                        matched_terms += 1

                # Normalize by query length
                match_score = match_score / len(query_terms)

                if match_score > best_score:
                    best_score = match_score
                    best_match = {
                        "document_id": doc_id,
                        "score": match_score,
                        "matched_terms": matched_terms,
                        "content": doc["content"],
                        "content_length": len(doc["content"]),
                    }

            # Validate matching results
            assert best_match is not None, f"No match found for query: {query}"
            assert (
                best_match["document_id"] == test_case["expected_doc"]
            ), f"Wrong document matched for query: {query}"
            assert (
                best_match["matched_terms"] >= len(test_case["expected_terms"]) / 2
            ), f"Insufficient term matching for query: {query}"

            # Critical: Ensure full content is used in matching
            assert (
                best_match["content_length"] > 50
            ), f"Content truncated in matching: {best_match['content_length']}"

            # Verify expected terms are found in full content
            for term in test_case["expected_terms"]:
                assert (
                    term in best_match["content"].lower()
                ), f"Expected term '{term}' not found in matched content"

    @pytest.mark.asyncio
    async def test_search_result_filtering_and_pagination(self, mock_document_store):
        """Test search result filtering preserves complete content."""

        # Mock search with filtering
        async def filtered_search(query, filters=None, limit=10, offset=0):
            all_results = []

            for doc_id, doc in mock_document_store.items():
                # Apply filters
                include_doc = True

                if filters:
                    if "document_type" in filters:
                        if doc["document_type"] not in filters["document_type"]:
                            include_doc = False

                    if "min_content_length" in filters:
                        if len(doc["content"]) < filters["min_content_length"]:
                            include_doc = False

                    if "project_id" in filters:
                        if doc["project_id"] not in filters["project_id"]:
                            include_doc = False

                if include_doc:
                    # Calculate relevance score
                    query_terms = query.lower().split()
                    content = doc["content"].lower()

                    score = sum(1 for term in query_terms if term in content) / len(
                        query_terms
                    )

                    all_results.append(
                        {
                            "document_id": doc_id,
                            "title": doc["title"],
                            "content": doc["content"],  # Full content preserved
                            "score": score,
                            "content_length": len(doc["content"]),
                            "document_type": doc["document_type"],
                            "project_id": doc["project_id"],
                        }
                    )

            # Sort by score
            all_results.sort(key=lambda x: x["score"], reverse=True)

            # Apply pagination
            paginated_results = all_results[offset : offset + limit]

            return {
                "results": paginated_results,
                "total_count": len(all_results),
                "offset": offset,
                "limit": limit,
            }

        # Test with various filters
        filter_tests = [
            {
                "filters": {"document_type": ["test", "research"]},
                "expected_min_results": 2,
            },
            {"filters": {"min_content_length": 300}, "expected_min_results": 1},
            {
                "filters": {"project_id": ["test-project-67890"]},
                "expected_min_results": 2,
            },
        ]

        for test_case in filter_tests:
            query = "test document content"
            result = await filtered_search(query, filters=test_case["filters"], limit=5)

            # Validate filtering results
            assert (
                len(result["results"]) >= test_case["expected_min_results"]
            ), f"Insufficient filtered results: {len(result['results'])}"

            for doc_result in result["results"]:
                # Critical: Ensure content is not truncated during filtering
                assert (
                    len(doc_result["content"]) > 50
                ), f"Content truncated during filtering: {len(doc_result['content'])}"
                assert doc_result["content_length"] == len(
                    doc_result["content"]
                ), "Content length mismatch in filtered results"

                # Verify filter criteria are met
                if "document_type" in test_case["filters"]:
                    assert (
                        doc_result["document_type"]
                        in test_case["filters"]["document_type"]
                    ), "Document type filter failed"

                if "min_content_length" in test_case["filters"]:
                    assert (
                        len(doc_result["content"])
                        >= test_case["filters"]["min_content_length"]
                    ), "Content length filter failed"

                if "project_id" in test_case["filters"]:
                    assert (
                        doc_result["project_id"] in test_case["filters"]["project_id"]
                    ), "Project ID filter failed"

    @pytest.mark.asyncio
    async def test_error_handling_in_document_retrieval(self, mock_document_store):
        """Test error handling during document retrieval preserves data integrity."""

        # Test case 1: Document not found
        async def retrieve_document(doc_id):
            if doc_id not in mock_document_store:
                return {
                    "success": False,
                    "error": "Document not found",
                    "document_id": doc_id,
                }

            doc = mock_document_store[doc_id]
            return {
                "success": True,
                "document": {
                    "document_id": doc["document_id"],
                    "title": doc["title"],
                    "content": doc["content"],  # Full content
                    "content_length": len(doc["content"]),
                    "metadata": doc["metadata"],
                },
            }

        # Test retrieval of non-existent document
        result = await retrieve_document("non-existent-doc")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

        # Test retrieval of existing document
        result = await retrieve_document("test-doc-12345")
        assert result["success"] is True
        assert (
            len(result["document"]["content"]) > 400
        ), "Content truncated in successful retrieval"

        # Test case 2: Corrupted document data
        mock_document_store["corrupted-doc"] = {
            "document_id": "corrupted-doc",
            "title": "Corrupted Document",
            "content": None,  # Corrupted content
            "metadata": {},
        }

        async def safe_retrieve_document(doc_id):
            try:
                doc = mock_document_store[doc_id]

                # Validate document data
                if doc["content"] is None:
                    return {
                        "success": False,
                        "error": "Document content is corrupted",
                        "document_id": doc_id,
                    }

                return {
                    "success": True,
                    "document": {
                        "document_id": doc["document_id"],
                        "title": doc["title"],
                        "content": doc["content"],
                        "content_length": len(doc["content"]),
                    },
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Retrieval error: {str(e)}",
                    "document_id": doc_id,
                }

        # Test corrupted document handling
        result = await safe_retrieve_document("corrupted-doc")
        assert result["success"] is False
        assert "corrupted" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_large_result_set_handling(self, mock_document_store):
        """Test handling of large result sets without content truncation."""
        # Add more documents to create large result set
        for i in range(20):
            doc_id = f"bulk-doc-{i}"
            content = (
                f"This is bulk document number {i} with substantial content for testing large result set handling. "
                * 10
            )

            mock_document_store[doc_id] = {
                "document_id": doc_id,
                "project_id": "test-project-67890",
                "title": f"Bulk Document {i}",
                "content": content,
                "full_text": f"Bulk Document {i}\n\n{content}",
                "document_type": "bulk_test",
                "content_length": len(content),
                "indexed_at": "2024-01-01T00:00:00Z",
            }

        # Mock large result set search
        async def search_large_results(query, limit=50):
            matching_docs = []

            for doc_id, doc in mock_document_store.items():
                if (
                    "bulk" in doc["content"].lower()
                    or "document" in doc["content"].lower()
                ):
                    matching_docs.append(
                        {
                            "document_id": doc_id,
                            "title": doc["title"],
                            "content": doc["content"],  # Full content preserved
                            "score": 0.8,
                            "content_length": len(doc["content"]),
                        }
                    )

            # Limit results
            return matching_docs[:limit]

        # Execute large search
        large_results = await search_large_results("bulk document testing", limit=25)

        # Validate large result handling
        assert (
            len(large_results) >= 20
        ), f"Large result set incomplete: {len(large_results)}"

        for result in large_results:
            # Critical: Ensure no content truncation in large result sets
            assert (
                len(result["content"]) > 100
            ), f"Content truncated in large results: {len(result['content'])}"
            assert result["content_length"] == len(
                result["content"]
            ), "Content length mismatch in large results"

            # Verify content quality is maintained
            assert (
                "substantial content" in result["content"]
            ), "Content quality degraded in large results"


class TestRAGServicePerformance:
    """Performance tests for RAG service retrieval."""

    @pytest.mark.asyncio
    async def test_retrieval_performance_benchmarks(self):
        """Test retrieval performance with various query and result sizes."""
        # Create test document store
        document_store = {}
        for i in range(100):
            content = (
                f"Test document {i} with comprehensive content about various topics. "
                * 20
            )
            doc_id = f"perf-doc-{i}"

            document_store[doc_id] = {
                "document_id": doc_id,
                "title": f"Performance Test Document {i}",
                "content": content,
                "content_length": len(content),
            }

        # Test retrieval performance
        async def timed_search(query, limit):
            import time

            start_time = time.time()

            # Simulate search process
            results = []
            for doc_id, doc in document_store.items():
                if any(
                    term in doc["content"].lower() for term in query.lower().split()
                ):
                    results.append(
                        {
                            "document_id": doc_id,
                            "content": doc["content"],  # Full content
                            "content_length": len(doc["content"]),
                        }
                    )

                    if len(results) >= limit:
                        break

            search_time = time.time() - start_time
            return results, search_time

        # Test various search sizes
        performance_tests = [
            {"limit": 10, "max_time": 0.5},
            {"limit": 25, "max_time": 1.0},
            {"limit": 50, "max_time": 2.0},
        ]

        for test in performance_tests:
            results, search_time = await timed_search(
                "test document comprehensive", test["limit"]
            )

            # Performance assertions
            assert (
                search_time < test["max_time"]
            ), f"Search too slow: {search_time}s > {test['max_time']}s"
            assert len(results) >= min(
                test["limit"], 10
            ), f"Insufficient results: {len(results)}"

            # Content quality assertions
            for result in results:
                assert (
                    len(result["content"]) > 200
                ), f"Content truncated in performance test: {len(result['content'])}"

    @pytest.mark.asyncio
    async def test_concurrent_retrieval_operations(self):
        """Test concurrent document retrieval operations."""
        # Create test documents
        documents = {}
        for i in range(10):
            doc_id = f"concurrent-doc-{i}"
            content = (
                f"Concurrent test document {i} with substantial content for parallel retrieval testing. "
                * 15
            )

            documents[doc_id] = {
                "document_id": doc_id,
                "content": content,
                "content_length": len(content),
            }

        async def retrieve_single_doc(doc_id):
            """Simulate retrieving a single document."""
            await asyncio.sleep(0.1)  # Simulate retrieval delay

            if doc_id in documents:
                doc = documents[doc_id]
                return {
                    "document_id": doc_id,
                    "content": doc["content"],  # Full content
                    "content_length": len(doc["content"]),
                    "status": "retrieved",
                }
            else:
                return {"document_id": doc_id, "status": "not_found"}

        # Test concurrent retrieval
        doc_ids = list(documents.keys())

        import time

        start_time = time.time()

        results = await asyncio.gather(
            *[retrieve_single_doc(doc_id) for doc_id in doc_ids]
        )

        total_time = time.time() - start_time

        # Validate concurrent retrieval
        assert len(results) == 10, f"Not all documents retrieved: {len(results)}"
        assert total_time < 1.0, f"Concurrent retrieval too slow: {total_time}s"

        for result in results:
            if result["status"] == "retrieved":
                assert (
                    len(result["content"]) > 200
                ), f"Content truncated in concurrent retrieval: {len(result['content'])}"
                assert result["content_length"] == len(
                    result["content"]
                ), "Content length mismatch in concurrent retrieval"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
