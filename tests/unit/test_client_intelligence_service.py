"""
Unit tests for IntelligenceServiceClient.

Tests the HTTP client with mocked dependencies - no real external services.
Covers: lifecycle, health checks, API methods, retry logic, circuit breaker,
error handling, and metrics.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from omniintelligence.clients.client_intelligence_service import (
    CircuitBreakerState,
    CoreErrorCode,
    IntelligenceServiceClient,
    IntelligenceServiceError,
    IntelligenceServiceRateLimit,
    IntelligenceServiceTimeout,
    IntelligenceServiceUnavailable,
    IntelligenceServiceValidation,
    OnexError,
)
from omniintelligence.models.model_intelligence_api_contracts import (
    ModelHealthCheckResponse,
    ModelPatternDetectionRequest,
    ModelPatternDetectionResponse,
    ModelPerformanceAnalysisRequest,
    ModelPerformanceAnalysisResponse,
    ModelQualityAssessmentRequest,
    ModelQualityAssessmentResponse,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create an IntelligenceServiceClient instance for testing."""
    return IntelligenceServiceClient(
        base_url="http://localhost:8053",
        timeout_seconds=30.0,
        max_retries=3,
        circuit_breaker_enabled=True,
    )


@pytest.fixture
def client_no_circuit_breaker():
    """Create a client with circuit breaker disabled."""
    return IntelligenceServiceClient(
        base_url="http://localhost:8053",
        timeout_seconds=30.0,
        max_retries=3,
        circuit_breaker_enabled=False,
    )


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.aclose = AsyncMock()
    return mock_client


@pytest.fixture
def quality_assessment_request():
    """Create a quality assessment request for testing."""
    return ModelQualityAssessmentRequest(
        content="def hello(): pass",
        source_path="test.py",
        language="python",
        include_recommendations=True,
        min_quality_threshold=0.7,
    )


@pytest.fixture
def performance_analysis_request():
    """Create a performance analysis request for testing."""
    return ModelPerformanceAnalysisRequest(
        operation_name="test_operation",
        code_content="async def fetch_data(): pass",
        context={"execution_type": "async"},
        include_opportunities=True,
        target_percentile=95,
    )


@pytest.fixture
def pattern_detection_request():
    """Create a pattern detection request for testing."""
    return ModelPatternDetectionRequest(
        content="class UserService:\n    def __init__(self, db):\n        self.db = db",
        source_path="src/services/user_service.py",
        min_confidence=0.7,
        include_recommendations=True,
    )


