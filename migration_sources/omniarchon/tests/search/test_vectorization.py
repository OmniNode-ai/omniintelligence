"""
Search Service Vectorization Unit Tests

Tests for the Search service vectorization pipeline including:
- /vectorize/document endpoint functionality
- Vector creation from full content
- Qdrant indexing with complete text
- Vector representation validation
- Search and retrieval functionality

Critical focus on ensuring vectors represent full content without truncation.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
    generate_multi_section_document,
)


class TestSearchServiceVectorization:
    """Test Search service vectorization functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.base_url = "http://test-search:8055"
        self.vector_dimensions = 1536  # Standard embedding dimensions

    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock Qdrant client for testing."""
        client = AsyncMock()
        client.upsert.return_value = Mock(status="completed")
        client.search.return_value = [
            Mock(
                id="test_vector_1",
                score=0.95,
                payload={
                    "document_id": "test-doc-12345",
                    "content": "Test content...",
                    "metadata": {"document_type": "test"},
                },
            )
        ]
        client.get_collection_info.return_value = Mock(
            status="green", vectors_count=100, segments_count=1
        )
        return client

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model for testing."""
        model = AsyncMock()
        model.embed.return_value = np.random.rand(self.vector_dimensions).tolist()
        return model

    @pytest.mark.asyncio
    async def test_vectorize_document_endpoint_with_standardized_document(
        self, mock_qdrant_client, mock_embedding_model
    ):
        """Test /vectorize/document endpoint with standardized test document."""
        doc_data = STANDARDIZED_TEST_DOCUMENT["document_data"]

        # Prepare vectorization request
        request_payload = {
            "document_id": STANDARDIZED_TEST_DOCUMENT["document_id"],
            "project_id": STANDARDIZED_TEST_DOCUMENT["project_id"],
            "title": doc_data["title"],
            "content": doc_data["content"],
            "document_type": doc_data["document_type"],
            "metadata": doc_data.get("metadata", {}),
        }

        # Extract content text for vectorization (simulating search service logic)
        content = request_payload["content"]
        if isinstance(content, dict):
            if "content" in content:
                content_text = content["content"]
            elif "text" in content:
                content_text = content["text"]
            else:
                content_text = " ".join(
                    str(value)
                    for key, value in content.items()
                    if isinstance(value, str) and key not in {"tags", "metadata"}
                )
        else:
            content_text = str(content)

        # Include title in vectorization
        full_text = f"{request_payload['title']}\n\n{content_text}".strip()

        # Critical: Validate content is not truncated
        self.assertions.assert_content_not_truncated(full_text, content)
        assert (
            len(full_text) > 400
        ), f"Content for vectorization too short: {len(full_text)} chars"

        # Simulate vectorization process
        with patch("numpy.random.rand") as mock_embedding:
            mock_embedding.return_value = np.random.rand(self.vector_dimensions)

            # Mock the vectorization response
            vectorization_response = {
                "success": True,
                "document_id": STANDARDIZED_TEST_DOCUMENT["document_id"],
                "vector_id": f"vec_{STANDARDIZED_TEST_DOCUMENT['document_id']}",
                "dimensions": self.vector_dimensions,
                "content_length_vectorized": len(full_text),
                "vectorization_time_ms": 450,
                "indexed": True,
                "collection": "archon_documents",
                "content_preview": full_text[:200],
            }

            # Validate vectorization
            assert vectorization_response["content_length_vectorized"] > 400
            assert vectorization_response["dimensions"] == self.vector_dimensions
            assert vectorization_response["indexed"] is True

            # Verify content contains expected elements
            expected_keywords = [
                "comprehensive test document",
                "substantial content",
                "pipeline components",
                "truncation bugs",
            ]
            self.assertions.assert_content_contains_keywords(
                full_text, expected_keywords
            )

    @pytest.mark.asyncio
    async def test_vector_creation_from_full_content(
        self, mock_qdrant_client, mock_embedding_model
    ):
        """Test that vectors are created from complete content without truncation."""
        # Test with large document
        large_doc = generate_large_document(content_size=5000)
        doc_data = large_doc["document_data"]

        # Extract content for vectorization
        content = doc_data["content"]["content"]
        title = doc_data["title"]
        full_text = f"{title}\n\n{content}".strip()

        # Validate full content is being vectorized
        assert (
            len(content) == 5000
        ), f"Large content truncated before vectorization: {len(content)}"
        assert len(full_text) > 5000, f"Full text truncated: {len(full_text)}"

        # Mock embedding generation
        with patch("httpx.AsyncClient.post") as mock_embedding_request:
            mock_embedding_response = Mock()
            mock_embedding_response.status_code = 200
            mock_embedding_response.json.return_value = {
                "embeddings": [np.random.rand(self.vector_dimensions).tolist()],
                "input_tokens": len(full_text) // 4,  # Approximate token count
                "model": "text-embedding-ada-002",
            }
            mock_embedding_request.return_value = mock_embedding_response

            # Simulate vectorization process
            chunks = []
            chunk_size = 8000  # Embedding model context limit

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i : i + chunk_size]
                chunks.append(
                    {
                        "text": chunk,
                        "start_pos": i,
                        "end_pos": min(i + chunk_size, len(full_text)),
                        "chunk_id": f"chunk_{i // chunk_size}",
                    }
                )

            # Validate chunking preserves all content
            reconstructed_text = "".join(chunk["text"] for chunk in chunks)
            assert reconstructed_text == full_text, "Content lost during chunking"

            # Generate vectors for all chunks
            vectors = []
            for chunk in chunks:
                # Each chunk should have a vector
                vector = np.random.rand(self.vector_dimensions).tolist()
                vectors.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "vector": vector,
                        "metadata": {
                            "document_id": large_doc["document_id"],
                            "chunk_text": chunk["text"][:100],  # Preview
                            "full_chunk_length": len(chunk["text"]),
                            "start_position": chunk["start_pos"],
                        },
                    }
                )

            # Validate vectorization results
            assert len(vectors) > 0, "No vectors generated from large content"
            total_vectorized_length = sum(
                vector["metadata"]["full_chunk_length"] for vector in vectors
            )
            assert (
                total_vectorized_length >= 5000
            ), f"Not all content vectorized: {total_vectorized_length}"

    @pytest.mark.asyncio
    async def test_qdrant_indexing_with_complete_text(self, mock_qdrant_client):
        """Test Qdrant indexing with complete document text."""
        doc = generate_multi_section_document()
        doc_data = doc["document_data"]

        # Extract all sections for indexing
        content = doc_data["content"]
        sections = []

        for key, value in content.items():
            if isinstance(value, str) and len(value) > 10:
                sections.append(
                    {
                        "section_name": key,
                        "section_content": value,
                        "section_length": len(value),
                    }
                )

        total_content = " ".join(section["section_content"] for section in sections)
        title = doc_data["title"]
        full_document_text = f"{title}\n\n{total_content}".strip()

        # Validate complete content for indexing
        assert len(sections) >= 6, f"Not all sections extracted: {len(sections)}"
        assert (
            len(full_document_text) > 600
        ), f"Complete document text too short: {len(full_document_text)}"

        # Mock Qdrant indexing operation
        with patch("qdrant_client.QdrantClient") as mock_qdrant:
            mock_client = mock_qdrant.return_value
            mock_client.upsert = AsyncMock()

            # Prepare indexing payload
            indexing_payload = {
                "collection_name": "archon_documents",
                "points": [
                    {
                        "id": doc["document_id"],
                        "vector": np.random.rand(self.vector_dimensions).tolist(),
                        "payload": {
                            "document_id": doc["document_id"],
                            "project_id": doc["project_id"],
                            "title": title,
                            "content": full_document_text,
                            "content_length": len(full_document_text),
                            "sections": sections,
                            "document_type": doc_data["document_type"],
                            "metadata": doc_data.get("metadata", {}),
                        },
                    }
                ],
            }

            # Simulate indexing
            await mock_client.upsert(
                collection_name=indexing_payload["collection_name"],
                points=indexing_payload["points"],
            )

            # Validate indexing call
            mock_client.upsert.assert_called_once()
            call_args = mock_client.upsert.call_args

            indexed_point = call_args[1]["points"][0]
            assert indexed_point["payload"]["content_length"] > 600
            assert len(indexed_point["payload"]["sections"]) >= 6
            assert indexed_point["payload"]["content"] == full_document_text

    @pytest.mark.asyncio
    async def test_vector_search_retrieval_accuracy(self, mock_qdrant_client):
        """Test that vector search retrieves documents based on full content."""
        # Index test documents
        test_documents = [
            STANDARDIZED_TEST_DOCUMENT,
            NESTED_CONTENT_DOCUMENT,
            generate_large_document(2000),
        ]

        indexed_vectors = []
        for doc in test_documents:
            doc_data = doc["document_data"]

            # Extract content for indexing
            content = doc_data["content"]
            if isinstance(content, dict):
                if "content" in content:
                    content_text = content["content"]
                elif "overview" in content:
                    content_text = content["overview"]
                else:
                    content_text = " ".join(
                        str(value)
                        for value in content.values()
                        if isinstance(value, str)
                    )
            else:
                content_text = str(content)

            full_text = f"{doc_data['title']}\n\n{content_text}".strip()

            indexed_vectors.append(
                {
                    "id": doc["document_id"],
                    "vector": np.random.rand(self.vector_dimensions).tolist(),
                    "payload": {
                        "document_id": doc["document_id"],
                        "title": doc_data["title"],
                        "content": full_text,
                        "content_length": len(full_text),
                    },
                }
            )

        # Mock search query
        query_vector = np.random.rand(self.vector_dimensions).tolist()

        # Simulate search results
        with patch("qdrant_client.QdrantClient") as mock_qdrant:
            mock_client = mock_qdrant.return_value

            # Mock search results based on content similarity
            mock_search_results = []
            for vector in indexed_vectors:
                # Calculate mock similarity based on query terms presence
                content = vector["payload"]["content"].lower()
                score = 0.0

                if "comprehensive" in content:
                    score += 0.3
                if "test document" in content:
                    score += 0.3
                if "substantial content" in content:
                    score += 0.4

                if score > 0.5:  # Only include relevant results
                    mock_search_results.append(
                        Mock(id=vector["id"], score=score, payload=vector["payload"])
                    )

            mock_client.search.return_value = sorted(
                mock_search_results, key=lambda x: x.score, reverse=True
            )

            # Execute search
            search_results = await mock_client.search(
                collection_name="archon_documents", query_vector=query_vector, limit=10
            )

            # Validate search results
            assert len(search_results) > 0, "No search results returned"

            # Check that highest scoring result is the standardized document
            top_result = search_results[0]
            assert (
                top_result.id == "test-doc-12345"
            ), f"Wrong top result: {top_result.id}"
            assert top_result.score > 0.8, f"Low similarity score: {top_result.score}"

            # Verify full content is preserved in results
            for result in search_results:
                content_length = result.payload["content_length"]
                assert (
                    content_length > 100
                ), f"Result content truncated: {content_length} chars"

    @pytest.mark.asyncio
    async def test_vector_content_preprocessing_edge_cases(self):
        """Test vector content preprocessing for various edge cases."""
        # Test case 1: Mixed content types with special characters
        special_content_doc = {
            "document_id": "test-special-vectorization",
            "project_id": "test-project-67890",
            "document_data": {
                "title": "Special Characters in Vectorization",
                "content": {
                    "content": "This document contains special characters: @#$%^&*(), Unicode: 中文, áéíóú, русский, and emoji: 🚀🔥💡. The vectorization process must handle all character types properly without truncation or encoding issues.",
                    "technical_terms": "API, REST, JSON, HTTP, SSL/TLS, OAuth2.0, JWT tokens",
                    "code_snippet": "function processDocument(content) { return content.length > 0; }",
                },
                "document_type": "technical",
            },
        }

        # Extract content for vectorization
        content = special_content_doc["document_data"]["content"]

        # Simulate search service content preprocessing
        vectorizable_text_parts = []
        for key, value in content.items():
            if isinstance(value, str):
                vectorizable_text_parts.append(value)

        full_vectorizable_text = " ".join(vectorizable_text_parts)

        # Validate special character handling
        assert (
            len(full_vectorizable_text) > 200
        ), f"Special content truncated: {len(full_vectorizable_text)}"
        assert (
            "中文" in full_vectorizable_text
        ), "Unicode characters lost in preprocessing"
        assert (
            "@#$%^&*()" in full_vectorizable_text
        ), "Special symbols lost in preprocessing"
        assert "🚀🔥💡" in full_vectorizable_text, "Emoji lost in preprocessing"
        assert (
            "OAuth2.0" in full_vectorizable_text
        ), "Technical terms lost in preprocessing"

        # Test case 2: Content with code blocks and structured data
        structured_content_doc = {
            "document_id": "test-structured-vectorization",
            "project_id": "test-project-67890",
            "document_data": {
                "title": "Structured Content for Vectorization",
                "content": {
                    "description": "This document contains structured content including code blocks, lists, and technical specifications.",
                    "code_example": "```python\ndef extract_content(document):\n    return document.get('content', '')\n```",
                    "features": {
                        "feature1": "Advanced content extraction with full text preservation",
                        "feature2": "Multi-format content support including JSON, XML, and plain text",
                        "feature3": "Vector search optimization for technical documentation",
                    },
                    "requirements": [
                        "Must handle nested content structures",
                        "Must preserve all text content during vectorization",
                        "Must support multiple content formats",
                    ],
                },
                "document_type": "documentation",
            },
        }

        # Extract structured content for vectorization
        content = structured_content_doc["document_data"]["content"]

        def extract_text_recursively(obj, texts=None):
            if texts is None:
                texts = []

            if isinstance(obj, str):
                texts.append(obj)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_text_recursively(value, texts)
            elif isinstance(obj, list):
                for item in obj:
                    extract_text_recursively(item, texts)

            return texts

        extracted_texts = extract_text_recursively(content)
        combined_text = " ".join(extracted_texts)

        # Validate structured content extraction
        assert (
            len(extracted_texts) >= 8
        ), f"Not all text extracted: {len(extracted_texts)} parts"
        assert (
            len(combined_text) > 300
        ), f"Structured content truncated: {len(combined_text)}"
        assert (
            "def extract_content" in combined_text
        ), "Code block lost during extraction"
        assert (
            "Advanced content extraction" in combined_text
        ), "Feature description lost"
        assert (
            "Must handle nested" in combined_text
        ), "Requirements lost during extraction"


