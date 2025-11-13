"""
Centralized HTTP Client Manager for Archon

Provides centralized HTTP connection management with proper connection pooling,
retry logic, and resource cleanup to prevent connection pool exhaustion issues.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """HTTP client configuration"""

    timeout: float = 30.0
    max_keepalive_connections: int = 20
    max_connections: int = 100
    keepalive_expiry: float = 30.0
    retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 10.0


class CentralizedHttpClientManager:
    """
    Centralized HTTP client manager with proper connection pooling.

    Features:
    - Singleton pattern for global access
    - Connection pooling with configurable limits
    - Automatic retry logic with exponential backoff
    - Resource cleanup and lifecycle management
    - Circuit breaker integration
    - Connection health monitoring
    """

    def __init__(self, default_config: Optional[ClientConfig] = None):
        self.default_config = default_config or ClientConfig()
        self.clients: dict[str, httpx.AsyncClient] = {}
        self.client_configs: dict[str, ClientConfig] = {}
        self.client_stats: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._is_initialized = False

    async def initialize(self):
        """Initialize the client manager"""
        if self._is_initialized:
            return

        logger.info("Initializing centralized HTTP client manager")
        self._is_initialized = True

    async def get_client(
        self, service_name: str, config: Optional[ClientConfig] = None
    ) -> httpx.AsyncClient:
        """
        Get HTTP client for a service with proper configuration.

        Args:
            service_name: Unique service identifier
            config: Optional custom configuration

        Returns:
            Configured HTTP client instance
        """
        async with self._lock:
            if service_name not in self.clients:
                await self._create_client(service_name, config)
            return self.clients[service_name]

    async def _create_client(
        self, service_name: str, config: Optional[ClientConfig] = None
    ):
        """Create new HTTP client with proper configuration"""
        client_config = config or self.default_config
        self.client_configs[service_name] = client_config

        # Configure connection limits
        limits = httpx.Limits(
            max_keepalive_connections=client_config.max_keepalive_connections,
            max_connections=client_config.max_connections,
            keepalive_expiry=client_config.keepalive_expiry,
        )

        # Configure retry transport
        transport = httpx.AsyncHTTPTransport(
            limits=limits, retries=client_config.retries
        )

        # Create client
        client = httpx.AsyncClient(
            timeout=client_config.timeout, transport=transport, follow_redirects=True
        )

        self.clients[service_name] = client
        self.client_stats[service_name] = {
            "created_at": time.time(),
            "request_count": 0,
            "error_count": 0,
            "last_used": time.time(),
        }

        logger.info(f"Created HTTP client for service: {service_name}")

    @asynccontextmanager
    async def request_context(self, service_name: str, method: str, url: str, **kwargs):
        """
        Context manager for making HTTP requests with automatic retries and error handling.

        Args:
            service_name: Service identifier
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Yields:
            HTTP response object
        """
        client = await self.get_client(service_name)
        stats = self.client_stats[service_name]

        max_retries = self.client_configs[service_name].retries
        retry_delay = self.client_configs[service_name].retry_delay
        max_retry_delay = self.client_configs[service_name].max_retry_delay

        for attempt in range(max_retries + 1):
            try:
                stats["request_count"] += 1
                stats["last_used"] = time.time()

                response = await client.request(method, url, **kwargs)

                # Log slow requests
                request_time = kwargs.get("timeout", self.default_config.timeout)
                if (
                    hasattr(response, "elapsed")
                    and response.elapsed.total_seconds() > request_time * 0.8
                ):
                    logger.warning(
                        f"Slow request to {service_name}: {response.elapsed.total_seconds():.2f}s"
                    )

                yield response
                return

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.NetworkError,
            ) as e:
                stats["error_count"] += 1

                if attempt == max_retries:
                    logger.error(
                        f"Request to {service_name} failed after {max_retries + 1} attempts: {e}"
                    )
                    raise

                # Exponential backoff
                delay = min(retry_delay * (2**attempt), max_retry_delay)
                logger.warning(
                    f"Request to {service_name} failed (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {delay:.2f}s: {e}"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                stats["error_count"] += 1
                logger.error(f"Unexpected error in request to {service_name}: {e}")
                raise

    async def make_request(
        self, service_name: str, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with automatic retries.

        Args:
            service_name: Service identifier
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response object
        """
        async with self.request_context(
            service_name, method, url, **kwargs
        ) as response:
            return response

    async def get(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make GET request"""
        return await self.make_request(service_name, "GET", url, **kwargs)

    async def post(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make POST request"""
        return await self.make_request(service_name, "POST", url, **kwargs)

    async def put(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make PUT request"""
        return await self.make_request(service_name, "PUT", url, **kwargs)

    async def delete(self, service_name: str, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request"""
        return await self.make_request(service_name, "DELETE", url, **kwargs)

    async def close_client(self, service_name: str):
        """Close specific client"""
        async with self._lock:
            if service_name in self.clients:
                await self.clients[service_name].aclose()
                del self.clients[service_name]
                del self.client_stats[service_name]
                if service_name in self.client_configs:
                    del self.client_configs[service_name]
                logger.info(f"Closed HTTP client for service: {service_name}")

    async def close_all_clients(self):
        """Close all clients and cleanup resources"""
        async with self._lock:
            logger.info("Closing all HTTP clients")

            for service_name, client in self.clients.items():
                try:
                    await client.aclose()
                    logger.debug(f"Closed client for {service_name}")
                except Exception as e:
                    logger.warning(f"Error closing client for {service_name}: {e}")

            self.clients.clear()
            self.client_stats.clear()
            self.client_configs.clear()

        logger.info("All HTTP clients closed")

    def get_client_stats(self, service_name: Optional[str] = None) -> dict[str, Any]:
        """Get client statistics"""
        if service_name:
            return self.client_stats.get(service_name, {})
        return self.client_stats.copy()

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary of all clients"""
        current_time = time.time()
        summary = {
            "total_clients": len(self.clients),
            "total_requests": sum(
                stats["request_count"] for stats in self.client_stats.values()
            ),
            "total_errors": sum(
                stats["error_count"] for stats in self.client_stats.values()
            ),
            "clients": {},
        }

        for service_name, stats in self.client_stats.items():
            error_rate = stats["error_count"] / max(stats["request_count"], 1)
            time_since_last_use = current_time - stats["last_used"]

            summary["clients"][service_name] = {
                "request_count": stats["request_count"],
                "error_count": stats["error_count"],
                "error_rate": error_rate,
                "last_used_seconds_ago": time_since_last_use,
                "is_active": time_since_last_use
                < 300,  # Active if used in last 5 minutes
                "health_status": (
                    "healthy"
                    if error_rate < 0.1
                    else "degraded" if error_rate < 0.5 else "unhealthy"
                ),
            }

        return summary

    async def health_check(self) -> bool:
        """Perform health check on client manager"""
        try:
            # Check if clients are properly initialized
            if not self._is_initialized:
                return False

            # Check for excessive error rates
            for service_name, stats in self.client_stats.items():
                if stats["request_count"] > 10:  # Only check if there's meaningful data
                    error_rate = stats["error_count"] / stats["request_count"]
                    if error_rate > 0.5:  # More than 50% error rate
                        logger.warning(
                            f"High error rate for {service_name}: {error_rate:.2%}"
                        )
                        return False

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def cleanup_idle_clients(self, max_idle_time: float = 1800):
        """Cleanup clients that haven't been used recently"""
        current_time = time.time()
        clients_to_close = []

        for service_name, stats in self.client_stats.items():
            if current_time - stats["last_used"] > max_idle_time:
                clients_to_close.append(service_name)

        for service_name in clients_to_close:
            await self.close_client(service_name)
            logger.info(f"Closed idle client: {service_name}")


# Global instance
_http_client_manager: Optional[CentralizedHttpClientManager] = None


async def get_http_client_manager() -> CentralizedHttpClientManager:
    """Get or create global HTTP client manager"""
    global _http_client_manager
    if _http_client_manager is None:
        _http_client_manager = CentralizedHttpClientManager()
        await _http_client_manager.initialize()
    return _http_client_manager


async def cleanup_http_client_manager():
    """Cleanup global HTTP client manager"""
    global _http_client_manager
    if _http_client_manager:
        await _http_client_manager.close_all_clients()
        _http_client_manager = None


# Convenience functions for common HTTP operations
async def http_get(service_name: str, url: str, **kwargs) -> httpx.Response:
    """Make GET request using centralized client manager"""
    manager = await get_http_client_manager()
    return await manager.get(service_name, url, **kwargs)


async def http_post(service_name: str, url: str, **kwargs) -> httpx.Response:
    """Make POST request using centralized client manager"""
    manager = await get_http_client_manager()
    return await manager.post(service_name, url, **kwargs)


async def http_put(service_name: str, url: str, **kwargs) -> httpx.Response:
    """Make PUT request using centralized client manager"""
    manager = await get_http_client_manager()
    return await manager.put(service_name, url, **kwargs)


async def http_delete(service_name: str, url: str, **kwargs) -> httpx.Response:
    """Make DELETE request using centralized client manager"""
    manager = await get_http_client_manager()
    return await manager.delete(service_name, url, **kwargs)