@pytest.fixture
def mock_health_response_data():
    """Create mock health response data."""
    return {
        "status": "healthy",
        "memgraph_connected": True,
        "ollama_connected": True,
        "freshness_database_connected": True,
        "service_version": "1.0.0",
        "uptime_seconds": 12345.0,
        "last_check": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def mock_quality_response_data():
    """Create mock quality assessment response data."""
    return {
        "success": True,
        "quality_score": 0.85,
        "architectural_compliance": {
            "score": 0.90,
            "reasoning": "Good ONEX compliance",
        },
        "code_patterns": [],
        "maintainability": {
            "complexity_score": 0.80,
            "readability_score": 0.85,
            "testability_score": 0.75,
        },
        "onex_compliance": {
            "score": 0.88,
            "violations": [],
            "recommendations": ["Add type hints"],
        },
        "architectural_era": "modern_archon",
        "temporal_relevance": 0.85,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def mock_performance_response_data():
    """Create mock performance analysis response data."""
    return {
        "operation_name": "test_operation",
        "average_response_time_ms": 100.0,
        "p50_ms": 90.0,
        "p95_ms": 150.0,
        "p99_ms": 200.0,
        "quality_score": 0.75,
        "complexity_score": 0.80,
        "sample_size": 1,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "code_analysis",
        "message": "Synthetic baseline generated",
    }


@pytest.fixture
def mock_pattern_response_data():
    """Create mock pattern detection response data."""
    return {
        "success": True,
        "detected_patterns": [
            {
                "pattern_id": "pat_001",
                "pattern_type": "dependency_injection",
                "category": "best_practices",
                "confidence": 0.92,
                "description": "Dependency injection via constructor",
            }
        ],
        "anti_patterns": [],
        "architectural_compliance": {
            "onex_compliance": True,
            "node_type_detected": "Effect",
            "contract_compliance": True,
            "violations": [],
        },
        "analysis_summary": {"patterns_found": 1},
        "confidence_scores": {"overall_confidence": 0.85},
        "recommendations": ["Consider adding interface"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ============================================================================
# Exception Tests
# ============================================================================


class TestExceptions:
    """Tests for custom exception classes."""

    def test_onex_error_initialization(self):
        """Test OnexError creates correctly with all parameters."""
        error = OnexError(
            message="Test error",
            error_code=CoreErrorCode.INTERNAL_ERROR,
            details={"key": "value"},
            status_code=500,
        )
        assert error.message == "Test error"
        assert error.error_code == CoreErrorCode.INTERNAL_ERROR
        assert error.details == {"key": "value"}
        assert error.status_code == 500
        assert str(error) == "Test error"

    def test_intelligence_service_error_default_values(self):
        """Test IntelligenceServiceError has correct defaults."""
        error = IntelligenceServiceError("Service failed")
        assert error.message == "Service failed"
        assert error.error_code == CoreErrorCode.INTERNAL_ERROR
        assert error.status_code == 500
        assert error.details == {}

    def test_intelligence_service_unavailable(self):
        """Test IntelligenceServiceUnavailable exception."""
        error = IntelligenceServiceUnavailable(
            "Service down", details={"reason": "maintenance"}
        )
        assert error.message == "Service down"
        assert error.error_code == CoreErrorCode.SERVICE_UNAVAILABLE
        assert error.status_code == 503
        assert error.details["reason"] == "maintenance"

    def test_intelligence_service_timeout(self):
        """Test IntelligenceServiceTimeout exception."""
        error = IntelligenceServiceTimeout(
            "Request timed out", timeout_seconds=30.0, details={"endpoint": "/test"}
        )
        assert error.message == "Request timed out"
        assert error.status_code == 504
        assert error.details["timeout_seconds"] == 30.0
        assert error.details["endpoint"] == "/test"

    def test_intelligence_service_validation(self):
        """Test IntelligenceServiceValidation exception."""
        error = IntelligenceServiceValidation(
            "Validation failed",
            validation_errors=["field required", "invalid type"],
            details={"field": "content"},
        )
        assert error.message == "Validation failed"
        assert error.error_code == CoreErrorCode.VALIDATION_ERROR
        assert error.status_code == 422
        assert "field required" in error.details["validation_errors"]
        assert error.details["field"] == "content"

    def test_intelligence_service_rate_limit(self):
        """Test IntelligenceServiceRateLimit exception."""
        error = IntelligenceServiceRateLimit(
            "Rate limit exceeded", retry_after=60, details={"limit": 100}
        )
        assert error.message == "Rate limit exceeded"
        assert error.error_code == CoreErrorCode.RATE_LIMIT_EXCEEDED
        assert error.status_code == 429
        assert error.details["retry_after"] == 60
        assert error.details["limit"] == 100

    def test_rate_limit_without_retry_after(self):
        """Test rate limit exception without retry_after header."""
        error = IntelligenceServiceRateLimit("Rate limit exceeded")
        assert "retry_after" not in error.details


# ============================================================================
# Circuit Breaker Tests
# ============================================================================


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState class."""

    def test_initialization(self):
        """Test circuit breaker initializes with correct defaults."""
        cb = CircuitBreakerState()
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout_seconds == 60.0
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"

    def test_custom_initialization(self):
        """Test circuit breaker with custom parameters."""
        cb = CircuitBreakerState(failure_threshold=3, recovery_timeout_seconds=30.0)
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout_seconds == 30.0

    def test_record_success_resets_state(self):
        """Test recording success resets failure count and state."""
        cb = CircuitBreakerState()
        cb.failure_count = 3
        cb.state = "half_open"

        cb.record_success()

        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_record_failure_increments_count(self):
        """Test recording failure increments counter."""
        cb = CircuitBreakerState(failure_threshold=5)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == "closed"
        assert cb.last_failure_time is not None

    def test_circuit_opens_after_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        cb = CircuitBreakerState(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()  # Third failure - threshold reached
        assert cb.state == "open"

    def test_is_available_when_closed(self):
        """Test circuit allows requests when closed."""
        cb = CircuitBreakerState()
        assert cb.is_available() is True

    def test_is_available_when_open(self):
        """Test circuit rejects requests when open."""
        cb = CircuitBreakerState(failure_threshold=1)
        cb.record_failure()  # Opens the circuit
        assert cb.state == "open"
        assert cb.is_available() is False

    def test_transition_to_half_open_after_timeout(self):
        """Test circuit transitions to half_open after recovery timeout."""
        cb = CircuitBreakerState(failure_threshold=1, recovery_timeout_seconds=0.1)
        cb.record_failure()
        assert cb.state == "open"

        # Wait for recovery timeout
        import time

        time.sleep(0.15)

        # Check availability - should transition to half_open
        assert cb.is_available() is True
        assert cb.state == "half_open"

    def test_is_available_when_half_open(self):
        """Test circuit allows one request when half_open."""
        cb = CircuitBreakerState()
        cb.state = "half_open"
        assert cb.is_available() is True


# ============================================================================
# Client Initialization Tests
# ============================================================================


class TestClientInitialization:
    """Tests for IntelligenceServiceClient initialization."""

    def test_default_initialization(self):
        """Test client initializes with defaults."""
        client = IntelligenceServiceClient()
        assert client.base_url == "http://localhost:8053"
        assert client.timeout_seconds == 30.0
        assert client.max_retries == 3
        assert client.circuit_breaker_enabled is True
        assert client.circuit_breaker is not None
        assert client.client is None

    def test_custom_initialization(self):
        """Test client initializes with custom parameters."""
        client = IntelligenceServiceClient(
            base_url="http://custom:9000/",  # Trailing slash should be stripped
            timeout_seconds=60.0,
            max_retries=5,
            circuit_breaker_enabled=False,
        )
        assert client.base_url == "http://custom:9000"
        assert client.timeout_seconds == 60.0
        assert client.max_retries == 5
        assert client.circuit_breaker_enabled is False
        assert client.circuit_breaker is None

    def test_initial_metrics(self):
        """Test client initializes with zero metrics."""
        client = IntelligenceServiceClient()
        assert client.metrics["total_requests"] == 0
        assert client.metrics["successful_requests"] == 0
        assert client.metrics["failed_requests"] == 0
        assert client.metrics["timeout_errors"] == 0
        assert client.metrics["circuit_breaker_opens"] == 0
        assert client.metrics["retries_attempted"] == 0
        assert client.metrics["total_duration_ms"] == 0.0

    def test_initial_health_state(self):
        """Test client initializes with healthy state."""
        client = IntelligenceServiceClient()
        assert client._is_healthy is True
        assert client._last_health_check is None
        assert client._health_check_task is None


# ============================================================================
# Lifecycle Tests (connect/close)
# ============================================================================


class TestClientLifecycle:
    """Tests for client connect/close lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_creates_client(self, client):
        """Test connect initializes httpx client."""
        assert client.client is None
        await client.connect()
        assert client.client is not None
        assert isinstance(client.client, httpx.AsyncClient)
        assert client._health_check_task is not None

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, client):
        """Test multiple connects don't create multiple clients."""
        await client.connect()
        first_client = client.client

        await client.connect()
        assert client.client is first_client

        await client.close()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, client):
        """Test close cleans up client and health check task."""
        await client.connect()
        assert client.client is not None
        assert client._health_check_task is not None

        await client.close()
        assert client.client is None
        assert client._health_check_task is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, client):
        """Test multiple closes don't raise errors."""
        await client.connect()
        await client.close()
        await client.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager protocol."""
        async with client as c:
            assert c is client
            assert c.client is not None

        assert client.client is None


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Tests for check_health method."""

    @pytest.mark.asyncio
    async def test_check_health_success(self, client, mock_health_response_data):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_health_response_data

        await client.connect()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.check_health()

            assert isinstance(result, ModelHealthCheckResponse)
            assert result.status == "healthy"
            assert client._is_healthy is True
            assert client._last_health_check is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_check_health_unhealthy_status_code(self, client):
        """Test health check with non-200 status code.

        Note: The client wraps IntelligenceServiceUnavailable in a generic
        IntelligenceServiceError due to the exception handling flow.
        """
        mock_response = MagicMock()
        mock_response.status_code = 503

        await client.connect()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # The exception is caught and re-wrapped as IntelligenceServiceError
            with pytest.raises(IntelligenceServiceError) as exc_info:
                await client.check_health()

            assert "503" in str(exc_info.value)
            assert client._is_healthy is False

        await client.close()

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, client):
        """Test health check timeout handling."""
        await client.connect()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Connection timed out")

            with pytest.raises(IntelligenceServiceTimeout) as exc_info:
                await client.check_health()

            assert client._is_healthy is False
            assert exc_info.value.details["timeout_seconds"] == 2.0

        await client.close()

    @pytest.mark.asyncio
    async def test_check_health_network_error(self, client):
        """Test health check network error handling."""
        await client.connect()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.NetworkError("Connection refused")

            with pytest.raises(IntelligenceServiceUnavailable) as exc_info:
                await client.check_health()

            assert "Network error" in str(exc_info.value)
            assert client._is_healthy is False

        await client.close()

    @pytest.mark.asyncio
    async def test_check_health_not_connected_error(self, client):
        """Test health check fails when not connected."""
        with pytest.raises(IntelligenceServiceError) as exc_info:
            await client.check_health()

        assert "not connected" in str(exc_info.value).lower()


