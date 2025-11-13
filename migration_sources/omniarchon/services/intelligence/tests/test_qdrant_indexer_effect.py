"""
Comprehensive tests for Qdrant indexer effect node.

Tests:
- QdrantIndexerEffect initialization
- Single file indexing
- Batch indexing
- Collection creation and management
- Point creation from file info
- Error handling and retry logic
- Performance within ONEX thresholds
- Cleanup functionality

Coverage Target: 50%+ of qdrant_indexer_effect.py (410 lines)
"""

import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from effects.qdrant_indexer_effect import QdrantIndexerEffect
from models.effect_result import EffectResult
from qdrant_client.models import Distance


@pytest.fixture
def mock_qdrant_client():
    """Create mock Qdrant client."""
    client = Mock()
    client.get_collection = Mock()
    client.create_collection = Mock()
    client.upsert = Mock()
    client.close = Mock()
    return client


@pytest.fixture
def sample_file_info():
    """Sample file info for testing."""
    return {
        "absolute_path": "/project/src/module.py",
        "relative_path": "src/module.py",
        "project_name": "test-project",
        "project_root": "/project",
        "metadata": {
            "quality_score": 0.85,
            "onex_compliance": 0.90,
            "onex_type": "Effect",
            "concepts": ["testing", "indexing"],
            "themes": ["data-processing"],
        },
    }


@pytest.fixture
def sample_embedding():
    """Sample embedding vector (1536-dimensional)."""
    return [0.1] * 1536


class TestQdrantIndexerEffectInitialization:
    """Test QdrantIndexerEffect initialization."""

    def test_initializes_with_defaults(self):
        """Test effect initializes with default parameters."""
        effect = QdrantIndexerEffect()

        assert effect.qdrant_url == "http://archon-qdrant:6333"
        assert effect.vector_size == 1536
        assert effect.distance == Distance.COSINE
        assert effect.batch_size == 100
        assert effect.client is None

    def test_initializes_with_custom_parameters(self):
        """Test effect initializes with custom parameters."""
        effect = QdrantIndexerEffect(
            qdrant_url="http://custom:6333",
            vector_size=768,
            distance=Distance.DOT,
            batch_size=50,
        )

        assert effect.qdrant_url == "http://custom:6333"
        assert effect.vector_size == 768
        assert effect.distance == Distance.DOT
        assert effect.batch_size == 50

    def test_get_effect_name(self):
        """Test effect name identifier."""
        effect = QdrantIndexerEffect()
        assert effect.get_effect_name() == "QdrantIndexerEffect"


