"""
HTTP Client Configuration with Connection Pooling

Provides optimized HTTP/2 connection pooling for the Bridge Service.
Implements Phase 1 performance optimizations from CLAUDE.md:
- Max connections: 100 total, 20 keepalive
- Keepalive expiry: 30s
- Timeouts: 5s connect, 10s read, 5s write
- Target: 30-50% latency reduction vs basic httpx clients
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class HTTPClientConfig:
    """HTTP client configuration with connection pooling and retry logic."""

    # Connection Pool Configuration (from CLAUDE.md Phase 1 targets)
    MAX_CONNECTIONS = int(os.getenv("HTTP_MAX_CONNECTIONS", "100"))
    MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("HTTP_MAX_KEEPALIVE", "20"))
    KEEPALIVE_EXPIRY = int(os.getenv("HTTP_KEEPALIVE_EXPIRY", "30"))  # seconds

    # Timeout Configuration
    CONNECT_TIMEOUT = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5.0"))  # seconds
    READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "10.0"))  # seconds
    WRITE_TIMEOUT = float(os.getenv("HTTP_WRITE_TIMEOUT", "5.0"))  # seconds
    POOL_TIMEOUT = float(os.getenv("HTTP_POOL_TIMEOUT", "5.0"))  # seconds

    # Retry Configuration (exponential backoff)
    MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR = float(os.getenv("HTTP_RETRY_BACKOFF", "1.0"))  # 1s, 2s, 4s

    @classmethod
    def create_pooled_client(
        cls,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        http2: bool = True,
    ) -> httpx.AsyncClient:
        """
        Create an httpx.AsyncClient with optimized connection pooling.

        Args:
            base_url: Optional base URL for the client
            timeout: Optional custom timeout (overrides defaults)
            http2: Enable HTTP/2 protocol (default: True)

        Returns:
            Configured httpx.AsyncClient with connection pooling

        Example:
            ```python
            client = HTTPClientConfig.create_pooled_client(
                base_url="http://archon-intelligence:8053"
            )
            try:
                response = await client.get("/health")
            finally:
                await client.aclose()
            ```
        """
        # Configure connection limits for pooling
        limits = httpx.Limits(
            max_connections=cls.MAX_CONNECTIONS,
            max_keepalive_connections=cls.MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=cls.KEEPALIVE_EXPIRY,
        )

        # Configure timeouts
        timeout_config = httpx.Timeout(
            connect=cls.CONNECT_TIMEOUT,
            read=cls.READ_TIMEOUT,
            write=cls.WRITE_TIMEOUT,
            pool=cls.POOL_TIMEOUT,
        )

        # Use custom timeout if provided
        if timeout is not None:
            timeout_config = httpx.Timeout(timeout)

        # Create client with pooling configuration
        client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_config,
            limits=limits,
            http2=http2,
            follow_redirects=True,
        )

        logger.info(
            f"Created pooled HTTP client | "
            f"max_connections={cls.MAX_CONNECTIONS} | "
            f"keepalive={cls.MAX_KEEPALIVE_CONNECTIONS} | "
            f"keepalive_expiry={cls.KEEPALIVE_EXPIRY}s | "
            f"http2={http2} | "
            f"base_url={base_url}"
        )

        return client

    @classmethod
    def get_retry_delays(cls) -> list[float]:
        """
        Get exponential backoff retry delays.

        Returns:
            List of retry delays in seconds (e.g., [1.0, 2.0, 4.0])
        """
        delays = []
        for i in range(cls.MAX_RETRIES):
            delay = cls.RETRY_BACKOFF_FACTOR * (2**i)
            delays.append(delay)
        return delays

    @classmethod
    def log_config(cls):
        """Log current HTTP client configuration."""
        logger.info("=" * 60)
        logger.info("HTTP Client Configuration (Phase 1 Performance)")
        logger.info("=" * 60)
        logger.info(f"Connection Pool:")
        logger.info(f"  - Max Connections: {cls.MAX_CONNECTIONS}")
        logger.info(f"  - Max Keepalive: {cls.MAX_KEEPALIVE_CONNECTIONS}")
        logger.info(f"  - Keepalive Expiry: {cls.KEEPALIVE_EXPIRY}s")
        logger.info(f"Timeouts:")
        logger.info(f"  - Connect: {cls.CONNECT_TIMEOUT}s")
        logger.info(f"  - Read: {cls.READ_TIMEOUT}s")
        logger.info(f"  - Write: {cls.WRITE_TIMEOUT}s")
        logger.info(f"  - Pool: {cls.POOL_TIMEOUT}s")
        logger.info(f"Retry Policy:")
        logger.info(f"  - Max Retries: {cls.MAX_RETRIES}")
        logger.info(f"  - Backoff Factor: {cls.RETRY_BACKOFF_FACTOR}s")
        logger.info(f"  - Retry Delays: {cls.get_retry_delays()}")
        logger.info("=" * 60)


# Singleton pattern for shared client instances (optional optimization)
_shared_clients: dict[str, httpx.AsyncClient] = {}


def get_shared_client(service_name: str, base_url: str) -> httpx.AsyncClient:
    """
    Get or create a shared pooled HTTP client for a service.

    This is useful for services that make multiple calls to the same endpoint
    and want to reuse the same connection pool.

    Args:
        service_name: Unique identifier for the service (e.g., "intelligence")
        base_url: Base URL for the service

    Returns:
        Shared httpx.AsyncClient instance

    Example:
        ```python
        # Multiple calls reuse the same connection pool
        client = get_shared_client("intelligence", "http://archon-intelligence:8053")
        response1 = await client.get("/health")
        response2 = await client.post("/assess/code", json=data)
        ```
    """
    if service_name not in _shared_clients:
        _shared_clients[service_name] = HTTPClientConfig.create_pooled_client(
            base_url=base_url
        )
        logger.info(f"Created shared HTTP client for service: {service_name}")
    return _shared_clients[service_name]


async def close_all_shared_clients():
    """
    Close all shared HTTP clients.

    Should be called during application shutdown to properly close connections.
    """
    for service_name, client in _shared_clients.items():
        await client.aclose()
        logger.info(f"Closed shared HTTP client for service: {service_name}")
    _shared_clients.clear()
