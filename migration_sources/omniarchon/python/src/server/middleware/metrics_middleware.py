"""
Production Monitoring Middleware for FastAPI Applications

This middleware provides comprehensive metrics collection for production monitoring
including response times, request counts, error rates, and system health metrics.
"""

import asyncio
import logging
import time
from typing import Any

import psutil
from fastapi import Request, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.exposition import choose_encoder
from starlette.middleware.base import BaseHTTPMiddleware

# Create metrics registry
REGISTRY = CollectorRegistry()

# Request metrics
REQUEST_COUNT = Counter(
    "archon_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code", "service"],
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "archon_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# Error metrics
ERROR_COUNT = Counter(
    "archon_http_errors_total",
    "Total number of HTTP errors",
    ["method", "endpoint", "status_code", "service"],
    registry=REGISTRY,
)

# Response size metrics
RESPONSE_SIZE = Histogram(
    "archon_http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint", "service"],
    registry=REGISTRY,
)

# System metrics
SYSTEM_CPU_USAGE = Gauge(
    "archon_system_cpu_usage_percent",
    "System CPU usage percentage",
    ["service"],
    registry=REGISTRY,
)

SYSTEM_MEMORY_USAGE = Gauge(
    "archon_system_memory_usage_bytes",
    "System memory usage in bytes",
    ["type", "service"],
    registry=REGISTRY,
)

SYSTEM_DISK_USAGE = Gauge(
    "archon_system_disk_usage_bytes",
    "System disk usage in bytes",
    ["type", "service"],
    registry=REGISTRY,
)

# Database connection metrics
DB_CONNECTIONS = Gauge(
    "archon_database_connections",
    "Number of active database connections",
    ["service"],
    registry=REGISTRY,
)

# Application-specific metrics
ACTIVE_WEBSOCKETS = Gauge(
    "archon_websocket_connections",
    "Number of active WebSocket connections",
    ["service"],
    registry=REGISTRY,
)

BACKGROUND_TASKS = Gauge(
    "archon_background_tasks",
    "Number of background tasks",
    ["status", "service"],
    registry=REGISTRY,
)

# Cache metrics
CACHE_HITS = Counter(
    "archon_cache_hits_total",
    "Total number of cache hits",
    ["cache_type", "service"],
    registry=REGISTRY,
)

CACHE_MISSES = Counter(
    "archon_cache_misses_total",
    "Total number of cache misses",
    ["cache_type", "service"],
    registry=REGISTRY,
)

# Custom business metrics
RAG_QUERIES = Counter(
    "archon_rag_queries_total",
    "Total number of RAG queries",
    ["query_type", "service"],
    registry=REGISTRY,
)

RAG_QUERY_DURATION = Histogram(
    "archon_rag_query_duration_seconds",
    "RAG query duration in seconds",
    ["query_type", "service"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

INTELLIGENCE_ANALYSIS = Counter(
    "archon_intelligence_analysis_total",
    "Total number of intelligence analyses",
    ["analysis_type", "service"],
    registry=REGISTRY,
)

logger = logging.getLogger(__name__)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect Prometheus metrics for FastAPI applications.

    Collects:
    - Request count and duration
    - Response size and status codes
    - Error rates and types
    - System resource usage
    - Application-specific metrics
    """

    def __init__(self, app, service_name: str = "archon-unknown"):
        super().__init__(app)
        self.service_name = service_name
        self._system_metrics_task = None
        self._start_system_metrics_collection()

    def _start_system_metrics_collection(self):
        """Start background system metrics collection."""
        try:
            # Create background task for system metrics
            loop = asyncio.get_event_loop()
            self._system_metrics_task = loop.create_task(self._collect_system_metrics())
        except Exception as e:
            logger.warning(f"Could not start system metrics collection: {e}")

    async def _collect_system_metrics(self):
        """Collect system metrics periodically."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                SYSTEM_CPU_USAGE.labels(service=self.service_name).set(cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                SYSTEM_MEMORY_USAGE.labels(type="used", service=self.service_name).set(
                    memory.used
                )
                SYSTEM_MEMORY_USAGE.labels(
                    type="available", service=self.service_name
                ).set(memory.available)
                SYSTEM_MEMORY_USAGE.labels(type="total", service=self.service_name).set(
                    memory.total
                )

                # Disk usage
                disk = psutil.disk_usage("/")
                SYSTEM_DISK_USAGE.labels(type="used", service=self.service_name).set(
                    disk.used
                )
                SYSTEM_DISK_USAGE.labels(type="free", service=self.service_name).set(
                    disk.free
                )
                SYSTEM_DISK_USAGE.labels(type="total", service=self.service_name).set(
                    disk.total
                )

                # Process-specific metrics
                process = psutil.Process()
                memory_info = process.memory_info()
                SYSTEM_MEMORY_USAGE.labels(
                    type="process_rss", service=self.service_name
                ).set(memory_info.rss)
                SYSTEM_MEMORY_USAGE.labels(
                    type="process_vms", service=self.service_name
                ).set(memory_info.vms)

                await asyncio.sleep(30)  # Collect every 30 seconds

            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()

        # Extract endpoint info
        method = request.method
        endpoint = request.url.path

        # Clean endpoint for consistent labeling
        endpoint = self._clean_endpoint(endpoint)

        try:
            # Process request
            response = await call_next(request)

            # Calculate metrics
            duration = time.time() - start_time
            status_code = str(response.status_code)

            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                service=self.service_name,
            ).inc()

            REQUEST_DURATION.labels(
                method=method, endpoint=endpoint, service=self.service_name
            ).observe(duration)

            # Record errors (4xx, 5xx)
            if response.status_code >= 400:
                ERROR_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    service=self.service_name,
                ).inc()

            # Try to get response size
            try:
                if (
                    hasattr(response, "headers")
                    and "content-length" in response.headers
                ):
                    response_size = int(response.headers["content-length"])
                    RESPONSE_SIZE.labels(
                        method=method, endpoint=endpoint, service=self.service_name
                    ).observe(response_size)
            except Exception:
                pass  # Response size not available

            return response

        except Exception as e:
            # Record exception as error
            duration = time.time() - start_time

            ERROR_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code="500",
                service=self.service_name,
            ).inc()

            REQUEST_DURATION.labels(
                method=method, endpoint=endpoint, service=self.service_name
            ).observe(duration)

            logger.error(f"Request error: {e}")
            raise

    def _clean_endpoint(self, endpoint: str) -> str:
        """Clean endpoint path for consistent labeling."""
        # Remove dynamic parts like UUIDs
        import re

        # Replace UUIDs with placeholder
        endpoint = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{id}",
            endpoint,
        )

        # Replace numeric IDs
        endpoint = re.sub(r"/\d+", "/{id}", endpoint)

        # Limit endpoint length
        if len(endpoint) > 100:
            endpoint = endpoint[:100] + "..."

        return endpoint


