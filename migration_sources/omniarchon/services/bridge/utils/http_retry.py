"""
HTTP Retry Logic with Exponential Backoff

Provides reusable retry utilities for HTTP clients across all services.
Implements exponential backoff retry logic as specified in CLAUDE.md:
- 3 retries max
- Exponential backoff: 1s → 2s → 4s
- Retries on transient failures (network errors, 5xx responses)
- Does NOT retry on 4xx client errors
- Thread-safe implementation

Usage:
    # As a decorator
    @with_retry(max_attempts=3, backoff_delays=[1.0, 2.0, 4.0])
    async def make_request():
        return await httpx_client.get(url)

    # As a context manager / wrapper
    result = await retry_async(
        httpx_client.get,
        url,
        max_attempts=3,
        backoff_delays=[1.0, 2.0, 4.0]
    )
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configuration (matches CLAUDE.md spec)
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_DELAYS = [1.0, 2.0, 4.0]  # Exponential: 1s → 2s → 4s

# HTTP status codes that should trigger retries
RETRYABLE_STATUS_CODES: Set[int] = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# HTTP status codes that should NOT trigger retries (client errors)
NON_RETRYABLE_STATUS_CODES: Set[int] = {
    400,  # Bad Request
    401,  # Unauthorized
    403,  # Forbidden
    404,  # Not Found
    405,  # Method Not Allowed
    422,  # Unprocessable Entity
}

# Exception types that should trigger retries (transient failures)
RETRYABLE_EXCEPTIONS: tuple = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        last_exception: Optional[Exception] = None,
        attempts: int = 0,
        **kwargs,
    ):
        super().__init__(message)
        self.message = message
        self.last_exception = last_exception
        self.attempts = attempts
        self.details = kwargs


class RetryMetrics:
    """Thread-safe metrics tracking for retry operations."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.total_retries = 0
        self.retries_by_reason: Dict[str, int] = {}
        self.total_delay_seconds = 0.0

    async def record_attempt(self, success: bool, retry_count: int, reason: str = ""):
        """Record a retry attempt."""
        async with self._lock:
            self.total_attempts += 1
            if success:
                self.successful_attempts += 1
            else:
                self.failed_attempts += 1

            if retry_count > 0:
                self.total_retries += retry_count
                if reason:
                    self.retries_by_reason[reason] = (
                        self.retries_by_reason.get(reason, 0) + 1
                    )

    async def record_delay(self, delay_seconds: float):
        """Record retry delay."""
        async with self._lock:
            self.total_delay_seconds += delay_seconds

    async def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        async with self._lock:
            return {
                "total_attempts": self.total_attempts,
                "successful_attempts": self.successful_attempts,
                "failed_attempts": self.failed_attempts,
                "total_retries": self.total_retries,
                "retries_by_reason": dict(self.retries_by_reason),
                "total_delay_seconds": self.total_delay_seconds,
                "success_rate": (
                    self.successful_attempts / self.total_attempts
                    if self.total_attempts > 0
                    else 0.0
                ),
            }


# Global metrics instance
_global_metrics = RetryMetrics()


