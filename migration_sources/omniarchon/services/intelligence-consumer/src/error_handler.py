"""
Error handling with retry logic and DLQ routing.

Implements exponential backoff retry strategy and dead letter queue
routing for failed message processing.
"""

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import structlog

from .config import get_config

logger = structlog.get_logger(__name__)


class RetryExhausted(Exception):
    """Exception raised when all retry attempts are exhausted."""

    pass


class ErrorHandler:
    """
    Error handler with retry logic and DLQ routing.

    Implements exponential backoff retry strategy and routes
    failed messages to dead letter queue after exhausting retries.
    """

    def __init__(
        self,
        dlq_publisher: Callable[
            [Dict[str, Any], Exception, int, Optional[Dict[str, Any]]], Awaitable[None]
        ],
    ):
        """
        Initialize error handler.

        Args:
            dlq_publisher: Async function to publish to DLQ
        """
        self.config = get_config()
        self.dlq_publisher = dlq_publisher

        self.logger = logger.bind(component="error_handler")

        # Track retry state per correlation ID
        self._retry_state: Dict[str, int] = {}

    async def handle_error(
        self,
        error: Exception,
        event_data: Dict[str, Any],
        processor: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Handle processing error with retry logic.

        Args:
            error: Exception that occurred
            event_data: Original event data
            processor: Async function to retry processing

        Raises:
            RetryExhausted: If all retry attempts are exhausted
        """
        correlation_id = event_data.get("correlation_id", "unknown")
        retry_count = self._get_retry_count(correlation_id)

        log = self.logger.bind(
            correlation_id=correlation_id,
            retry_count=retry_count,
            error_type=type(error).__name__,
        )

        log.warning("processing_error_occurred", error_message=str(error))

        # Check if retries exhausted
        if retry_count >= self.config.max_retry_attempts:
            log.error(
                "retry_attempts_exhausted", max_attempts=self.config.max_retry_attempts
            )

            # Route to DLQ
            await self._route_to_dlq(
                event_data=event_data, error=error, retry_count=retry_count
            )

            # Clear retry state
            self._clear_retry_state(correlation_id)

            raise RetryExhausted(
                f"Max retry attempts ({self.config.max_retry_attempts}) exhausted"
            )

        # Calculate backoff delay
        delay = self._calculate_backoff(retry_count)

        log.info("retrying_after_delay", delay_seconds=delay, attempt=retry_count + 1)

        # Wait before retry
        await asyncio.sleep(delay)

        # Increment retry count
        self._increment_retry_count(correlation_id)

        # Retry processing
        try:
            await processor(event_data)

            # Success - clear retry state
            self._clear_retry_state(correlation_id)

            log.info("retry_successful", attempt=retry_count + 1)

        except Exception as retry_error:
            log.warning(
                "retry_failed",
                attempt=retry_count + 1,
                error_type=type(retry_error).__name__,
                error_message=str(retry_error),
            )

            # Recursive retry
            await self.handle_error(retry_error, event_data, processor)

    async def _route_to_dlq(
        self, event_data: Dict[str, Any], error: Exception, retry_count: int
    ) -> None:
        """
        Route failed event to dead letter queue.

        Args:
            event_data: Original event data
            error: Final error that caused failure
            retry_count: Number of retry attempts made
        """
        correlation_id = event_data.get("correlation_id", "unknown")

        self.logger.warning(
            "routing_to_dlq",
            correlation_id=correlation_id,
            retry_count=retry_count,
            error_type=type(error).__name__,
        )

        # Build error details
        error_details = {
            "error_message": str(error),
            "error_type": type(error).__name__,
            "retry_history": self._get_retry_history(correlation_id),
            "final_retry_count": retry_count,
        }

        try:
            # Publish to DLQ
            await self.dlq_publisher(
                original_event=event_data,
                error=error,
                retry_count=retry_count,
                error_details=error_details,
            )

            self.logger.info("dlq_routing_successful", correlation_id=correlation_id)

        except Exception as dlq_error:
            self.logger.error(
                "dlq_routing_failed",
                correlation_id=correlation_id,
                dlq_error=str(dlq_error),
            )
            # DLQ routing failure is critical but don't raise
            # to prevent blocking consumer

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base^retry_count
        delay = self.config.retry_backoff_base**retry_count

        # Cap at max backoff
        delay = min(delay, self.config.retry_backoff_max)

        return float(delay)

    def _get_retry_count(self, correlation_id: str) -> int:
        """Get retry count for correlation ID."""
        return self._retry_state.get(correlation_id, 0)

    def _increment_retry_count(self, correlation_id: str) -> None:
        """Increment retry count for correlation ID."""
        current = self._retry_state.get(correlation_id, 0)
        self._retry_state[correlation_id] = current + 1

    def _clear_retry_state(self, correlation_id: str) -> None:
        """Clear retry state for correlation ID."""
        if correlation_id in self._retry_state:
            del self._retry_state[correlation_id]

    def _get_retry_history(self, correlation_id: str) -> list:
        """
        Get retry history for correlation ID.

        Returns:
            List of retry timestamps and counts
        """
        # Simple implementation - could be enhanced to track timestamps
        retry_count = self._get_retry_count(correlation_id)

        return [
            {"attempt": i + 1, "backoff_seconds": self._calculate_backoff(i)}
            for i in range(retry_count)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get error handler statistics.

        Returns:
            Stats dictionary
        """
        return {
            "active_retries": len(self._retry_state),
            "retry_states": {cid: count for cid, count in self._retry_state.items()},
        }


class ErrorClassifier:
    """
    Classify errors for appropriate handling.

    Determines if errors are retryable or should go directly to DLQ.
    """

    # Non-retryable error types
    NON_RETRYABLE_ERRORS = {
        "ValueError",
        "KeyError",
        "JSONDecodeError",
        "ValidationError",
    }

    @classmethod
    def is_retryable(cls, error: Exception) -> bool:
        """
        Determine if error is retryable.

        Args:
            error: Exception to classify

        Returns:
            True if error should be retried, False otherwise
        """
        error_type = type(error).__name__

        # Non-retryable errors should go directly to DLQ
        if error_type in cls.NON_RETRYABLE_ERRORS:
            return False

        # Specific error message patterns
        error_message = str(error).lower()

        # Validation errors - non-retryable
        if "validation" in error_message or "invalid" in error_message:
            return False

        # Default: retry
        return True

    @classmethod
    def should_skip_retry(cls, error: Exception) -> bool:
        """
        Determine if retry should be skipped entirely.

        Args:
            error: Exception to classify

        Returns:
            True if should skip retry and route directly to DLQ
        """
        return not cls.is_retryable(error)
