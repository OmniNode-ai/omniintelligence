"""
HTTP Client Optimization Module

Provides optimized HTTP clients with connection pooling, circuit breakers,
retry logic, and performance monitoring for inter-service communication.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


@dataclass
class HTTPClientConfig:
    """HTTP client configuration for performance optimization"""

    # Connection Pool Settings
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    http2: bool = True

    # Timeout Settings
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    pool_timeout: float = 5.0

    # Retry Settings
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    retry_status_codes: List[int] = field(default_factory=lambda: [500, 502, 503, 504])

    # Circuit Breaker Settings
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0

    # Performance Settings
    enable_compression: bool = True
    enable_metrics: bool = True
    max_request_size_mb: int = 32


class HTTPCircuitBreaker:
    """Circuit breaker for HTTP requests"""

    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.success_count = 0  # For half-open state

    def is_available(self) -> bool:
        """Check if circuit breaker allows requests"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                self.success_count = 0
                return True
            return False

        # HALF_OPEN state
        return True

    def record_success(self):
        """Record successful request"""
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= 3:  # Require 3 successes to close
                self.state = "CLOSED"
                self.failure_count = 0

        elif self.state == "CLOSED":
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


@dataclass
class RequestMetrics:
    """HTTP request performance metrics"""

    url: str
    method: str
    status_code: int
    duration_ms: float
    retry_count: int
    timestamp: float


