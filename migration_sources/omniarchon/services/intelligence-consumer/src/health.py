"""
Health check HTTP server for consumer service.

Provides health and readiness endpoints for Kubernetes/Docker
health probes.
"""

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import structlog
from aiohttp import web

from .config import get_config

logger = structlog.get_logger(__name__)


class HealthCheckServer:
    """HTTP server for health and readiness checks."""

    def __init__(
        self,
        consumer_health_check: Callable[[], Awaitable[bool]],
        intelligence_health_check: Callable[[], Awaitable[bool]],
        get_consumer_lag: Callable[[], Awaitable[Dict[str, int]]],
        get_error_stats: Callable[[], Dict[str, Any]],
        circuit_state_check: Callable[[], str],
        get_invalid_event_stats: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """
        Initialize health check server.

        Args:
            consumer_health_check: Async function to check consumer health
            intelligence_health_check: Async function to check intelligence service health
            get_consumer_lag: Async function to get consumer lag
            get_error_stats: Function to get error handler stats
            circuit_state_check: Function to get circuit breaker state
            get_invalid_event_stats: Optional function to get invalid event stats
        """
        self.config = get_config()
        self.consumer_health_check = consumer_health_check
        self.intelligence_health_check = intelligence_health_check
        self.get_consumer_lag = get_consumer_lag
        self.get_error_stats = get_error_stats
        self.circuit_state_check = circuit_state_check
        self.get_invalid_event_stats = get_invalid_event_stats

        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        self.start_time = datetime.utcnow()

        self.logger = logger.bind(
            component="health_server", port=self.config.health_check_port
        )

    async def start(self) -> None:
        """Start health check HTTP server."""
        self.app = web.Application()

        # Register routes
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/ready", self.readiness_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)

        # Start server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "0.0.0.0", self.config.health_check_port)

        await self.site.start()

        self.logger.info("health_server_started", port=self.config.health_check_port)

    async def stop(self) -> None:
        """Stop health check HTTP server."""
        self.logger.info("stopping_health_server")

        if self.runner:
            await self.runner.cleanup()

        self.logger.info("health_server_stopped")

    async def health_handler(self, request: web.Request) -> web.Response:
        """
        Health check endpoint.

        Returns 200 if service is alive (basic liveness check).
        """
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

        return web.json_response(
            {
                "status": "healthy",
                "service": "intelligence-consumer",
                "uptime_seconds": uptime_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def readiness_handler(self, request: web.Request) -> web.Response:
        """
        Readiness check endpoint.

        Returns 200 if service is ready to process messages.
        Checks consumer connection, intelligence service, and circuit breaker.
        """
        # Check consumer health
        consumer_healthy = await self.consumer_health_check()

        # Check intelligence service health
        intelligence_healthy = await self.intelligence_health_check()

        # Check circuit breaker state
        circuit_state = self.circuit_state_check()
        circuit_healthy = circuit_state != "open"

        # Overall readiness
        ready = consumer_healthy and intelligence_healthy and circuit_healthy

        status_code = 200 if ready else 503

        response_data = {
            "ready": ready,
            "checks": {
                "consumer": consumer_healthy,
                "intelligence_service": intelligence_healthy,
                "circuit_breaker": {"healthy": circuit_healthy, "state": circuit_state},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return web.json_response(response_data, status=status_code)

    async def metrics_handler(self, request: web.Request) -> web.Response:
        """
        Metrics endpoint.

        Returns service metrics including consumer lag, error stats, and invalid event stats.
        """
        # Get consumer lag
        consumer_lag = await self.get_consumer_lag()

        # Get error handler stats
        error_stats = self.get_error_stats()

        # Get invalid event stats (if available)
        invalid_event_stats = {}
        if self.get_invalid_event_stats:
            invalid_event_stats = self.get_invalid_event_stats()

        # Calculate uptime
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

        # Get circuit breaker state
        circuit_state = self.circuit_state_check()

        metrics_data = {
            "service": "intelligence-consumer",
            "uptime_seconds": uptime_seconds,
            "consumer": {
                "lag_by_partition": consumer_lag,
                "total_lag": sum(consumer_lag.values()),
                "partition_count": len(consumer_lag),
            },
            "errors": error_stats,
            "invalid_events": invalid_event_stats,
            "circuit_breaker": {"state": circuit_state},
            "timestamp": datetime.utcnow().isoformat(),
        }

        return web.json_response(metrics_data)


async def run_health_server(
    consumer_health_check: Callable[[], Awaitable[bool]],
    intelligence_health_check: Callable[[], Awaitable[bool]],
    get_consumer_lag: Callable[[], Awaitable[Dict[str, int]]],
    get_error_stats: Callable[[], Dict[str, Any]],
    circuit_state_check: Callable[[], str],
    get_invalid_event_stats: Optional[Callable[[], Dict[str, Any]]] = None,
) -> HealthCheckServer:
    """
    Run health check server.

    Args:
        consumer_health_check: Async function to check consumer health
        intelligence_health_check: Async function to check intelligence service health
        get_consumer_lag: Async function to get consumer lag
        get_error_stats: Function to get error handler stats
        circuit_state_check: Function to get circuit breaker state
        get_invalid_event_stats: Optional function to get invalid event stats

    Returns:
        Running HealthCheckServer instance
    """
    server = HealthCheckServer(
        consumer_health_check=consumer_health_check,
        intelligence_health_check=intelligence_health_check,
        get_consumer_lag=get_consumer_lag,
        get_error_stats=get_error_stats,
        circuit_state_check=circuit_state_check,
        get_invalid_event_stats=get_invalid_event_stats,
    )

    await server.start()

    return server