# ============================================================================
# Code Quality Assessment Tests
# ============================================================================


class TestAssessCodeQuality:
    """Tests for assess_code_quality method.

    Tests cover the public API as well as internal methods to ensure
    comprehensive coverage of the quality assessment logic.
    """

    @pytest.mark.asyncio
    async def test_assess_code_quality_via_execute_with_retry(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test successful code quality assessment via _execute_with_retry.

        Uses _execute_with_retry directly to test the core logic and
        ensure internal methods work correctly.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client._execute_with_retry(
                method="POST",
                endpoint="/assess/code",
                request_model=quality_assessment_request,
                response_model_class=ModelQualityAssessmentResponse,
            )

            assert isinstance(result, ModelQualityAssessmentResponse)
            assert result.success is True
            assert result.quality_score == 0.85
            mock_post.assert_called_once()

            # Verify request was sent to correct endpoint
            call_args = mock_post.call_args
            assert "/assess/code" in call_args[0][0]

        await client.close()

    @pytest.mark.asyncio
    async def test_assess_code_quality_with_timeout_override_via_execute(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test quality assessment with custom timeout via _execute_with_retry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await client._execute_with_retry(
                method="POST",
                endpoint="/assess/code",
                request_model=quality_assessment_request,
                response_model_class=ModelQualityAssessmentResponse,
                timeout_override=60.0,
            )

            call_args = mock_post.call_args
            assert call_args[1]["timeout"] == 60.0

        await client.close()

    @pytest.mark.asyncio
    async def test_assess_code_quality_validation_error(
        self, client, quality_assessment_request
    ):
        """Test quality assessment with validation error response."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [{"loc": ["content"], "msg": "field required"}]
        }

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(IntelligenceServiceValidation):
                await client.assess_code_quality(quality_assessment_request)

        await client.close()

    @pytest.mark.asyncio
    async def test_assess_code_quality_logs_quality_score(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test that assess_code_quality correctly logs the quality_score.

        Verifies the fix for the bug where quality_metrics was incorrectly
        referenced instead of quality_score in the logging statement.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # This should succeed now that the bug is fixed
            result = await client.assess_code_quality(quality_assessment_request)

            # Verify the result has quality_score (not quality_metrics)
            assert hasattr(result, "quality_score")
            assert isinstance(result.quality_score, float)
            assert result.quality_score == mock_quality_response_data["quality_score"]

        await client.close()


# ============================================================================
# Performance Analysis Tests
# ============================================================================


class TestAnalyzePerformance:
    """Tests for analyze_performance method."""

    @pytest.mark.asyncio
    async def test_analyze_performance_success(
        self, client, performance_analysis_request, mock_performance_response_data
    ):
        """Test successful performance analysis."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_performance_response_data

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client.analyze_performance(performance_analysis_request)

            assert isinstance(result, ModelPerformanceAnalysisResponse)
            assert result.operation_name == "test_operation"
            assert result.average_response_time_ms == 100.0

        await client.close()


# ============================================================================
# Pattern Detection Tests
# ============================================================================


class TestDetectPatterns:
    """Tests for detect_patterns method."""

    @pytest.mark.asyncio
    async def test_detect_patterns_success(
        self, client, pattern_detection_request, mock_pattern_response_data
    ):
        """Test successful pattern detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pattern_response_data

        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client.detect_patterns(pattern_detection_request)

            assert isinstance(result, ModelPatternDetectionResponse)
            assert result.success is True
            assert len(result.detected_patterns) == 1
            assert result.detected_patterns[0].pattern_type == "dependency_injection"

        await client.close()


# ============================================================================
# Retry Logic Tests
# ============================================================================


class TestRetryLogic:
    """Tests for retry logic in _execute_with_retry.

    Uses _execute_with_retry directly to test retry behavior with
    fine-grained control over the request execution.
    """

    @pytest.mark.asyncio
    async def test_retry_on_service_unavailable(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test retries on 503 Service Unavailable."""
        await client.connect()

        # First two calls fail with 503, third succeeds
        mock_fail_response = MagicMock()
        mock_fail_response.status_code = 503

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                mock_fail_response,
                mock_fail_response,
                mock_success_response,
            ]

            # Patch sleep to speed up test
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._execute_with_retry(
                    method="POST",
                    endpoint="/assess/code",
                    request_model=quality_assessment_request,
                    response_model_class=ModelQualityAssessmentResponse,
                )

            assert result.success is True
            assert mock_post.call_count == 3

        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test retries on 429 Rate Limit."""
        await client.connect()

        mock_rate_limit = MagicMock()
        mock_rate_limit.status_code = 429
        mock_rate_limit.headers = {"Retry-After": "5"}

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [mock_rate_limit, mock_success]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._execute_with_retry(
                    method="POST",
                    endpoint="/assess/code",
                    request_model=quality_assessment_request,
                    response_model_class=ModelQualityAssessmentResponse,
                )

            assert result.success is True
            assert mock_post.call_count == 2

        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_timeout(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test retries on timeout errors."""
        await client.connect()

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.TimeoutException("timeout"),
                mock_success,
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._execute_with_retry(
                    method="POST",
                    endpoint="/assess/code",
                    request_model=quality_assessment_request,
                    response_model_class=ModelQualityAssessmentResponse,
                )

            assert result.success is True
            assert mock_post.call_count == 2
            assert client.metrics["timeout_errors"] == 1

        await client.close()

    @pytest.mark.asyncio
    async def test_no_retry_on_validation_error(
        self, client, quality_assessment_request
    ):
        """Test no retries on 422 validation errors."""
        await client.connect()

        mock_validation_error = MagicMock()
        mock_validation_error.status_code = 422
        mock_validation_error.json.return_value = {"detail": "Invalid request"}

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_validation_error

            with pytest.raises(IntelligenceServiceValidation):
                await client._execute_with_retry(
                    method="POST",
                    endpoint="/assess/code",
                    request_model=quality_assessment_request,
                    response_model_class=ModelQualityAssessmentResponse,
                )

            # Should only call once - no retries
            assert mock_post.call_count == 1

        await client.close()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, client, quality_assessment_request):
        """Test failure after max retries exceeded."""
        await client.connect()

        mock_fail = MagicMock()
        mock_fail.status_code = 503

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_fail

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(IntelligenceServiceUnavailable):
                    await client._execute_with_retry(
                        method="POST",
                        endpoint="/assess/code",
                        request_model=quality_assessment_request,
                        response_model_class=ModelQualityAssessmentResponse,
                    )

            # Should call max_retries + 1 times (initial + 3 retries)
            assert mock_post.call_count == 4

        await client.close()

    @pytest.mark.asyncio
    async def test_retries_increment_metrics(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test that retry attempts update metrics."""
        await client.connect()

        mock_fail = MagicMock()
        mock_fail.status_code = 503

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [mock_fail, mock_fail, mock_success]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await client._execute_with_retry(
                    method="POST",
                    endpoint="/assess/code",
                    request_model=quality_assessment_request,
                    response_model_class=ModelQualityAssessmentResponse,
                )

            assert client.metrics["retries_attempted"] == 2
            assert client.metrics["successful_requests"] == 1

        await client.close()


# ============================================================================
# Circuit Breaker Integration Tests
# ============================================================================


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with client."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(
        self, client, quality_assessment_request
    ):
        """Test circuit breaker opens after threshold failures."""
        await client.connect()

        mock_fail = MagicMock()
        mock_fail.status_code = 503

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_fail

            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Execute multiple failing requests to open circuit
                for _ in range(2):
                    with pytest.raises(IntelligenceServiceUnavailable):
                        await client.assess_code_quality(quality_assessment_request)

        # Circuit should be open now (5 failures from 2 requests with 3 retries each = 8 failures, > threshold)
        assert client.circuit_breaker.state == "open"

        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(
        self, client, quality_assessment_request
    ):
        """Test requests rejected when circuit breaker is open."""
        await client.connect()

        # Manually open the circuit breaker
        client.circuit_breaker.state = "open"
        client.circuit_breaker.last_failure_time = 999999999999  # Far future

        with pytest.raises(IntelligenceServiceUnavailable) as exc_info:
            await client.assess_code_quality(quality_assessment_request)

        assert "circuit breaker is open" in str(exc_info.value).lower()
        assert client.metrics["circuit_breaker_opens"] == 1

        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled(
        self, client_no_circuit_breaker, quality_assessment_request
    ):
        """Test client works without circuit breaker."""
        client = client_no_circuit_breaker
        await client.connect()

        assert client.circuit_breaker is None

        mock_fail = MagicMock()
        mock_fail.status_code = 503

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_fail

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(IntelligenceServiceUnavailable):
                    await client.assess_code_quality(quality_assessment_request)

        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test circuit breaker resets after successful request."""
        await client.connect()

        # Set up partial failure state
        client.circuit_breaker.failure_count = 3

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_success

            # Use _execute_with_retry directly for testing circuit breaker state
            await client._execute_with_retry(
                method="POST",
                endpoint="/assess/code",
                request_model=quality_assessment_request,
                response_model_class=ModelQualityAssessmentResponse,
            )

        assert client.circuit_breaker.failure_count == 0
        assert client.circuit_breaker.state == "closed"

        await client.close()


# ============================================================================
# Response Parsing Tests
# ============================================================================


class TestResponseParsing:
    """Tests for _parse_response method."""

    @pytest.mark.asyncio
    async def test_parse_200_response(self, client, mock_quality_response_data):
        """Test parsing successful 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        result = client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert isinstance(result, ModelQualityAssessmentResponse)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_parse_422_validation_error(self, client):
        """Test parsing 422 validation error response."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [{"loc": ["body", "content"], "msg": "field required"}]
        }

        with pytest.raises(IntelligenceServiceValidation) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_parse_429_rate_limit(self, client):
        """Test parsing 429 rate limit response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with pytest.raises(IntelligenceServiceRateLimit) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert exc_info.value.details["retry_after"] == 30

    @pytest.mark.asyncio
    async def test_parse_503_service_unavailable(self, client):
        """Test parsing 503 service unavailable response."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with pytest.raises(IntelligenceServiceUnavailable):
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

    @pytest.mark.asyncio
    async def test_parse_500_server_error(self, client):
        """Test parsing 500 server error response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}

        with pytest.raises(IntelligenceServiceError) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_parse_unexpected_status_code(self, client):
        """Test parsing unexpected status code response."""
        mock_response = MagicMock()
        mock_response.status_code = 418  # I'm a teapot
        mock_response.text = "I'm a teapot"

        with pytest.raises(IntelligenceServiceError) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert exc_info.value.status_code == 418

    @pytest.mark.asyncio
    async def test_parse_invalid_json_response(self, client):
        """Test parsing invalid JSON in 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "not valid json"

        with pytest.raises(IntelligenceServiceError) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert "Failed to parse response" in str(exc_info.value)


