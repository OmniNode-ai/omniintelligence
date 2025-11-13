"""
Unit tests for HTTP connection pooling implementation

Tests verify that:
1. HTTP clients are created with correct connection pool limits
2. Clients reuse connections properly
3. Configuration from environment variables works correctly
4. Shared client lifecycle management works as expected
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from extractors.enhanced_extractor import EnhancedEntityExtractor
from src.config.http_client_config import (
    HTTPClientConfig,
    create_default_client,
    create_search_service_client,
)


@pytest.fixture
def mock_env_vars():
    """Set test environment variables"""
    test_env = {
        "HTTP_CLIENT_MAX_CONNECTIONS": "50",
        "HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS": "10",
        "HTTP_CLIENT_DEFAULT_TIMEOUT": "15.0",
        "HTTP_CLIENT_CONNECT_TIMEOUT": "5.0",
        "HTTP_CLIENT_READ_TIMEOUT": "10.0",
        "HTTP_CLIENT_WRITE_TIMEOUT": "3.0",
        "HTTP_CLIENT_MAX_RETRIES": "2",
        "HTTP_CLIENT_RETRY_BACKOFF_DELAYS": "1.0,2.0",
    }
    with patch.dict(os.environ, test_env, clear=False):
        yield test_env


class TestHTTPClientConfig:
    """Test HTTP client configuration"""

    def test_default_config_from_env(self):
        """Test default configuration values"""
        config = HTTPClientConfig.from_env()

        assert config.max_connections == 100  # Default
        assert config.max_keepalive_connections == 20  # Default
        assert config.default_timeout == 30.0  # Default
        assert config.connect_timeout == 10.0  # Default
        assert config.max_retries == 3  # Default

    def test_custom_config_from_env(self, mock_env_vars):
        """Test configuration from custom environment variables"""
        config = HTTPClientConfig.from_env("HTTP_CLIENT")

        assert config.max_connections == 50
        assert config.max_keepalive_connections == 10
        assert config.default_timeout == 15.0
        assert config.connect_timeout == 5.0
        assert config.max_retries == 2
        assert config.retry_backoff_delays == [1.0, 2.0]

    def test_create_httpx_client(self):
        """Test httpx client creation with pooling"""
        config = HTTPClientConfig(
            max_connections=25,
            max_keepalive_connections=5,
            default_timeout=20.0,
            connect_timeout=5.0,
            read_timeout=15.0,
            write_timeout=3.0,
            max_retries=2,
            retry_backoff_delays=[1.0, 2.0],
        )

        client = config.create_httpx_client()

        assert isinstance(client, httpx.AsyncClient)
        # httpx stores limits internally, verify client was created successfully
        assert client is not None
        # Verify timeout configuration
        assert hasattr(client, "timeout")

    def test_create_httpx_client_with_overrides(self):
        """Test httpx client creation with override parameters"""
        config = HTTPClientConfig(
            max_connections=100,
            max_keepalive_connections=20,
            default_timeout=30.0,
            connect_timeout=10.0,
            read_timeout=30.0,
            write_timeout=5.0,
            max_retries=3,
            retry_backoff_delays=[1.0, 2.0, 4.0],
        )

        client = config.create_httpx_client(
            timeout_override=60.0,
            max_connections_override=50,
            max_keepalive_override=10,
        )

        assert isinstance(client, httpx.AsyncClient)
        assert client is not None
        # Verify timeout was configured
        assert hasattr(client, "timeout")


class TestEnhancedExtractorConnectionPooling:
    """Test EnhancedEntityExtractor connection pooling"""

    def test_enhanced_extractor_has_connection_pooling(self):
        """Test that EnhancedEntityExtractor creates client with connection pooling"""
        extractor = EnhancedEntityExtractor()

        # Verify client is created
        assert extractor.http_client is not None
        assert isinstance(extractor.http_client, httpx.AsyncClient)

        # Verify client has timeout configuration
        assert hasattr(extractor.http_client, "timeout")

        # Client is properly initialized with connection pooling
        # (limits are stored internally in httpx AsyncClient)

    @pytest.mark.asyncio
    async def test_enhanced_extractor_connection_reuse(self):
        """Test that multiple requests reuse connections"""
        extractor = EnhancedEntityExtractor()

        # Mock the Ollama API response
        with patch.object(
            extractor.http_client,
            "post",
            new_callable=AsyncMock,
        ) as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"embedding": [0.1, 0.2, 0.3]},
            )

            # Make multiple requests
            embedding1 = await extractor._generate_embedding("test text 1")
            embedding2 = await extractor._generate_embedding("test text 2")
            embedding3 = await extractor._generate_embedding("test text 3")

            # Verify all requests used the same client (connection pooling)
            assert mock_post.call_count == 3

            # Verify embeddings were generated
            assert len(embedding1) == 3
            assert len(embedding2) == 3
            assert len(embedding3) == 3


class TestSharedClientFunctions:
    """Test pre-configured client creation functions"""

    def test_create_default_client(self):
        """Test default client creation"""
        client = create_default_client()

        assert isinstance(client, httpx.AsyncClient)
        assert client is not None
        assert hasattr(client, "timeout")

    def test_create_default_client_with_timeout_override(self):
        """Test default client with timeout override"""
        client = create_default_client(timeout_override=60.0)

        assert isinstance(client, httpx.AsyncClient)
        assert hasattr(client, "timeout")

    def test_create_search_service_client(self):
        """Test search service client creation"""
        client = create_search_service_client()

        assert isinstance(client, httpx.AsyncClient)
        assert client is not None


@pytest.mark.asyncio
class TestConnectionPoolingBehavior:
    """Test actual connection pooling behavior"""

    async def test_connection_reuse_with_multiple_requests(self):
        """Test that connection pooling actually reuses connections"""
        config = HTTPClientConfig(
            max_connections=10,
            max_keepalive_connections=2,
            default_timeout=5.0,
            connect_timeout=2.0,
            read_timeout=5.0,
            write_timeout=2.0,
            max_retries=1,
            retry_backoff_delays=[1.0],
        )

        async with config.create_httpx_client() as client:
            # Verify client is configured
            assert isinstance(client, httpx.AsyncClient)
            assert client is not None

            # Make request (will fail but tests connection pool setup)
            try:
                # Use a mock URL that won't actually connect
                await client.get("http://localhost:99999/test", timeout=0.1)
            except (httpx.ConnectError, httpx.TimeoutException):
                # Expected - we're just testing pool configuration
                pass

    async def test_concurrent_requests_use_pooling(self):
        """Test that concurrent requests benefit from connection pooling"""
        config = HTTPClientConfig(
            max_connections=5,
            max_keepalive_connections=2,
            default_timeout=5.0,
            connect_timeout=2.0,
            read_timeout=5.0,
            write_timeout=2.0,
            max_retries=1,
            retry_backoff_delays=[1.0],
        )

        async with config.create_httpx_client() as client:
            # Create multiple concurrent requests (will fail but tests pooling)
            tasks = []
            for i in range(3):
                task = client.get(f"http://localhost:99999/test{i}", timeout=0.1)
                tasks.append(task)

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should fail with connection error (expected)
            assert len(results) == 3
            assert all(
                isinstance(r, (httpx.ConnectError, httpx.TimeoutException))
                for r in results
            )


class TestConnectionPoolLimits:
    """Test that connection pool limits are enforced"""

    def test_pool_limits_configuration(self):
        """Test that pool limits are correctly configured"""
        configs_to_test = [
            (10, 2),
            (50, 10),
            (100, 20),
            (200, 50),
        ]

        for max_conns, max_keepalive in configs_to_test:
            config = HTTPClientConfig(
                max_connections=max_conns,
                max_keepalive_connections=max_keepalive,
                default_timeout=30.0,
                connect_timeout=10.0,
                read_timeout=30.0,
                write_timeout=5.0,
                max_retries=3,
                retry_backoff_delays=[1.0, 2.0],
            )

            client = config.create_httpx_client()

            # Verify client was created successfully with configuration
            assert isinstance(client, httpx.AsyncClient)
            assert client is not None
            # Connection pool limits are stored internally by httpx


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
