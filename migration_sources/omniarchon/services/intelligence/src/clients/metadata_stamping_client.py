"""
Metadata Stamping HTTP Client - ONEX Effect Node

Async HTTP client for Metadata Stamping service with circuit breaker pattern,
retry logic, and comprehensive error handling.

ONEX Pattern: Effect Node (External HTTP I/O)
Performance Target: <100ms for single stamp, <1s for batch operations
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field
from src.infrastructure import AsyncCircuitBreaker, CircuitBreakerError

# Add config path for centralized timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from src.config.timeout_config import (
    get_async_timeout,
    get_http_timeout,
    get_retry_config,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


# NOTE: Distributed tracing via X-Correlation-ID header
class MetadataStamp(BaseModel):
    """Metadata stamp model."""

    file_hash: str = Field(..., description="Hash of the file")
    metadata: Dict[str, Any] = Field(..., description="Metadata to stamp")
    timestamp: Optional[str] = Field(default=None, description="Timestamp")
    source: Optional[str] = Field(default="intelligence", description="Source system")


class StampRequest(BaseModel):
    """Request model for stamping a single file."""

    file_hash: str = Field(..., description="Hash of the file")
    metadata: Dict[str, Any] = Field(..., description="Metadata to stamp")
    overwrite: bool = Field(default=False, description="Overwrite existing stamp")


class BatchStampRequest(BaseModel):
    """Request model for batch stamping."""

    stamps: List[MetadataStamp] = Field(..., description="List of stamps")
    overwrite: bool = Field(default=False, description="Overwrite existing stamps")
    batch_size: int = Field(default=100, description="Batch processing size")


class StampResult(BaseModel):
    """Result model for stamp operations."""

    success: bool
    file_hash: str
    stamped_at: str
    metadata: Dict[str, Any]
    processing_time_ms: float


class BatchStampResult(BaseModel):
    """Result model for batch stamp operations."""

    success: bool
    total_stamps: int
    successful_stamps: int
    failed_stamps: int
    results: List[StampResult]
    processing_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationRequest(BaseModel):
    """Request model for metadata validation."""

    metadata: Dict[str, Any] = Field(..., description="Metadata to validate")
    schema_version: Optional[str] = Field(default=None, description="Schema version")


class ValidationResult(BaseModel):
    """Result model for validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StampRetrievalResult(BaseModel):
    """Result model for stamp retrieval."""

    found: bool
    file_hash: str
    metadata: Optional[Dict[str, Any]] = None
    stamped_at: Optional[str] = None
    source: Optional[str] = None


class MetricsResult(BaseModel):
    """Result model for service metrics."""

    total_stamps: int
    stamps_last_hour: int
    stamps_last_day: int
    avg_processing_time_ms: float
    error_rate: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Custom Exceptions
# ============================================================================


