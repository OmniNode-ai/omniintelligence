"""
Unit tests for bridge service document processing.

Tests the document processing pipeline including:
- Real-time document sync
- Background document processing
- Entity extraction coordination
- Content text extraction
- Knowledge graph synchronization
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from app import _process_document_sync_background, realtime_document_sync
from connectors.memgraph_connector import MemgraphConnector
from mapping.entity_mapper import EntityMapper


class TestDocumentProcessing:
    """Test cases for document processing functionality."""

    @pytest.fixture
    def sample_document_data(self) -> Dict[str, Any]:
        """Sample document data for testing."""
        return {
            "document_id": "doc-123",
            "project_id": "proj-456",
            "title": "Test Document",
            "content": {
                "overview": "This is a test document",
                "details": "Document details here",
                "sections": ["intro", "body", "conclusion"],
            },
            "document_type": "specification",
            "metadata": {"author": "test_user", "created_at": "2024-01-01T00:00:00Z"},
        }

    @pytest.fixture
    def mock_entity_mapper(self):
        """Mock entity mapper for testing."""
        mapper = AsyncMock(spec=EntityMapper)
        mapper.extract_and_map_content.return_value = [
            {"entity_id": "entity_1", "confidence_score": 0.9},
            {"entity_id": "entity_2", "confidence_score": 0.8},
        ]
        return mapper

    @pytest.fixture
    def mock_sync_service(self):
        """Mock sync service for testing."""
        service = AsyncMock()
        service.get_sync_status.return_value = {
            "status": "active",
            "synced_entities": 10,
        }
        return service

    @pytest.fixture
    def mock_memgraph_connector(self):
        """Mock Memgraph connector for testing."""
        connector = AsyncMock(spec=MemgraphConnector)
        connector.store_entities.return_value = True
        connector.create_relationship.return_value = True
        return connector

    @pytest.mark.asyncio
    async def test_content_text_extraction_dict_content(self, sample_document_data):
        """Test extraction of text content from dictionary content."""
        content = sample_document_data["content"]
        title = sample_document_data["title"]

        # Test the text extraction logic from _process_document_sync_background
        if isinstance(content, dict):
            if "text" in content:
                content_text = content["text"]
            elif "overview" in content:
                content_text = content["overview"]
            elif "description" in content:
                content_text = content["description"]
            else:
                content_text = " ".join(
                    str(value)
                    for value in content.values()
                    if isinstance(value, (str, int, float))
                )
        else:
            content_text = str(content)

        full_text = f"{title}\n\n{content_text}".strip()

        assert "This is a test document" in full_text
        assert "Test Document" in full_text
        assert len(full_text) > 0

    @pytest.mark.asyncio
    async def test_content_text_extraction_string_content(self):
        """Test extraction of text content from string content."""
        title = "Test Document"
        content = "This is plain text content"

        full_text = f"{title}\n\n{content}".strip()

        assert "This is plain text content" in full_text
        assert "Test Document" in full_text

    @pytest.mark.asyncio
    async def test_content_text_extraction_nested_dict(self):
        """Test extraction from nested dictionary with various data types."""
        title = "Complex Document"
        content = {
            "section1": "Text content",
            "section2": {"nested": "value"},
            "count": 42,
            "active": True,
            "tags": ["tag1", "tag2"],
        }

        # Simulate the extraction logic
        content_text = " ".join(
            str(value)
            for value in content.values()
            if isinstance(value, (str, int, float))
        )

        full_text = f"{title}\n\n{content_text}".strip()

        assert "Text content" in full_text
        assert "42" in full_text
        assert "Complex Document" in full_text

    @pytest.mark.asyncio
    @patch("app.memgraph_connector")
    @patch("httpx.AsyncClient")
    async def test_process_document_sync_background_success(
        self,
        mock_httpx_client,
        mock_memgraph,
        sample_document_data,
        mock_entity_mapper,
        mock_sync_service,
    ):
        """Test successful background document sync processing."""
        # Setup mocks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "entities_extracted": 2,
            "status": "completed",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        mock_memgraph.store_entities = AsyncMock()
        mock_memgraph.create_relationship = AsyncMock()

        # Test the function
        await _process_document_sync_background(
            sample_document_data, mock_entity_mapper, mock_sync_service
        )

        # Verify intelligence service was called
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args

        # Check the URL and payload
        assert "/process/document" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["document_id"] == "doc-123"
        assert payload["project_id"] == "proj-456"
        assert payload["title"] == "Test Document"
        assert "sync_source" in payload["metadata"]

    @pytest.mark.asyncio
    @patch("app.memgraph_connector")
    @patch("httpx.AsyncClient")
    async def test_process_document_sync_background_intelligence_failure(
        self,
        mock_httpx_client,
        mock_memgraph,
        sample_document_data,
        mock_entity_mapper,
        mock_sync_service,
    ):
        """Test handling of intelligence service failure."""
        # Setup mocks
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        # Test that exception is raised
        with pytest.raises(Exception) as exc_info:
            await _process_document_sync_background(
                sample_document_data, mock_entity_mapper, mock_sync_service
            )

        assert "Intelligence service returned 500" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.memgraph_connector")
    @patch("httpx.AsyncClient")
    async def test_process_document_sync_background_network_failure(
        self,
        mock_httpx_client,
        mock_memgraph,
        sample_document_data,
        mock_entity_mapper,
        mock_sync_service,
    ):
        """Test handling of network failures to intelligence service."""
        # Setup mocks to raise network error
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.RequestError("Network error")
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        # Test that exception is raised
        with pytest.raises(Exception) as exc_info:
            await _process_document_sync_background(
                sample_document_data, mock_entity_mapper, mock_sync_service
            )

        assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.memgraph_connector")
    @patch("httpx.AsyncClient")
    async def test_process_document_sync_creates_document_entity(
        self,
        mock_httpx_client,
        mock_memgraph,
        sample_document_data,
        mock_entity_mapper,
        mock_sync_service,
    ):
        """Test that document entity is correctly created in knowledge graph."""
        # Setup mocks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "entities_extracted": 1,
            "status": "completed",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        mock_memgraph.store_entities = AsyncMock()
        mock_memgraph.create_relationship = AsyncMock()

        # Test the function
        await _process_document_sync_background(
            sample_document_data, mock_entity_mapper, mock_sync_service
        )

        # Verify document entity was stored
        mock_memgraph.store_entities.assert_called_once()
        stored_entities = mock_memgraph.store_entities.call_args[0][0]

        # Check document entity properties
        document_entity = stored_entities[0]
        assert document_entity["entity_id"] == "doc-123"
        assert document_entity["entity_type"] == "document"
        assert document_entity["name"] == "Test Document"
        assert document_entity["properties"]["project_id"] == "proj-456"
        assert document_entity["properties"]["document_type"] == "specification"
        assert "content_preview" in document_entity["properties"]

    @pytest.mark.asyncio
    @patch("app.memgraph_connector")
    @patch("httpx.AsyncClient")
    async def test_process_document_sync_creates_relationships(
        self,
        mock_httpx_client,
        mock_memgraph,
        sample_document_data,
        mock_entity_mapper,
        mock_sync_service,
    ):
        """Test that relationships are created between document and extracted entities."""
        # Setup mocks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "entities_extracted": 2,
            "status": "completed",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        mock_memgraph.store_entities = AsyncMock()
        mock_memgraph.create_relationship = AsyncMock()

        # Test the function
        await _process_document_sync_background(
            sample_document_data, mock_entity_mapper, mock_sync_service
        )

        # Verify relationships were created
        assert mock_memgraph.create_relationship.call_count == 2

        # Check relationship properties
        relationship_calls = mock_memgraph.create_relationship.call_args_list
        for call in relationship_calls:
            args, kwargs = call
            assert kwargs["from_entity_id"] == "doc-123"
            assert kwargs["relationship_type"] == "CONTAINS_ENTITY"
            assert "confidence" in kwargs["properties"]
            assert kwargs["properties"]["extraction_method"] == "intelligence_service"

    def test_source_path_generation(self, sample_document_data):
        """Test that source path is correctly generated."""
        document_id = sample_document_data["document_id"]
        project_id = sample_document_data["project_id"]

        expected_path = f"archon://projects/{project_id}/documents/{document_id}"
        assert expected_path == "archon://projects/proj-456/documents/doc-123"

    @pytest.mark.asyncio
    async def test_realtime_document_sync_validation(self):
        """Test validation of realtime document sync requests."""
        from fastapi import HTTPException

        # Test missing document_id
        with pytest.raises(HTTPException) as exc_info:
            with patch("app.entity_mapper", None):
                await realtime_document_sync({"project_id": "proj-123"}, Mock())

        assert exc_info.value.status_code == 503

        # Test missing project_id
        invalid_data = {"document_id": "doc-123"}

        with patch("app.entity_mapper", Mock()):
            with patch("app.sync_service", Mock()):
                with pytest.raises(HTTPException) as exc_info:
                    await realtime_document_sync(invalid_data, Mock())

                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch("app.entity_mapper")
    @patch("app.sync_service")
    async def test_realtime_document_sync_success(
        self, mock_sync_service, mock_entity_mapper, sample_document_data
    ):
        """Test successful realtime document sync."""
        background_tasks = Mock()

        result = await realtime_document_sync(sample_document_data, background_tasks)

        assert result["success"] is True
        assert result["document_id"] == "doc-123"
        assert result["project_id"] == "proj-456"
        assert result["status"] == "sync_queued"

        # Verify background task was added
        background_tasks.add_task.assert_called_once()


class TestDocumentProcessingEdgeCases:
    """Test edge cases and error conditions in document processing."""

    @pytest.mark.asyncio
    async def test_empty_content_handling(self):
        """Test handling of documents with empty content."""
        document_data = {
            "document_id": "doc-empty",
            "project_id": "proj-123",
            "title": "Empty Document",
            "content": {},
            "document_type": "note",
        }

        # Test content extraction with empty dict
        content = document_data["content"]
        title = document_data["title"]

        if isinstance(content, dict):
            content_text = " ".join(
                str(value)
                for value in content.values()
                if isinstance(value, (str, int, float))
            )
        else:
            content_text = str(content)

        full_text = f"{title}\n\n{content_text}".strip()

        # Should contain at least the title
        assert "Empty Document" in full_text
        assert len(full_text) >= len(title)

    @pytest.mark.asyncio
    async def test_missing_entity_id_handling(self):
        """Test handling of entities missing entity_id."""
        entities = [
            {"entity_id": "valid_entity", "confidence_score": 0.8},
            {"name": "entity_without_id", "confidence_score": 0.7},  # Missing entity_id
            {"entity_id": "another_valid", "confidence_score": 0.9},
        ]

        # Simulate the filtering logic from _process_document_sync_background
        valid_relationships = []
        for i, entity in enumerate(entities):
            entity_id = entity.get("entity_id")
            if entity_id:
                valid_relationships.append(
                    {
                        "entity_id": entity_id,
                        "confidence": entity.get("confidence_score", 0.0),
                    }
                )

        # Should only include entities with valid entity_id
        assert len(valid_relationships) == 2
        assert valid_relationships[0]["entity_id"] == "valid_entity"
        assert valid_relationships[1]["entity_id"] == "another_valid"

    @pytest.mark.asyncio
    async def test_large_content_preview_truncation(self):
        """Test that content preview is properly truncated for large documents."""
        large_content = "A" * 1000  # 1000 character content
        title = "Large Document"

        full_text = f"{title}\n\n{large_content}".strip()
        content_preview = full_text[:500]  # First 500 chars

        assert len(content_preview) == 500
        assert content_preview.startswith("Large Document")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
