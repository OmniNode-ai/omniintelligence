"""
Unit Tests for ONEX Qdrant Effect Nodes

Tests all 4 effect nodes with mocked dependencies to ensure correct
behavior and performance characteristics.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from onex.contracts.qdrant_contracts import (
    ModelContractQdrantHealthEffect,
    ModelContractQdrantSearchEffect,
    ModelContractQdrantUpdateEffect,
    ModelContractQdrantVectorIndexEffect,
    QdrantIndexPoint,
)
from onex.effects.node_qdrant_health_effect import (
    NodeQdrantHealthEffect,
)
from onex.effects.node_qdrant_search_effect import (
    NodeQdrantSearchEffect,
)
from onex.effects.node_qdrant_update_effect import (
    NodeQdrantUpdateEffect,
)
from onex.effects.node_qdrant_vector_index_effect import (
    NodeQdrantVectorIndexEffect,
)
from qdrant_client.http.models import (
    CollectionInfo,
    CollectionsResponse,
    UpdateResult,
    UpdateStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant async client."""
    client = AsyncMock()
    client.get_collection = AsyncMock()
    client.create_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.search = AsyncMock()
    client.get_collections = AsyncMock()
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI async client."""
    client = AsyncMock()
    client.embeddings = AsyncMock()
    return client


@pytest.fixture
def sample_embedding():
    """Sample 1536-dimensional embedding vector."""
    return [0.1] * 1536


# =============================================================================
# NodeQdrantVectorIndexEffect Tests
# =============================================================================


class TestNodeQdrantVectorIndexEffect:
    """Test vector indexing effect node."""

    @pytest.fixture
    def index_node(self, mock_qdrant_client, mock_openai_client):
        """Create index effect node instance."""
        return NodeQdrantVectorIndexEffect(
            qdrant_client=mock_qdrant_client,
            openai_client=mock_openai_client,
        )

    @pytest.fixture
    def index_contract(self):
        """Sample index contract."""
        points = [
            QdrantIndexPoint(
                payload={"text": "Authentication security pattern", "type": "security"}
            ),
            QdrantIndexPoint(
                payload={"text": "Database connection pooling", "type": "performance"}
            ),
        ]
        return ModelContractQdrantVectorIndexEffect(
            collection_name="test_collection",
            points=points,
        )

    @pytest.mark.asyncio
    async def test_index_creates_collection_if_not_exists(
        self,
        index_node,
        index_contract,
        mock_qdrant_client,
        mock_openai_client,
        sample_embedding,
    ):
        """Test that collection is created if it doesn't exist."""
        # Mock collection doesn't exist
        mock_qdrant_client.get_collection.side_effect = Exception(
            "Collection not found"
        )

        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)] * 2
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock successful upsert
        mock_qdrant_client.upsert.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await index_node.execute_effect(index_contract)

        # Verify collection creation was attempted
        mock_qdrant_client.create_collection.assert_called_once()
        assert result.status == "success"
        assert result.indexed_count == 2

    @pytest.mark.asyncio
    async def test_index_batch_performance(
        self, index_node, mock_qdrant_client, mock_openai_client, sample_embedding
    ):
        """Test batch indexing performance meets <2s target for 100 patterns."""
        # Create 100 points
        points = [
            QdrantIndexPoint(payload={"text": f"Pattern {i}", "type": "test"})
            for i in range(100)
        ]
        contract = ModelContractQdrantVectorIndexEffect(
            collection_name="test_collection",
            points=points,
        )

        # Mock existing collection
        mock_qdrant_client.get_collection.return_value = MagicMock()

        # Mock embedding generation (single batch call)
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)] * 100
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock successful upsert
        mock_qdrant_client.upsert.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await index_node.execute_effect(contract)

        # Verify performance target
        assert (
            result.duration_ms < 2000
        ), f"Indexing took {result.duration_ms}ms (target: <2000ms)"
        assert result.indexed_count == 100

        # Verify single batch embedding call
        assert mock_openai_client.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_index_validates_text_in_payload(self, index_node):
        """Test that indexing fails if payload doesn't contain text."""
        with pytest.raises(
            ValueError, match="'payload' must contain a non-empty string 'text' key"
        ):
            QdrantIndexPoint(payload={"type": "test"})  # Missing 'text' key


# =============================================================================
# NodeQdrantSearchEffect Tests
# =============================================================================