class MetadataStampingError(Exception):
    """Base exception for Metadata Stamping client errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        self.message = message
        self.details = kwargs


class MetadataStampingUnavailableError(MetadataStampingError):
    """Raised when Metadata Stamping service is unavailable."""

    pass


class MetadataStampingTimeoutError(MetadataStampingError):
    """Raised when request times out."""

    def __init__(self, message: str, timeout_seconds: float, **kwargs):
        super().__init__(message, timeout_seconds=timeout_seconds, **kwargs)
        self.timeout_seconds = timeout_seconds


class MetadataStampingValidationError(MetadataStampingError):
    """Raised when request validation fails."""

    def __init__(self, message: str, validation_errors: List[Dict] = None, **kwargs):
        super().__init__(message, validation_errors=validation_errors or [], **kwargs)
        self.validation_errors = validation_errors or []


class MetadataStampingRateLimitError(MetadataStampingError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, retry_after=retry_after, **kwargs)
        self.retry_after = retry_after


class MetadataStampingServerError(MetadataStampingError):
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
# Metadata Stamping HTTP Client
# ============================================================================


class MetadataStampingClient:
    """
    Async HTTP client for Metadata Stamping service.

    ONEX Node Type: Effect (External HTTP I/O)

    Features:
    - Circuit breaker pattern (opens after 5 failures, resets after 60s)
    - Retry logic with exponential backoff (max 3 retries)
    - Timeout handling (2s default for single, 10s for batch)
    - Health check integration with periodic polling
    - Comprehensive error logging and metrics
    - Batch processing support (100 items per batch)

    Architecture:
    - Uses httpx async HTTP client for efficient connection pooling
    - Circuit breaker prevents cascade failures
    - Retries on transient errors (503, 429, timeouts)
    - Fails fast on validation errors (422, 400)

    Performance:
    - Target: <100ms for single stamp operations
    - Target: <1s for batch operations (100 items)
    - Circuit breaker prevents unnecessary retries when service is down
    - Health checks run every 30 seconds in background

    Usage:
        async with MetadataStampingClient() as client:
            result = await client.stamp_file("hash123", {"key": "value"})
    """

    def __init__(
        self,
        base_url: str = "http://omninode-bridge-metadata-stamping:8057",
        timeout_seconds: Optional[float] = None,
        batch_timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        circuit_breaker_enabled: bool = True,
    ):
        """
        Initialize Metadata Stamping HTTP client.

        Args:
            base_url: Base URL for Metadata Stamping service
            timeout_seconds: Request timeout in seconds (default: from config)
            batch_timeout_seconds: Batch request timeout (default: from config)
            max_retries: Maximum retry attempts (default: from config)
            circuit_breaker_enabled: Enable circuit breaker (default: True)
        """
        self.base_url = base_url.rstrip("/")

        # Use centralized configuration with fallback to passed values
        retry_config = get_retry_config()
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else get_http_timeout("default")
        )
        self.batch_timeout_seconds = (
            batch_timeout_seconds
            if batch_timeout_seconds is not None
            else get_async_timeout("standard")
        )
        self.max_retries = (
            max_retries if max_retries is not None else retry_config["max_attempts"]
        )

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
                name="metadata_stamping_service",
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
            "total_stamps_created": 0,
            "batch_operations": 0,
        }

        logger.info(
            f"MetadataStampingClient initialized: base_url={base_url}, "
            f"timeout={timeout_seconds}s, batch_timeout={batch_timeout_seconds}s, "
            f"max_retries={max_retries}, circuit_breaker={circuit_breaker_enabled}"
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

    async def stamp_file(
        self,
        file_hash: str,
        metadata: Dict[str, Any],
        overwrite: bool = False,
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
    ) -> StampResult:
        """
        Stamp a file with metadata.

        Args:
            file_hash: Hash of the file to stamp
            metadata: Metadata dictionary to stamp
            overwrite: Overwrite existing stamp if present
            timeout_override: Optional timeout override in seconds
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            StampResult with stamping status

        Raises:
            MetadataStampingUnavailableError: Service is unavailable or circuit breaker is open
            MetadataStampingTimeoutError: Request timed out
            MetadataStampingValidationError: Request validation failed
            MetadataStampingServerError: Server-side error (5xx)
        """
        if not self.client:
            raise MetadataStampingError(
                "Client not connected. Use async context manager."
            )

        # Check circuit breaker state
        if self.circuit_breaker_enabled and self.circuit_breaker:
            if self.circuit_breaker.current_state == "open":
                logger.warning("Circuit breaker is OPEN - rejecting request")
                self.metrics["circuit_breaker_opens"] += 1
                raise MetadataStampingUnavailableError(
                    "Metadata Stamping service circuit breaker is open"
                )

        # Build request
        request = StampRequest(
            file_hash=file_hash, metadata=metadata, overwrite=overwrite
        )

        # Execute with retry logic
        result = await self._execute_with_retry(
            "POST",
            "/api/v1/metadata-stamping/stamp",
            request,
            StampResult,
            timeout_override,
            correlation_id,
        )

        self.metrics["total_stamps_created"] += 1
        return result

    async def batch_stamp(
        self,
        stamps: List[Dict[str, Any]],
        overwrite: bool = False,
        batch_size: int = 100,
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
    ) -> BatchStampResult:
        """
        Stamp multiple files in batch.

        Args:
            stamps: List of stamp dictionaries with file_hash and metadata
            overwrite: Overwrite existing stamps
            batch_size: Batch processing size (default: 100)
            timeout_override: Optional timeout override in seconds
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            BatchStampResult with batch stamping status

        Raises:
            MetadataStampingUnavailableError: Service is unavailable
            MetadataStampingTimeoutError: Request timed out
            MetadataStampingValidationError: Request validation failed
        """
        if not self.client:
            raise MetadataStampingError(
                "Client not connected. Use async context manager."
            )

        # Convert to MetadataStamp models
        stamp_models = [MetadataStamp(**s) for s in stamps]

        # Build request
        request = BatchStampRequest(
            stamps=stamp_models, overwrite=overwrite, batch_size=batch_size
        )

        # Use batch timeout
        timeout = timeout_override or self.batch_timeout_seconds

        # Execute with retry logic
        result = await self._execute_with_retry(
            "POST",
            "/api/v1/metadata-stamping/batch",
            request,
            BatchStampResult,
            timeout,
            correlation_id,
        )

        self.metrics["batch_operations"] += 1
        self.metrics["total_stamps_created"] += result.successful_stamps
        return result

    async def validate_stamp(
        self,
        metadata: Dict[str, Any],
        schema_version: Optional[str] = None,
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
    ) -> ValidationResult:
        """
        Validate metadata before stamping.

        Args:
            metadata: Metadata to validate
            schema_version: Optional schema version to validate against
            timeout_override: Optional timeout override in seconds
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            ValidationResult with validation status and errors

        Raises:
            MetadataStampingUnavailableError: Service is unavailable
            MetadataStampingTimeoutError: Request timed out
        """
        if not self.client:
            raise MetadataStampingError(
                "Client not connected. Use async context manager."
            )

        # Build request
        request = ValidationRequest(metadata=metadata, schema_version=schema_version)

        # Execute with retry logic
        return await self._execute_with_retry(
            "POST",
            "/api/v1/metadata-stamping/validate",
            request,
            ValidationResult,
            timeout_override,
            correlation_id,
        )

    async def get_stamp(
        self,
        file_hash: str,
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
    ) -> StampRetrievalResult:
        """
        Retrieve stamp for a file.

        Args:
            file_hash: Hash of the file
            timeout_override: Optional timeout override in seconds
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            StampRetrievalResult with stamp data if found

        Raises:
            MetadataStampingUnavailableError: Service is unavailable
            MetadataStampingTimeoutError: Request timed out
        """
        if not self.client:
            raise MetadataStampingError(
                "Client not connected. Use async context manager."
            )

        # Execute with retry logic
        url = f"/api/v1/metadata-stamping/stamp/{file_hash}"
        timeout = timeout_override or self.timeout_seconds

        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        # Build headers with optional correlation ID for distributed tracing
        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = str(correlation_id)

        try:
            response = await self.client.get(
                f"{self.base_url}{url}", timeout=timeout, headers=headers
            )

            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms
            self.metrics["successful_requests"] += 1

            # Parse response
            if response.status_code == 200:
                data = response.json()
                return StampRetrievalResult(**data)
            elif response.status_code == 404:
                return StampRetrievalResult(found=False, file_hash=file_hash)
            else:
                raise MetadataStampingError(
                    f"Unexpected status code: {response.status_code}"
                )

        except httpx.TimeoutException:
            self.metrics["timeout_errors"] += 1
            raise MetadataStampingTimeoutError(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )
        except Exception as e:
            self.metrics["failed_requests"] += 1
            raise MetadataStampingError(f"Error retrieving stamp: {e}")

    async def get_metrics(self) -> MetricsResult:
        """
        Get service metrics.

        Returns:
            MetricsResult with service metrics

        Raises:
            MetadataStampingUnavailableError: Service is unavailable
            MetadataStampingTimeoutError: Request timed out
        """
        if not self.client:
            raise MetadataStampingError(
                "Client not connected. Use async context manager."
            )

        start_time = time.perf_counter()
        metrics_timeout = get_http_timeout("health")

        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/metadata-stamping/metrics",
                timeout=metrics_timeout,
            )

            # Record metrics
            (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return MetricsResult(**data)
            else:
                raise MetadataStampingError(
                    f"Unexpected status code: {response.status_code}"
                )

        except httpx.TimeoutException:
            raise MetadataStampingTimeoutError(
                "Metrics request timed out", timeout_seconds=metrics_timeout
            )
        except Exception as e:
            raise MetadataStampingError(f"Error retrieving metrics: {e}")

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        request: BaseModel,
        result_type: type[BaseModel],
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
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
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            Result of specified type
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Execute the request
                result = await self._execute_request(
                    method,
                    endpoint,
                    request,
                    result_type,
                    timeout_override,
                    correlation_id,
                )

                # Success - record metrics
                self.metrics["successful_requests"] += 1
                if attempt > 0:
                    self.metrics["retries_attempted"] += attempt
                    logger.info(f"Request succeeded after {attempt} retries")

                return result

            except (
                MetadataStampingUnavailableError,
                MetadataStampingTimeoutError,
                MetadataStampingRateLimitError,
                MetadataStampingServerError,
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

            except (MetadataStampingValidationError, MetadataStampingError) as e:
                # Don't retry validation errors or generic errors
                logger.error(f"Request failed with non-retryable error: {e}")
                self.metrics["failed_requests"] += 1
                raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error
        raise MetadataStampingError("Unknown error during request execution")

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        request: BaseModel,
        result_type: type[BaseModel],
        timeout_override: Optional[float] = None,
        correlation_id: Optional[UUID] = None,
    ) -> BaseModel:
        """
        Execute single HTTP request to Metadata Stamping service.

        Args:
            method: HTTP method
            endpoint: API endpoint
            request: Request to execute
            result_type: Expected result type
            timeout_override: Optional timeout override
            correlation_id: Optional correlation ID for distributed tracing

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
                    self._make_http_request,
                    method,
                    url,
                    request,
                    timeout,
                    correlation_id,
                )
            else:
                response = await self._make_http_request(
                    method, url, request, timeout, correlation_id
                )

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
            raise MetadataStampingTimeoutError(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )

        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise MetadataStampingUnavailableError(
                f"Network error connecting to Metadata Stamping service: {e}"
            )

        except CircuitBreakerError as e:
            self.metrics["circuit_breaker_opens"] += 1
            logger.error(f"Circuit breaker prevented request: {e}")
            raise MetadataStampingUnavailableError(
                "Circuit breaker is open - service unavailable"
            )

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}", exc_info=True)
            raise MetadataStampingError(f"Unexpected error: {e}")

    async def _make_http_request(
        self,
        method: str,
        url: str,
        request: BaseModel,
        timeout: float,
        correlation_id: Optional[UUID] = None,
    ) -> httpx.Response:
        """
        Make the actual HTTP request.

        Separated to allow circuit breaker wrapping.

        Args:
            method: HTTP method
            url: Request URL
            request: Request payload
            timeout: Timeout in seconds
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            HTTP response
        """
        # Build headers with optional correlation ID for distributed tracing
        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = str(correlation_id)

        if method == "POST":
            response = await self.client.post(
                url, json=request.model_dump(), timeout=timeout, headers=headers
            )
        else:
            raise MetadataStampingError(f"Unsupported HTTP method: {method}")

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
                raise MetadataStampingError(f"Failed to parse response: {e}")

        elif response.status_code == 422:
            # Validation error
            error_data = response.json()
            raise MetadataStampingValidationError(
                f"Request validation failed: {error_data}",
                validation_errors=error_data.get("detail", []),
            )

        elif response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise MetadataStampingRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        elif response.status_code == 503:
            # Service unavailable
            raise MetadataStampingUnavailableError(
                "Metadata Stamping service is temporarily unavailable"
            )

        elif 500 <= response.status_code < 600:
            # Server error
            error_data = response.json() if response.content else {}
            raise MetadataStampingServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
                response_data=error_data,
            )

        else:
            # Other error
            raise MetadataStampingError(
                f"Unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_health(self) -> Dict[str, Any]:
        """
        Check health of Metadata Stamping service.

        Returns:
            Health check result with service status and metrics
        """
        if not self.client:
            return {"healthy": False, "error": "Client not connected"}

        try:
            start_time = time.perf_counter()
            health_timeout = get_http_timeout("health")
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=health_timeout,  # Short timeout for health checks
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

        Runs at configured intervals to monitor service health.
        """
        health_check_interval = get_async_timeout("standard")
        while True:
            try:
                await asyncio.sleep(
                    health_check_interval
                )  # Check at configured interval
                await self.check_health()
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}", exc_info=True)

    # ========================================================================
    # Metrics and Monitoring
    # ========================================================================

    def get_client_metrics(self) -> Dict[str, Any]:
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
            "total_stamps_created": 0,
            "batch_operations": 0,
        }
        logger.info("Metrics reset")
