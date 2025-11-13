"""
Test External API Response Validation

Comprehensive tests for Pydantic validation of external API responses
(Ollama, Qdrant, Memgraph, RAG search, LangExtract).

Tests cover:
- Valid response scenarios
- Malformed response handling
- Missing required fields
- Invalid data types
- Graceful degradation
- Performance validation (<5ms target)
"""

import time

import pytest
from models.external_api import (
    MemgraphQueryResponse,
    OllamaEmbeddingResponse,
    QdrantSearchHit,
    QdrantSearchResponse,
    RAGSearchResponse,
    RAGSearchResult,
)
from pydantic import ValidationError

# ============================================================================
# Ollama API Validation Tests
# ============================================================================


class TestOllamaValidation:
    """Test Ollama API response validation."""

    def test_valid_embedding_response(self):
        """Test valid Ollama embedding response."""
        valid_data = {
            "embedding": [0.1, 0.2, 0.3] * 256,  # 768 dimensions
            "model": "nomic-embed-text",
            "prompt": "test text",
        }

        response = OllamaEmbeddingResponse.model_validate(valid_data)
        assert len(response.embedding) == 768
        assert response.model == "nomic-embed-text"

    def test_embedding_missing_field(self):
        """Test Ollama response with missing embedding field."""
        invalid_data = {"model": "nomic-embed-text", "prompt": "test"}

        with pytest.raises(ValidationError) as exc_info:
            OllamaEmbeddingResponse.model_validate(invalid_data)

        assert "embedding" in str(exc_info.value)

    def test_embedding_wrong_type(self):
        """Test Ollama response with wrong embedding type."""
        invalid_data = {"embedding": "not a list", "model": "nomic-embed-text"}

        with pytest.raises(ValidationError):
            OllamaEmbeddingResponse.model_validate(invalid_data)

    def test_embedding_empty_list(self):
        """Test Ollama response with empty embedding."""
        invalid_data = {"embedding": [], "model": "nomic-embed-text"}

        with pytest.raises(ValidationError) as exc_info:
            OllamaEmbeddingResponse.model_validate(invalid_data)

        assert "empty" in str(exc_info.value).lower()

    def test_embedding_invalid_dimensions(self):
        """Test Ollama response with unusual dimension count (should warn but accept)."""
        # Non-standard dimension count - should log warning but not fail
        unusual_data = {
            "embedding": [0.1] * 100,  # Not a standard dimension
            "model": "custom-model",
        }

        response = OllamaEmbeddingResponse.model_validate(unusual_data)
        assert len(response.embedding) == 100

    def test_embedding_validation_performance(self):
        """Test that validation overhead is <1ms."""
        valid_data = {"embedding": [0.1] * 768, "model": "nomic-embed-text"}

        start = time.perf_counter()
        for _ in range(100):
            OllamaEmbeddingResponse.model_validate(valid_data)
        duration_ms = (time.perf_counter() - start) * 1000

        avg_duration_ms = duration_ms / 100
        assert (
            avg_duration_ms < 1.0
        ), f"Validation took {avg_duration_ms:.3f}ms, expected <1ms"


# ============================================================================
# Qdrant API Validation Tests
# ============================================================================


class TestQdrantValidation:
    """Test Qdrant API response validation."""

    def test_valid_search_response(self):
        """Test valid Qdrant search response."""
        valid_data = {
            "results": [
                {
                    "id": "test-123",
                    "score": 0.92,
                    "payload": {"text": "sample", "path": "/test.md"},
                },
                {"id": 456, "score": 0.87, "payload": {"text": "another"}},
            ]
        }

        response = QdrantSearchResponse.model_validate(valid_data)
        assert len(response.results) == 2
        assert response.results[0].score == 0.92

    def test_search_response_empty_results(self):
        """Test Qdrant search with no results."""
        empty_data = {"results": []}

        response = QdrantSearchResponse.model_validate(empty_data)
        assert len(response.results) == 0
        assert response.is_empty() == True

    def test_search_response_missing_payload(self):
        """Test Qdrant search result with missing payload."""
        data = {
            "results": [
                {
                    "id": "test-123",
                    "score": 0.92,
                    # payload is optional
                }
            ]
        }

        response = QdrantSearchResponse.model_validate(data)
        assert response.results[0].payload is None

    def test_search_response_invalid_score(self):
        """Test Qdrant search with invalid score type."""
        invalid_data = {
            "results": [{"id": "test", "score": "not a number", "payload": {}}]
        }

        with pytest.raises(ValidationError):
            QdrantSearchResponse.model_validate(invalid_data)

    def test_search_hit_conversion(self):
        """Test conversion from QdrantScoredPoint to SearchHit."""
        valid_data = {
            "results": [
                {
                    "id": "uuid-123",
                    "score": 0.95,
                    "payload": {"content": "test content"},
                }
            ]
        }

        response = QdrantSearchResponse.model_validate(valid_data)
        hits = response.get_hits()

        assert len(hits) == 1
        assert isinstance(hits[0], QdrantSearchHit)
        assert hits[0].id == "uuid-123"
        assert hits[0].score == 0.95

    def test_search_validation_performance(self):
        """Test that search validation is <2ms."""
        valid_data = {
            "results": [
                {"id": f"id-{i}", "score": 0.9, "payload": {"text": f"doc {i}"}}
                for i in range(10)
            ]
        }

        start = time.perf_counter()
        for _ in range(50):
            QdrantSearchResponse.model_validate(valid_data)
        duration_ms = (time.perf_counter() - start) * 1000

        avg_duration_ms = duration_ms / 50
        assert (
            avg_duration_ms < 2.0
        ), f"Validation took {avg_duration_ms:.3f}ms, expected <2ms"


