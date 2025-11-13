"""
Monitoring and Observability for Hybrid Pattern Scoring System

This module provides comprehensive Prometheus metrics for monitoring:
- Langextract client performance and reliability
- Semantic cache effectiveness
- Hybrid scoring performance
- Pattern similarity distributions
- Circuit breaker and error handling
- Overall system health

Metrics are exposed for Prometheus scraping and used by Grafana dashboards
and AlertManager for real-time monitoring and alerting.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Optional
from uuid import UUID, uuid4

from prometheus_client import Counter, Gauge, Histogram, Info

logger = logging.getLogger(__name__)

# ============================================================================
# Langextract Client Metrics
# ============================================================================

langextract_requests_total = Counter(
    "langextract_requests_total",
    "Total number of langextract API requests",
    ["endpoint", "status"],
)

langextract_request_duration = Histogram(
    "langextract_request_duration_seconds",
    "Langextract API request duration in seconds",
    ["endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

langextract_request_size = Histogram(
    "langextract_request_size_bytes",
    "Size of langextract API requests in bytes",
    ["endpoint"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
)

langextract_response_size = Histogram(
    "langextract_response_size_bytes",
    "Size of langextract API responses in bytes",
    ["endpoint"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
)

langextract_errors_total = Counter(
    "langextract_errors_total",
    "Total number of langextract API errors",
    ["endpoint", "error_type"],
)

langextract_circuit_breaker_state = Gauge(
    "langextract_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["endpoint"],
)

langextract_circuit_breaker_failures = Counter(
    "langextract_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["endpoint"],
)

langextract_retry_attempts = Counter(
    "langextract_retry_attempts_total",
    "Total retry attempts for langextract requests",
    ["endpoint", "attempt"],
)

# ============================================================================
# Cache Metrics
# ============================================================================

cache_hit_total = Counter(
    "semantic_cache_hits_total", "Total number of semantic cache hits"
)

cache_miss_total = Counter(
    "semantic_cache_misses_total", "Total number of semantic cache misses"
)

cache_hit_rate = Gauge(
    "semantic_cache_hit_rate", "Current semantic cache hit rate (0.0-1.0)"
)

cache_size = Gauge(
    "semantic_cache_size_entries", "Current number of entries in semantic cache"
)

cache_evictions_total = Counter(
    "semantic_cache_evictions_total", "Total number of cache evictions"
)

cache_lookup_duration = Histogram(
    "semantic_cache_lookup_duration_seconds",
    "Cache lookup duration in seconds",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

cache_memory_usage = Gauge(
    "semantic_cache_memory_usage_bytes",
    "Estimated memory usage of semantic cache in bytes",
)

# ============================================================================
# Hybrid Scoring Metrics
# ============================================================================

hybrid_scoring_duration = Histogram(
    "hybrid_scoring_duration_seconds",
    "Hybrid scoring calculation duration in seconds",
    ["scoring_strategy"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0],
)

hybrid_scoring_requests_total = Counter(
    "hybrid_scoring_requests_total",
    "Total number of hybrid scoring requests",
    ["scoring_strategy", "status"],
)

pattern_similarity_score = Histogram(
    "pattern_similarity_score",
    "Distribution of pattern similarity scores",
    ["similarity_type"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

pattern_matching_candidates = Histogram(
    "pattern_matching_candidates_count",
    "Number of candidate patterns evaluated per matching request",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500],
)

pattern_matching_duration = Histogram(
    "pattern_matching_duration_seconds",
    "Total pattern matching operation duration",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ============================================================================
# Component-Specific Metrics
# ============================================================================

semantic_similarity_computation = Histogram(
    "semantic_similarity_computation_seconds",
    "Time spent computing semantic similarity",
    ["method"],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)

structural_similarity_computation = Histogram(
    "structural_similarity_computation_seconds",
    "Time spent computing structural similarity",
    ["method"],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)

weight_calculation_duration = Histogram(
    "weight_calculation_duration_seconds",
    "Time spent calculating dynamic weights",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

# ============================================================================
# System Health Metrics
# ============================================================================

pattern_learning_system_info = Info(
    "pattern_learning_system", "Pattern learning system version and configuration info"
)

active_pattern_learning_sessions = Gauge(
    "active_pattern_learning_sessions", "Number of active pattern learning sessions"
)

pattern_database_size = Gauge(
    "pattern_database_size_entries", "Total number of patterns in database"
)

last_successful_operation = Gauge(
    "last_successful_operation_timestamp",
    "Timestamp of last successful operation",
    ["operation_type"],
)

# ============================================================================
# Helper Functions and Decorators
# ============================================================================


# NOTE: correlation_id support enabled for tracing
def update_cache_hit_rate():
    """Update the cache hit rate gauge based on current counters."""
    try:
        hits = cache_hit_total._value.get()
        misses = cache_miss_total._value.get()
        total = hits + misses

        if total > 0:
            hit_rate = hits / total
            cache_hit_rate.set(hit_rate)
        else:
            cache_hit_rate.set(0.0)
    except Exception as e:
        logger.error(f"Error updating cache hit rate: {e}")


@contextmanager
def track_langextract_request(endpoint: str):
    """
    Context manager to track langextract API requests.

    Usage:
        with track_langextract_request('/extract'):
            result = await client.extract(...)
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        langextract_errors_total.labels(endpoint=endpoint, error_type=error_type).inc()
        raise
    finally:
        duration = time.time() - start_time
        langextract_request_duration.labels(endpoint=endpoint).observe(duration)
        langextract_requests_total.labels(endpoint=endpoint, status=status).inc()


