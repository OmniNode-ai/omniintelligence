"""
Comprehensive Test Suite for Langextract HTTP Client

Tests cover:
- Successful semantic analysis
- Timeout handling
- Circuit breaker behavior
- Retry logic
- Health checks
- Error scenarios
- Metrics tracking

Target: >90% code coverage
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from archon_services.pattern_learning.phase2_matching.client_langextract_http import (
    ClientLangextractHttp,
)
from archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
    LangextractError,
    LangextractRateLimitError,
    LangextractServerError,
    LangextractTimeoutError,
    LangextractUnavailableError,
    LangextractValidationError,
)
from archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
    SemanticAnalysisResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_success_response():
    """Mock successful response from langextract service."""
    return {
        "concepts": [
            {"concept": "authentication", "score": 0.92, "context": "security"},
            {"concept": "api_endpoint", "score": 0.87, "context": "api_design"},
        ],
        "themes": [
            {
                "theme": "api_security",
                "weight": 0.85,
                "related_concepts": ["authentication", "authorization"],
            }
        ],
        "domains": [
            {"domain": "api_design", "confidence": 0.91, "subdomain": "security"}
        ],
        "patterns": [
            {
                "pattern_type": "best-practice",
                "description": "JWT-based authentication pattern",
                "strength": 0.88,
                "indicators": ["token", "bearer", "jwt"],
            }
        ],
        "language": "en",
        "processing_time_ms": 245.3,
        "metadata": {"model_version": "1.0.0", "confidence_threshold": 0.7},
    }


@pytest.fixture
async def client():
    """Create and yield a connected client instance."""
    client = ClientLangextractHttp(
        base_url="http://test-langextract:8156", timeout_seconds=2.0, max_retries=2
    )
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def client_no_circuit_breaker():
    """Create client with circuit breaker disabled for testing."""
    client = ClientLangextractHttp(
        base_url="http://test-langextract:8156",
        timeout_seconds=2.0,
        max_retries=2,
        circuit_breaker_enabled=False,
    )
    await client.connect()
    yield client
    await client.close()


# ============================================================================
# Successful Request Tests
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_semantic_success(client, mock_success_response):
    """Test successful semantic analysis request."""
    # Mock the HTTP response
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Execute request
        result = await client.analyze_semantic(
            content="Implement JWT authentication for REST API",
            context="api_development",
        )

        # Verify result
        assert isinstance(result, SemanticAnalysisResult)
        assert len(result.concepts) == 2
        assert result.concepts[0].concept == "authentication"
        assert result.concepts[0].score == 0.92
        assert len(result.themes) == 1
        assert result.themes[0].theme == "api_security"
        assert len(result.domains) == 1
        assert result.domains[0].domain == "api_design"
        assert len(result.patterns) == 1
        assert result.patterns[0].pattern_type == "best-practice"

        # Verify metrics
        metrics = client.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1
        assert metrics["failed_requests"] == 0


@pytest.mark.asyncio
async def test_analyze_semantic_with_minimal_response(client):
    """Test semantic analysis with minimal response data."""
    # Mock minimal response
    minimal_response = {
        "concepts": [],
        "themes": [],
        "domains": [],
        "patterns": [],
        "language": "en",
    }

    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = minimal_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await client.analyze_semantic("test content")

        assert isinstance(result, SemanticAnalysisResult)
        assert len(result.concepts) == 0
        assert len(result.themes) == 0
        assert result.language == "en"


# ============================================================================
# Timeout Tests
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_semantic_timeout(client):
    """Test timeout handling during semantic analysis."""
    # Mock timeout exception
    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timed out")

        # Should raise LangextractTimeoutError
        with pytest.raises(LangextractTimeoutError) as exc_info:
            await client.analyze_semantic("test content")

        assert "timed out after 2.0s" in str(exc_info.value)
        assert exc_info.value.timeout_seconds == 2.0

        # Verify metrics
        metrics = client.get_metrics()
        assert metrics["timeout_errors"] == 3  # 1 attempt + 2 retries
        assert metrics["failed_requests"] == 1


@pytest.mark.asyncio
async def test_timeout_with_override(client):
    """Test timeout with custom timeout override."""
    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(LangextractTimeoutError) as exc_info:
            await client.analyze_semantic("test content", timeout_override=10.0)

        assert exc_info.value.timeout_seconds == 10.0


# ============================================================================
# Circuit Breaker Tests
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_triggers_on_failures(client, mock_success_response):
    """Test circuit breaker opens after consecutive failures."""
    # Simulate 5 consecutive failures to trigger circuit breaker
    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        # First 5 requests fail
        mock_post.side_effect = httpx.NetworkError("Connection failed")

        # Execute 5 failing requests
        for i in range(5):
            with pytest.raises(LangextractUnavailableError):
                await client.analyze_semantic(f"test content {i}")

        # Circuit breaker should now be open
        assert client.circuit_breaker.current_state == "open"

        # Next request should fail immediately with circuit breaker error
        with pytest.raises(LangextractUnavailableError) as exc_info:
            await client.analyze_semantic("test content after open")

        assert "circuit breaker is open" in str(exc_info.value).lower()

        # Verify metrics
        metrics = client.get_metrics()
        assert metrics["circuit_breaker_opens"] > 0


@pytest.mark.asyncio
async def test_circuit_breaker_disabled(client_no_circuit_breaker):
    """Test client behavior when circuit breaker is disabled."""
    assert client_no_circuit_breaker.circuit_breaker is None

    # Should still handle errors normally
    with patch.object(
        client_no_circuit_breaker.client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = httpx.NetworkError("Connection failed")

        with pytest.raises(LangextractUnavailableError):
            await client_no_circuit_breaker.analyze_semantic("test content")


# ============================================================================
# Retry Logic Tests
# ============================================================================


@pytest.mark.asyncio
async def test_retry_logic_succeeds_on_second_attempt(client, mock_success_response):
    """Test retry logic succeeds after initial failure."""
    # First call fails, second succeeds
    mock_response_success = Mock(spec=httpx.Response)
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.NetworkError("Temporary failure"),
            mock_response_success,
        ]

        result = await client.analyze_semantic("test content")

        # Should succeed after retry
        assert isinstance(result, SemanticAnalysisResult)

        # Verify retries were attempted
        metrics = client.get_metrics()
        assert metrics["retries_attempted"] >= 1
        assert metrics["successful_requests"] == 1


@pytest.mark.asyncio
async def test_retry_logic_with_503_error(client, mock_success_response):
    """Test retry on 503 Service Unavailable."""
    mock_response_503 = Mock(spec=httpx.Response)
    mock_response_503.status_code = 503
    mock_response_503.json.return_value = {"error": "Service unavailable"}

    mock_response_success = Mock(spec=httpx.Response)
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_response_503, mock_response_success]

        result = await client.analyze_semantic("test content")

        assert isinstance(result, SemanticAnalysisResult)
        assert client.get_metrics()["successful_requests"] == 1


@pytest.mark.asyncio
async def test_retry_logic_fails_after_max_retries(client):
    """Test retry logic gives up after max retries."""
    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.NetworkError("Persistent failure")

        with pytest.raises(LangextractUnavailableError):
            await client.analyze_semantic("test content")

        # Should have attempted 1 initial + 2 retries = 3 total
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_validation_error(client):
    """Test validation errors are not retried."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 422
    mock_response.json.return_value = {
        "detail": [{"loc": ["body", "content"], "msg": "field required"}]
    }

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(LangextractValidationError):
            await client.analyze_semantic("test content")

        # Should not retry validation errors
        assert mock_post.call_count == 1


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validation_error_422(client):
    """Test 422 validation error handling."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 422
    mock_response.json.return_value = {
        "detail": [{"loc": ["body", "content"], "msg": "field required"}]
    }

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(LangextractValidationError) as exc_info:
            await client.analyze_semantic("test content")

        assert len(exc_info.value.validation_errors) > 0


@pytest.mark.asyncio
async def test_rate_limit_error_429(client):
    """Test 429 rate limit error handling."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}
    mock_response.json.return_value = {"error": "Rate limit exceeded"}

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(LangextractRateLimitError) as exc_info:
            await client.analyze_semantic("test content")

        assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_server_error_500(client):
    """Test 500 server error handling."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.content = b'{"error": "Internal server error"}'
    mock_response.json.return_value = {"error": "Internal server error"}

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(LangextractServerError) as exc_info:
            await client.analyze_semantic("test content")

        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_network_error(client):
    """Test network connection error handling."""
    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.NetworkError("Connection refused")

        with pytest.raises(LangextractUnavailableError):
            await client.analyze_semantic("test content")


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_health_success(client):
    """Test successful health check."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        health = await client.check_health()

        assert health["healthy"] is True
        assert health["status_code"] == 200
        assert "response_time_ms" in health
        assert client._is_healthy is True


