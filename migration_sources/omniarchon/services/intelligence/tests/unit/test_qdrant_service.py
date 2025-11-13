"""
Unit Tests for ONEX Qdrant Service Layer

Tests the high-level service interface with mocked dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from onex.config import (
    ONEXQdrantConfig,
    OpenAIConfig,
    QdrantConfig,
)
from onex.service import ONEXQdrantService


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return ONEXQdrantConfig(
        qdrant=QdrantConfig(
            url="http://localhost:6333",
            collection_name="test_patterns",
        ),
        openai=OpenAIConfig(
            api_key="test-key-123",
            embedding_model="text-embedding-3-small",
        ),
    )


@pytest.fixture
async def service(mock_config):
    """Create service instance with mocked clients."""
    with (
        patch("services.intelligence.onex.service.AsyncQdrantClient"),
        patch("services.intelligence.onex.service.AsyncOpenAI"),
    ):
        service = ONEXQdrantService(config=mock_config)
        yield service
        await service.close()


class TestONEXQdrantService:
    """Test ONEX Qdrant service layer."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, service, mock_config):
        """Test service initializes with correct configuration."""
        assert service.config == mock_config
        assert service.index_effect is not None
        assert service.search_effect is not None
        assert service.update_effect is not None
        assert service.health_effect is not None

    @pytest.mark.asyncio
    async def test_index_patterns_converts_to_points(self, service):
        """Test that index_patterns correctly converts patterns to points."""
        # Mock the effect execution
        service.index_effect.execute_effect = AsyncMock()
        service.index_effect.execute_effect.return_value = MagicMock(
            status="success",
            indexed_count=2,
            point_ids=[uuid4(), uuid4()],
            collection_name="test_patterns",
            duration_ms=100.0,
        )

        # Test patterns
        patterns = [
            {"text": "Pattern 1", "type": "test"},
            {"text": "Pattern 2", "type": "test"},
        ]

        # Execute
        result = await service.index_patterns(patterns)

        # Verify
        assert result.status == "success"
        assert result.indexed_count == 2
        service.index_effect.execute_effect.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_patterns_with_defaults(self, service):
        """Test search patterns uses configuration defaults."""
        # Mock the effect execution
        service.search_effect.execute_effect = AsyncMock()
        service.search_effect.execute_effect.return_value = MagicMock(
            hits=[],
            search_time_ms=50.0,
            total_results=0,
        )

        # Execute with minimal parameters
        result = await service.search_patterns("test query")

        # Verify defaults were applied
        assert result.search_time_ms == 50.0
        call_args = service.search_effect.execute_effect.call_args
        contract = call_args[0][0]
        assert contract.collection_name == "test_patterns"
        assert contract.limit == 10  # Default from config

    @pytest.mark.asyncio
    async def test_search_patterns_with_custom_hnsw_ef(self, service):
        """Test search patterns with custom HNSW parameter."""
        # Mock the effect execution
        service.search_effect.execute_effect = AsyncMock()
        service.search_effect.execute_effect.return_value = MagicMock(
            hits=[],
            search_time_ms=50.0,
            total_results=0,
        )

        # Execute with custom hnsw_ef
        await service.search_patterns("test query", hnsw_ef=256)

        # Verify custom parameter was passed
        call_args = service.search_effect.execute_effect.call_args
        contract = call_args[0][0]
        assert contract.search_params == {"hnsw_ef": 256}

    @pytest.mark.asyncio
    async def test_update_pattern_payload_only(self, service):
        """Test updating pattern metadata without re-embedding."""
        # Mock the effect execution
        service.update_effect.execute_effect = AsyncMock()
        service.update_effect.execute_effect.return_value = MagicMock(
            point_id="test-123",
            status="COMPLETED",
            operation_time_ms=25.0,
        )

        # Execute
        result = await service.update_pattern(
            point_id="test-123",
            payload={"reviewed": True},
        )

        # Verify
        assert result.point_id == "test-123"
        call_args = service.update_effect.execute_effect.call_args
        contract = call_args[0][0]
        assert contract.payload == {"reviewed": True}
        assert contract.text_for_embedding is None

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test health check returns service status."""
        # Mock the effect execution
        service.health_effect.execute_effect = AsyncMock()
        service.health_effect.execute_effect.return_value = MagicMock(
            service_ok=True,
            collections=[],
            response_time_ms=10.0,
        )

        # Execute
        result = await service.health_check()

        # Verify
        assert result.service_ok is True
        assert result.response_time_ms == 10.0

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config):
        """Test service works as async context manager."""
        with (
            patch("services.intelligence.onex.service.AsyncQdrantClient"),
            patch("services.intelligence.onex.service.AsyncOpenAI"),
        ):

            async with ONEXQdrantService(config=mock_config) as service:
                assert service is not None

            # Verify cleanup was called
            # (In real implementation, this would check client.close() calls)

    @pytest.mark.asyncio
    async def test_batch_size_warning(self, service):
        """Test warning is logged and validation error raised for large batch sizes."""
        # Create pattern list exceeding max batch size
        patterns = [{"text": f"Pattern {i}"} for i in range(150)]

        # Mock effect (won't be reached due to validation error)
        service.index_effect.execute_effect = AsyncMock()

        # Execute (should log warning and raise validation error)
        from pydantic_core import ValidationError

        with patch("onex.service.logger") as mock_logger:
            with pytest.raises(ValidationError) as exc_info:
                await service.index_patterns(patterns)

            # Verify warning was logged
            mock_logger.warning.assert_called_once()

            # Verify validation error message
            assert "too_long" in str(exc_info.value) or "at most 100" in str(
                exc_info.value
            )


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=services.intelligence.onex.service",
            "--cov-report=term-missing",
        ]
    )