@contextmanager
def track_hybrid_scoring(strategy: str = "default"):
    """
    Context manager to track hybrid scoring operations.

    Usage:
        with track_hybrid_scoring('weighted_average'):
            score = calculate_hybrid_score(...)
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        hybrid_scoring_duration.labels(scoring_strategy=strategy).observe(duration)
        hybrid_scoring_requests_total.labels(
            scoring_strategy=strategy, status=status
        ).inc()


@contextmanager
def track_cache_lookup():
    """
    Context manager to track cache lookup operations.

    Usage:
        with track_cache_lookup():
            result = cache.get(key)
    """
    start_time = time.time()

    try:
        yield
    finally:
        duration = time.time() - start_time
        cache_lookup_duration.observe(duration)


def record_cache_hit():
    """Record a cache hit and update the hit rate."""
    cache_hit_total.inc()
    update_cache_hit_rate()


def record_cache_miss():
    """Record a cache miss and update the hit rate."""
    cache_miss_total.inc()
    update_cache_hit_rate()


def record_pattern_similarity(similarity_type: str, score: float):
    """
    Record a pattern similarity score.

    Args:
        similarity_type: Type of similarity (semantic, structural, hybrid)
        score: Similarity score between 0.0 and 1.0
    """
    pattern_similarity_score.labels(similarity_type=similarity_type).observe(score)


def record_circuit_breaker_state(endpoint: str, state: str):
    """
    Record circuit breaker state.

    Args:
        endpoint: API endpoint
        state: State (closed=0, open=1, half_open=2)
    """
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    langextract_circuit_breaker_state.labels(endpoint=endpoint).set(
        state_map.get(state, 0)
    )


def record_circuit_breaker_failure(endpoint: str):
    """Record a circuit breaker failure."""
    langextract_circuit_breaker_failures.labels(endpoint=endpoint).inc()


def record_retry_attempt(endpoint: str, attempt: int):
    """
    Record a retry attempt.

    Args:
        endpoint: API endpoint
        attempt: Retry attempt number (1, 2, 3, etc.)
    """
    langextract_retry_attempts.labels(endpoint=endpoint, attempt=str(attempt)).inc()


def track_metric(metric_name: str, value: float, labels: Optional[dict] = None):
    """
    Generic function to track a metric value.

    Args:
        metric_name: Name of the metric to track
        value: Metric value
        labels: Optional labels for the metric
    """
    try:
        # Find the metric by name
        metric_map = {
            "semantic_similarity": semantic_similarity_computation,
            "structural_similarity": structural_similarity_computation,
            "weight_calculation": weight_calculation_duration,
            "pattern_matching": pattern_matching_duration,
        }

        metric = metric_map.get(metric_name)
        if metric:
            if labels:
                metric.labels(**labels).observe(value)
            else:
                metric.observe(value)
    except Exception as e:
        logger.error(f"Error tracking metric {metric_name}: {e}")


def initialize_system_info(version: str, config: dict):
    """
    Initialize system information metrics.

    Args:
        version: System version
        config: Configuration dictionary
    """
    info_dict = {
        "version": version,
        "environment": config.get("environment", "production"),
        "langextract_url": config.get("langextract_url", "unknown"),
        "cache_enabled": str(config.get("cache_enabled", True)),
    }
    pattern_learning_system_info.info(info_dict)


# ============================================================================
# Metric Export and Reset Functions
# ============================================================================


def get_metrics_summary() -> dict:
    """
    Get a summary of current metrics for debugging/monitoring.

    Returns:
        Dictionary containing current metric values
    """
    try:
        hits = cache_hit_total._value.get()
        misses = cache_miss_total._value.get()
        total = hits + misses

        return {
            "cache": {
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / total if total > 0 else 0.0,
                "size": cache_size._value.get(),
            },
            "langextract": {
                "total_requests": sum(
                    (
                        m._value.get()
                        for m in langextract_requests_total._metrics.values()
                    ),
                    start=0,
                ),
                "circuit_breaker_failures": sum(
                    (
                        m._value.get()
                        for m in langextract_circuit_breaker_failures._metrics.values()
                    ),
                    start=0,
                ),
            },
            "hybrid_scoring": {
                "total_requests": sum(
                    (
                        m._value.get()
                        for m in hybrid_scoring_requests_total._metrics.values()
                    ),
                    start=0,
                ),
            },
        }
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        return {}


def reset_metrics():
    """
    Reset all metrics (useful for testing).

    WARNING: This should only be used in testing/development environments.
    """
    logger.warning("Resetting all metrics - this should only be done in testing!")

    # Note: Prometheus metrics cannot be truly reset in production.
    # This function is mainly for documentation and testing purposes.
    # In production, metrics are cumulative and reset on service restart.
    pass


# ============================================================================
# Metric Middleware/Hooks
# ============================================================================


def instrument_async_function(metric_name: str, labels: Optional[dict] = None):
    """
    Decorator to automatically instrument async functions with timing metrics.

    Usage:
        @instrument_async_function('my_operation', {'type': 'batch'})
        async def my_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                track_metric(metric_name, duration, labels)

        return wrapper

    return decorator