# ============================================================================
# Memgraph API Validation Tests
# ============================================================================


class TestMemgraphValidation:
    """Test Memgraph query response validation."""

    def test_valid_query_response(self):
        """Test valid Memgraph query response."""
        valid_data = {
            "records": [
                {
                    "data": {
                        "name": "test.py",
                        "description": "Test file",
                        "labels": ["Document", "Code"],
                    }
                }
            ],
            "summary": {"query_type": "r", "result_available_after": 10},
        }

        response = MemgraphQueryResponse.model_validate(valid_data)
        assert len(response.records) == 1
        assert response.records[0].get("name") == "test.py"

    def test_query_response_empty_records(self):
        """Test Memgraph response with no records."""
        empty_data = {"records": []}

        response = MemgraphQueryResponse.model_validate(empty_data)
        assert response.is_empty() == True
        assert response.get_record_count() == 0

    def test_query_response_no_summary(self):
        """Test Memgraph response without summary (optional)."""
        data = {"records": [{"data": {"name": "test"}}]}

        response = MemgraphQueryResponse.model_validate(data)
        assert response.summary is None

    def test_query_response_nested_data(self):
        """Test Memgraph response with complex nested data."""
        complex_data = {
            "records": [
                {
                    "data": {
                        "name": "complex",
                        "metadata": {"nested": {"deep": "value"}},
                        "tags": ["tag1", "tag2"],
                    }
                }
            ]
        }

        response = MemgraphQueryResponse.model_validate(complex_data)
        record = response.records[0]
        assert record.get("metadata")["nested"]["deep"] == "value"

    def test_memgraph_validation_performance(self):
        """Test that Memgraph validation is <2ms."""
        valid_data = {
            "records": [
                {
                    "data": {
                        "name": f"doc-{i}",
                        "description": f"Description {i}",
                        "labels": ["Document"],
                    }
                }
                for i in range(10)
            ]
        }

        start = time.perf_counter()
        for _ in range(50):
            MemgraphQueryResponse.model_validate(valid_data)
        duration_ms = (time.perf_counter() - start) * 1000

        avg_duration_ms = duration_ms / 50
        assert (
            avg_duration_ms < 2.0
        ), f"Validation took {avg_duration_ms:.3f}ms, expected <2ms"


# ============================================================================
# RAG Search API Validation Tests
# ============================================================================