@pytest.mark.asyncio
async def test_check_health_failure(client):
    """Test health check failure."""
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.NetworkError("Connection failed")

        health = await client.check_health()

        assert health["healthy"] is False
        assert "error" in health
        assert client._is_healthy is False


# ============================================================================
# Context Manager Tests
# ============================================================================


@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager protocol."""
    async with ClientLangextractHttp() as client:
        assert client.client is not None
        assert client._health_check_task is not None

    # After exit, client should be closed
    assert client.client is None
    assert client._health_check_task is None


@pytest.mark.asyncio
async def test_request_without_connection():
    """Test request fails if client not connected."""
    client = ClientLangextractHttp()

    with pytest.raises(LangextractError) as exc_info:
        await client.analyze_semantic("test content")

    assert "not connected" in str(exc_info.value).lower()


# ============================================================================
# Metrics Tests
# ============================================================================


@pytest.mark.asyncio
async def test_metrics_tracking(client, mock_success_response):
    """Test comprehensive metrics tracking."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Execute multiple requests
        for i in range(5):
            await client.analyze_semantic(f"test content {i}")

        metrics = client.get_metrics()

        assert metrics["total_requests"] == 5
        assert metrics["successful_requests"] == 5
        assert metrics["failed_requests"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_duration_ms"] > 0


@pytest.mark.asyncio
async def test_reset_metrics(client):
    """Test metrics reset functionality."""
    # Manually set some metrics
    client.metrics["total_requests"] = 10
    client.metrics["successful_requests"] = 8

    # Reset
    client.reset_metrics()

    metrics = client.get_metrics()
    assert metrics["total_requests"] == 0
    assert metrics["successful_requests"] == 0


# ============================================================================
# Edge Cases and Boundary Conditions
# ============================================================================


@pytest.mark.asyncio
async def test_empty_content(client):
    """Test handling of empty content."""
    # Empty content should fail validation at Pydantic level
    with pytest.raises(Exception):  # Pydantic validation error
        await client.analyze_semantic("")


@pytest.mark.asyncio
async def test_very_long_content(client, mock_success_response):
    """Test handling of very long content."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        long_content = "test " * 10000  # 50,000 characters
        result = await client.analyze_semantic(long_content)

        assert isinstance(result, SemanticAnalysisResult)


@pytest.mark.asyncio
async def test_special_characters_in_content(client, mock_success_response):
    """Test handling of special characters."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        special_content = "Test with emoji 🚀 and unicode © ™ ® and symbols @#$%^&*()"
        result = await client.analyze_semantic(special_content)

        assert isinstance(result, SemanticAnalysisResult)


@pytest.mark.asyncio
async def test_concurrent_requests(client, mock_success_response):
    """Test concurrent request handling."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_success_response

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Execute 10 concurrent requests
        tasks = [client.analyze_semantic(f"test content {i}") for i in range(10)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(isinstance(r, SemanticAnalysisResult) for r in results)
        assert client.get_metrics()["total_requests"] == 10
