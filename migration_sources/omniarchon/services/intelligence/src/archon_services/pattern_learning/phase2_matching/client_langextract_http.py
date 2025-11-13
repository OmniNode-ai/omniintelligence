"""
Langextract HTTP Client - ONEX Effect Node

Async HTTP client for langextract semantic analysis service with circuit breaker
pattern, retry logic, and comprehensive error handling.

ONEX Pattern: Effect Node (External HTTP I/O)
Performance Target: <5s for semantic analysis (uncached)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

try:
    # Try without src prefix first (matches test imports)
    from infrastructure import AsyncCircuitBreaker, CircuitBreakerError
except ImportError:
    # Fall back to src prefix if needed
    from src.infrastructure import AsyncCircuitBreaker, CircuitBreakerError

try:
    # Try without src prefix first (matches test imports - CRITICAL for isinstance checks)
    from archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
        LangextractError,
        LangextractRateLimitError,
        LangextractServerError,
        LangextractTimeoutError,
        LangextractUnavailableError,
        LangextractValidationError,
    )
except ImportError:
    # Fall back to src prefix if needed
    from src.archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
        LangextractError,
        LangextractRateLimitError,
        LangextractServerError,
        LangextractTimeoutError,
        LangextractUnavailableError,
        LangextractValidationError,
    )

try:
    # Try without src prefix first (matches test imports - CRITICAL for isinstance checks)
    from archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
        SemanticAnalysisRequest,
        SemanticAnalysisResult,
        SemanticConcept,
        SemanticDomain,
        SemanticPattern,
        SemanticTheme,
    )
except ImportError:
    # Fall back to src prefix if needed
    from src.archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
        SemanticAnalysisRequest,
        SemanticAnalysisResult,
        SemanticConcept,
        SemanticDomain,
        SemanticPattern,
        SemanticTheme,
    )

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class ClientLangextractHttp:
    """
    Async HTTP client for langextract semantic analysis service.

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
    - Target: <5s for semantic analysis (uncached)
    - Circuit breaker prevents unnecessary retries when service is down
    - Health checks run every 30 seconds in background

    Usage:
        async with ClientLangextractHttp() as client:
            result = await client.analyze_semantic("content text")
    """

    def __init__(
        self,
        base_url: str = "http://archon-langextract:8156",
        timeout_seconds: float = 5.0,
        max_retries: int = 3,
        circuit_breaker_enabled: bool = True,
    ):
        """
        Initialize langextract HTTP client.

        Args:
            base_url: Base URL for langextract service
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
                name="langextract_service",
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
            f"ClientLangextractHttp initialized: base_url={base_url}, "
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

    async def analyze_semantic(
        self,
        content: str,
        context: Optional[str] = None,
        language: str = "en",
        min_confidence: float = 0.7,
        timeout_override: Optional[float] = None,
    ) -> SemanticAnalysisResult:
        """
        Perform semantic analysis on content using langextract service.

        Args:
            content: Text content to analyze
            context: Optional context to guide analysis
            language: Language code (default: "en")
            min_confidence: Minimum confidence threshold (0.0-1.0)
            timeout_override: Optional timeout override in seconds

        Returns:
            SemanticAnalysisResult with concepts, themes, domains, and patterns

        Raises:
            LangextractUnavailableError: Service is unavailable or circuit breaker is open
            LangextractTimeoutError: Request timed out
            LangextractValidationError: Request validation failed
            LangextractRateLimitError: Rate limit exceeded
            LangextractServerError: Server-side error (5xx)
            LangextractError: Other errors
        """
        if not self.client:
            raise LangextractError("Client not connected. Use async context manager.")

        # Check circuit breaker state
        if self.circuit_breaker_enabled and self.circuit_breaker:
            if self.circuit_breaker.current_state == "open":
                logger.warning("Circuit breaker is OPEN - rejecting request")
                self.metrics["circuit_breaker_opens"] += 1
                raise LangextractUnavailableError(
                    "Langextract service circuit breaker is open"
                )

        # Build request
        request = SemanticAnalysisRequest(
            content=content,
            context=context,
            language=language,
            min_confidence=min_confidence,
        )

        # Execute with retry logic
        return await self._execute_with_retry(request, timeout_override)

    async def _execute_with_retry(
        self, request: SemanticAnalysisRequest, timeout_override: Optional[float] = None
    ) -> SemanticAnalysisResult:
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
            request: Request to execute
            timeout_override: Optional timeout override

        Returns:
            SemanticAnalysisResult

        Raises:
            Various LangextractError subclasses
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Execute the request
                result = await self._execute_request(request, timeout_override)

                # Success - record metrics
                self.metrics["successful_requests"] += 1
                if attempt > 0:
                    self.metrics["retries_attempted"] += attempt
                    logger.info(f"Request succeeded after {attempt} retries")

                return result

            except (
                LangextractUnavailableError,
                LangextractTimeoutError,
                LangextractRateLimitError,
                LangextractServerError,
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

            except (LangextractValidationError, LangextractError) as e:
                # Don't retry validation errors or generic errors
                logger.error(f"Request failed with non-retryable error: {e}")
                self.metrics["failed_requests"] += 1
                raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error
        raise LangextractError("Unknown error during request execution")

    async def _execute_request(
        self, request: SemanticAnalysisRequest, timeout_override: Optional[float] = None
    ) -> SemanticAnalysisResult:
        """
        Execute single HTTP request to langextract service.

        Args:
            request: Request to execute
            timeout_override: Optional timeout override

        Returns:
            SemanticAnalysisResult

        Raises:
            Various LangextractError subclasses
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        url = f"{self.base_url}/analyze/semantic"
        timeout = timeout_override or self.timeout_seconds

        try:
            logger.debug(f"Sending request to {url}")

            # Execute with circuit breaker if enabled
            if self.circuit_breaker_enabled and self.circuit_breaker:
                response = await self.circuit_breaker.call_async(
                    self._make_http_request, url, request, timeout
                )
            else:
                response = await self._make_http_request(url, request, timeout)

            # Parse response
            result = self._parse_response(response)

            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms

            logger.info(
                f"Semantic analysis completed in {duration_ms:.2f}ms: "
                f"{len(result.concepts)} concepts, {len(result.themes)} themes, "
                f"{len(result.domains)} domains, {len(result.patterns)} patterns"
            )

            return result

        except httpx.TimeoutException as e:
            self.metrics["timeout_errors"] += 1
            logger.error(f"Request timed out after {timeout}s: {e}")
            raise LangextractTimeoutError(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )

        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise LangextractUnavailableError(
                f"Network error connecting to langextract service: {e}"
            )

        except CircuitBreakerError as e:
            self.metrics["circuit_breaker_opens"] += 1
            logger.error(f"Circuit breaker prevented request: {e}")
            raise LangextractUnavailableError(
                "Circuit breaker is open - service unavailable"
            )

        except (
            LangextractValidationError,
            LangextractRateLimitError,
            LangextractServerError,
            LangextractUnavailableError,
            LangextractTimeoutError,
            LangextractError,
        ):
            # Let specific Langextract exceptions propagate as-is
            raise

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}", exc_info=True)
            raise LangextractError(f"Unexpected error: {e}")

    async def _make_http_request(
        self, url: str, request: SemanticAnalysisRequest, timeout: float
    ) -> httpx.Response:
        """
        Make the actual HTTP request.

        Separated to allow circuit breaker wrapping.

        Args:
            url: Request URL
            request: Request payload
            timeout: Timeout in seconds

        Returns:
            HTTP response

        Raises:
            httpx exceptions
        """
        response = await self.client.post(
            url, json=request.model_dump(), timeout=timeout
        )

        return response

    def _parse_response(self, response: httpx.Response) -> SemanticAnalysisResult:
        """
        Parse HTTP response into SemanticAnalysisResult.

        Args:
            response: HTTP response

        Returns:
            SemanticAnalysisResult

        Raises:
            Various LangextractError subclasses based on status code
        """
        # Check status code
        if response.status_code == 200:
            try:
                raw_data = response.json()

                # Validate raw JSON with Pydantic model
                # The SemanticAnalysisResult model will validate all nested models
                try:
                    validated_result = SemanticAnalysisResult.model_validate(raw_data)
                    logger.debug(
                        f"LangExtract response validated: "
                        f"{len(validated_result.concepts)} concepts, "
                        f"{len(validated_result.themes)} themes"
                    )
                    return validated_result

                except ValidationError as ve:
                    logger.error(
                        f"LangExtract response validation failed: {ve}. "
                        f"Raw keys: {list(raw_data.keys())}"
                    )

                    # Fallback: try manual parsing with less strict validation
                    logger.warning(
                        "Attempting fallback parsing with less strict validation"
                    )

                    # Parse nested models with lenient error handling
                    concepts = []
                    for c in raw_data.get("concepts", []):
                        try:
                            concepts.append(SemanticConcept(**c))
                        except Exception as ce:
                            logger.warning(f"Skipping invalid concept: {ce}")

                    themes = []
                    for t in raw_data.get("themes", []):
                        try:
                            themes.append(SemanticTheme(**t))
                        except Exception as te:
                            logger.warning(f"Skipping invalid theme: {te}")

                    domains = []
                    for d in raw_data.get("domains", []):
                        try:
                            domains.append(SemanticDomain(**d))
                        except Exception as de:
                            logger.warning(f"Skipping invalid domain: {de}")

                    patterns = []
                    for p in raw_data.get("patterns", []):
                        try:
                            patterns.append(SemanticPattern(**p))
                        except Exception as pe:
                            logger.warning(f"Skipping invalid pattern: {pe}")

                    # Return partially validated result
                    return SemanticAnalysisResult(
                        concepts=concepts,
                        themes=themes,
                        domains=domains,
                        patterns=patterns,
                        language=raw_data.get("language", "en"),
                        processing_time_ms=raw_data.get("processing_time_ms"),
                        metadata=raw_data.get("metadata", {}),
                    )

            except ValidationError as ve:
                logger.error(
                    f"LangExtract validation failed completely: {ve}", exc_info=True
                )
                raise LangextractError(f"Response validation failed: {ve}")
            except Exception as e:
                logger.error(f"Failed to parse response: {e}", exc_info=True)
                raise LangextractError(f"Failed to parse response: {e}")

        elif response.status_code == 422:
            # Validation error
            error_data = response.json()
            raise LangextractValidationError(
                f"Request validation failed: {error_data}",
                validation_errors=error_data.get("detail", []),
            )

        elif response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise LangextractRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        elif response.status_code == 503:
            # Service unavailable
            raise LangextractUnavailableError(
                "Langextract service is temporarily unavailable"
            )

        elif 500 <= response.status_code < 600:
            # Server error
            error_data = response.json() if response.content else {}
            raise LangextractServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
                response_data=error_data,
            )

        else:
            # Other error
            raise LangextractError(
                f"Unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_health(self) -> Dict[str, Any]:
        """
        Check health of langextract service.

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

            return {
                "healthy": is_healthy,
                "status_code": response.status_code,
                "response_time_ms": duration_ms,
                "last_check": self._last_health_check.isoformat(),
            }

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