class OptimizedHTTPClient:
    """High-performance HTTP client with advanced features"""

    def __init__(self, config: HTTPClientConfig = None, service_name: str = "archon"):
        self.config = config or HTTPClientConfig()
        self.service_name = service_name
        self.client = None
        self.circuit_breaker = HTTPCircuitBreaker(
            self.config.circuit_breaker_threshold, self.config.circuit_breaker_timeout
        )
        self.metrics: List[RequestMetrics] = []
        self._initialized = False

    async def initialize(self):
        """Initialize the HTTP client with optimized settings"""
        try:
            # Configure timeouts
            timeout = httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=self.config.write_timeout,
                pool=self.config.pool_timeout,
            )

            # Configure connection limits
            limits = httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
                keepalive_expiry=self.config.keepalive_expiry,
            )

            # Configure headers
            headers = {
                "User-Agent": f"{self.service_name}/1.0",
                "Connection": "keep-alive",
            }

            if self.config.enable_compression:
                headers["Accept-Encoding"] = "gzip, deflate"

            # Create optimized client
            self.client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                headers=headers,
                http2=self.config.http2,
                verify=True,
                trust_env=True,
            )

            self._initialized = True
            logger.info(f"Optimized HTTP client initialized for {self.service_name}")

        except Exception as e:
            logger.error(f"Failed to initialize HTTP client: {e}")
            raise

    async def request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request with circuit breaker and retry logic"""
        if not self._initialized:
            await self.initialize()

        if not self.circuit_breaker.is_available():
            raise HTTPException(
                status_code=503, detail=f"Circuit breaker open for {self.service_name}"
            )

        # Prepare request
        request_kwargs = {
            "method": method,
            "url": url,
            "params": params,
            "headers": headers or {},
            **kwargs,
        }

        if json_data is not None:
            request_kwargs["json"] = json_data

        if timeout:
            request_kwargs["timeout"] = timeout

        # Execute with retry logic
        last_exception = None
        start_time = time.time()

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self.client.request(**request_kwargs)

                # Check if response indicates success
                if response.status_code < 500:
                    self.circuit_breaker.record_success()

                    # Record metrics
                    if self.config.enable_metrics:
                        self._record_metrics(
                            url,
                            method,
                            response.status_code,
                            (time.time() - start_time) * 1000,
                            attempt,
                        )

                    return response

                else:
                    # Server error - treat as failure for circuit breaker
                    if (
                        response.status_code in self.config.retry_status_codes
                        and attempt < self.config.max_retries
                    ):
                        await asyncio.sleep(
                            self.config.retry_backoff_factor * (2**attempt)
                        )
                        continue
                    else:
                        self.circuit_breaker.record_failure()
                        if self.config.enable_metrics:
                            self._record_metrics(
                                url,
                                method,
                                response.status_code,
                                (time.time() - start_time) * 1000,
                                attempt,
                            )
                        return response

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_backoff_factor * (2**attempt))
                    continue

            except Exception as e:
                last_exception = e
                self.circuit_breaker.record_failure()
                break

        # All retries exhausted
        self.circuit_breaker.record_failure()
        if self.config.enable_metrics:
            self._record_metrics(
                url,
                method,
                0,
                (time.time() - start_time) * 1000,
                self.config.max_retries,
            )

        raise HTTPException(
            status_code=503,
            detail=f"Request failed after {self.config.max_retries + 1} attempts: {last_exception}",
        )

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request"""
        return await self.request("GET", url, **kwargs)

    async def post(
        self, url: str, json_data: Optional[Dict] = None, **kwargs
    ) -> httpx.Response:
        """POST request"""
        return await self.request("POST", url, json_data=json_data, **kwargs)

    async def put(
        self, url: str, json_data: Optional[Dict] = None, **kwargs
    ) -> httpx.Response:
        """PUT request"""
        return await self.request("PUT", url, json_data=json_data, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE request"""
        return await self.request("DELETE", url, **kwargs)

    def _record_metrics(
        self,
        url: str,
        method: str,
        status_code: int,
        duration_ms: float,
        retry_count: int,
    ):
        """Record request metrics"""
        metric = RequestMetrics(
            url=url,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            retry_count=retry_count,
            timestamp=time.time(),
        )

        self.metrics.append(metric)

        # Keep only last 1000 metrics to prevent memory issues
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        if not self.metrics:
            return {
                "total_requests": 0,
                "circuit_breaker_state": self.circuit_breaker.state,
                "average_response_time_ms": 0,
                "success_rate": 0,
            }

        total_requests = len(self.metrics)
        successful_requests = sum(1 for m in self.metrics if 200 <= m.status_code < 400)
        total_duration = sum(m.duration_ms for m in self.metrics)

        # Calculate metrics by URL
        url_metrics = {}
        for metric in self.metrics:
            if metric.url not in url_metrics:
                url_metrics[metric.url] = {"count": 0, "total_duration": 0, "errors": 0}

            url_metrics[metric.url]["count"] += 1
            url_metrics[metric.url]["total_duration"] += metric.duration_ms
            if metric.status_code >= 400:
                url_metrics[metric.url]["errors"] += 1

        # Process URL metrics
        for url, stats in url_metrics.items():
            stats["average_duration_ms"] = stats["total_duration"] / stats["count"]
            stats["error_rate"] = stats["errors"] / stats["count"]

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": (
                successful_requests / total_requests if total_requests > 0 else 0
            ),
            "average_response_time_ms": (
                total_duration / total_requests if total_requests > 0 else 0
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "url_metrics": url_metrics,
            "recent_errors": [
                {
                    "url": m.url,
                    "status_code": m.status_code,
                    "duration_ms": m.duration_ms,
                    "timestamp": m.timestamp,
                }
                for m in self.metrics[-10:]
                if m.status_code >= 400
            ],
        }

    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False


class ServiceHTTPClientManager:
    """Manager for HTTP clients to different services"""

    def __init__(self):
        self.clients: Dict[str, OptimizedHTTPClient] = {}
        self.service_urls: Dict[str, str] = {}

    def register_service(
        self, service_name: str, base_url: str, config: HTTPClientConfig = None
    ):
        """Register a service with its base URL"""
        self.service_urls[service_name] = base_url.rstrip("/")
        self.clients[service_name] = OptimizedHTTPClient(
            config=config or HTTPClientConfig(), service_name=service_name
        )

    async def get_client(self, service_name: str) -> OptimizedHTTPClient:
        """Get HTTP client for a service"""
        if service_name not in self.clients:
            raise ValueError(f"Service {service_name} not registered")

        client = self.clients[service_name]
        if not client._initialized:
            await client.initialize()

        return client

    async def call_service(
        self,
        service_name: str,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a call to a registered service"""
        if service_name not in self.service_urls:
            raise ValueError(f"Service {service_name} not registered")

        client = await self.get_client(service_name)
        url = f"{self.service_urls[service_name]}{endpoint}"

        response = await client.request(method, url, json_data=json_data, **kwargs)

        # Handle response
        if response.status_code >= 400:
            logger.error(
                f"Service call failed: {service_name}{endpoint} - {response.status_code}"
            )
            raise HTTPException(status_code=response.status_code, detail=response.text)

        try:
            return response.json()
        except json.JSONDecodeError:
            return {"response": response.text}

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all registered services"""
        return {
            service_name: client.get_performance_metrics()
            for service_name, client in self.clients.items()
            if client._initialized
        }

    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all registered services"""
        health_status = {}

        for service_name, base_url in self.service_urls.items():
            try:
                client = await self.get_client(service_name)
                response = await client.get(f"{base_url}/health", timeout=5.0)
                health_status[service_name] = 200 <= response.status_code < 300
            except Exception as e:
                logger.warning(f"Health check failed for {service_name}: {e}")
                health_status[service_name] = False

        return health_status

    async def close_all(self):
        """Close all HTTP clients"""
        for client in self.clients.values():
            await client.close()


# Global service manager
service_http_manager = ServiceHTTPClientManager()


def setup_service_clients():
    """Setup HTTP clients for all Archon services"""
    import os

    # Define service configurations
    services = {
        "archon-server": os.getenv("API_SERVICE_URL", "http://archon-server:8181"),
        "archon-intelligence": os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        ),
        "archon-bridge": os.getenv("BRIDGE_SERVICE_URL", "http://archon-bridge:8054"),
        "archon-search": os.getenv("SEARCH_SERVICE_URL", "http://archon-search:8055"),
        "archon-langextract": os.getenv(
            "LANGEXTRACT_SERVICE_URL", "http://archon-langextract:8156"
        ),
    }

    # Register services with optimized configurations
    for service_name, base_url in services.items():
        if base_url:
            # Create service-specific configuration
            config = HTTPClientConfig()

            # Adjust config based on service type
            if "intelligence" in service_name:
                config.read_timeout = 60.0  # Intelligence operations can take longer
                config.max_retries = 2
            elif "search" in service_name:
                config.read_timeout = 45.0  # Search operations can be heavy
                config.max_retries = 2
            elif "langextract" in service_name:
                config.read_timeout = 90.0  # Language extraction can be slow
                config.max_retries = 1

            service_http_manager.register_service(service_name, base_url, config)

    logger.info(f"Configured HTTP clients for {len(services)} services")


async def get_service_client(service_name: str) -> OptimizedHTTPClient:
    """Get HTTP client for a specific service"""
    return await service_http_manager.get_client(service_name)
