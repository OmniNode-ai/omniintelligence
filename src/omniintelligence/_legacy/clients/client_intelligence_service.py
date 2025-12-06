"""
Intelligence Service HTTP Client - ONEX Effect Node

Async HTTP client for Archon Intelligence Service with:
- Circuit breaker pattern for resilience
- Retry logic with exponential backoff
- HTTP/2 connection pooling
- Comprehensive error handling (HTTP errors -> OnexError)
- Request/response model validation
- Metrics tracking and monitoring
- Health check integration

ONEX Pattern: Effect Node (External HTTP I/O)
Service: Archon Intelligence Service
Base URL: http://localhost:8053 (configurable)

Performance Targets:
- Quality Assessment: <2s (uncached), <500ms (cached)
- Performance Analysis: <3s
- Pattern Detection: <1.5s
- Circuit Breaker: Opens after 5 failures, resets after 60s
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import httpx

# Import API contract models from omniintelligence
from omniintelligence._legacy.models.model_intelligence_api_contracts import (
    ModelHealthCheckResponse,
    ModelPatternDetectionRequest,
    ModelPatternDetectionResponse,
    ModelPerformanceAnalysisRequest,
    ModelPerformanceAnalysisResponse,
    ModelQualityAssessmentRequest,
    ModelQualityAssessmentResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Error Codes and Base Exception
# ============================================================================


class CoreErrorCode(Enum):
    """Core error codes for intelligence service errors."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class OnexError(Exception):
    """Base exception for ONEX errors."""

    def __init__(
        self,
        message: str,
        error_code: CoreErrorCode,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


# ============================================================================
# Custom Exceptions (Intelligence Service Specific)
# ============================================================================


class IntelligenceServiceError(OnexError):
    """Base exception for Intelligence Service client errors."""

    def __init__(
        self,
        message: str,
        error_code: CoreErrorCode = CoreErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        super().__init__(message, error_code, details, status_code)


class IntelligenceServiceUnavailable(IntelligenceServiceError):
    """Raised when Intelligence Service is unavailable."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            error_code=CoreErrorCode.SERVICE_UNAVAILABLE,
            details=details,
            status_code=503,
        )


class IntelligenceServiceTimeout(IntelligenceServiceError):
    """Raised when request times out."""

    def __init__(
        self,
        message: str,
        timeout_seconds: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message,
            error_code=CoreErrorCode.INTERNAL_ERROR,
            details=details,
            status_code=504,
        )


class IntelligenceServiceValidation(IntelligenceServiceError):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[list[Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["validation_errors"] = validation_errors or []
        super().__init__(
            message,
            error_code=CoreErrorCode.VALIDATION_ERROR,
            details=details,
            status_code=422,
        )


class IntelligenceServiceRateLimit(IntelligenceServiceError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message,
            error_code=CoreErrorCode.RATE_LIMIT_EXCEEDED,
            details=details,
            status_code=429,
        )


# ============================================================================
# Simple Circuit Breaker Implementation
# ============================================================================


class CircuitBreakerState:
    """Circuit breaker state management."""

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open

    def record_success(self) -> None:
        """Record successful request."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )

    def is_available(self) -> bool:
        """Check if circuit breaker allows requests."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout has elapsed
            if self.last_failure_time and (
                time.time() - self.last_failure_time > self.recovery_timeout_seconds
            ):
                self.state = "half_open"
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False

        # half_open state - allow one request to test
        return True


# ============================================================================
# Intelligence Service HTTP Client
# ============================================================================


class IntelligenceServiceClient:
    """
    Async HTTP client for Archon Intelligence Service.

    ONEX Node Type: Effect (External HTTP I/O)

    Features:
    - Circuit breaker pattern (opens after 5 failures, resets after 60s)
    - Retry logic with exponential backoff (max 3 retries)
    - HTTP/2 connection pooling (20 max connections, 5 keepalive)
    - Timeout handling (30s default, configurable per request)
    - Health check integration with periodic polling
    - Comprehensive error handling (HTTP -> OnexError)
    - Request/response validation with Pydantic models
    - Metrics tracking (requests, failures, latency)

    Architecture:
    - Uses httpx async HTTP client for efficient connection pooling
    - Circuit breaker prevents cascade failures
    - Retries on transient errors (503, 429, timeouts)
    - Fails fast on validation errors (422, 400)

    Performance Targets:
    - Quality Assessment: <2s (uncached), <500ms (cached)
    - Performance Analysis: <3s
    - Pattern Detection: <1.5s
    - Circuit breaker prevents unnecessary retries when service is down
    - Health checks run every 30 seconds in background

    Usage:
        async with IntelligenceServiceClient() as client:
            result = await client.assess_code_quality(request)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8053",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        circuit_breaker_enabled: bool = True,
    ):
        """
        Initialize Intelligence Service HTTP client.

        Args:
            base_url: Base URL for Intelligence Service (default: http://localhost:8053)
            timeout_seconds: Request timeout in seconds (default: 30.0)
            max_retries: Maximum retry attempts (default: 3)
            circuit_breaker_enabled: Enable circuit breaker (default: True)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # HTTP client with connection pooling
        self.client: Optional[httpx.AsyncClient] = None

        # Circuit breaker configuration
        self.circuit_breaker_enabled = circuit_breaker_enabled
        self.circuit_breaker: Optional[CircuitBreakerState] = None

        if circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreakerState(
                failure_threshold=5, recovery_timeout_seconds=60.0
            )

        # Health check state
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._is_healthy: bool = True
        self._last_health_check: Optional[datetime] = None

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_errors": 0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
            "total_duration_ms": 0.0,
        }

        logger.info(
            f"IntelligenceServiceClient initialized: base_url={base_url}, "
            f"timeout={timeout_seconds}s, max_retries={max_retries}, "
            f"circuit_breaker={circuit_breaker_enabled}"
        )

    # ========================================================================
    # Context Manager Protocol
    # ========================================================================

    async def __aenter__(self) -> "IntelligenceServiceClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize HTTP client and start health checks."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                http2=True,  # Enable HTTP/2 multiplexing
                follow_redirects=True,
            )

            # Start health check background task
            self._health_check_task = asyncio.create_task(self._periodic_health_check())

            logger.info("HTTP client connected and health checks started")

    async def close(self) -> None:
        """Close HTTP client and stop health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        if self.client:
            await self.client.aclose()
            self.client = None

            logger.info("HTTP client closed")

    # ========================================================================
    # Core API Methods
    # ========================================================================

    async def check_health(self) -> ModelHealthCheckResponse:
        """
        Check health of Intelligence Service.

        Returns:
            ModelHealthCheckResponse with service status and metrics

        Raises:
            IntelligenceServiceUnavailable: Service is unavailable
            IntelligenceServiceTimeout: Request timed out
        """
        if not self.client:
            raise IntelligenceServiceError(
                "Client not connected. Use async context manager."
            )

        try:
            start_time = time.perf_counter()
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=2.0,  # Short timeout for health checks
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code != 200:
                logger.warning(f"Health check returned {response.status_code}")
                raise IntelligenceServiceUnavailable(
                    f"Health check failed with status {response.status_code}",
                    details={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )

            # Parse and validate response
            health_data = response.json()
            health_response = ModelHealthCheckResponse(**health_data)

            self._is_healthy = health_response.status == "healthy"
            self._last_health_check = datetime.now(timezone.utc)

            logger.info(
                f"Health check passed: {health_response.status} ({duration_ms:.2f}ms)"
            )
            return health_response

        except httpx.TimeoutException as e:
            self._is_healthy = False
            self._last_health_check = datetime.now(timezone.utc)
            logger.error(f"Health check timed out: {e}")
            raise IntelligenceServiceTimeout(
                "Health check timed out", timeout_seconds=2.0
            )

        except httpx.NetworkError as e:
            self._is_healthy = False
            self._last_health_check = datetime.now(timezone.utc)
            logger.error(f"Health check network error: {e}")
            raise IntelligenceServiceUnavailable(
                f"Network error connecting to Intelligence Service: {e}"
            )

        except Exception as e:
            self._is_healthy = False
            self._last_health_check = datetime.now(timezone.utc)
            logger.error(f"Health check failed: {e}", exc_info=True)
            raise IntelligenceServiceError(f"Health check failed: {e}")

    async def assess_code_quality(
        self,
        request: ModelQualityAssessmentRequest,
        timeout_override: Optional[float] = None,
    ) -> ModelQualityAssessmentResponse:
        """
        Assess code quality with comprehensive analysis.

        Endpoint: POST /assess/code

        Performs 6-dimensional quality analysis:
        1. Complexity (20%)
        2. Maintainability (20%)
        3. Documentation (15%)
        4. Temporal Relevance (15%)
        5. Pattern Compliance (15%)
        6. Architectural Compliance (15%)

        Args:
            request: Quality assessment request with code content
            timeout_override: Optional timeout override in seconds

        Returns:
            ModelQualityAssessmentResponse with quality metrics

        Raises:
            IntelligenceServiceUnavailable: Service unavailable or circuit breaker open
            IntelligenceServiceTimeout: Request timed out
            IntelligenceServiceValidation: Request validation failed
        """
        start_time = time.perf_counter()
        timeout_used = timeout_override or self.timeout_seconds

        logger.info(
            f"Starting code quality assessment | timeout={timeout_used}s | "
            f"code_length={len(request.content)} chars"
        )

        try:
            result = await self._execute_with_retry(
                method="POST",
                endpoint="/assess/code",
                request_model=request,
                response_model_class=ModelQualityAssessmentResponse,
                timeout_override=timeout_override,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Code quality assessment completed | duration={duration_ms:.2f}ms | "
                f"timeout={timeout_used}s | quality_score={result.quality_score}"
            )

            return result
        except IntelligenceServiceTimeout as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Code quality assessment timed out | duration={duration_ms:.2f}ms | "
                f"timeout={timeout_used}s | code_length={len(request.content)} chars"
            )
            raise
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Code quality assessment failed | duration={duration_ms:.2f}ms | "
                f"timeout={timeout_used}s | error={type(e).__name__}"
            )
            raise

    async def analyze_performance(
        self,
        request: ModelPerformanceAnalysisRequest,
        timeout_override: Optional[float] = None,
    ) -> ModelPerformanceAnalysisResponse:
        """
        Analyze performance baseline and identify optimization opportunities.

        Endpoint: POST /performance/baseline

        Establishes performance baselines and identifies optimization
        opportunities ranked by ROI (return on investment).

        Args:
            request: Performance analysis request
            timeout_override: Optional timeout override in seconds

        Returns:
            ModelPerformanceAnalysisResponse with baseline and opportunities

        Raises:
            IntelligenceServiceUnavailable: Service unavailable
            IntelligenceServiceTimeout: Request timed out
            IntelligenceServiceValidation: Request validation failed
        """
        return await self._execute_with_retry(
            method="POST",
            endpoint="/performance/baseline",
            request_model=request,
            response_model_class=ModelPerformanceAnalysisResponse,
            timeout_override=timeout_override,
        )

    async def detect_patterns(
        self,
        request: ModelPatternDetectionRequest,
        timeout_override: Optional[float] = None,
    ) -> ModelPatternDetectionResponse:
        """
        Detect code patterns (best practices, anti-patterns, security).

        Endpoint: POST /patterns/extract

        Detects patterns across categories:
        - Best practices (SOLID, DRY, KISS)
        - Anti-patterns (code smells, performance issues)
        - Security patterns (input validation, authentication)
        - Architectural patterns (ONEX node types, contracts)

        Args:
            request: Pattern detection request
            timeout_override: Optional timeout override in seconds

        Returns:
            ModelPatternDetectionResponse with detected patterns

        Raises:
            IntelligenceServiceUnavailable: Service unavailable
            IntelligenceServiceTimeout: Request timed out
            IntelligenceServiceValidation: Request validation failed
        """
        return await self._execute_with_retry(
            method="POST",
            endpoint="/patterns/extract",
            request_model=request,
            response_model_class=ModelPatternDetectionResponse,
            timeout_override=timeout_override,
        )

    # ========================================================================
    # Internal Request Execution
    # ========================================================================

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        request_model: Any,
        response_model_class: type,
        timeout_override: Optional[float] = None,
    ) -> Any:
        """
        Execute request with exponential backoff retry logic.

        Retries on:
        - 503 Service Unavailable
        - 429 Rate Limit
        - Timeout errors
        - Network errors

        Does NOT retry on:
        - 422 Validation errors
        - 400 Bad Request
        - 401/403 Authentication errors

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            request_model: Request model (Pydantic BaseModel)
            response_model_class: Expected response model class
            timeout_override: Optional timeout override

        Returns:
            Response model instance

        Raises:
            Various IntelligenceService* exceptions
        """
        if not self.client:
            raise IntelligenceServiceError(
                "Client not connected. Use async context manager."
            )

        # Check circuit breaker state
        if self.circuit_breaker_enabled and self.circuit_breaker:
            if not self.circuit_breaker.is_available():
                logger.warning("Circuit breaker is OPEN - rejecting request")
                self.metrics["circuit_breaker_opens"] += 1
                raise IntelligenceServiceUnavailable(
                    "Intelligence Service circuit breaker is open",
                    details={"state": self.circuit_breaker.state},
                )

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Execute the request
                result = await self._execute_request(
                    method,
                    endpoint,
                    request_model,
                    response_model_class,
                    timeout_override,
                )

                # Success - record metrics and circuit breaker
                self.metrics["successful_requests"] += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                if attempt > 0:
                    self.metrics["retries_attempted"] += attempt
                    logger.info(f"Request succeeded after {attempt} retries")

                return result

            except (
                IntelligenceServiceUnavailable,
                IntelligenceServiceTimeout,
                IntelligenceServiceRateLimit,
            ) as e:
                last_error = e

                # Record failure in circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Check if we should retry
                if attempt < self.max_retries:
                    # Calculate exponential backoff delay
                    delay = min(2**attempt, 10)  # Cap at 10 seconds

                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )

                    await asyncio.sleep(delay)
                    continue
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Request failed after {self.max_retries + 1} attempts: {e}"
                    )
                    self.metrics["failed_requests"] += 1
                    raise

            except (IntelligenceServiceValidation, IntelligenceServiceError) as e:
                # Don't retry validation errors or generic errors
                logger.error(f"Request failed with non-retryable error: {e}")
                self.metrics["failed_requests"] += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error
        raise IntelligenceServiceError("Unknown error during request execution")

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        request_model: Any,
        response_model_class: type,
        timeout_override: Optional[float] = None,
    ) -> Any:
        """
        Execute single HTTP request to Intelligence Service.

        Args:
            method: HTTP method
            endpoint: API endpoint
            request_model: Request model
            response_model_class: Expected response class
            timeout_override: Optional timeout override

        Returns:
            Response model instance

        Raises:
            Various IntelligenceService* exceptions
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        url = f"{self.base_url}{endpoint}"
        timeout = timeout_override or self.timeout_seconds

        try:
            logger.debug(f"Sending {method} request to {url}")

            # Ensure client is available (should be checked by caller, but mypy needs this)
            if self.client is None:
                raise IntelligenceServiceError(
                    "Client not connected. Use async context manager."
                )

            # Execute HTTP request
            if method == "POST":
                response = await self.client.post(
                    url, json=request_model.model_dump(), timeout=timeout
                )
            elif method == "GET":
                response = await self.client.get(
                    url, params=request_model.model_dump(), timeout=timeout
                )
            else:
                raise IntelligenceServiceError(f"Unsupported HTTP method: {method}")

            # Parse response
            result = self._parse_response(response, response_model_class)

            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms

            logger.info(f"Request completed in {duration_ms:.2f}ms: {endpoint}")

            return result

        except httpx.TimeoutException as e:
            self.metrics["timeout_errors"] += 1
            logger.error(f"Request timed out after {timeout}s: {e}")
            raise IntelligenceServiceTimeout(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )

        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise IntelligenceServiceUnavailable(
                f"Network error connecting to Intelligence Service: {e}"
            )

        except IntelligenceServiceError:
            # Re-raise Intelligence Service errors
            raise

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}", exc_info=True)
            raise IntelligenceServiceError(f"Unexpected error: {e}")

    def _parse_response(
        self, response: httpx.Response, response_model_class: type
    ) -> Any:
        """
        Parse HTTP response into response model.

        Args:
            response: HTTP response
            response_model_class: Expected response model class

        Returns:
            Response model instance

        Raises:
            Various IntelligenceService* exceptions based on status code
        """
        # Check status code
        if response.status_code == 200:
            try:
                data = response.json()
                return response_model_class(**data)
            except Exception as e:
                logger.error(f"Failed to parse response: {e}", exc_info=True)
                raise IntelligenceServiceError(
                    f"Failed to parse response: {e}",
                    details={"response_text": response.text[:500]},
                )

        elif response.status_code == 422:
            # Validation error
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}

            raise IntelligenceServiceValidation(
                "Request validation failed",
                validation_errors=error_data.get("detail", []),
                details=error_data,
            )

        elif response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise IntelligenceServiceRateLimit(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        elif response.status_code == 503:
            # Service unavailable
            raise IntelligenceServiceUnavailable(
                "Intelligence Service is temporarily unavailable"
            )

        elif 500 <= response.status_code < 600:
            # Server error
            try:
                error_data = response.json()
            except Exception:
                error_data = {"error": response.text}

            raise IntelligenceServiceError(
                f"Server error: {response.status_code}",
                details={"status_code": response.status_code, "error_data": error_data},
                status_code=response.status_code,
            )

        else:
            # Other error
            raise IntelligenceServiceError(
                f"Unexpected status code: {response.status_code}",
                details={
                    "status_code": response.status_code,
                    "response_text": response.text[:500],
                },
                status_code=response.status_code,
            )

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def _periodic_health_check(self) -> None:
        """
        Background task for periodic health checks.

        Runs every 30 seconds to monitor service health.
        """
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self.check_health()
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.warning(f"Periodic health check failed: {e}")
                # Don't raise - just log and continue

    # ========================================================================
    # Metrics and Monitoring
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive client metrics.

        Returns:
            Dictionary with request statistics and performance data
        """
        total_requests = self.metrics["total_requests"]

        return {
            **self.metrics,
            "success_rate": (
                self.metrics["successful_requests"] / total_requests
                if total_requests > 0
                else 0.0
            ),
            "avg_duration_ms": (
                self.metrics["total_duration_ms"] / self.metrics["successful_requests"]
                if self.metrics["successful_requests"] > 0
                else 0.0
            ),
            "circuit_breaker_state": (
                self.circuit_breaker.state if self.circuit_breaker else "disabled"
            ),
            "is_healthy": self._is_healthy,
            "last_health_check": (
                self._last_health_check.isoformat() if self._last_health_check else None
            ),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_errors": 0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
            "total_duration_ms": 0.0,
        }
        logger.info("Metrics reset")
