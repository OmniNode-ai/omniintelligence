"""
HTTP Client Configuration for Intelligence Service

Centralized configuration for HTTP connection pooling, timeout settings, and retry logic.
All HTTP clients should use these settings for consistent performance.

Retry Logic:
- 3 retries max (configurable)
- Exponential backoff: 1s → 2s → 4s (configurable)
- Retries on transient failures (network errors, 5xx responses)
- Does NOT retry on 4xx client errors
- Thread-safe implementation with metrics tracking
"""

import os
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from src.infrastructure.http_retry import RetryableHTTPClient


@dataclass
# NOTE: correlation_id support enabled for tracing
class HTTPClientConfig:
    """Configuration for HTTP client connection pooling, timeouts, and retry logic"""

    # Connection pool settings
    max_connections: int
    max_keepalive_connections: int

    # Timeout settings (seconds)
    default_timeout: float
    connect_timeout: float
    read_timeout: float
    write_timeout: float

    # Retry settings
    max_retries: int
    retry_backoff_delays: List[float]

    @classmethod
    def from_env(cls, prefix: str = "HTTP_CLIENT") -> "HTTPClientConfig":
        """
        Create configuration from environment variables.

        Args:
            prefix: Environment variable prefix (default: HTTP_CLIENT)

        Environment Variables:
            {PREFIX}_MAX_CONNECTIONS: Maximum total connections (default: 100)
            {PREFIX}_MAX_KEEPALIVE_CONNECTIONS: Maximum keepalive connections (default: 20)
            {PREFIX}_DEFAULT_TIMEOUT: Default timeout in seconds (default: 30.0)
            {PREFIX}_CONNECT_TIMEOUT: Connect timeout in seconds (default: 10.0)
            {PREFIX}_READ_TIMEOUT: Read timeout in seconds (default: 30.0)
            {PREFIX}_WRITE_TIMEOUT: Write timeout in seconds (default: 5.0)
            {PREFIX}_MAX_RETRIES: Maximum retry attempts (default: 3)
            {PREFIX}_RETRY_BACKOFF_DELAYS: Comma-separated retry delays in seconds (default: "1.0,2.0,4.0")

        Returns:
            HTTPClientConfig instance
        """
        # Parse backoff delays from comma-separated string
        backoff_delays_str = os.getenv(f"{prefix}_RETRY_BACKOFF_DELAYS", "1.0,2.0,4.0")
        retry_backoff_delays = [
            float(delay.strip()) for delay in backoff_delays_str.split(",")
        ]

        return cls(
            max_connections=int(os.getenv(f"{prefix}_MAX_CONNECTIONS", "100")),
            max_keepalive_connections=int(
                os.getenv(f"{prefix}_MAX_KEEPALIVE_CONNECTIONS", "20")
            ),
            default_timeout=float(os.getenv(f"{prefix}_DEFAULT_TIMEOUT", "30.0")),
            connect_timeout=float(os.getenv(f"{prefix}_CONNECT_TIMEOUT", "10.0")),
            read_timeout=float(os.getenv(f"{prefix}_READ_TIMEOUT", "30.0")),
            write_timeout=float(os.getenv(f"{prefix}_WRITE_TIMEOUT", "5.0")),
            max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "3")),
            retry_backoff_delays=retry_backoff_delays,
        )

    def create_httpx_client(
        self,
        timeout_override: Optional[float] = None,
        max_connections_override: Optional[int] = None,
        max_keepalive_override: Optional[int] = None,
    ) -> httpx.AsyncClient:
        """
        Create configured httpx AsyncClient with connection pooling (without retry logic).

        Note: For clients with automatic retry logic, use create_retryable_client() instead.

        Args:
            timeout_override: Override default timeout (seconds)
            max_connections_override: Override max connections
            max_keepalive_override: Override max keepalive connections

        Returns:
            Configured httpx.AsyncClient with connection pooling
        """
        timeout = timeout_override or self.default_timeout
        max_conns = max_connections_override or self.max_connections
        max_keepalive = max_keepalive_override or self.max_keepalive_connections

        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=timeout,
                connect=self.connect_timeout,
                read=self.read_timeout,
                write=self.write_timeout,
            ),
            limits=httpx.Limits(
                max_connections=max_conns,
                max_keepalive_connections=max_keepalive,
            ),
        )

    def create_retryable_client(
        self,
        timeout_override: Optional[float] = None,
        max_connections_override: Optional[int] = None,
        max_keepalive_override: Optional[int] = None,
        max_retries_override: Optional[int] = None,
        backoff_delays_override: Optional[List[float]] = None,
    ) -> RetryableHTTPClient:
        """
        Create HTTP client with automatic retry logic and exponential backoff.

        This is the RECOMMENDED method for creating HTTP clients in production.
        All HTTP methods (GET, POST, etc.) will automatically retry on transient failures.

        Args:
            timeout_override: Override default timeout (seconds)
            max_connections_override: Override max connections
            max_keepalive_override: Override max keepalive connections
            max_retries_override: Override max retry attempts
            backoff_delays_override: Override backoff delays

        Returns:
            RetryableHTTPClient with automatic retry logic

        Example:
            config = HTTPClientConfig.from_env()
            async with config.create_retryable_client() as client:
                response = await client.get("https://api.example.com/data")
                # Automatically retries on failures
        """
        timeout = timeout_override or self.default_timeout
        max_conns = max_connections_override or self.max_connections
        max_keepalive = max_keepalive_override or self.max_keepalive_connections
        max_retries = max_retries_override or self.max_retries
        backoff_delays = backoff_delays_override or self.retry_backoff_delays

        return RetryableHTTPClient(
            timeout=timeout,
            max_connections=max_conns,
            max_keepalive_connections=max_keepalive,
            max_attempts=max_retries,
            backoff_delays=backoff_delays,
        )


