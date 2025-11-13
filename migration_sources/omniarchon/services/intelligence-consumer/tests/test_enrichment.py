"""
Comprehensive tests for intelligence service client and circuit breaker.

Tests:
- CircuitBreaker state management (CLOSED, OPEN, HALF_OPEN)
- CircuitBreaker failure tracking and recovery
- IntelligenceServiceClient initialization and lifecycle
- Document processing with circuit breaker protection
- Code assessment functionality
- Intelligence timeout retrieval (fixed timeout)
- HTTP error handling
- Health checks

Coverage Target: 50%+ of enrichment.py (543 lines)
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from src.enrichment import (
    CircuitBreaker,
    CircuitState,
    IntelligenceServiceClient,
    get_intelligence_timeout,
)


def create_mock_response(status=200, json_data=None):
    """Helper to create properly mocked aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.text = AsyncMock(return_value="")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


class TestIntelligenceTimeout:
    """Test intelligence timeout retrieval (fixed timeout)."""

    def test_small_file_timeout(self):
        """Test timeout for small files (<10KB) - returns fixed base_timeout."""
        timeout = get_intelligence_timeout(5000)
        assert timeout == 900  # Returns base_timeout regardless of size

    def test_medium_file_timeout(self):
        """Test timeout for medium files (10-20KB) - returns fixed base_timeout."""
        timeout = get_intelligence_timeout(15000)
        assert timeout == 900  # Returns base_timeout regardless of size

    def test_large_file_timeout(self):
        """Test timeout for large files (20-30KB) - returns fixed base_timeout."""
        timeout = get_intelligence_timeout(25000)
        assert timeout == 900  # Returns base_timeout regardless of size

    def test_very_large_file_timeout(self):
        """Test timeout for very large files (>30KB) - returns fixed base_timeout."""
        timeout = get_intelligence_timeout(50000)
        assert timeout == 900  # Returns base_timeout regardless of size

    def test_boundary_conditions(self):
        """Test boundary conditions - all return fixed base_timeout."""
        # Pattern matching against 25K+ patterns takes time regardless of file size
        assert get_intelligence_timeout(9999) == 900
        assert get_intelligence_timeout(10000) == 900
        assert get_intelligence_timeout(19999) == 900
        assert get_intelligence_timeout(20000) == 900
        assert get_intelligence_timeout(29999) == 900
        assert get_intelligence_timeout(30000) == 900


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with test thresholds."""
        return CircuitBreaker(failure_threshold=3, timeout=5, success_threshold=2)

    def test_circuit_breaker_initializes_closed(self, circuit_breaker):
        """Test circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert not circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_call(self, circuit_breaker):
        """Test successful function call through circuit breaker."""

        async def mock_func(x, y):
            return x + y

        result = await circuit_breaker.call(mock_func, 2, 3)
        assert result == 5
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold_failures(
        self, circuit_breaker
    ):
        """Test circuit breaker opens after exceeding failure threshold."""

        async def failing_func():
            raise Exception("Function failed")

        # Trigger failures to reach threshold (3)
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_func)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open
        assert circuit_breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_calls_when_open(self, circuit_breaker):
        """Test circuit breaker rejects calls when OPEN."""
        # Force circuit to OPEN state
        circuit_breaker.state = CircuitState.OPEN

        async def mock_func():
            return "success"

        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(mock_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions_to_half_open(self, circuit_breaker):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        # Force circuit to OPEN state with old failure time
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=10)

        async def mock_func():
            return "success"

        # First call transitions to HALF_OPEN
        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.success_count == 1

        # Second call should close the circuit (success_threshold=2)
        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.success_count == 0  # Reset after closing

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_success_threshold(
        self, circuit_breaker
    ):
        """Test circuit breaker closes after success threshold in HALF_OPEN."""
        # Set circuit to HALF_OPEN
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.failure_count = 0

        async def mock_func():
            return "success"

        # Call twice to reach success threshold (2)
        await circuit_breaker.call(mock_func)
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.success_count == 1

        await circuit_breaker.call(mock_func)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.success_count == 0  # Reset

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_half_open_failure(self, circuit_breaker):
        """Test circuit breaker reopens if call fails in HALF_OPEN state."""
        # Set circuit to HALF_OPEN
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.failure_count = 2  # Just below threshold

        async def failing_func():
            raise Exception("Failed again")

        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    def test_should_attempt_reset_returns_false_when_no_failure(self, circuit_breaker):
        """Test _should_attempt_reset returns False when no prior failure."""
        circuit_breaker.last_failure_time = None
        assert not circuit_breaker._should_attempt_reset()

    def test_should_attempt_reset_returns_false_when_timeout_not_reached(
        self, circuit_breaker
    ):
        """Test _should_attempt_reset returns False before timeout."""
        circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=2)
        circuit_breaker.timeout = 5
        assert not circuit_breaker._should_attempt_reset()

    def test_should_attempt_reset_returns_true_after_timeout(self, circuit_breaker):
        """Test _should_attempt_reset returns True after timeout."""
        circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=10)
        circuit_breaker.timeout = 5
        assert circuit_breaker._should_attempt_reset()


