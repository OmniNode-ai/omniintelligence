"""
OnexTree HTTP Client - ONEX Effect Node

Async HTTP client for OnexTree service with circuit breaker pattern,
retry logic, and comprehensive error handling.

ONEX Pattern: Effect Node (External HTTP I/O)
Performance Target: <2s for tree generation, <500ms for queries
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from infrastructure import AsyncCircuitBreaker, CircuitBreakerError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class TreeGenerationRequest(BaseModel):
    """Request model for tree generation."""

    project_path: str = Field(..., description="Path to project root")
    include_tests: bool = Field(default=True, description="Include test files")
    max_depth: Optional[int] = Field(default=None, description="Maximum tree depth")


class TreeGenerationResult(BaseModel):
    """Result model for tree generation."""

    success: bool
    files_tracked: int
    tree_structure: Dict[str, Any]
    processing_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TreeQueryRequest(BaseModel):
    """Request model for tree queries."""

    path_pattern: str = Field(..., description="Path pattern to query")
    include_content: bool = Field(default=False, description="Include file content")
    max_results: int = Field(default=100, description="Maximum results")


class TreeQueryResult(BaseModel):
    """Result model for tree queries."""

    matches: List[Dict[str, Any]]
    total_matches: int
    query_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatternEnrichmentRequest(BaseModel):
    """Request model for pattern enrichment."""

    file_paths: List[str] = Field(..., description="Files to enrich")
    patterns: Dict[str, Any] = Field(..., description="Patterns to apply")
    merge_strategy: str = Field(default="append", description="How to merge patterns")


class PatternEnrichmentResult(BaseModel):
    """Result model for pattern enrichment."""

    enriched_count: int
    failed_count: int
    enriched_files: List[str]
    processing_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Custom Exceptions
# ============================================================================


class OnexTreeError(Exception):
    """Base exception for OnexTree client errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        self.message = message
        self.details = kwargs


class OnexTreeUnavailableError(OnexTreeError):
    """Raised when OnexTree service is unavailable."""

    pass


class OnexTreeTimeoutError(OnexTreeError):
    """Raised when request times out."""

    def __init__(self, message: str, timeout_seconds: float, **kwargs):
        super().__init__(message, timeout_seconds=timeout_seconds, **kwargs)
        self.timeout_seconds = timeout_seconds


class OnexTreeValidationError(OnexTreeError):
    """Raised when request validation fails."""

    def __init__(self, message: str, validation_errors: List[Dict] = None, **kwargs):
        super().__init__(message, validation_errors=validation_errors or [], **kwargs)
        self.validation_errors = validation_errors or []


class OnexTreeRateLimitError(OnexTreeError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, retry_after=retry_after, **kwargs)
        self.retry_after = retry_after


class OnexTreeServerError(OnexTreeError):
    """Raised when server returns 5xx error."""

    def __init__(
        self, message: str, status_code: int, response_data: Dict = None, **kwargs
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_data=response_data or {},
            **kwargs,
        )
        self.status_code = status_code
        self.response_data = response_data or {}


# ============================================================================
# OnexTree HTTP Client
# ============================================================================


