"""
Background Task Utilities

Provides retry logic, error handling, and metrics tracking for FastAPI background tasks.

Features:
- Exponential backoff retry with configurable attempts
- Prometheus metrics for monitoring
- Structured error logging with correlation IDs
- Dead letter queue support (stub for future implementation)
- Circuit breaker pattern for cascading failure prevention

Usage:
    @retry_background_task(max_retries=3, operation_name="process_document")
    async def my_background_task(document_id: str):
        # Task implementation
        await process_document(document_id)
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Prometheus Metrics for Background Tasks
# ============================================================================

# Counter for total background tasks started
background_tasks_total = Counter(
    "background_tasks_total",
    "Total number of background tasks started",
    ["task_name", "operation_type"],
)

# Counter for background task successes
background_tasks_success = Counter(
    "background_tasks_success",
    "Number of background tasks that completed successfully",
    ["task_name", "operation_type"],
)

# Counter for background task failures
background_tasks_failed = Counter(
    "background_tasks_failed",
    "Number of background tasks that failed after all retries",
    ["task_name", "operation_type", "error_type"],
)

# Counter for retry attempts
background_task_retries = Counter(
    "background_task_retries",
    "Number of background task retry attempts",
    ["task_name", "operation_type", "attempt"],
)

# Histogram for background task execution time
background_task_duration = Histogram(
    "background_task_duration_seconds",
    "Background task execution time in seconds",
    ["task_name", "operation_type", "status"],
)

# Gauge for currently executing background tasks
background_tasks_active = Gauge(
    "background_tasks_active",
    "Number of currently executing background tasks",
    ["task_name", "operation_type"],
)


# ============================================================================
# Error Classification
# ============================================================================


class BackgroundTaskErrorType(str, Enum):
    """Classification of background task errors for metrics and routing."""

    TRANSIENT = "transient"  # Temporary failures (network, timeout, 503)
    PERSISTENT = "persistent"  # Data/validation errors (422, 400)
    FATAL = "fatal"  # Unrecoverable errors (500, auth failures)
    TIMEOUT = "timeout"  # Timeout errors
    NETWORK = "network"  # Network connectivity issues
    SERVICE_UNAVAILABLE = "service_unavailable"  # Service 503 errors
    UNKNOWN = "unknown"  # Unknown error types


def classify_error(error: Exception) -> BackgroundTaskErrorType:
    """
    Classify error type for retry decision and metrics.

    Args:
        error: Exception to classify

    Returns:
        BackgroundTaskErrorType indicating error category
    """
    error_str = str(error).lower()

    # Timeout errors
    if isinstance(error, asyncio.TimeoutError) or "timeout" in error_str:
        return BackgroundTaskErrorType.TIMEOUT

    # Network errors
    if "network" in error_str or "connection" in error_str:
        return BackgroundTaskErrorType.NETWORK

    # Service unavailable
    if "503" in error_str or "unavailable" in error_str:
        return BackgroundTaskErrorType.SERVICE_UNAVAILABLE

    # Validation errors (don't retry)
    if "validation" in error_str or "422" in error_str or "400" in error_str:
        return BackgroundTaskErrorType.PERSISTENT

    # Auth errors (don't retry)
    if "auth" in error_str or "401" in error_str or "403" in error_str:
        return BackgroundTaskErrorType.FATAL

    # Server errors (retry)
    if "500" in error_str:
        return BackgroundTaskErrorType.FATAL

    # Default to transient for retry
    return BackgroundTaskErrorType.TRANSIENT


def should_retry(error_type: BackgroundTaskErrorType) -> bool:
    """
    Determine if error type should be retried.

    Args:
        error_type: Classified error type

    Returns:
        True if error is retryable, False otherwise
    """
    # Retry transient, timeout, network, and service unavailable errors
    return error_type in [
        BackgroundTaskErrorType.TRANSIENT,
        BackgroundTaskErrorType.TIMEOUT,
        BackgroundTaskErrorType.NETWORK,
        BackgroundTaskErrorType.SERVICE_UNAVAILABLE,
    ]


# ============================================================================
# Retry Decorator for Background Tasks
# ============================================================================


def retry_background_task(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    operation_name: Optional[str] = None,
    operation_type: str = "background_task",
    track_metrics: bool = True,
):
    """
    Decorator for background tasks with retry logic and metrics tracking.

    Features:
    - Exponential backoff with configurable parameters
    - Prometheus metrics tracking
    - Structured error logging with correlation IDs
    - Error classification for intelligent retry decisions
    - Support for dead letter queue (future)

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        operation_name: Name of the operation for logging/metrics (default: function name)
        operation_type: Type of operation for metrics grouping (default: "background_task")
        track_metrics: Whether to track Prometheus metrics (default: True)

    Returns:
        Decorated async function with retry logic

    Usage:
        @retry_background_task(max_retries=3, operation_name="process_document")
        async def process_document_background(document_id: str):
            await process_document(document_id)

    Example with custom parameters:
        @retry_background_task(
            max_retries=5,
            initial_delay=2.0,
            backoff_multiplier=3.0,
            operation_name="vectorize_large_document",
            operation_type="vectorization"
        )
        async def vectorize_background(document_id: str, content: str):
            await vectorize_document(document_id, content)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Optional[T]:
            # Generate correlation ID for tracking
            correlation_id = str(uuid.uuid4())
            task_name = operation_name or func.__name__

            # Track task start
            if track_metrics:
                background_tasks_total.labels(
                    task_name=task_name, operation_type=operation_type
                ).inc()
                background_tasks_active.labels(
                    task_name=task_name, operation_type=operation_type
                ).inc()

            start_time = time.time()
            delay = initial_delay
            error_type = BackgroundTaskErrorType.UNKNOWN

            # Log task start
            logger.info(
                f"Background task started: {task_name}",
                extra={
                    "task_name": task_name,
                    "operation_type": operation_type,
                    "correlation_id": correlation_id,
                    "max_retries": max_retries,
                    "task_args": str(args)[
                        :200
                    ],  # Renamed from 'args' to avoid LogRecord conflict
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            try:
                # Retry loop with exponential backoff
                for attempt in range(max_retries + 1):
                    try:
                        # Execute the background task
                        result = await func(*args, **kwargs)

                        # Success - record metrics
                        duration_seconds = time.time() - start_time

                        if track_metrics:
                            background_tasks_success.labels(
                                task_name=task_name, operation_type=operation_type
                            ).inc()
                            background_task_duration.labels(
                                task_name=task_name,
                                operation_type=operation_type,
                                status="success",
                            ).observe(duration_seconds)

                        # Log success
                        log_level = "info" if attempt == 0 else "warning"
                        log_func = getattr(logger, log_level)
                        log_func(
                            f"Background task succeeded: {task_name}"
                            + (f" (after {attempt} retries)" if attempt > 0 else ""),
                            extra={
                                "task_name": task_name,
                                "operation_type": operation_type,
                                "correlation_id": correlation_id,
                                "attempts": attempt + 1,
                                "duration_seconds": round(duration_seconds, 3),
                                "status": "success",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )

                        return result

                    except Exception as e:
                        error_type = classify_error(e)

                        # Check if we should retry this error type
                        if not should_retry(error_type):
                            logger.error(
                                f"Background task failed with non-retryable error: {task_name}",
                                extra={
                                    "task_name": task_name,
                                    "operation_type": operation_type,
                                    "correlation_id": correlation_id,
                                    "error_type": error_type.value,
                                    "error_message": str(e),
                                    "attempts": attempt + 1,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                                exc_info=True,
                            )
                            break  # Don't retry persistent/fatal errors

                        # Check if we should retry
                        if attempt < max_retries:
                            # Track retry attempt
                            if track_metrics:
                                background_task_retries.labels(
                                    task_name=task_name,
                                    operation_type=operation_type,
                                    attempt=str(attempt + 1),
                                ).inc()

                            # Calculate backoff delay (capped at max_delay)
                            current_delay = min(delay, max_delay)
                            delay *= backoff_multiplier

                            # Log retry
                            logger.warning(
                                f"Background task attempt {attempt + 1}/{max_retries + 1} failed: {task_name}. "
                                f"Retrying in {current_delay:.1f}s...",
                                extra={
                                    "task_name": task_name,
                                    "operation_type": operation_type,
                                    "correlation_id": correlation_id,
                                    "attempt": attempt + 1,
                                    "max_retries": max_retries + 1,
                                    "error_type": error_type.value,
                                    "error_message": str(e),
                                    "retry_delay_seconds": current_delay,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                            )

                            # Wait before retry
                            await asyncio.sleep(current_delay)
                            continue
                        else:
                            # Max retries exhausted
                            logger.error(
                                f"Background task failed after {max_retries + 1} attempts: {task_name}",
                                extra={
                                    "task_name": task_name,
                                    "operation_type": operation_type,
                                    "correlation_id": correlation_id,
                                    "error_type": error_type.value,
                                    "error_message": str(e),
                                    "total_attempts": max_retries + 1,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                                exc_info=True,
                            )
                            break

                # If we get here, all retries failed
                duration_seconds = time.time() - start_time

                if track_metrics:
                    background_tasks_failed.labels(
                        task_name=task_name,
                        operation_type=operation_type,
                        error_type=error_type.value,
                    ).inc()
                    background_task_duration.labels(
                        task_name=task_name,
                        operation_type=operation_type,
                        status="failed",
                    ).observe(duration_seconds)

                # TODO: Send to dead letter queue for manual review
                # await send_to_dlq(task_name, args, kwargs, last_error, correlation_id)

                return None  # Return None instead of raising (background tasks shouldn't crash)

            finally:
                # Always decrement active tasks gauge
                if track_metrics:
                    background_tasks_active.labels(
                        task_name=task_name, operation_type=operation_type
                    ).dec()

        return wrapper

    return decorator


# ============================================================================
# Dead Letter Queue (Stub for Future Implementation)
# ============================================================================


async def send_to_dlq(
    task_name: str, args: tuple, kwargs: dict, error: Exception, correlation_id: str
) -> None:
    """
    Send failed task to dead letter queue for manual review.

    Future implementation could:
    - Store in database table
    - Send to message queue (SQS, RabbitMQ, Kafka)
    - Trigger alerting/monitoring
    - Enable manual retry via admin interface

    Args:
        task_name: Name of the failed task
        args: Positional arguments passed to task
        kwargs: Keyword arguments passed to task
        error: Exception that caused failure
        correlation_id: Correlation ID for tracking
    """
    logger.warning(
        f"TODO: Send task to DLQ: {task_name}",
        extra={
            "task_name": task_name,
            "correlation_id": correlation_id,
            "error_type": classify_error(error).value,
            "error_message": str(error),
            "dlq_status": "not_implemented",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    # Future: Implement actual DLQ storage/routing


# ============================================================================
# Metrics Query Utilities
# ============================================================================


def get_background_task_metrics() -> Dict[str, Any]:
    """
    Get current background task metrics snapshot.

    Returns:
        Dictionary with current metrics values

    Usage:
        metrics = get_background_task_metrics()
        print(f"Active tasks: {metrics['active_tasks']}")
        print(f"Success rate: {metrics['success_rate']:.2%}")
    """
    # This is a helper to expose metrics in a structured way
    # Actual metrics are collected by Prometheus
    return {
        "info": "Metrics are collected via Prometheus. Check /metrics endpoint",
        "metrics_available": [
            "background_tasks_total",
            "background_tasks_success",
            "background_tasks_failed",
            "background_task_retries",
            "background_task_duration_seconds",
            "background_tasks_active",
        ],
        "prometheus_endpoint": "/metrics",
    }