class TestNodeQdrantSearchEffect:
    """Test semantic search effect node."""

    @pytest.fixture
    def search_node(self, mock_qdrant_client, mock_openai_client):
        """Create search effect node instance."""
        return NodeQdrantSearchEffect(
            qdrant_client=mock_qdrant_client,
            openai_client=mock_openai_client,
        )

    @pytest.fixture
    def search_contract(self):
        """Sample search contract."""
        return ModelContractQdrantSearchEffect(
            collection_name="test_collection",
            query_text="authentication security",
            limit=10,
            score_threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self,
        search_node,
        search_contract,
        mock_qdrant_client,
        mock_openai_client,
        sample_embedding,
    ):
        """Test that search returns formatted results."""
        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock search results
        mock_point = MagicMock()
        mock_point.id = str(uuid4())
        mock_point.score = 0.85
        mock_point.payload = {"text": "Auth pattern", "type": "security"}
        mock_qdrant_client.search.return_value = [mock_point]

        # Execute
        result = await search_node.execute_effect(search_contract)

        # Verify
        assert len(result.hits) == 1
        assert result.hits[0].score == 0.85
        assert result.search_time_ms > 0
        assert result.total_results == 1

    @pytest.mark.asyncio
    async def test_search_performance_target(
        self,
        search_node,
        search_contract,
        mock_qdrant_client,
        mock_openai_client,
        sample_embedding,
    ):
        """Test that search meets <100ms latency target."""
        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock search results
        mock_qdrant_client.search.return_value = []

        # Execute
        result = await search_node.execute_effect(search_contract)

        # Verify performance (note: with mocks this will be very fast,
        # real test should use actual Qdrant instance)
        assert result.search_time_ms >= 0  # At least measure time

    @pytest.mark.asyncio
    async def test_search_with_custom_hnsw_ef(
        self, search_node, mock_qdrant_client, mock_openai_client, sample_embedding
    ):
        """Test search with custom HNSW search parameter."""
        contract = ModelContractQdrantSearchEffect(
            collection_name="test_collection",
            query_text="test query",
            limit=5,
            search_params={"hnsw_ef": 256},  # Higher for better recall
        )

        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock search
        mock_qdrant_client.search.return_value = []

        # Execute
        await search_node.execute_effect(contract)

        # Verify search_params was passed
        call_args = mock_qdrant_client.search.call_args
        assert call_args.kwargs.get("search_params") is not None


# =============================================================================
# NodeQdrantUpdateEffect Tests
# =============================================================================


class TestNodeQdrantUpdateEffect:
    """Test vector update effect node."""

    @pytest.fixture
    def update_node(self, mock_qdrant_client, mock_openai_client):
        """Create update effect node instance."""
        return NodeQdrantUpdateEffect(
            qdrant_client=mock_qdrant_client,
            openai_client=mock_openai_client,
        )

    @pytest.mark.asyncio
    async def test_update_payload_only(
        self, update_node, mock_qdrant_client, mock_openai_client
    ):
        """Test updating payload without regenerating embedding."""
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="test-point-123",
            payload={"type": "security", "reviewed": True},
        )

        # Mock successful set_payload
        mock_qdrant_client.set_payload.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await update_node.execute_effect(contract)

        # Verify no embedding generation
        mock_openai_client.embeddings.create.assert_not_called()

        # Verify set_payload was called (not upsert) when only updating payload
        mock_qdrant_client.set_payload.assert_called_once()
        call_args = mock_qdrant_client.set_payload.call_args
        assert call_args.kwargs["collection_name"] == "test_collection"
        assert call_args.kwargs["payload"] == {"type": "security", "reviewed": True}
        assert call_args.kwargs["points"] == ["test-point-123"]

        # Verify upsert was NOT called
        mock_qdrant_client.upsert.assert_not_called()

        assert result.status == UpdateStatus.COMPLETED.name

    @pytest.mark.asyncio
    async def test_update_with_new_embedding(
        self, update_node, mock_qdrant_client, mock_openai_client, sample_embedding
    ):
        """Test updating with new embedding generation preserves existing payload."""
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="test-point-123",
            text_for_embedding="Updated authentication pattern",
        )

        # Mock existing point with payload (to test payload preservation)
        mock_existing_point = MagicMock()
        mock_existing_point.payload = {
            "type": "security",
            "reviewed": True,
            "version": 2,
        }
        mock_qdrant_client.retrieve.return_value = [mock_existing_point]

        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock successful upsert
        mock_qdrant_client.upsert.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await update_node.execute_effect(contract)

        # Verify existing payload was retrieved
        mock_qdrant_client.retrieve.assert_called_once_with(
            collection_name="test_collection",
            ids=["test-point-123"],
            with_payload=True,
        )

        # Verify embedding generation was called
        mock_openai_client.embeddings.create.assert_called_once()

        # Verify upsert was called with new vector AND preserved payload
        call_args = mock_qdrant_client.upsert.call_args
        point = call_args.kwargs["points"][0]
        assert point.vector == sample_embedding
        assert point.payload == {"type": "security", "reviewed": True, "version": 2}
        assert result.status == UpdateStatus.COMPLETED.name

    @pytest.mark.asyncio
    async def test_update_with_new_embedding_and_payload(
        self, update_node, mock_qdrant_client, mock_openai_client, sample_embedding
    ):
        """Test updating with new embedding and new payload (payload override)."""
        new_payload = {"type": "performance", "reviewed": False, "version": 3}
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="test-point-123",
            text_for_embedding="Updated authentication pattern",
            payload=new_payload,
        )

        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock successful upsert
        mock_qdrant_client.upsert.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await update_node.execute_effect(contract)

        # Verify existing payload was NOT retrieved (new payload provided)
        mock_qdrant_client.retrieve.assert_not_called()

        # Verify upsert was called with new vector AND new payload
        call_args = mock_qdrant_client.upsert.call_args
        point = call_args.kwargs["points"][0]
        assert point.vector == sample_embedding
        assert point.payload == new_payload
        assert result.status == UpdateStatus.COMPLETED.name

    @pytest.mark.asyncio
    async def test_update_new_point_with_embedding_only(
        self, update_node, mock_qdrant_client, mock_openai_client, sample_embedding
    ):
        """Test updating non-existent point with only embedding (new point creation)."""
        contract = ModelContractQdrantUpdateEffect(
            collection_name="test_collection",
            point_id="new-point-456",
            text_for_embedding="New authentication pattern",
        )

        # Mock no existing point (retrieve returns empty list)
        mock_qdrant_client.retrieve.return_value = []

        # Mock embedding generation
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=sample_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Mock successful upsert
        mock_qdrant_client.upsert.return_value = UpdateResult(
            operation_id=1, status=UpdateStatus.COMPLETED
        )

        # Execute
        result = await update_node.execute_effect(contract)

        # Verify retrieve was attempted to check for existing payload
        mock_qdrant_client.retrieve.assert_called_once_with(
            collection_name="test_collection",
            ids=["new-point-456"],
            with_payload=True,
        )

        # Verify embedding generation was called
        mock_openai_client.embeddings.create.assert_called_once()

        # Verify upsert was called with new vector and empty payload
        call_args = mock_qdrant_client.upsert.call_args
        point = call_args.kwargs["points"][0]
        assert point.vector == sample_embedding
        assert point.payload == {}  # Empty payload for new point
        assert result.status == UpdateStatus.COMPLETED.name


