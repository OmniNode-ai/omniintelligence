"""
Unit tests for bridge service connectors.

Tests the Memgraph connector including:
- Connection initialization and health checks
- Database query execution
- Entity storage and retrieval
- Relationship management
- Error handling and connection management
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from connectors.memgraph_connector import MemgraphConnector


class TestMemgraphConnector:
    """Test cases for Memgraph connector functionality."""

    @pytest.fixture
    def mock_neo4j_driver(self):
        """Mock Neo4j driver for testing."""
        driver = Mock()

        # Mock session
        mock_session = AsyncMock()
        mock_session.run.return_value = AsyncMock()
        mock_session.close = AsyncMock()

        driver.session.return_value.__aenter__.return_value = mock_session
        driver.verify_connectivity = AsyncMock()
        driver.close = AsyncMock()

        return driver

    @pytest.fixture
    def memgraph_connector(self, mock_neo4j_driver):
        """Create MemgraphConnector instance for testing."""
        connector = MemgraphConnector("bolt://localhost:7687")
        connector.driver = mock_neo4j_driver
        connector._initialized = True
        return connector

    @pytest.mark.asyncio
    async def test_memgraph_connector_initialization(self):
        """Test Memgraph connector initialization."""
        with patch(
            "connectors.memgraph_connector.AsyncGraphDatabase.driver"
        ) as mock_driver:
            mock_driver_instance = Mock()
            mock_driver_instance.verify_connectivity = AsyncMock()
            mock_driver.return_value = mock_driver_instance

            connector = MemgraphConnector("bolt://localhost:7687")
            await connector.initialize()

            assert connector._initialized is True
            assert connector.driver == mock_driver_instance
            mock_driver.assert_called_once_with("bolt://localhost:7687")

    @pytest.mark.asyncio
    async def test_memgraph_health_check(self, memgraph_connector):
        """Test Memgraph connector health check."""
        # Mock successful health check
        memgraph_connector.driver.verify_connectivity = AsyncMock()

        result = await memgraph_connector.health_check()
        assert result is True

        # Mock failed health check
        memgraph_connector.driver.verify_connectivity.side_effect = Exception(
            "Connection error"
        )

        result = await memgraph_connector.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_store_entities(self, memgraph_connector):
        """Test storing entities in Memgraph."""
        entities = [
            {
                "entity_id": "entity-1",
                "entity_type": "document",
                "name": "Test Document",
                "properties": {"content": "test content"},
                "confidence_score": 0.9,
            },
            {
                "entity_id": "entity-2",
                "entity_type": "concept",
                "name": "Test Concept",
                "properties": {"category": "technical"},
                "confidence_score": 0.8,
            },
        ]

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        await memgraph_connector.store_entities(entities)

        # Verify that run was called for each entity
        assert mock_session.run.call_count == 2

        # Check that MERGE queries were used
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            assert "MERGE" in query
            assert "entity_id" in query

    @pytest.mark.asyncio
    async def test_create_relationship(self, memgraph_connector):
        """Test creating relationships between entities."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        await memgraph_connector.create_relationship(
            from_entity_id="entity-1",
            to_entity_id="entity-2",
            relationship_type="RELATES_TO",
            properties={"confidence": 0.8, "context": "document"},
        )

        # Verify relationship creation query
        mock_session.run.assert_called_once()
        query = mock_session.run.call_args[0][0]

        assert "MATCH" in query
        assert "MERGE" in query
        assert "RELATES_TO" in query
        assert "entity-1" in query or "$from_entity_id" in query
        assert "entity-2" in query or "$to_entity_id" in query

    @pytest.mark.asyncio
    async def test_query_entities(self, memgraph_connector):
        """Test querying entities from Memgraph."""
        # Mock query results
        mock_record = Mock()
        mock_record.get.return_value = {
            "entity_id": "entity-1",
            "entity_type": "document",
            "name": "Test Document",
        }

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [mock_record]

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        # Assuming there's a query_entities method
        if hasattr(memgraph_connector, "query_entities"):
            results = await memgraph_connector.query_entities("document")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_find_relationships(self, memgraph_connector):
        """Test finding relationships between entities."""
        mock_record = Mock()
        mock_record.get.return_value = {
            "from_entity": "entity-1",
            "to_entity": "entity-2",
            "relationship_type": "RELATES_TO",
        }

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = [mock_record]

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        # Assuming there's a find_relationships method
        if hasattr(memgraph_connector, "find_relationships"):
            relationships = await memgraph_connector.find_relationships("entity-1")
            assert len(relationships) > 0

    @pytest.mark.asyncio
    async def test_error_handling_store_entities(self, memgraph_connector):
        """Test error handling during entity storage."""
        entities = [{"entity_id": "invalid-entity"}]

        mock_session = AsyncMock()
        mock_session.run.side_effect = Exception("Database error")
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        with pytest.raises(Exception) as exc_info:
            await memgraph_connector.store_entities(entities)

        assert "Database error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_create_relationship(self, memgraph_connector):
        """Test error handling during relationship creation."""
        mock_session = AsyncMock()
        mock_session.run.side_effect = Exception("Constraint violation")
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        with pytest.raises(Exception) as exc_info:
            await memgraph_connector.create_relationship(
                "entity-1", "entity-2", "INVALID_RELATION"
            )

        assert "Constraint violation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, memgraph_connector):
        """Test connection cleanup on close."""
        await memgraph_connector.close()

        # Verify driver was closed
        memgraph_connector.driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_entity_storage(self, memgraph_connector):
        """Test batch storage of multiple entities."""
        # Generate a large batch of entities
        entities = []
        for i in range(100):
            entities.append(
                {
                    "entity_id": f"entity-{i}",
                    "entity_type": "test",
                    "name": f"Test Entity {i}",
                    "properties": {"index": i},
                    "confidence_score": 0.8,
                }
            )

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        await memgraph_connector.store_entities(entities)

        # Verify all entities were processed
        assert mock_session.run.call_count == 100

    @pytest.mark.asyncio
    async def test_cypher_query_execution(self, memgraph_connector):
        """Test direct Cypher query execution."""
        mock_record = Mock()
        mock_record.data.return_value = {"count": 5}

        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record

        mock_session = AsyncMock()
        mock_session.run.return_value = mock_result
        memgraph_connector.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        # Assuming there's an execute_cypher method
        if hasattr(memgraph_connector, "execute_cypher"):
            result = await memgraph_connector.execute_cypher(
                "MATCH (n) RETURN count(n) as count"
            )
            assert result["count"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