# Global metrics collection functions
def record_rag_query(query_type: str, duration: float, service_name: str = "archon"):
    """Record a RAG query metric."""
    RAG_QUERIES.labels(query_type=query_type, service=service_name).inc()
    RAG_QUERY_DURATION.labels(query_type=query_type, service=service_name).observe(
        duration
    )


def record_intelligence_analysis(analysis_type: str, service_name: str = "archon"):
    """Record an intelligence analysis metric."""
    INTELLIGENCE_ANALYSIS.labels(
        analysis_type=analysis_type, service=service_name
    ).inc()


def record_cache_hit(cache_type: str, service_name: str = "archon"):
    """Record a cache hit."""
    CACHE_HITS.labels(cache_type=cache_type, service=service_name).inc()


def record_cache_miss(cache_type: str, service_name: str = "archon"):
    """Record a cache miss."""
    CACHE_MISSES.labels(cache_type=cache_type, service=service_name).inc()


def set_websocket_connections(count: int, service_name: str = "archon"):
    """Set the number of active WebSocket connections."""
    ACTIVE_WEBSOCKETS.labels(service=service_name).set(count)


def set_background_tasks(status: str, count: int, service_name: str = "archon"):
    """Set the number of background tasks."""
    BACKGROUND_TASKS.labels(status=status, service=service_name).set(count)


def set_db_connections(count: int, service_name: str = "archon"):
    """Set the number of database connections."""
    DB_CONNECTIONS.labels(service=service_name).set(count)


# Metrics endpoint handler
def get_metrics():
    """Get Prometheus metrics in the expected format."""
    encoder, content_type = choose_encoder(None)
    return Response(content=encoder(REGISTRY), media_type=content_type)


# Health check with metrics
def get_health_status() -> dict[str, Any]:
    """Get comprehensive health status including metrics."""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Get process metrics
        process = psutil.Process()
        process_memory = process.memory_info()

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "metrics": {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used // (1024 * 1024),
                    "memory_available_mb": memory.available // (1024 * 1024),
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_free_gb": disk.free // (1024 * 1024 * 1024),
                },
                "process": {
                    "memory_rss_mb": process_memory.rss // (1024 * 1024),
                    "memory_vms_mb": process_memory.vms // (1024 * 1024),
                    "cpu_percent": process.cpu_percent(),
                },
            },
        }
    except Exception as e:
        return {"status": "error", "timestamp": time.time(), "error": str(e)}


# Intelligence-enhanced monitoring functions
def monitor_performance_trend(
    operation_name: str, duration: float, service_name: str = "archon"
):
    """
    Monitor performance trends with intelligence integration.
    This works with Archon's intelligence service for optimization insights.
    """
    # Record the metric
    REQUEST_DURATION.labels(
        method="CUSTOM", endpoint=f"/operations/{operation_name}", service=service_name
    ).observe(duration)

    # Additional intelligence context could be added here
    # For example, correlating with quality metrics or system load


def get_intelligent_health_insights() -> dict[str, Any]:
    """
    Get intelligent health insights by analyzing metrics patterns.
    This can integrate with Archon's intelligence services.
    """
    basic_health = get_health_status()

    # Add intelligent insights
    insights = []

    try:
        # CPU usage insights
        if basic_health["metrics"]["system"]["cpu_percent"] > 80:
            insights.append(
                {
                    "type": "performance",
                    "severity": "warning",
                    "message": "High CPU usage detected",
                    "recommendation": "Consider scaling or optimizing high-CPU operations",
                }
            )

        # Memory usage insights
        if basic_health["metrics"]["system"]["memory_percent"] > 85:
            insights.append(
                {
                    "type": "resource",
                    "severity": "warning",
                    "message": "High memory usage detected",
                    "recommendation": "Check for memory leaks or consider increasing memory allocation",
                }
            )

        # Disk space insights
        if basic_health["metrics"]["system"]["disk_percent"] > 90:
            insights.append(
                {
                    "type": "storage",
                    "severity": "critical",
                    "message": "Low disk space detected",
                    "recommendation": "Clean up logs or increase storage capacity",
                }
            )

        basic_health["intelligence"] = {
            "insights": insights,
            "analysis_timestamp": time.time(),
            "health_score": max(0, 100 - len(insights) * 10),  # Simple scoring
        }

    except Exception as e:
        logger.error(f"Error generating health insights: {e}")

    return basic_health