def instrument_sync_function(metric_name: str, labels: Optional[dict] = None):
    """
    Decorator to automatically instrument sync functions with timing metrics.

    Usage:
        @instrument_sync_function('my_operation', {'type': 'sync'})
        def my_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                track_metric(metric_name, duration, labels)

        return wrapper

    return decorator


# ============================================================================
# Export All Metrics
# ============================================================================

__all__ = [
    # Metrics
    "langextract_requests_total",
    "langextract_request_duration",
    "langextract_request_size",
    "langextract_response_size",
    "langextract_errors_total",
    "langextract_circuit_breaker_state",
    "langextract_circuit_breaker_failures",
    "langextract_retry_attempts",
    "cache_hit_total",
    "cache_miss_total",
    "cache_hit_rate",
    "cache_size",
    "cache_evictions_total",
    "cache_lookup_duration",
    "cache_memory_usage",
    "hybrid_scoring_duration",
    "hybrid_scoring_requests_total",
    "pattern_similarity_score",
    "pattern_matching_candidates",
    "pattern_matching_duration",
    "semantic_similarity_computation",
    "structural_similarity_computation",
    "weight_calculation_duration",
    "pattern_learning_system_info",
    "active_pattern_learning_sessions",
    "pattern_database_size",
    "last_successful_operation",
    # Helper functions
    "track_langextract_request",
    "track_hybrid_scoring",
    "track_cache_lookup",
    "record_cache_hit",
    "record_cache_miss",
    "record_pattern_similarity",
    "record_circuit_breaker_state",
    "record_circuit_breaker_failure",
    "record_retry_attempt",
    "track_metric",
    "initialize_system_info",
    "get_metrics_summary",
    "reset_metrics",
    "instrument_async_function",
    "instrument_sync_function",
]
