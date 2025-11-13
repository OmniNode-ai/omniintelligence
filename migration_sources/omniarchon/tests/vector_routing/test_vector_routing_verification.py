"""
Vector Routing Verification Tests

Tests that documents are actually indexed to the correct Qdrant collections
and that the vector routing functionality works end-to-end.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

# Add the search service to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))

from app import determine_collection_for_document, vectorize_document


class TestVectorRoutingVerification:
    """Test suite for vector routing verification"""

    @pytest.fixture
    def mock_search_orchestrator(self):
        """Mock search orchestrator with vector engine"""
        orchestrator = Mock()

        # Mock vector engine with qdrant adapter
        vector_engine = Mock()
        qdrant_adapter = Mock()
        qdrant_adapter.index_vectors = AsyncMock(return_value=1)
        vector_engine.qdrant_adapter = qdrant_adapter
        vector_engine.generate_embeddings = AsyncMock(
            return_value=[np.random.rand(1536)]
        )

        orchestrator.vector_engine = vector_engine
        orchestrator._index_document_vectors = AsyncMock(return_value=1)

        return orchestrator

    @pytest.fixture
    def mock_http_request(self):
        """Mock HTTP request object"""
        request = Mock()
        request.headers = {}
        return request

    @pytest.fixture
    def sample_quality_document_request(self):
        """Sample request for a quality document"""
        return {
            "document_id": "test-quality-doc-123",
            "project_id": "test-project",
            "content": "This is a technical diagnosis report analyzing system performance issues.",
            "metadata": {
                "document_type": "technical_diagnosis",
                "title": "System Performance Diagnosis",
                "author": "AI Agent",
                "created_at": "2025-01-01T00:00:00Z",
            },
            "source_path": "archon://projects/test-project/documents/test-quality-doc-123",
        }

    @pytest.fixture
    def sample_general_document_request(self):
        """Sample request for a general document"""
        return {
            "document_id": "test-general-doc-456",
            "project_id": "test-project",
            "content": "This is a specification document describing the API endpoints.",
            "metadata": {
                "document_type": "spec",
                "title": "API Specification",
                "author": "Developer",
                "created_at": "2025-01-01T00:00:00Z",
            },
            "source_path": "archon://projects/test-project/documents/test-general-doc-456",
        }

    @pytest.mark.asyncio
    async def test_quality_document_routes_to_quality_vectors(
        self,
        mock_search_orchestrator,
        mock_http_request,
        sample_quality_document_request,
    ):
        """Test that quality documents are routed to quality_vectors collection"""

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(
                sample_quality_document_request, mock_http_request
            )

            # Verify successful response
            assert result["success"] is True
            assert result["document_id"] == "test-quality-doc-123"
            assert result["indexed"] is True

            # Verify that index_vectors was called with quality_vectors collection
            mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.assert_called_once()

            # Extract the call arguments
            call_args = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args
            )
            vectors_arg = call_args[0][0]  # First positional argument (vectors list)
            collection_name = call_args[1]["collection_name"]  # Keyword argument

            # Verify collection routing
            assert (
                collection_name == "quality_vectors"
            ), "Quality document should be routed to quality_vectors collection"

            # Verify vector data structure
            assert len(vectors_arg) == 1
            entity_id, vector, metadata = vectors_arg[0]
            assert entity_id == "test-quality-doc-123"
            assert metadata["document_type"] == "technical_diagnosis"

    @pytest.mark.asyncio
    async def test_general_document_routes_to_archon_vectors(
        self,
        mock_search_orchestrator,
        mock_http_request,
        sample_general_document_request,
    ):
        """Test that general documents are routed to archon_vectors collection"""

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(
                sample_general_document_request, mock_http_request
            )

            # Verify successful response
            assert result["success"] is True
            assert result["document_id"] == "test-general-doc-456"
            assert result["indexed"] is True

            # Verify that index_vectors was called with archon_vectors collection
            mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.assert_called_once()

            # Extract the call arguments
            call_args = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args
            )
            collection_name = call_args[1]["collection_name"]  # Keyword argument

            # Verify collection routing
            assert (
                collection_name == "archon_vectors"
            ), "General document should be routed to archon_vectors collection"

    @pytest.mark.asyncio
    async def test_orchestrator_fallback_with_collection_routing(
        self, mock_http_request, sample_quality_document_request
    ):
        """Test that orchestrator fallback still respects collection routing"""

        # Mock orchestrator without qdrant adapter (to trigger fallback)
        orchestrator = Mock()
        vector_engine = Mock()
        vector_engine.qdrant_adapter = None  # No qdrant adapter to trigger fallback
        vector_engine.generate_embeddings = AsyncMock(
            return_value=[np.random.rand(1536)]
        )
        orchestrator.vector_engine = vector_engine
        orchestrator._index_document_vectors = AsyncMock(return_value=1)

        with (
            patch("app.search_orchestrator", orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(
                sample_quality_document_request, mock_http_request
            )

            # Verify successful response
            assert result["success"] is True
            assert result["indexed"] is True

            # Verify that orchestrator fallback was called with correct collection
            orchestrator._index_document_vectors.assert_called_once()

            # Extract the call arguments to verify collection name was passed
            call_args = orchestrator._index_document_vectors.call_args
            collection_name = call_args[1]["collection_name"]  # Keyword argument

            # Verify collection routing in fallback
            assert (
                collection_name == "quality_vectors"
            ), "Fallback should still route to quality_vectors"

    @pytest.mark.asyncio
    async def test_metadata_preservation_during_routing(
        self,
        mock_search_orchestrator,
        mock_http_request,
        sample_quality_document_request,
    ):
        """Test that document metadata is preserved during vector routing"""

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(
                sample_quality_document_request, mock_http_request
            )

            # Verify successful response
            assert result["success"] is True

            # Extract vector metadata
            call_args = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args
            )
            vectors_arg = call_args[0][0]
            entity_id, vector, metadata = vectors_arg[0]

            # Verify all essential metadata is preserved
            assert metadata["document_id"] == "test-quality-doc-123"
            assert metadata["project_id"] == "test-project"
            assert metadata["document_type"] == "technical_diagnosis"
            assert metadata["title"] == "System Performance Diagnosis"
            assert metadata["entity_type"] == "page"
            assert (
                metadata["source_path"]
                == "archon://projects/test-project/documents/test-quality-doc-123"
            )
            assert "content" in metadata
            assert "created_at" in metadata

    @pytest.mark.asyncio
    async def test_entity_metadata_handling_during_routing(
        self, mock_search_orchestrator, mock_http_request
    ):
        """Test that entity metadata is properly handled during routing"""

        # Request with entity information
        request_with_entities = {
            "document_id": "test-doc-with-entities",
            "project_id": "test-project",
            "content": "This document contains code quality analysis.",
            "metadata": {
                "document_type": "quality_assessment",
                "title": "Code Quality Report",
            },
            "entities": [
                {
                    "name": "function_analysis",
                    "entity_type": "function",
                    "confidence_score": 0.9,
                },
                {
                    "name": "code_metrics",
                    "entity_type": "variable",
                    "confidence_score": 0.8,
                },
                {
                    "name": "quality_score",
                    "entity_type": "function",
                    "confidence_score": 0.95,
                },
            ],
        }

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(request_with_entities, mock_http_request)

            # Verify successful response
            assert result["success"] is True

            # Extract vector metadata
            call_args = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args
            )
            vectors_arg = call_args[0][0]
            collection_name = call_args[1]["collection_name"]
            entity_id, vector, metadata = vectors_arg[0]

            # Verify collection routing for quality document
            assert collection_name == "quality_vectors"

            # Verify entity metadata is included
            assert "entity_names" in metadata
            assert "entity_types" in metadata
            assert metadata["entity_count"] == 3

            # Check entity names and types
            expected_names = ["function_analysis", "code_metrics", "quality_score"]
            expected_types = ["function", "variable"]

            assert all(name in metadata["entity_names"] for name in expected_names)
            assert all(etype in metadata["entity_types"] for etype in expected_types)

    @pytest.mark.asyncio
    async def test_error_handling_during_routing(
        self, mock_http_request, sample_quality_document_request
    ):
        """Test error handling when vector routing fails"""

        # Mock orchestrator that fails indexing
        orchestrator = Mock()
        vector_engine = Mock()
        qdrant_adapter = Mock()
        qdrant_adapter.index_vectors = AsyncMock(
            side_effect=Exception("Indexing failed")
        )
        vector_engine.qdrant_adapter = qdrant_adapter
        vector_engine.generate_embeddings = AsyncMock(
            return_value=[np.random.rand(1536)]
        )
        orchestrator.vector_engine = vector_engine

        with (
            patch("app.search_orchestrator", orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization and expect HTTPException
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await vectorize_document(
                    sample_quality_document_request, mock_http_request
                )

            assert exc_info.value.status_code == 500
            assert "Failed to index document vector" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_embedding_generation_failure_handling(
        self, mock_http_request, sample_quality_document_request
    ):
        """Test handling when embedding generation fails"""

        # Mock orchestrator with failing embedding generation
        orchestrator = Mock()
        vector_engine = Mock()
        vector_engine.generate_embeddings = AsyncMock(return_value=[])  # Empty result
        orchestrator.vector_engine = vector_engine

        with (
            patch("app.search_orchestrator", orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
        ):
            # Execute vectorization and expect HTTPException
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await vectorize_document(
                    sample_quality_document_request, mock_http_request
                )

            assert exc_info.value.status_code == 500
            assert "Failed to generate document embedding" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_missing_required_fields_handling(
        self, mock_search_orchestrator, mock_http_request
    ):
        """Test handling when required fields are missing"""

        # Request missing document_id
        invalid_request_1 = {"project_id": "test-project", "content": "Some content"}

        # Request missing content
        invalid_request_2 = {"document_id": "test-doc", "project_id": "test-project"}

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
        ):
            # Test missing document_id
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await vectorize_document(invalid_request_1, mock_http_request)
            assert exc_info.value.status_code == 400
            assert "document_id and content are required" in str(exc_info.value.detail)

            # Test missing content
            with pytest.raises(HTTPException) as exc_info:
                await vectorize_document(invalid_request_2, mock_http_request)
            assert exc_info.value.status_code == 400
            assert "document_id and content are required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_concurrent_routing_consistency(
        self, mock_search_orchestrator, mock_http_request
    ):
        """Test that concurrent vectorization requests maintain routing consistency"""

        # Create multiple requests with same document type
        quality_requests = []
        general_requests = []

        for i in range(5):
            quality_requests.append(
                {
                    "document_id": f"quality-doc-{i}",
                    "project_id": "test-project",
                    "content": f"Quality document {i} content",
                    "metadata": {"document_type": "technical_diagnosis"},
                }
            )

            general_requests.append(
                {
                    "document_id": f"general-doc-{i}",
                    "project_id": "test-project",
                    "content": f"General document {i} content",
                    "metadata": {"document_type": "spec"},
                }
            )

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute all requests concurrently
            all_requests = quality_requests + general_requests
            tasks = [vectorize_document(req, mock_http_request) for req in all_requests]
            results = await asyncio.gather(*tasks)

            # Verify all succeeded
            assert all(result["success"] for result in results)

            # Verify call count matches request count
            assert (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_count
                == 10
            )

            # Verify collection routing consistency by checking calls
            calls = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args_list
            )

            quality_collection_calls = 0
            general_collection_calls = 0

            for call in calls:
                collection_name = call[1]["collection_name"]
                if collection_name == "quality_vectors":
                    quality_collection_calls += 1
                elif collection_name == "archon_vectors":
                    general_collection_calls += 1

            # Should have 5 quality and 5 general collections calls
            assert (
                quality_collection_calls == 5
            ), "Should have 5 calls to quality_vectors"
            assert (
                general_collection_calls == 5
            ), "Should have 5 calls to archon_vectors"

    def test_collection_determination_edge_cases(self):
        """Test edge cases in collection determination logic"""

        # Test with None metadata
        collection = determine_collection_for_document(None)
        assert collection == "archon_vectors"

        # Test with non-dict metadata (should handle gracefully)
        collection = determine_collection_for_document("not_a_dict")
        assert collection == "archon_vectors"

        # Test with metadata containing non-string document_type
        collection = determine_collection_for_document({"document_type": 123})
        assert collection == "archon_vectors"

        # Test with metadata containing None document_type
        collection = determine_collection_for_document({"document_type": None})
        assert collection == "archon_vectors"

    @pytest.mark.asyncio
    async def test_auto_refresh_trigger_after_routing(
        self,
        mock_search_orchestrator,
        mock_http_request,
        sample_quality_document_request,
    ):
        """Test that auto-refresh is triggered after successful routing"""

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch(
                "app._auto_refresh_vector_index", new_callable=AsyncMock
            ) as mock_refresh,
        ):
            # Execute vectorization
            result = await vectorize_document(
                sample_quality_document_request, mock_http_request
            )

            # Verify successful response
            assert result["success"] is True
            assert result["index_refreshed"] is True

            # Verify auto-refresh was triggered
            mock_refresh.assert_called_once()

    @pytest.mark.parametrize(
        "doc_type,expected_collection",
        [
            ("technical_diagnosis", "quality_vectors"),
            ("quality_assessment", "quality_vectors"),
            ("code_review", "quality_vectors"),
            ("execution_report", "quality_vectors"),
            ("quality_report", "quality_vectors"),
            ("compliance_check", "quality_vectors"),
            ("performance_analysis", "quality_vectors"),
            ("spec", "archon_vectors"),
            ("design", "archon_vectors"),
            ("note", "archon_vectors"),
            ("api", "archon_vectors"),
            ("unknown_type", "archon_vectors"),
        ],
    )
    @pytest.mark.asyncio
    async def test_parametrized_routing_verification(
        self, mock_search_orchestrator, mock_http_request, doc_type, expected_collection
    ):
        """Parametrized test for routing verification across different document types"""

        request_data = {
            "document_id": f"test-{doc_type}-doc",
            "project_id": "test-project",
            "content": f"This is a {doc_type} document",
            "metadata": {"document_type": doc_type},
        }

        with (
            patch("app.search_orchestrator", mock_search_orchestrator),
            patch("app.search_service_logger"),
            patch("app.CorrelationHeaders.extract_headers", return_value={}),
            patch("app._auto_refresh_vector_index", new_callable=AsyncMock),
        ):
            # Execute vectorization
            result = await vectorize_document(request_data, mock_http_request)

            # Verify successful response
            assert result["success"] is True

            # Extract collection name from call
            call_args = (
                mock_search_orchestrator.vector_engine.qdrant_adapter.index_vectors.call_args
            )
            collection_name = call_args[1]["collection_name"]

            # Verify expected collection
            assert (
                collection_name == expected_collection
            ), f"Document type '{doc_type}' should route to {expected_collection}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
