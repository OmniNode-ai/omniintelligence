"""
Tests for Vectorization Compute Node

Tests both OpenAI API integration and TF-IDF fallback functionality.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from omniintelligence.nodes.vectorization_compute.v1_0_0.compute import (
    ModelVectorizationConfig,
    ModelVectorizationInput,
    VectorizationCompute,
)


class TestVectorizationCompute:
    """Test suite for VectorizationCompute node."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ModelVectorizationConfig(
            default_model="text-embedding-3-small",
            max_batch_size=100,
            enable_caching=True,
            cache_ttl_seconds=3600,
            embedding_dimension=1536,
        )

    @pytest.fixture
    def node_with_api_key(self, config):
        """Create node with mocked API key."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-api-key",
                "EMBEDDING_MODEL": "text-embedding-3-small",
            },
        ):
            return VectorizationCompute(config)

    @pytest.fixture
    def node_without_api_key(self, config):
        """Create node without API key (fallback mode)."""
        with patch.dict(os.environ, {}, clear=True):
            return VectorizationCompute(config)

    async def test_initialization_with_api_key(self, node_with_api_key):
        """Test node initialization with API key."""
        assert node_with_api_key.openai_api_key == "test-api-key"
        assert (
            node_with_api_key.embedding_model == "text-embedding-3-small"
        )
        assert node_with_api_key.config.embedding_dimension == 1536

    async def test_initialization_without_api_key(self, node_without_api_key):
        """Test node initialization without API key."""
        assert node_without_api_key.openai_api_key is None
        assert node_without_api_key.config.embedding_dimension == 1536

    async def test_openai_embedding_success(self, node_with_api_key):
        """Test successful OpenAI API embedding generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = (
                AsyncMock(return_value=mock_response)
            )

            input_data = ModelVectorizationInput(
                content="Test content for embedding"
            )
            result = await node_with_api_key.process(input_data)

            assert result.success is True
            assert len(result.embeddings) == 1536
            assert result.model_used == "text-embedding-3-small"
            assert result.metadata["method"] == "openai_api"
            assert result.metadata["content_length"] == len(input_data.content)

    async def test_openai_embedding_failure_fallback(self, node_with_api_key):
        """Test fallback to TF-IDF when OpenAI API fails."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "API Error", request=MagicMock(), response=MagicMock()
                )
            )

            input_data = ModelVectorizationInput(
                content="Test content for embedding"
            )
            result = await node_with_api_key.process(input_data)

            assert result.success is True
            assert len(result.embeddings) == 1536
            assert result.model_used == "tfidf-fallback"
            assert result.metadata["method"] == "tfidf_fallback"

    async def test_tfidf_embedding_generation(self, node_without_api_key):
        """Test TF-IDF embedding generation."""
        input_data = ModelVectorizationInput(
            content="The quick brown fox jumps over the lazy dog"
        )
        result = await node_without_api_key.process(input_data)

        assert result.success is True
        assert len(result.embeddings) == 1536
        assert result.model_used == "tfidf-fallback"
        assert result.metadata["method"] == "tfidf_fallback"

        # Verify embedding is normalized (unit length)
        norm = sum(x * x for x in result.embeddings) ** 0.5
        assert abs(norm - 1.0) < 0.001

    async def test_tfidf_deterministic(self, node_without_api_key):
        """Test that TF-IDF embeddings are deterministic."""
        content = "Test content for deterministic check"

        result1 = await node_without_api_key.process(
            ModelVectorizationInput(content=content)
        )
        result2 = await node_without_api_key.process(
            ModelVectorizationInput(content=content)
        )

        assert result1.embeddings == result2.embeddings

    async def test_empty_content_handling(self, node_with_api_key):
        """Test handling of empty content."""
        input_data = ModelVectorizationInput(content="   ")
        result = await node_with_api_key.process(input_data)

        assert result.success is False
        assert len(result.embeddings) == 1536
        assert result.model_used == "none"
        assert "error" in result.metadata
        assert result.metadata["error"] == "Empty content"

    async def test_metadata_propagation(self, node_without_api_key):
        """Test that input metadata is propagated to output."""
        input_data = ModelVectorizationInput(
            content="Test content",
            metadata={"source": "test", "doc_id": "123"},
        )
        result = await node_without_api_key.process(input_data)

        assert result.success is True
        assert result.metadata["source"] == "test"
        assert result.metadata["doc_id"] == "123"

    async def test_retry_logic(self, node_with_api_key):
        """Test retry logic for transient failures."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [{"embedding": [0.1] * 1536}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post

            input_data = ModelVectorizationInput(content="Test retry")
            result = await node_with_api_key.process(input_data)

            assert result.success is True
            assert call_count == 3  # Should retry until success

    async def test_different_content_types(self, node_without_api_key):
        """Test embedding generation for different content types."""
        # Code snippet
        code_input = ModelVectorizationInput(
            content="""
            def hello_world():
                print("Hello, World!")
            """
        )
        code_result = await node_without_api_key.process(code_input)
        assert code_result.success is True
        assert len(code_result.embeddings) == 1536

        # Natural language
        text_input = ModelVectorizationInput(
            content="This is a natural language sentence with multiple words."
        )
        text_result = await node_without_api_key.process(text_input)
        assert text_result.success is True
        assert len(text_result.embeddings) == 1536

        # Mixed content
        mixed_input = ModelVectorizationInput(
            content="Code: def test(): pass\nText: This is documentation."
        )
        mixed_result = await node_without_api_key.process(mixed_input)
        assert mixed_result.success is True
        assert len(mixed_result.embeddings) == 1536

    async def test_exception_handling(self, node_with_api_key):
        """Test that unexpected exceptions are handled gracefully."""
        with patch.object(
            node_with_api_key,
            "_generate_openai_embedding",
            side_effect=Exception("Unexpected error"),
        ):
            with patch.object(
                node_with_api_key,
                "_generate_tfidf_embedding",
                side_effect=Exception("TF-IDF error"),
            ):
                input_data = ModelVectorizationInput(content="Test error")
                result = await node_with_api_key.process(input_data)

                assert result.success is False
                assert result.model_used == "error"
                assert "error" in result.metadata

    async def test_large_content(self, node_without_api_key):
        """Test handling of large content."""
        large_content = "word " * 10000  # 50,000 characters
        input_data = ModelVectorizationInput(content=large_content)
        result = await node_without_api_key.process(input_data)

        assert result.success is True
        assert len(result.embeddings) == 1536
        assert result.metadata["content_length"] == len(large_content)

    async def test_special_characters(self, node_without_api_key):
        """Test handling of special characters and Unicode."""
        special_content = "Test with émojis 🚀 and spëcial çharacters: @#$%^&*()"
        input_data = ModelVectorizationInput(content=special_content)
        result = await node_without_api_key.process(input_data)

        assert result.success is True
        assert len(result.embeddings) == 1536

    async def test_custom_model_name(self, config):
        """Test using custom embedding model name."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "EMBEDDING_MODEL": "text-embedding-3-large",
            },
        ):
            node = VectorizationCompute(config)
            assert node.embedding_model == "text-embedding-3-large"

    async def test_config_validation(self):
        """Test configuration model validation."""
        config = ModelVectorizationConfig(
            default_model="custom-model",
            max_batch_size=50,
            enable_caching=False,
            cache_ttl_seconds=1800,
            embedding_dimension=768,
        )

        assert config.default_model == "custom-model"
        assert config.max_batch_size == 50
        assert config.enable_caching is False
        assert config.cache_ttl_seconds == 1800
        assert config.embedding_dimension == 768