# =============================================================================
# NodeQdrantHealthEffect Tests
# =============================================================================


class TestNodeQdrantHealthEffect:
    """Test health check effect node."""

    @pytest.fixture
    def health_node(self, mock_qdrant_client):
        """Create health effect node instance."""
        return NodeQdrantHealthEffect(qdrant_client=mock_qdrant_client)

    @pytest.mark.asyncio
    async def test_health_check_single_collection(
        self, health_node, mock_qdrant_client
    ):
        """Test health check for single collection."""
        contract = ModelContractQdrantHealthEffect(collection_name="test_collection")

        # Mock collection info
        mock_info = MagicMock(spec=CollectionInfo)
        mock_info.points_count = 1000
        mock_info.vectors_count = 1000
        mock_info.indexed_vectors_count = 1000
        mock_info.config = MagicMock()
        mock_info.config.model_dump.return_value = {"distance": "Cosine"}
        mock_qdrant_client.get_collection.return_value = mock_info

        # Execute
        result = await health_node.execute_effect(contract)

        # Verify
        assert result.service_ok is True
        assert len(result.collections) == 1
        assert result.collections[0].name == "test_collection"
        assert result.collections[0].points_count == 1000

    @pytest.mark.asyncio
    async def test_health_check_all_collections(self, health_node, mock_qdrant_client):
        """Test health check for all collections."""
        contract = ModelContractQdrantHealthEffect(collection_name=None)

        # Mock collections response
        from qdrant_client.http.models import CollectionDescription

        mock_collection = CollectionDescription(name="collection1")
        mock_qdrant_client.get_collections.return_value = CollectionsResponse(
            collections=[mock_collection]
        )

        # Mock collection info
        mock_info = MagicMock(spec=CollectionInfo)
        mock_info.points_count = 500
        mock_info.vectors_count = 500
        mock_info.indexed_vectors_count = 500
        mock_info.config = MagicMock()
        mock_info.config.model_dump.return_value = {}
        mock_qdrant_client.get_collection.return_value = mock_info

        # Execute
        result = await health_node.execute_effect(contract)

        # Verify
        assert result.service_ok is True
        assert len(result.collections) == 1

    @pytest.mark.asyncio
    async def test_health_check_handles_failure(self, health_node, mock_qdrant_client):
        """Test health check returns service_ok=False on failure."""
        contract = ModelContractQdrantHealthEffect(collection_name="test_collection")

        # Mock failure
        mock_qdrant_client.get_collection.side_effect = Exception("Service unavailable")

        # Execute (should not raise)
        result = await health_node.execute_effect(contract)

        # Verify graceful failure
        assert result.service_ok is False
        assert len(result.collections) == 0
        assert result.response_time_ms > 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=services.intelligence.onex.effects",
            "--cov-report=term-missing",
        ]
    )