class OnexTreeClient:
    """
    Async HTTP client for OnexTree service.

    ONEX Node Type: Effect (External HTTP I/O)

    Features:
    - Circuit breaker pattern (opens after 5 failures, resets after 60s)
    - Retry logic with exponential backoff (max 3 retries)
    - Timeout handling (5s default, configurable)
    - Health check integration with periodic polling
    - Comprehensive error logging and metrics
    - Graceful degradation patterns

    Architecture:
    - Uses httpx async HTTP client for efficient connection pooling
    - Circuit breaker prevents cascade failures
    - Retries on transient errors (503, 429, timeouts)
    - Fails fast on validation errors (422, 400)

    Performance:
    - Target: <2s for tree generation (uncached)
    - Target: <500ms for queries
    - Circuit breaker prevents unnecessary retries when service is down
    - Health checks run every 30 seconds in background

    Usage:
        async with OnexTreeClient() as client:
            result = await client.generate_tree("/path/to/project")
    """

    def __init__(
        self,
        base_url: str = "http://omninode-bridge-onextree:8058",
        timeout_seconds: float = 5.0,
        max_retries: int = 3,
        circuit_breaker_enabled: bool = True,
    ):
        """
        Initialize OnexTree HTTP client.

        Args:
            base_url: Base URL for OnexTree service
            timeout_seconds: Request timeout in seconds (default: 5.0)
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
        self.circuit_breaker: Optional[AsyncCircuitBreaker] = None

        if circuit_breaker_enabled:
            self.circuit_breaker = AsyncCircuitBreaker(
                failure_threshold=5,  # Open after 5 failures
                recovery_timeout_seconds=60,  # Reset after 60 seconds
                half_open_max_attempts=3,
                name="onextree_service",
            )

        # Health check state
        self._health_check_task: Optional[asyncio.Task] = None
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
            f"OnexTreeClient initialized: base_url={base_url}, "
            f"timeout={timeout_seconds}s, max_retries={max_retries}, "
            f"circuit_breaker={circuit_breaker_enabled}"
        )

    # ========================================================================
    # Context Manager Protocol
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize HTTP client and start health checks."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
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

    async def get_tree_health(self) -> Dict[str, Any]:
        """
        Get OnexTree service health status.

        Returns:
            Health status with service metrics

        Raises:
            OnexTreeUnavailableError: Service is unavailable
            OnexTreeTimeoutError: Request timed out
        """
        return await self.check_health()

    async def generate_tree(
        self,
        project_path: str,
        include_tests: bool = True,
        max_depth: Optional[int] = None,
        timeout_override: Optional[float] = None,
    ) -> TreeGenerationResult:
        """
        Generate project tree structure.

        Args:
            project_path: Path to project root
            include_tests: Include test files in tree
            max_depth: Maximum tree depth (None = unlimited)
            timeout_override: Optional timeout override in seconds

        Returns:
            TreeGenerationResult with tree structure and metadata

        Raises:
            OnexTreeUnavailableError: Service is unavailable or circuit breaker is open
            OnexTreeTimeoutError: Request timed out
            OnexTreeValidationError: Request validation failed
            OnexTreeServerError: Server-side error (5xx)
        """
        if not self.client:
            raise OnexTreeError("Client not connected. Use async context manager.")

        # Check circuit breaker state
        if self.circuit_breaker_enabled and self.circuit_breaker:
            if self.circuit_breaker.current_state == "open":
                logger.warning("Circuit breaker is OPEN - rejecting request")
                self.metrics["circuit_breaker_opens"] += 1
                raise OnexTreeUnavailableError(
                    "OnexTree service circuit breaker is open"
                )

        # Build request
        request = TreeGenerationRequest(
            project_path=project_path, include_tests=include_tests, max_depth=max_depth
        )

        # Execute with retry logic
        return await self._execute_with_retry(
            "POST", "/generate", request, TreeGenerationResult, timeout_override
        )

    async def query_tree(
        self,
        path_pattern: str,
        include_content: bool = False,
        max_results: int = 100,
        timeout_override: Optional[float] = None,
    ) -> TreeQueryResult:
        """
        Query tree structure by path pattern.

        Args:
            path_pattern: Path pattern to query (supports wildcards)
            include_content: Include file content in results
            max_results: Maximum results to return
            timeout_override: Optional timeout override in seconds

        Returns:
            TreeQueryResult with matching files

        Raises:
            OnexTreeUnavailableError: Service is unavailable
            OnexTreeTimeoutError: Request timed out
            OnexTreeValidationError: Request validation failed
        """
        if not self.client:
            raise OnexTreeError("Client not connected. Use async context manager.")

        # Build request
        request = TreeQueryRequest(
            path_pattern=path_pattern,
            include_content=include_content,
            max_results=max_results,
        )

        # Execute with retry logic
        return await self._execute_with_retry(
            "GET", "/query", request, TreeQueryResult, timeout_override
        )

    async def enrich_with_patterns(
        self,
        file_paths: List[str],
        patterns: Dict[str, Any],
        merge_strategy: str = "append",
        timeout_override: Optional[float] = None,
    ) -> PatternEnrichmentResult:
        """
        Enrich files with pattern metadata.

        Args:
            file_paths: List of file paths to enrich
            patterns: Pattern metadata to apply
            merge_strategy: How to merge patterns ("append", "replace", "merge")
            timeout_override: Optional timeout override in seconds

        Returns:
            PatternEnrichmentResult with enrichment status

        Raises:
            OnexTreeUnavailableError: Service is unavailable
            OnexTreeTimeoutError: Request timed out
            OnexTreeValidationError: Request validation failed
        """
        if not self.client:
            raise OnexTreeError("Client not connected. Use async context manager.")

        # Build request
        request = PatternEnrichmentRequest(
            file_paths=file_paths, patterns=patterns, merge_strategy=merge_strategy
        )

        # Execute with retry logic
        return await self._execute_with_retry(
            "POST", "/enrich", request, PatternEnrichmentResult, timeout_override
        )

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        request: BaseModel,
        result_type: type[BaseModel],
        timeout_override: Optional[float] = None,
    ) -> BaseModel:
        """
        Execute request with exponential backoff retry logic.

        Retries on:
        - 503 Service Unavailable
        - 429 Rate Limit
        - Timeout errors
        - Connection errors

        Does NOT retry on:
        - 422 Validation errors
        - 400 Bad Request
        - 401/403 Authentication errors

        Args:
            method: HTTP method
            endpoint: API endpoint
            request: Request to execute
            result_type: Expected result type
            timeout_override: Optional timeout override

        Returns:
            Result of specified type
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Execute the request
                result = await self._execute_request(
                    method, endpoint, request, result_type, timeout_override
                )

                # Success - record metrics
                self.metrics["successful_requests"] += 1
                if attempt > 0:
                    self.metrics["retries_attempted"] += attempt
                    logger.info(f"Request succeeded after {attempt} retries")

                return result

            except (
                OnexTreeUnavailableError,
                OnexTreeTimeoutError,
                OnexTreeRateLimitError,
                OnexTreeServerError,
            ) as e:
                last_error = e

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

            except (OnexTreeValidationError, OnexTreeError) as e:
                # Don't retry validation errors or generic errors
                logger.error(f"Request failed with non-retryable error: {e}")
                self.metrics["failed_requests"] += 1
                raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error
        raise OnexTreeError("Unknown error during request execution")

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        request: BaseModel,
        result_type: type[BaseModel],
        timeout_override: Optional[float] = None,
    ) -> BaseModel:
        """
        Execute single HTTP request to OnexTree service.

        Args:
            method: HTTP method
            endpoint: API endpoint
            request: Request to execute
            result_type: Expected result type
            timeout_override: Optional timeout override

        Returns:
            Result of specified type
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        url = f"{self.base_url}{endpoint}"
        timeout = timeout_override or self.timeout_seconds

        try:
            logger.debug(f"Sending {method} request to {url}")

            # Execute with circuit breaker if enabled
            if self.circuit_breaker_enabled and self.circuit_breaker:
                response = await self.circuit_breaker.call_async(
                    self._make_http_request, method, url, request, timeout
                )
            else:
                response = await self._make_http_request(method, url, request, timeout)

            # Parse response
            result = self._parse_response(response, result_type)

            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms

            logger.info(f"Request completed in {duration_ms:.2f}ms: {endpoint}")

            return result

        except httpx.TimeoutException as e:
            self.metrics["timeout_errors"] += 1
            logger.error(f"Request timed out after {timeout}s: {e}")
            raise OnexTreeTimeoutError(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )

        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise OnexTreeUnavailableError(
                f"Network error connecting to OnexTree service: {e}"
            )

        except CircuitBreakerError as e:
            self.metrics["circuit_breaker_opens"] += 1
            logger.error(f"Circuit breaker prevented request: {e}")
            raise OnexTreeUnavailableError(
                "Circuit breaker is open - service unavailable"
            )

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}", exc_info=True)
            raise OnexTreeError(f"Unexpected error: {e}")

    async def _make_http_request(
        self, method: str, url: str, request: BaseModel, timeout: float
    ) -> httpx.Response:
        """
        Make the actual HTTP request.

        Separated to allow circuit breaker wrapping.

        Args:
            method: HTTP method
            url: Request URL
            request: Request payload
            timeout: Timeout in seconds

        Returns:
            HTTP response
        """
        if method == "GET":
            response = await self.client.get(
                url, params=request.model_dump(), timeout=timeout
            )
        elif method == "POST":
            response = await self.client.post(
                url, json=request.model_dump(), timeout=timeout
            )
        else:
            raise OnexTreeError(f"Unsupported HTTP method: {method}")

        return response

    def _parse_response(
        self, response: httpx.Response, result_type: type[BaseModel]
    ) -> BaseModel:
        """
        Parse HTTP response into result model.

        Args:
            response: HTTP response
            result_type: Expected result type

        Returns:
            Parsed result model
        """
        # Check status code
        if response.status_code == 200:
            try:
                data = response.json()
                return result_type(**data)
            except Exception as e:
                logger.error(f"Failed to parse response: {e}", exc_info=True)
                raise OnexTreeError(f"Failed to parse response: {e}")

        elif response.status_code == 422:
            # Validation error
            error_data = response.json()
            raise OnexTreeValidationError(
                f"Request validation failed: {error_data}",
                validation_errors=error_data.get("detail", []),
            )

        elif response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise OnexTreeRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        elif response.status_code == 503:
            # Service unavailable
            raise OnexTreeUnavailableError(
                "OnexTree service is temporarily unavailable"
            )

        elif 500 <= response.status_code < 600:
            # Server error
            error_data = response.json() if response.content else {}
            raise OnexTreeServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
                response_data=error_data,
            )

        else:
            # Other error
            raise OnexTreeError(
                f"Unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_health(self) -> Dict[str, Any]:
        """
        Check health of OnexTree service.

        Returns:
            Health check result with service status and metrics
        """
        if not self.client:
            return {"healthy": False, "error": "Client not connected"}

        try:
            start_time = time.perf_counter()
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=2.0,  # Short timeout for health checks
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            is_healthy = response.status_code == 200
            self._is_healthy = is_healthy
            self._last_health_check = datetime.now(timezone.utc)

            result = {
                "healthy": is_healthy,
                "status_code": response.status_code,
                "response_time_ms": duration_ms,
                "last_check": self._last_health_check.isoformat(),
            }

            # Include service metrics if available
            if is_healthy and response.content:
                try:
                    service_data = response.json()
                    result["service_metrics"] = service_data
                except:
                    pass

            return result

        except Exception as e:
            self._is_healthy = False
            self._last_health_check = datetime.now(timezone.utc)

            logger.warning(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "last_check": self._last_health_check.isoformat(),
            }

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
                logger.error(f"Error in periodic health check: {e}", exc_info=True)

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
                self.circuit_breaker.current_state
                if self.circuit_breaker
                else "disabled"
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