# ============================================================================
# Execute Request Tests
# ============================================================================


class TestExecuteRequest:
    """Tests for _execute_request method."""

    @pytest.mark.asyncio
    async def test_execute_post_request(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test executing POST request."""
        await client.connect()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client._execute_request(
                "POST",
                "/assess/code",
                quality_assessment_request,
                ModelQualityAssessmentResponse,
            )

            assert isinstance(result, ModelQualityAssessmentResponse)
            mock_post.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_execute_get_request(self, client, mock_quality_response_data):
        """Test executing GET request."""
        await client.connect()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        mock_request = MagicMock()
        mock_request.model_dump.return_value = {"key": "value"}

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await client._execute_request(
                "GET",
                "/test",
                mock_request,
                ModelQualityAssessmentResponse,
            )

            mock_get.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_execute_unsupported_method(self, client):
        """Test executing unsupported HTTP method raises error."""
        await client.connect()

        mock_request = MagicMock()
        mock_request.model_dump.return_value = {}

        with pytest.raises(IntelligenceServiceError) as exc_info:
            await client._execute_request(
                "DELETE",
                "/test",
                mock_request,
                ModelQualityAssessmentResponse,
            )

        assert "Unsupported HTTP method" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_execute_request_network_error(
        self, client, quality_assessment_request
    ):
        """Test handling network error during request."""
        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.NetworkError("Connection refused")

            with pytest.raises(IntelligenceServiceUnavailable) as exc_info:
                await client._execute_request(
                    "POST",
                    "/assess/code",
                    quality_assessment_request,
                    ModelQualityAssessmentResponse,
                )

            assert "Network error" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_execute_request_updates_metrics(
        self, client, quality_assessment_request, mock_quality_response_data
    ):
        """Test request execution updates metrics."""
        await client.connect()

        initial_total = client.metrics["total_requests"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_quality_response_data

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await client._execute_request(
                "POST",
                "/assess/code",
                quality_assessment_request,
                ModelQualityAssessmentResponse,
            )

        assert client.metrics["total_requests"] == initial_total + 1
        assert client.metrics["total_duration_ms"] > 0

        await client.close()


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for metrics tracking."""

    def test_get_metrics_initial_state(self, client):
        """Test get_metrics returns initial state."""
        metrics = client.get_metrics()

        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
        assert metrics["failed_requests"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["avg_duration_ms"] == 0.0
        assert metrics["circuit_breaker_state"] == "closed"
        assert metrics["is_healthy"] is True
        assert metrics["last_health_check"] is None

    def test_get_metrics_success_rate_calculation(self, client):
        """Test success rate calculation in metrics."""
        client.metrics["total_requests"] = 100
        client.metrics["successful_requests"] = 95
        client.metrics["failed_requests"] = 5

        metrics = client.get_metrics()

        assert metrics["success_rate"] == 0.95

    def test_get_metrics_avg_duration_calculation(self, client):
        """Test average duration calculation in metrics."""
        client.metrics["successful_requests"] = 10
        client.metrics["total_duration_ms"] = 1000.0

        metrics = client.get_metrics()

        assert metrics["avg_duration_ms"] == 100.0

    def test_get_metrics_circuit_breaker_disabled(self, client_no_circuit_breaker):
        """Test metrics when circuit breaker is disabled."""
        metrics = client_no_circuit_breaker.get_metrics()

        assert metrics["circuit_breaker_state"] == "disabled"

    def test_reset_metrics(self, client):
        """Test reset_metrics clears all counters."""
        client.metrics["total_requests"] = 100
        client.metrics["successful_requests"] = 95
        client.metrics["failed_requests"] = 5
        client.metrics["total_duration_ms"] = 5000.0

        client.reset_metrics()

        assert client.metrics["total_requests"] == 0
        assert client.metrics["successful_requests"] == 0
        assert client.metrics["failed_requests"] == 0
        assert client.metrics["total_duration_ms"] == 0.0


# ============================================================================
# Periodic Health Check Tests
# ============================================================================


class TestPeriodicHealthCheck:
    """Tests for periodic health check background task."""

    @pytest.mark.asyncio
    async def test_periodic_health_check_runs(self, client, mock_health_response_data):
        """Test periodic health check task starts and runs."""
        await client.connect()

        assert client._health_check_task is not None
        assert not client._health_check_task.done()

        await client.close()

    @pytest.mark.asyncio
    async def test_periodic_health_check_cancellation(self, client):
        """Test periodic health check task is properly cancelled."""
        await client.connect()
        task = client._health_check_task

        await client.close()

        assert client._health_check_task is None
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_periodic_health_check_handles_errors(self, client):
        """Test periodic health check handles errors gracefully."""
        await client.connect()

        # Force an error in check_health
        with patch.object(
            client, "check_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.side_effect = Exception("Test error")

            # The periodic task should continue running despite errors
            await asyncio.sleep(0.1)

            assert not client._health_check_task.done()

        await client.close()


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_not_connected(
        self, client, quality_assessment_request
    ):
        """Test _execute_with_retry fails when client not connected."""
        with pytest.raises(IntelligenceServiceError) as exc_info:
            await client._execute_with_retry(
                "POST",
                "/assess/code",
                quality_assessment_request,
                ModelQualityAssessmentResponse,
            )

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_malformed_422_response(self, client):
        """Test handling malformed 422 response that fails JSON parse."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid request body"

        with pytest.raises(IntelligenceServiceValidation) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        # Should still raise validation error with text as detail
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_malformed_500_response(self, client):
        """Test handling malformed 500 response that fails JSON parse."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Internal server error"

        with pytest.raises(IntelligenceServiceError) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_execute_request(
        self, client, quality_assessment_request
    ):
        """Test handling unexpected exception during request execution."""
        await client.connect()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(IntelligenceServiceError) as exc_info:
                await client._execute_request(
                    "POST",
                    "/assess/code",
                    quality_assessment_request,
                    ModelQualityAssessmentResponse,
                )

            assert "Unexpected error" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limit_without_retry_after_header(self, client):
        """Test rate limit response without Retry-After header."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}  # No Retry-After header

        with pytest.raises(IntelligenceServiceRateLimit) as exc_info:
            client._parse_response(mock_response, ModelQualityAssessmentResponse)

        # Should still work without retry_after
        assert "retry_after" not in exc_info.value.details

    def test_base_url_trailing_slash_stripped(self):
        """Test that trailing slash is stripped from base URL."""
        client = IntelligenceServiceClient(base_url="http://localhost:8053/")
        assert client.base_url == "http://localhost:8053"

        client2 = IntelligenceServiceClient(base_url="http://localhost:8053/api/v1/")
        assert client2.base_url == "http://localhost:8053/api/v1"

    @pytest.mark.asyncio
    async def test_generic_error_during_health_check(
        self, client, mock_health_response_data
    ):
        """Test handling generic exception during health check."""
        await client.connect()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = RuntimeError("Unexpected")

            with pytest.raises(IntelligenceServiceError) as exc_info:
                await client.check_health()

            assert "Health check failed" in str(exc_info.value)
            assert client._is_healthy is False

        await client.close()