class TestRAGSearchValidation:
    """Test RAG search service response validation."""

    def test_valid_search_response(self):
        """Test valid RAG search response."""
        valid_data = {
            "results": [
                {
                    "source_path": "/docs/test.md",
                    "score": 0.92,
                    "content": "Test content",
                    "title": "Test Document",
                }
            ],
            "total_results": 1,
            "query": "test query",
            "processing_time_ms": 250.5,
            "sources": ["qdrant"],
            "cache_hit": False,
        }

        response = RAGSearchResponse.model_validate(valid_data)
        assert len(response.results) == 1
        assert response.total_results == 1
        assert response.cache_hit == False

    def test_search_result_path_fallback(self):
        """Test RAG search result with legacy 'path' field."""
        data = {
            "results": [
                {
                    "path": "/old/path.md",  # Legacy field
                    "score": 0.85,
                    "content": "Content",
                }
            ]
        }

        response = RAGSearchResponse.model_validate(data)
        result = response.results[0]
        assert result.get_path() == "/old/path.md"

    def test_search_score_normalization(self):
        """Test RAG search score normalization (>1.0 clamped)."""
        data = {
            "results": [
                {
                    "source_path": "/test.md",
                    "score": 1.5,  # Invalid score > 1.0
                    "content": "Test",
                }
            ]
        }

        response = RAGSearchResponse.model_validate(data)
        assert response.results[0].score == 1.0  # Should be clamped

    def test_search_response_utility_methods(self):
        """Test RAG search response utility methods."""
        data = {
            "results": [
                {"source_path": "/a.md", "score": 0.9, "content": "A"},
                {"source_path": "/b.md", "score": 0.8, "content": "B"},
                {"source_path": "/c.md", "score": 0.7, "content": "C"},
            ]
        }

        response = RAGSearchResponse.model_validate(data)
        assert response.get_result_count() == 3
        assert response.is_empty() == False

        top_result = response.get_top_result()
        assert top_result.score == 0.9

        avg_score = response.get_avg_score()
        assert abs(avg_score - 0.8) < 0.01

    def test_rag_validation_performance(self):
        """Test that RAG validation is <2ms."""
        valid_data = {
            "results": [
                {
                    "source_path": f"/doc-{i}.md",
                    "score": 0.9 - (i * 0.01),
                    "content": f"Content {i}",
                    "title": f"Doc {i}",
                }
                for i in range(10)
            ],
            "total_results": 10,
        }

        start = time.perf_counter()
        for _ in range(50):
            RAGSearchResponse.model_validate(valid_data)
        duration_ms = (time.perf_counter() - start) * 1000

        avg_duration_ms = duration_ms / 50
        assert (
            avg_duration_ms < 2.0
        ), f"Validation took {avg_duration_ms:.3f}ms, expected <2ms"


# ============================================================================
# Integration Tests
# ============================================================================


class TestValidationIntegration:
    """Integration tests for validation across multiple APIs."""

    def test_end_to_end_search_workflow(self):
        """Test complete search workflow with all validations."""
        # 1. Ollama embedding
        embedding_data = {"embedding": [0.1] * 768, "model": "nomic-embed-text"}
        embedding = OllamaEmbeddingResponse.model_validate(embedding_data)
        assert len(embedding.embedding) == 768

        # 2. Qdrant search
        qdrant_data = {
            "results": [{"id": "doc1", "score": 0.95, "payload": {"content": "test"}}]
        }
        qdrant_results = QdrantSearchResponse.model_validate(qdrant_data)
        assert len(qdrant_results.results) == 1

        # 3. RAG search aggregation
        rag_data = {
            "results": [
                {"source_path": "/test.md", "score": 0.92, "content": "content"}
            ],
            "total_results": 1,
        }
        rag_response = RAGSearchResponse.model_validate(rag_data)
        assert rag_response.total_results == 1

    def test_graceful_degradation_fallback(self):
        """Test that validation errors can be caught and handled gracefully."""
        # Invalid data that should fail validation
        invalid_ollama = {"embedding": "not a list"}

        try:
            OllamaEmbeddingResponse.model_validate(invalid_ollama)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            # Application can catch this and use fallback
            assert "embedding" in str(e)
            # Graceful degradation: use default or skip processing

    def test_performance_budget_compliance(self):
        """Test that all validations combined stay within <5ms budget."""
        test_data = {
            "ollama": {"embedding": [0.1] * 768},
            "qdrant": {
                "results": [
                    {"id": f"id-{i}", "score": 0.9, "payload": {"text": f"doc {i}"}}
                    for i in range(5)
                ]
            },
            "rag": {
                "results": [
                    {
                        "source_path": f"/doc-{i}.md",
                        "score": 0.9,
                        "content": f"content {i}",
                    }
                    for i in range(5)
                ]
            },
            "memgraph": {
                "records": [{"data": {"name": f"node-{i}"}} for i in range(5)]
            },
        }

        start = time.perf_counter()

        # Validate all APIs in sequence (simulating typical workflow)
        for _ in range(20):
            OllamaEmbeddingResponse.model_validate(test_data["ollama"])
            QdrantSearchResponse.model_validate(test_data["qdrant"])
            RAGSearchResponse.model_validate(test_data["rag"])
            MemgraphQueryResponse.model_validate(test_data["memgraph"])

        duration_ms = (time.perf_counter() - start) * 1000
        avg_total_ms = duration_ms / 20

        # All 4 validations combined should be <5ms
        assert (
            avg_total_ms < 5.0
        ), f"Total validation took {avg_total_ms:.3f}ms, expected <5ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