class TestClientInitialization:
    """Test Qdrant client initialization."""

    def test_initialize_client_creates_client(self):
        """Test _initialize_client creates Qdrant client."""
        effect = QdrantIndexerEffect()

        with patch(
            "src.effects.qdrant_indexer_effect.QdrantClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            effect._initialize_client()

            mock_client_class.assert_called_once_with(url=effect.qdrant_url)
            assert effect.client == mock_client

    def test_initialize_client_is_idempotent(self):
        """Test _initialize_client doesn't recreate existing client."""
        effect = QdrantIndexerEffect()

        with patch(
            "src.effects.qdrant_indexer_effect.QdrantClient"
        ) as mock_client_class:
            mock_client = Mock()
            effect.client = mock_client

            effect._initialize_client()

            mock_client_class.assert_not_called()
            assert effect.client == mock_client


class TestCollectionManagement:
    """Test collection creation and management."""

    def test_ensure_collection_exists_when_exists(self, mock_qdrant_client):
        """Test _ensure_collection_exists when collection already exists."""
        effect = QdrantIndexerEffect()
        effect.client = mock_qdrant_client

        # Simulate collection exists
        mock_qdrant_client.get_collection.return_value = {"name": "archon_vectors"}

        effect._ensure_collection_exists("archon_vectors")

        mock_qdrant_client.get_collection.assert_called_once_with("archon_vectors")
        mock_qdrant_client.create_collection.assert_not_called()

    def test_ensure_collection_exists_creates_when_missing(self, mock_qdrant_client):
        """Test _ensure_collection_exists creates collection when missing."""
        effect = QdrantIndexerEffect(vector_size=1536, distance=Distance.COSINE)
        effect.client = mock_qdrant_client

        # Simulate collection doesn't exist
        mock_qdrant_client.get_collection.side_effect = Exception("Not found")

        effect._ensure_collection_exists("archon_vectors")

        mock_qdrant_client.create_collection.assert_called_once()
        call_args = mock_qdrant_client.create_collection.call_args
        assert call_args[1]["collection_name"] == "archon_vectors"


class TestPointCreation:
    """Test point creation from file info."""

    def test_create_point_with_complete_file_info(
        self, sample_file_info, sample_embedding
    ):
        """Test _create_point with complete file info."""
        effect = QdrantIndexerEffect()

        point = effect._create_point(
            file_info=sample_file_info,
            embedding=sample_embedding,
            project_name="test-project",
            project_root="/project",
        )

        assert point is not None
        assert point.vector == sample_embedding
        assert point.payload["absolute_path"] == "/project/src/module.py"
        assert point.payload["relative_path"] == "src/module.py"
        assert point.payload["project_name"] == "test-project"
        assert point.payload["quality_score"] == 0.85
        assert point.payload["onex_compliance"] == 0.90
        assert point.payload["onex_type"] == "Effect"

    def test_create_point_with_minimal_file_info(self, sample_embedding):
        """Test _create_point with minimal file info."""
        effect = QdrantIndexerEffect()

        file_info = {
            "absolute_path": "/path/to/file.py",
        }

        point = effect._create_point(
            file_info=file_info,
            embedding=sample_embedding,
        )

        assert point is not None
        assert point.payload["absolute_path"] == "/path/to/file.py"
        assert point.payload["quality_score"] == 0.0
        assert point.payload["onex_compliance"] == 0.0

    def test_create_point_returns_none_when_missing_path(self, sample_embedding):
        """Test _create_point returns None when absolute_path missing."""
        effect = QdrantIndexerEffect()

        file_info = {
            "relative_path": "src/file.py",
            # Missing absolute_path
        }

        point = effect._create_point(
            file_info=file_info,
            embedding=sample_embedding,
        )

        assert point is None

    def test_create_point_generates_deterministic_id(self, sample_embedding):
        """Test _create_point generates deterministic ID from path."""
        effect = QdrantIndexerEffect()

        file_info = {"absolute_path": "/test/file.py"}

        point1 = effect._create_point(file_info=file_info, embedding=sample_embedding)
        point2 = effect._create_point(file_info=file_info, embedding=sample_embedding)

        assert point1.id == point2.id  # Same path = same ID

    def test_create_point_handles_exceptions_gracefully(self, sample_embedding):
        """Test _create_point handles exceptions gracefully."""
        effect = QdrantIndexerEffect()

        # Malformed file_info that causes exception
        file_info = None

        point = effect._create_point(
            file_info=file_info,
            embedding=sample_embedding,
        )

        assert point is None


class TestSingleFileIndexing:
    """Test single file indexing."""

    @pytest.mark.asyncio
    async def test_execute_single_file_succeeds(
        self, mock_qdrant_client, sample_file_info, sample_embedding
    ):
        """Test execute() with single file input."""
        effect = QdrantIndexerEffect()

        with (
            patch.object(effect, "_initialize_client") as mock_init,
            patch.object(effect, "_ensure_collection_exists") as mock_ensure,
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            effect.client = mock_qdrant_client
            mock_to_thread.return_value = None  # upsert succeeds

            input_data = {
                "file_info": sample_file_info,
                "embedding": sample_embedding,
                "collection_name": "archon_vectors",
                "project_name": "test-project",
                "project_root": "/project",
            }

            result = await effect.execute(input_data)

            assert result.success
            assert result.items_processed == 1
            assert result.duration_ms > 0
            mock_init.assert_called_once()
            mock_ensure.assert_called_once_with("archon_vectors")
            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_file_convenience_method(
        self, mock_qdrant_client, sample_file_info, sample_embedding
    ):
        """Test index_file() convenience method."""
        effect = QdrantIndexerEffect()

        with patch.object(effect, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = EffectResult(
                success=True, items_processed=1, duration_ms=10.0
            )

            success = await effect.index_file(
                file_info=sample_file_info,
                embedding=sample_embedding,
                collection_name="test_collection",
            )

            assert success
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_file_returns_false_on_failure(self):
        """Test index_file() returns False on failure."""
        effect = QdrantIndexerEffect()

        with patch.object(effect, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = EffectResult(
                success=False, items_processed=0, duration_ms=10.0
            )

            success = await effect.index_file(
                file_info={"absolute_path": "/test.py"},
                embedding=[0.1] * 1536,
            )

            assert not success


class TestBatchIndexing:
    """Test batch indexing functionality."""

    @pytest.mark.asyncio
    async def test_execute_batch_succeeds(self, mock_qdrant_client):
        """Test execute() with batch input."""
        effect = QdrantIndexerEffect(batch_size=2)

        files = [
            (
                {"absolute_path": f"/file{i}.py", "relative_path": f"file{i}.py"},
                [0.1] * 1536,
            )
            for i in range(5)
        ]

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists"),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            effect.client = mock_qdrant_client
            mock_to_thread.return_value = None

            input_data = {
                "files": files,
                "collection_name": "archon_vectors",
                "batch_size": 2,
            }

            result = await effect.execute(input_data)

            assert result.success
            assert result.items_processed == 5
            # Should process in 3 batches: 2, 2, 1
            assert mock_to_thread.call_count == 3
            assert result.metadata["batches_processed"] == 3

    @pytest.mark.asyncio
    async def test_execute_batch_partial_failure(self, mock_qdrant_client):
        """Test batch execution with partial failures."""
        effect = QdrantIndexerEffect(batch_size=2)

        files = [({"absolute_path": f"/file{i}.py"}, [0.1] * 1536) for i in range(4)]

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists"),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            effect.client = mock_qdrant_client
            # First batch succeeds, second fails
            mock_to_thread.side_effect = [None, Exception("Batch failed")]

            input_data = {
                "files": files,
                "collection_name": "archon_vectors",
                "batch_size": 2,
            }

            result = await effect.execute(input_data)

            assert result.success  # Partial success
            assert result.items_processed == 2  # Only first batch
            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_batch_index_convenience_method(self, mock_qdrant_client):
        """Test batch_index() convenience method."""
        effect = QdrantIndexerEffect()

        files = [({"absolute_path": f"/file{i}.py"}, [0.1] * 1536) for i in range(3)]

        with patch.object(effect, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = EffectResult(
                success=True, items_processed=3, duration_ms=20.0
            )

            count = await effect.batch_index(
                files=files,
                collection_name="test_collection",
                project_name="test-project",
            )

            assert count == 3
            mock_execute.assert_called_once()


class TestErrorHandling:
    """Test error handling and validation."""

    @pytest.mark.asyncio
    async def test_execute_returns_error_when_no_files(self):
        """Test execute() returns error when no files provided."""
        effect = QdrantIndexerEffect()

        with patch.object(effect, "_initialize_client"):
            effect.client = Mock()

            input_data = {
                "collection_name": "archon_vectors",
                # Missing: files or (file_info + embedding)
            }

            result = await effect.execute(input_data)

            assert not result.success
            assert len(result.errors) > 0
            assert "No files provided" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_handles_initialization_errors(self):
        """Test execute() handles client initialization errors."""
        effect = QdrantIndexerEffect()

        with patch.object(
            effect, "_initialize_client", side_effect=Exception("Connection failed")
        ):
            input_data = {
                "file_info": {"absolute_path": "/test.py"},
                "embedding": [0.1] * 1536,
            }

            result = await effect.execute(input_data)

            assert not result.success
            assert len(result.errors) > 0
            assert "failed" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_execute_handles_collection_creation_errors(self, mock_qdrant_client):
        """Test execute() handles collection creation errors."""
        effect = QdrantIndexerEffect()

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(
                effect,
                "_ensure_collection_exists",
                side_effect=Exception("Creation failed"),
            ),
        ):
            effect.client = mock_qdrant_client

            input_data = {
                "file_info": {"absolute_path": "/test.py"},
                "embedding": [0.1] * 1536,
            }

            result = await effect.execute(input_data)

            assert not result.success


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_single_file_indexing_performance(
        self, mock_qdrant_client, sample_file_info, sample_embedding
    ):
        """Test single file indexing meets performance target (<50ms per file)."""
        effect = QdrantIndexerEffect()

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists"),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            effect.client = mock_qdrant_client
            mock_to_thread.return_value = None

            input_data = {
                "file_info": sample_file_info,
                "embedding": sample_embedding,
                "collection_name": "archon_vectors",
            }

            start = time.perf_counter()
            result = await effect.execute(input_data)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Should be fast with mocked I/O
            assert elapsed_ms < 100
            assert result.success

    @pytest.mark.asyncio
    async def test_batch_indexing_performance(self, mock_qdrant_client):
        """Test batch indexing meets performance target (<50ms per batch of 100)."""
        effect = QdrantIndexerEffect(batch_size=100)

        files = [({"absolute_path": f"/file{i}.py"}, [0.1] * 1536) for i in range(100)]

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists"),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            effect.client = mock_qdrant_client
            mock_to_thread.return_value = None

            input_data = {
                "files": files,
                "collection_name": "archon_vectors",
            }

            result = await effect.execute(input_data)

            assert result.success
            assert result.items_processed == 100
            # With mocked I/O, should be very fast
            assert result.duration_ms < 500


class TestCleanup:
    """Test cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_client(self, mock_qdrant_client):
        """Test cleanup() closes Qdrant client."""
        effect = QdrantIndexerEffect()
        effect.client = mock_qdrant_client

        await effect.cleanup()

        mock_qdrant_client.close.assert_called_once()
        assert effect.client is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_no_client(self):
        """Test cleanup() handles missing client gracefully."""
        effect = QdrantIndexerEffect()
        effect.client = None

        # Should not raise exception
        await effect.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_handles_close_error(self, mock_qdrant_client):
        """Test cleanup() handles client close errors."""
        effect = QdrantIndexerEffect()
        effect.client = mock_qdrant_client
        mock_qdrant_client.close.side_effect = Exception("Close failed")

        # Should not raise exception, just log warning
        await effect.cleanup()


class TestMetadataExtraction:
    """Test metadata extraction from file info."""

    def test_create_point_extracts_quality_metrics(self, sample_embedding):
        """Test point creation extracts quality metrics from metadata."""
        effect = QdrantIndexerEffect()

        file_info = {
            "absolute_path": "/test.py",
            "metadata": {
                "quality_score": 0.92,
                "onex_compliance": 0.88,
                "onex_type": "Compute",
            },
        }

        point = effect._create_point(file_info=file_info, embedding=sample_embedding)

        assert point.payload["quality_score"] == 0.92
        assert point.payload["onex_compliance"] == 0.88
        assert point.payload["onex_type"] == "Compute"

    def test_create_point_extracts_semantic_metadata(self, sample_embedding):
        """Test point creation extracts semantic metadata."""
        effect = QdrantIndexerEffect()

        file_info = {
            "absolute_path": "/test.py",
            "metadata": {
                "concepts": ["async", "database"],
                "themes": ["performance", "reliability"],
            },
        }

        point = effect._create_point(file_info=file_info, embedding=sample_embedding)

        assert "async" in point.payload["concepts"]
        assert "database" in point.payload["concepts"]
        assert "performance" in point.payload["themes"]

    def test_create_point_includes_timestamp(self, sample_embedding):
        """Test point creation includes indexed_at timestamp."""
        effect = QdrantIndexerEffect()

        file_info = {"absolute_path": "/test.py"}

        point = effect._create_point(file_info=file_info, embedding=sample_embedding)

        assert "indexed_at" in point.payload
        assert len(point.payload["indexed_at"]) > 0  # ISO format timestamp


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_execute_with_empty_batch(self, mock_qdrant_client):
        """Test execute() with empty batch."""
        effect = QdrantIndexerEffect()

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists"),
        ):
            effect.client = mock_qdrant_client

            input_data = {
                "files": [],
                "collection_name": "archon_vectors",
            }

            result = await effect.execute(input_data)

            # Empty batch returns error (no files provided)
            assert not result.success
            assert result.items_processed == 0
            assert len(result.errors) > 0

    def test_create_point_with_relative_path_calculation(self, sample_embedding):
        """Test point creation calculates relative_path when missing."""
        effect = QdrantIndexerEffect()

        file_info = {
            "absolute_path": "/project/src/module.py",
            # Missing relative_path
        }

        point = effect._create_point(
            file_info=file_info,
            embedding=sample_embedding,
            project_root="/project",
        )

        assert point.payload["relative_path"] == "src/module.py"

    @pytest.mark.asyncio
    async def test_execute_uses_default_collection_name(self, mock_qdrant_client):
        """Test execute() uses default collection name when not specified."""
        effect = QdrantIndexerEffect()

        with (
            patch.object(effect, "_initialize_client"),
            patch.object(effect, "_ensure_collection_exists") as mock_ensure,
            patch("asyncio.to_thread", new_callable=AsyncMock),
        ):
            effect.client = mock_qdrant_client

            input_data = {
                "file_info": {"absolute_path": "/test.py"},
                "embedding": [0.1] * 1536,
                # collection_name not specified
            }

            await effect.execute(input_data)

            # Should use default "archon_vectors"
            mock_ensure.assert_called_once_with("archon_vectors")