# Global configuration instances
DEFAULT_CONFIG = HTTPClientConfig.from_env("HTTP_CLIENT")
SEARCH_SERVICE_CONFIG = HTTPClientConfig.from_env("SEARCH_SERVICE_HTTP_CLIENT")


# Pre-configured client creation functions
def create_default_client(
    timeout_override: Optional[float] = None,
) -> httpx.AsyncClient:
    """
    Create HTTP client with default configuration (without retry logic).

    Note: For production use, prefer create_default_retryable_client() for automatic retry support.
    """
    return DEFAULT_CONFIG.create_httpx_client(timeout_override=timeout_override)


def create_default_retryable_client(
    timeout_override: Optional[float] = None,
    max_retries_override: Optional[int] = None,
) -> RetryableHTTPClient:
    """
    Create HTTP client with retry logic and default configuration.

    RECOMMENDED for production use - automatically retries on transient failures.

    Args:
        timeout_override: Override default timeout (seconds)
        max_retries_override: Override max retry attempts

    Returns:
        RetryableHTTPClient with automatic retry logic
    """
    return DEFAULT_CONFIG.create_retryable_client(
        timeout_override=timeout_override,
        max_retries_override=max_retries_override,
    )


def create_search_service_client(
    timeout_override: Optional[float] = None,
) -> httpx.AsyncClient:
    """
    Create HTTP client for search service with optimized settings (without retry logic).

    Note: For production use, prefer create_search_service_retryable_client() for automatic retry support.
    """
    return SEARCH_SERVICE_CONFIG.create_httpx_client(timeout_override=timeout_override)


def create_search_service_retryable_client(
    timeout_override: Optional[float] = None,
    max_retries_override: Optional[int] = None,
) -> RetryableHTTPClient:
    """
    Create HTTP client for search service with retry logic and optimized settings.

    RECOMMENDED for production use - automatically retries on transient failures.

    Args:
        timeout_override: Override default timeout (seconds)
        max_retries_override: Override max retry attempts

    Returns:
        RetryableHTTPClient with automatic retry logic
    """
    return SEARCH_SERVICE_CONFIG.create_retryable_client(
        timeout_override=timeout_override,
        max_retries_override=max_retries_override,
    )