def should_retry_status_code(status_code: int):
    """
    Determine if a status code should trigger a retry.

    Args:
        status_code: HTTP status code

    Returns:
        True if the request should be retried, False otherwise
    """
    # Don't retry client errors (4xx except specific cases)
    if status_code in NON_RETRYABLE_STATUS_CODES:
        return False

    # Retry on transient failures (5xx, 408, 429)
    return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def should_retry_exception(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.

    Args:
        exception: Exception that occurred

    Returns:
        True if the request should be retried, False otherwise
    """
    # Retry on transient network/connection errors
    return isinstance(exception, RETRYABLE_EXCEPTIONS)


async def retry_async(
    func: Callable[..., Any],
    *args,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_delays: Optional[List[float]] = None,
    retryable_status_codes: Optional[Set[int]] = None,
    retryable_exceptions: Optional[tuple] = None,
    logger_instance: Optional[logging.Logger] = None,
    operation_name: str = "HTTP request",
    **kwargs,
) -> Any:
    """
    Execute an async function with retry logic and exponential backoff.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts (default: 3)
        backoff_delays: List of delay seconds between retries (default: [1.0, 2.0, 4.0])
        retryable_status_codes: Set of HTTP status codes to retry (default: RETRYABLE_STATUS_CODES)
        retryable_exceptions: Tuple of exception types to retry (default: RETRYABLE_EXCEPTIONS)
        logger_instance: Logger to use (default: module logger)
        operation_name: Name of operation for logging
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function execution

    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
        Exception: If a non-retryable error occurs
    """
    if backoff_delays is None:
        backoff_delays = DEFAULT_BACKOFF_DELAYS
    if retryable_status_codes is None:
        retryable_status_codes = RETRYABLE_STATUS_CODES
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS
    if logger_instance is None:
        logger_instance = logger

    last_exception: Optional[Exception] = None
    retry_count = 0

    for attempt in range(max_attempts):
        try:
            start_time = time.perf_counter()

            # Execute the function
            result = await func(*args, **kwargs)

            # Record success
            duration_ms = (time.perf_counter() - start_time) * 1000
            if attempt > 0:
                logger_instance.info(
                    f"{operation_name} succeeded after {attempt} retries "
                    f"(duration: {duration_ms:.2f}ms)"
                )
                await _global_metrics.record_attempt(
                    success=True, retry_count=retry_count, reason="eventual_success"
                )
            else:
                await _global_metrics.record_attempt(
                    success=True, retry_count=0, reason=""
                )

            # Check if result is an HTTP response that needs retry
            if isinstance(result, httpx.Response):
                if should_retry_status_code(result.status_code):
                    if attempt < max_attempts - 1:
                        # Get delay for this attempt
                        delay = (
                            backoff_delays[attempt]
                            if attempt < len(backoff_delays)
                            else backoff_delays[-1]
                        )

                        logger_instance.warning(
                            f"{operation_name} returned retryable status {result.status_code} "
                            f"(attempt {attempt + 1}/{max_attempts}). "
                            f"Retrying in {delay}s..."
                        )

                        await asyncio.sleep(delay)
                        await _global_metrics.record_delay(delay)
                        retry_count += 1
                        continue
                    else:
                        # Max attempts reached with retryable status code
                        raise RetryExhaustedError(
                            f"{operation_name} failed after {max_attempts} attempts "
                            f"(final status: {result.status_code})",
                            attempts=max_attempts,
                            status_code=result.status_code,
                        )

            # Success!
            return result

        except retryable_exceptions as e:
            last_exception = e
            retry_count += 1

            if attempt < max_attempts - 1:
                # Get delay for this attempt
                delay = (
                    backoff_delays[attempt]
                    if attempt < len(backoff_delays)
                    else backoff_delays[-1]
                )

                logger_instance.warning(
                    f"{operation_name} failed with {type(e).__name__}: {e} "
                    f"(attempt {attempt + 1}/{max_attempts}). "
                    f"Retrying in {delay}s..."
                )

                await asyncio.sleep(delay)
                await _global_metrics.record_delay(delay)
                continue
            else:
                # Max attempts reached
                logger_instance.error(
                    f"{operation_name} failed after {max_attempts} attempts: {e}"
                )
                await _global_metrics.record_attempt(
                    success=False,
                    retry_count=retry_count,
                    reason=type(e).__name__,
                )
                raise RetryExhaustedError(
                    f"{operation_name} failed after {max_attempts} attempts",
                    last_exception=e,
                    attempts=max_attempts,
                )

        except httpx.HTTPStatusError as e:
            # HTTP status error (4xx/5xx) - check if retryable
            if should_retry_status_code(e.response.status_code):
                last_exception = e
                retry_count += 1

                if attempt < max_attempts - 1:
                    delay = (
                        backoff_delays[attempt]
                        if attempt < len(backoff_delays)
                        else backoff_delays[-1]
                    )

                    logger_instance.warning(
                        f"{operation_name} failed with status {e.response.status_code} "
                        f"(attempt {attempt + 1}/{max_attempts}). "
                        f"Retrying in {delay}s..."
                    )

                    await asyncio.sleep(delay)
                    await _global_metrics.record_delay(delay)
                    continue
                else:
                    # Max attempts reached
                    logger_instance.error(
                        f"{operation_name} failed after {max_attempts} attempts "
                        f"with status {e.response.status_code}"
                    )
                    await _global_metrics.record_attempt(
                        success=False,
                        retry_count=retry_count,
                        reason=f"status_{e.response.status_code}",
                    )
                    raise RetryExhaustedError(
                        f"{operation_name} failed after {max_attempts} attempts",
                        last_exception=e,
                        attempts=max_attempts,
                        status_code=e.response.status_code,
                    )
            else:
                # Non-retryable status code (4xx client error)
                logger_instance.error(
                    f"{operation_name} failed with non-retryable status "
                    f"{e.response.status_code}: {e}"
                )
                await _global_metrics.record_attempt(
                    success=False,
                    retry_count=0,
                    reason=f"non_retryable_status_{e.response.status_code}",
                )
                raise

        except Exception as e:
            # Non-retryable exception
            logger_instance.error(
                f"{operation_name} failed with non-retryable error: {type(e).__name__}: {e}"
            )
            await _global_metrics.record_attempt(
                success=False, retry_count=0, reason=f"non_retryable_{type(e).__name__}"
            )
            raise

    # Should never reach here, but just in case
    if last_exception:
        raise RetryExhaustedError(
            f"{operation_name} failed after {max_attempts} attempts",
            last_exception=last_exception,
            attempts=max_attempts,
        )

    raise RetryExhaustedError(
        f"{operation_name} failed after {max_attempts} attempts",
        attempts=max_attempts,
    )


def with_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_delays: Optional[List[float]] = None,
    retryable_status_codes: Optional[Set[int]] = None,
    retryable_exceptions: Optional[tuple] = None,
    operation_name: Optional[str] = None,
):
    """
    Decorator for adding retry logic to async functions.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_delays: List of delay seconds between retries (default: [1.0, 2.0, 4.0])
        retryable_status_codes: Set of HTTP status codes to retry
        retryable_exceptions: Tuple of exception types to retry
        operation_name: Name of operation for logging (default: function name)

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(max_attempts=3, backoff_delays=[1.0, 2.0, 4.0])
        async def fetch_data(url: str):
            async with httpx.AsyncClient() as client:
                return await client.get(url)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            return await retry_async(
                func,
                *args,
                max_attempts=max_attempts,
                backoff_delays=backoff_delays,
                retryable_status_codes=retryable_status_codes,
                retryable_exceptions=retryable_exceptions,
                operation_name=op_name,
                **kwargs,
            )

        return wrapper

    return decorator


async def get_retry_metrics() -> Dict[str, Any]:
    """
    Get global retry metrics.

    Returns:
        Dictionary with retry statistics
    """
    return await _global_metrics.get_metrics()


def reset_retry_metrics():
    """Reset global retry metrics."""
    global _global_metrics
    _global_metrics = RetryMetrics()


# Convenience wrapper for httpx.AsyncClient methods
class RetryableHTTPClient:
    """
    Wrapper around httpx.AsyncClient that adds retry logic to all HTTP methods.

    Usage:
        async with RetryableHTTPClient(
            timeout=30.0,
            max_attempts=3,
            backoff_delays=[1.0, 2.0, 4.0]
        ) as client:
            response = await client.get("https://api.example.com/data")
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_delays: Optional[List[float]] = None,
        **httpx_kwargs,
    ):
        """
        Initialize retryable HTTP client.

        Args:
            timeout: Request timeout in seconds
            max_connections: Maximum total connections
            max_keepalive_connections: Maximum keepalive connections
            max_attempts: Maximum retry attempts
            backoff_delays: Backoff delays between retries
            **httpx_kwargs: Additional arguments for httpx.AsyncClient
        """
        self.max_attempts = max_attempts
        self.backoff_delays = backoff_delays or DEFAULT_BACKOFF_DELAYS

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
            **httpx_kwargs,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get(self, *args, **kwargs) -> httpx.Response:
        """GET request with retry logic."""
        return await retry_async(
            self.client.get,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name="GET request",
            **kwargs,
        )

    async def post(self, *args, **kwargs) -> httpx.Response:
        """POST request with retry logic."""
        return await retry_async(
            self.client.post,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name="POST request",
            **kwargs,
        )

    async def put(self, *args, **kwargs) -> httpx.Response:
        """PUT request with retry logic."""
        return await retry_async(
            self.client.put,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name="PUT request",
            **kwargs,
        )

    async def delete(self, *args, **kwargs) -> httpx.Response:
        """DELETE request with retry logic."""
        return await retry_async(
            self.client.delete,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name="DELETE request",
            **kwargs,
        )

    async def patch(self, *args, **kwargs) -> httpx.Response:
        """PATCH request with retry logic."""
        return await retry_async(
            self.client.patch,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name="PATCH request",
            **kwargs,
        )

    async def request(self, method: str, *args, **kwargs) -> httpx.Response:
        """Generic request with retry logic."""
        return await retry_async(
            self.client.request,
            method,
            *args,
            max_attempts=self.max_attempts,
            backoff_delays=self.backoff_delays,
            operation_name=f"{method} request",
            **kwargs,
        )