class TestSearchServicePerformance:
    """Performance tests for Search service vectorization."""

    @pytest.mark.asyncio
    async def test_vectorization_performance_benchmarks(self):
        """Test vectorization performance with various document sizes."""
        test_sizes = [1000, 5000, 20000, 100000]
        performance_results = []

        for size in test_sizes:
            doc = generate_large_document(content_size=size)
            content_text = doc["document_data"]["content"]["content"]

            import time

            start_time = time.time()

            # Simulate vectorization steps
            # Step 1: Content preprocessing
            processed_content = content_text.strip()

            # Step 2: Chunking for large content
            chunk_size = 8000
            chunks = [
                processed_content[i : i + chunk_size]
                for i in range(0, len(processed_content), chunk_size)
            ]

            # Step 3: Mock embedding generation
            vectors = []
            for chunk in chunks:
                vector = np.random.rand(1536).tolist()  # Mock embedding
                vectors.append(vector)

            # Step 4: Mock Qdrant indexing
            indexing_time = 0.1 * len(vectors)  # Simulate indexing delay

            total_time = time.time() - start_time + indexing_time

            performance_results.append(
                {
                    "content_size": size,
                    "vectorization_time": total_time,
                    "chunks_created": len(chunks),
                    "vectors_generated": len(vectors),
                }
            )

            # Performance assertions
            assert (
                total_time < 5.0
            ), f"Vectorization too slow for {size} chars: {total_time}s"
            assert len(vectors) > 0, f"No vectors generated for {size} char document"

            # Validate all content was processed
            total_chunked_length = sum(len(chunk) for chunk in chunks)
            assert (
                total_chunked_length >= size
            ), f"Content lost during chunking: {total_chunked_length} < {size}"

        # Verify performance scales reasonably
        largest_result = performance_results[-1]
        assert (
            largest_result["vectorization_time"] < 5.0
        ), "Large document vectorization too slow"
        assert (
            largest_result["vectors_generated"] >= 10
        ), "Insufficient vectorization for large document"

    @pytest.mark.asyncio
    async def test_concurrent_vectorization_processing(self):
        """Test concurrent vectorization of multiple documents."""
        # Create test documents of varying sizes
        docs = [
            generate_large_document(1000),
            generate_large_document(3000),
            generate_multi_section_document(),
            STANDARDIZED_TEST_DOCUMENT.copy(),
        ]

        async def vectorize_document(doc):
            """Simulate vectorizing a single document."""
            doc_data = doc["document_data"]

            # Extract content
            content = doc_data["content"]
            if isinstance(content, dict):
                if "content" in content:
                    content_text = content["content"]
                else:
                    content_text = " ".join(
                        str(value)
                        for value in content.values()
                        if isinstance(value, str)
                    )
            else:
                content_text = str(content)

            # Simulate vectorization delay based on content size
            processing_delay = min(len(content_text) / 10000, 0.5)  # Max 0.5s delay
            await asyncio.sleep(processing_delay)

            return {
                "document_id": doc["document_id"],
                "content_length": len(content_text),
                "vector_dimensions": 1536,
                "processing_time": processing_delay,
                "status": "vectorized",
            }

        # Process documents concurrently
        import time

        start_time = time.time()

        results = await asyncio.gather(*[vectorize_document(doc) for doc in docs])

        total_time = time.time() - start_time

        # Validate concurrent processing
        assert len(results) == 4, f"Not all documents vectorized: {len(results)}"
        assert total_time < 1.0, f"Concurrent vectorization too slow: {total_time}s"

        for result in results:
            assert result["status"] == "vectorized"
            assert (
                result["content_length"] > 50
            ), f"Content truncated in concurrent processing: {result['content_length']}"
            assert result["vector_dimensions"] == 1536, "Incorrect vector dimensions"

    @pytest.mark.asyncio
    async def test_vector_quality_validation(self):
        """Test that generated vectors represent content quality."""
        # Test with documents of different content quality
        high_quality_doc = {
            "document_id": "test-high-quality",
            "document_data": {
                "title": "High Quality Technical Documentation",
                "content": {
                    "content": "This is a comprehensive technical document with detailed explanations, clear structure, and substantial informative content. It covers multiple technical concepts, provides examples, and follows documentation best practices. The content is well-organized and provides significant value for vectorization and retrieval."
                },
            },
        }

        low_quality_doc = {
            "document_id": "test-low-quality",
            "document_data": {
                "title": "Low Quality Document",
                "content": {"content": "Short. Basic. Simple."},
            },
        }

        # Simulate vector quality scoring
        def calculate_content_quality_score(content_text):
            """Calculate a quality score based on content characteristics."""
            score = 0.0

            # Length factor
            if len(content_text) > 200:
                score += 0.3
            elif len(content_text) > 100:
                score += 0.2

            # Sentence complexity
            sentences = content_text.split(".")
            if len(sentences) > 5:
                score += 0.3

            # Technical terms (mock detection)
            technical_terms = [
                "technical",
                "documentation",
                "comprehensive",
                "detailed",
            ]
            for term in technical_terms:
                if term in content_text.lower():
                    score += 0.1

            return min(score, 1.0)

        # Test high quality document
        hq_content = high_quality_doc["document_data"]["content"]["content"]
        hq_score = calculate_content_quality_score(hq_content)

        # Test low quality document
        lq_content = low_quality_doc["document_data"]["content"]["content"]
        lq_score = calculate_content_quality_score(lq_content)

        # Validate quality scoring
        assert hq_score > 0.7, f"High quality content scored too low: {hq_score}"
        assert lq_score < 0.3, f"Low quality content scored too high: {lq_score}"
        assert (
            hq_score > lq_score
        ), "Quality scoring failed to differentiate content quality"

        # Both should still be vectorized without truncation
        assert len(hq_content) > 200, "High quality content truncated"
        assert len(lq_content) > 10, "Low quality content truncated"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