class TestIntelligenceServiceClient:
    """Test intelligence service client."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock()
        config.intelligence_service_url = "http://localhost:8053"
        config.intelligence_timeout = 60
        config.circuit_breaker_threshold = 5
        config.circuit_breaker_timeout = 30
        config.circuit_breaker_success_threshold = 3
        config.instance_id = "test-instance"
        return config

    @pytest.fixture
    def client(self, mock_config):
        """Create client instance with mocked config."""
        with patch("src.enrichment.get_config", return_value=mock_config):
            return IntelligenceServiceClient()

    @pytest.fixture
    def mock_session(self):
        """Create mock aiohttp session."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        session.close = AsyncMock()
        return session

    def test_client_initializes_with_circuit_breaker(self, client, mock_config):
        """Test client initializes with circuit breaker."""
        assert client.config == mock_config
        assert client.circuit_breaker is not None
        assert client.circuit_breaker.state == CircuitState.CLOSED
        assert client.session is None

    @pytest.mark.asyncio
    async def test_client_starts_http_session(self, client):
        """Test client starts HTTP session."""
        await client.start()
        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)
        await client.stop()

    @pytest.mark.asyncio
    async def test_client_stops_http_session(self, client):
        """Test client stops HTTP session."""
        await client.start()
        await client.stop()
        # Session should be closed (can't test directly due to async nature)

    @pytest.mark.asyncio
    async def test_process_document_succeeds(self, client, mock_session):
        """Test successful document processing."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(
            status=200,
            json_data={
                "entities": [{"entity_type": "function", "name": "test"}],
                "patterns": ["pattern1"],
                "quality_score": 0.85,
            },
        )

        # Mock post to return the response directly (not wrapped in AsyncMock)
        mock_session.post = Mock(return_value=mock_response)

        result = await client.process_document(
            file_path="/path/to/file.py",
            content="print('hello')",
            project_name="test-project",
            correlation_id="test-123",
        )

        assert result["quality_score"] == 0.85
        assert len(result["entities"]) == 1
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_uses_circuit_breaker(self, client, mock_session):
        """Test document processing uses circuit breaker protection."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(
            status=200, json_data={"entities": [], "patterns": []}
        )
        mock_session.post = Mock(return_value=mock_response)

        with patch.object(
            client.circuit_breaker, "call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"entities": [], "patterns": []}

            await client.process_document(
                file_path="/test.py",
                content="code",
                project_name="test",
            )

            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_raises_when_not_started(self, client):
        """Test process_document raises if client not started."""
        client.session = None

        with pytest.raises(RuntimeError, match="Client not started"):
            await client.process_document(
                file_path="/test.py",
                content="code",
                project_name="test",
            )

    @pytest.mark.asyncio
    async def test_call_intelligence_service_handles_non_200_response(
        self, client, mock_session
    ):
        """Test HTTP call handles non-200 status codes."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=500)
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_session.post = Mock(return_value=mock_response)

        with pytest.raises(Exception, match="Intelligence service returned 500"):
            await client._call_intelligence_service(
                file_path="/test.py",
                content="code",
                project_name="test",
            )

    @pytest.mark.asyncio
    async def test_call_intelligence_service_handles_timeout(
        self, client, mock_session
    ):
        """Test HTTP call handles timeouts."""
        client.session = mock_session

        # Mock to raise timeout immediately when called
        mock_session.post = Mock(side_effect=asyncio.TimeoutError())

        with pytest.raises(Exception, match="timed out"):
            await client._call_intelligence_service(
                file_path="/test.py",
                content="code",
                project_name="test",
            )

    @pytest.mark.asyncio
    async def test_call_intelligence_service_handles_client_error(
        self, client, mock_session
    ):
        """Test HTTP call handles client errors."""
        client.session = mock_session

        # Mock to raise client error immediately when called
        mock_session.post = Mock(side_effect=aiohttp.ClientError("Connection failed"))

        with pytest.raises(Exception, match="client error"):
            await client._call_intelligence_service(
                file_path="/test.py",
                content="code",
                project_name="test",
            )

    @pytest.mark.asyncio
    async def test_call_intelligence_service_builds_correct_payload(
        self, client, mock_session
    ):
        """Test HTTP call builds correct payload structure."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=200, json_data={})
        mock_session.post = Mock(return_value=mock_response)

        await client._call_intelligence_service(
            file_path="/path/to/test.py",
            content="print('hello')",
            project_name="test-project",
        )

        # Verify payload structure
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]

        assert payload["document_id"] == "/path/to/test.py"
        assert payload["project_id"] == "test-project"
        assert payload["title"] == "test.py"
        assert payload["content"] == "print('hello')"
        assert payload["document_type"] in ["code", "documentation", "configuration"]

    @pytest.mark.asyncio
    async def test_call_intelligence_service_detects_document_types(
        self, client, mock_session
    ):
        """Test document type detection from file extension."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=200, json_data={})
        mock_session.post = Mock(return_value=mock_response)

        test_cases = [
            ("/test.md", "documentation"),
            ("/test.json", "configuration"),
            ("/test_example.py", "test"),
            ("/regular.py", "code"),
        ]

        for file_path, expected_type in test_cases:
            mock_session.post.reset_mock()

            await client._call_intelligence_service(
                file_path=file_path,
                content="content",
                project_name="test",
            )

            payload = mock_session.post.call_args[1]["json"]
            assert payload["document_type"] == expected_type

    @pytest.mark.asyncio
    async def test_health_check_succeeds_when_healthy(self, client, mock_session):
        """Test health check returns True when service is healthy."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=200)
        mock_session.get = Mock(return_value=mock_response)

        is_healthy = await client.health_check()
        assert is_healthy

    @pytest.mark.asyncio
    async def test_health_check_fails_when_unhealthy(self, client, mock_session):
        """Test health check returns False when service is unhealthy."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=503)
        mock_session.get = Mock(return_value=mock_response)

        is_healthy = await client.health_check()
        assert not is_healthy

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_started(self, client):
        """Test health check returns False when client not started."""
        client.session = None

        is_healthy = await client.health_check()
        assert not is_healthy

    @pytest.mark.asyncio
    async def test_health_check_handles_exceptions(self, client, mock_session):
        """Test health check handles exceptions gracefully."""
        client.session = mock_session
        # Mock to raise exception immediately when called
        mock_session.get = Mock(side_effect=Exception("Connection error"))

        is_healthy = await client.health_check()
        assert not is_healthy

    def test_circuit_state_property(self, client):
        """Test circuit_state property returns current state."""
        assert client.circuit_state == "closed"

        client.circuit_breaker.state = CircuitState.OPEN
        assert client.circuit_state == "open"

    def test_is_healthy_property(self, client):
        """Test is_healthy property reflects circuit breaker state."""
        assert client.is_healthy

        client.circuit_breaker.state = CircuitState.OPEN
        assert not client.is_healthy


class TestCodeAssessment:
    """Test code assessment functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock()
        config.intelligence_service_url = "http://localhost:8053"
        config.intelligence_timeout = 60
        config.circuit_breaker_threshold = 5
        config.circuit_breaker_timeout = 30
        config.circuit_breaker_success_threshold = 3
        config.instance_id = "test-instance"
        return config

    @pytest.fixture
    def client(self, mock_config):
        """Create client instance."""
        with patch("src.enrichment.get_config", return_value=mock_config):
            return IntelligenceServiceClient()

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        return session

    @pytest.mark.asyncio
    async def test_assess_code_succeeds(self, client, mock_session):
        """Test successful code assessment."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(
            status=200,
            json_data={
                "quality_score": 0.80,
                "issues": [],
                "recommendations": ["Add docstrings"],
            },
        )
        mock_session.post = Mock(return_value=mock_response)

        result = await client.assess_code(
            source_path="/test.py",
            content="def test(): pass",
            language="python",
            correlation_id="test-123",
        )

        assert result["quality_score"] == 0.80
        assert len(result["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_assess_code_uses_circuit_breaker(self, client, mock_session):
        """Test code assessment uses circuit breaker protection."""
        client.session = mock_session

        with patch.object(
            client.circuit_breaker, "call", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"quality_score": 0.75, "issues": []}

            await client.assess_code(
                source_path="/test.py",
                content="code",
                language="python",
            )

            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_assess_code_raises_when_not_started(self, client):
        """Test assess_code raises if client not started."""
        client.session = None

        with pytest.raises(RuntimeError, match="Client not started"):
            await client.assess_code(
                source_path="/test.py",
                content="code",
                language="python",
            )

    @pytest.mark.asyncio
    async def test_call_assess_code_endpoint_builds_correct_payload(
        self, client, mock_session
    ):
        """Test assess code endpoint builds correct payload."""
        client.session = mock_session

        # Mock response using helper
        mock_response = create_mock_response(status=200, json_data={})
        mock_session.post = Mock(return_value=mock_response)

        await client._call_assess_code_endpoint(
            source_path="/test.py",
            content="def test(): pass",
            language="python",
        )

        payload = mock_session.post.call_args[1]["json"]
        assert payload["source_path"] == "/test.py"
        assert payload["content"] == "def test(): pass"
        assert payload["language"] == "python"
        assert payload["include_patterns"] is True
        assert payload["include_compliance"] is True
        assert payload["include_recommendations"] is True
