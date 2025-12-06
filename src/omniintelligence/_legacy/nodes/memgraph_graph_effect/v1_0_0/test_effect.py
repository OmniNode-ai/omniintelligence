"""
Tests for Memgraph Graph Effect Node.

Tests cover:
- Entity creation and updates
- Relationship creation
- Batch operations
- Query execution
- Entity deletion
- Error handling
- Connection management
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence._legacy.enums import EnumEntityType, EnumRelationshipType
from omniintelligence._legacy.models import ModelEntity, ModelRelationship
from omniintelligence.nodes.memgraph_graph_effect.v1_0_0.effect import (
    ModelMemgraphGraphConfig,
    ModelMemgraphGraphInput,
    NodeMemgraphGraphEffect,
)


@pytest.fixture
def config() -> ModelMemgraphGraphConfig:
    """Create test configuration."""
    return ModelMemgraphGraphConfig(
        memgraph_uri="bolt://localhost:7687",
        memgraph_user="test_user",
        memgraph_password="test_password",
        max_connection_pool_size=10,
        connection_timeout_s=10,
        max_retries=2,
        retry_backoff_ms=100,
    )


@pytest.fixture
def node(config: ModelMemgraphGraphConfig) -> NodeMemgraphGraphEffect:
    """Create test node instance."""
    return NodeMemgraphGraphEffect(container=None, config=config)


@pytest.fixture
def sample_entity() -> ModelEntity:
    """Create sample entity."""
    return ModelEntity(
        entity_id="ent_test_123",
        entity_type=EnumEntityType.CLASS,
        name="TestClass",
        metadata={"file_path": "src/test.py", "line_number": 42},
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_relationship() -> ModelRelationship:
    """Create sample relationship."""
    return ModelRelationship(
        source_id="ent_source_123",
        target_id="ent_target_456",
        relationship_type=EnumRelationshipType.CALLS,
        metadata={"call_count": 5},
    )


class TestNodeMemgraphGraphEffect:
    """Test suite for NodeMemgraphGraphEffect."""

    @pytest.mark.asyncio
    async def test_initialization(self, node: NodeMemgraphGraphEffect) -> None:
        """Test node initialization."""
        assert node.node_id is not None
        assert node.driver is None
        assert node.metrics["operations_executed"] == 0

    @pytest.mark.asyncio
    async def test_initialize_driver(self, node: NodeMemgraphGraphEffect) -> None:
        """Test driver initialization."""
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"test": 1})

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)

        with patch(
            "omniintelligence.nodes.memgraph_graph_effect.v1_0_0.effect.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            await node.initialize()
            assert node.driver is not None

    @pytest.mark.asyncio
    async def test_shutdown(self, node: NodeMemgraphGraphEffect) -> None:
        """Test driver shutdown."""
        mock_driver = AsyncMock()
        mock_driver.close = AsyncMock()

        node.driver = mock_driver
        await node.shutdown()

        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_entity(
        self, node: NodeMemgraphGraphEffect, sample_entity: ModelEntity
    ) -> None:
        """Test entity creation."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_record = {
            "entity_id": sample_entity.entity_id,
            "label": sample_entity.entity_type.value,
            "action": "created",
        }
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="CREATE_ENTITY",
            entity=sample_entity,
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.nodes_created == 1
        assert output.nodes_updated == 0
        assert output.error is None

    @pytest.mark.asyncio
    async def test_create_entity_update(
        self, node: NodeMemgraphGraphEffect, sample_entity: ModelEntity
    ) -> None:
        """Test entity update (MERGE with existing)."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_record = {
            "entity_id": sample_entity.entity_id,
            "label": sample_entity.entity_type.value,
            "action": "updated",
        }
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="CREATE_ENTITY",
            entity=sample_entity,
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.nodes_created == 0
        assert output.nodes_updated == 1

    @pytest.mark.asyncio
    async def test_create_relationship(
        self, node: NodeMemgraphGraphEffect, sample_relationship: ModelRelationship
    ) -> None:
        """Test relationship creation."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_record = {
            "source_id": sample_relationship.source_id,
            "target_id": sample_relationship.target_id,
            "relationship_type": sample_relationship.relationship_type.value,
        }
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="CREATE_RELATIONSHIP",
            relationship=sample_relationship,
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.relationships_created == 1
        assert output.error is None

    @pytest.mark.asyncio
    async def test_batch_upsert(
        self, node: NodeMemgraphGraphEffect, sample_entity: ModelEntity
    ) -> None:
        """Test batch upsert operation."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_tx = AsyncMock()

        # Mock transaction methods
        mock_tx.run = AsyncMock()
        mock_tx.commit = AsyncMock()
        mock_tx.rollback = AsyncMock()

        # Mock entity result
        entity_result = AsyncMock()
        entity_result.single = AsyncMock(return_value={"action": "created"})

        # Setup transaction run to return entity result
        mock_tx.run = AsyncMock(return_value=entity_result)

        mock_session.begin_transaction = AsyncMock(return_value=mock_tx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Create multiple entities
        entities = [sample_entity]

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="BATCH_UPSERT",
            entities=entities,
            relationships=None,
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.nodes_created == 1
        mock_tx.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_graph(self, node: NodeMemgraphGraphEffect) -> None:
        """Test graph query execution."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_records = [
            {"entity_id": "ent_1", "name": "Entity1"},
            {"entity_id": "ent_2", "name": "Entity2"},
        ]
        mock_result.values = AsyncMock(return_value=mock_records)

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="QUERY_GRAPH",
            query="MATCH (e) RETURN e.entity_id AS entity_id, e.name AS name LIMIT 10",
            query_params={},
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.query_results is not None
        assert len(output.query_results) == 2

    @pytest.mark.asyncio
    async def test_delete_entity(self, node: NodeMemgraphGraphEffect) -> None:
        """Test entity deletion."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        mock_result.single = AsyncMock(return_value={"deleted_count": 1})

        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="DELETE_ENTITY",
            entity_id="ent_test_123",
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is True
        assert output.nodes_deleted == 1

    @pytest.mark.asyncio
    async def test_invalid_operation(self, node: NodeMemgraphGraphEffect) -> None:
        """Test invalid operation handling."""
        mock_driver = AsyncMock()
        node.driver = mock_driver

        input_data = ModelMemgraphGraphInput(
            operation="INVALID_OPERATION",
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        assert output.success is False
        assert output.error is not None
        assert "Invalid operation" in output.error

    @pytest.mark.asyncio
    async def test_create_entity_missing_data(
        self, node: NodeMemgraphGraphEffect
    ) -> None:
        """Test create entity with missing entity data."""
        mock_driver = AsyncMock()
        node.driver = mock_driver

        input_data = ModelMemgraphGraphInput(
            operation="CREATE_ENTITY",
            entity=None,  # Missing entity
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        assert output.success is False
        assert output.error is not None
        assert "Entity data required" in output.error

    @pytest.mark.asyncio
    async def test_driver_not_initialized(
        self, node: NodeMemgraphGraphEffect
    ) -> None:
        """Test execute without initializing driver."""
        input_data = ModelMemgraphGraphInput(
            operation="CREATE_ENTITY",
            entity=None,
            correlation_id=uuid4(),
        )

        with pytest.raises(ValueError, match="not initialized"):
            await node.execute_effect(input_data)

    @pytest.mark.asyncio
    async def test_get_metrics(self, node: NodeMemgraphGraphEffect) -> None:
        """Test metrics retrieval."""
        metrics = node.get_metrics()

        assert "operations_executed" in metrics
        assert "operations_failed" in metrics
        assert "nodes_created" in metrics
        assert "relationships_created" in metrics
        assert "avg_operation_time_ms" in metrics
        assert "node_id" in metrics

    @pytest.mark.asyncio
    async def test_batch_upsert_rollback_on_error(
        self, node: NodeMemgraphGraphEffect, sample_entity: ModelEntity
    ) -> None:
        """Test batch upsert rolls back on error."""
        # Setup mocks
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_tx = AsyncMock()

        # Mock transaction to raise error
        mock_tx.run = AsyncMock(side_effect=Exception("Database error"))
        mock_tx.rollback = AsyncMock()

        mock_session.begin_transaction = AsyncMock(return_value=mock_tx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_driver.session = MagicMock(return_value=mock_session)
        node.driver = mock_driver

        # Execute
        input_data = ModelMemgraphGraphInput(
            operation="BATCH_UPSERT",
            entities=[sample_entity],
            correlation_id=uuid4(),
        )

        output = await node.execute_effect(input_data)

        # Assert
        assert output.success is False
        assert output.error is not None
        mock_tx.rollback.assert_called_once()
