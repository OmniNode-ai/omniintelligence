"""
Base Effect Node - ONEX Pattern

Abstract base class for all effect nodes (external I/O operations).
Defines common interface and error handling patterns.

ONEX Pattern: Effect (External I/O, side effects)
Characteristics:
- Handles external resources (files, databases, APIs)
- Implements retry logic with exponential backoff
- Graceful degradation on failures
- Atomic operations where possible
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.models.effect_result import EffectResult

logger = logging.getLogger(__name__)


class BaseEffect(ABC):
    """
    Base class for ONEX effect nodes.

    Effect nodes handle external I/O operations with:
    - Retry logic (exponential backoff)
    - Error handling (graceful degradation)
    - Performance tracking
    - Atomic operations

    Subclasses must implement:
    - execute(): Main effect operation
    - get_effect_name(): Unique identifier
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_ms: float = 100.0,
        retry_backoff: float = 2.0,
    ):
        """
        Initialize base effect node.

        Args:
            max_retries: Maximum retry attempts for failed operations
            retry_delay_ms: Initial retry delay in milliseconds
            retry_backoff: Exponential backoff multiplier (delay *= backoff)
        """
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.retry_backoff = retry_backoff

        # Metrics
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_retries": 0,
            "total_duration_ms": 0.0,
        }

        logger.debug(
            f"{self.get_effect_name()} initialized: "
            f"max_retries={max_retries}, retry_delay={retry_delay_ms}ms, "
            f"backoff={retry_backoff}"
        )

    @abstractmethod
    async def execute(self, input_data: Any) -> EffectResult:
        """
        Execute effect operation.

        This is the main method that performs the external I/O operation.
        Subclasses must implement this method with their specific logic.

        Args:
            input_data: Input data for effect operation (type varies by effect)

        Returns:
            EffectResult with operation status and metrics

        Raises:
            Exception: Implementation-specific exceptions
        """
        pass

    @abstractmethod
    def get_effect_name(self) -> str:
        """
        Get unique effect identifier.

        Returns:
            Effect name (e.g., "FileWriterEffect", "QdrantIndexerEffect")
        """
        pass

    async def execute_with_retry(
        self, input_data: Any, retry: bool = True
    ) -> EffectResult:
        """
        Execute effect with automatic retry logic.

        Wraps execute() with exponential backoff retry logic for transient failures.

        Args:
            input_data: Input data for effect operation
            retry: Whether to enable retry logic (default: True)

        Returns:
            EffectResult from successful execution or final failure
        """
        import time

        start_time = time.perf_counter()
        last_exception: Optional[Exception] = None

        # Track execution attempt
        self.metrics["total_executions"] += 1

        # Attempt execution with retries
        for attempt in range(self.max_retries if retry else 1):
            try:
                logger.debug(
                    f"{self.get_effect_name()} execution attempt {attempt + 1}/{self.max_retries}"
                )

                result = await self.execute(input_data)

                # Success
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.metrics["successful_executions"] += 1
                self.metrics["total_duration_ms"] += duration_ms

                logger.info(
                    f"✅ {self.get_effect_name()} success: "
                    f"{result.items_processed} items in {duration_ms:.1f}ms "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"❌ {self.get_effect_name()} attempt {attempt + 1} failed: {e}"
                )

                # Don't retry on last attempt
                if attempt < self.max_retries - 1 and retry:
                    # Calculate exponential backoff delay
                    delay_seconds = (
                        self.retry_delay_ms * (self.retry_backoff**attempt)
                    ) / 1000.0

                    logger.info(
                        f"⏳ Retrying {self.get_effect_name()} in {delay_seconds:.1f}s..."
                    )
                    self.metrics["total_retries"] += 1

                    await asyncio.sleep(delay_seconds)
                else:
                    # Final failure
                    break

        # All retries failed
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.metrics["failed_executions"] += 1
        self.metrics["total_duration_ms"] += duration_ms

        logger.error(
            f"❌ {self.get_effect_name()} failed after {self.max_retries} attempts: "
            f"{last_exception}"
        )

        return EffectResult(
            success=False,
            items_processed=0,
            duration_ms=duration_ms,
            errors=[f"Failed after {self.max_retries} attempts: {last_exception}"],
            metadata={
                "attempts": self.max_retries,
                "final_exception": str(last_exception),
                "exception_type": type(last_exception).__name__,
            },
        )

    def get_metrics(self) -> dict:
        """
        Get effect node performance metrics.

        Returns:
            Dictionary with execution statistics
        """
        total = self.metrics["total_executions"]
        success_rate = (
            self.metrics["successful_executions"] / total if total > 0 else 0.0
        )
        avg_duration = self.metrics["total_duration_ms"] / total if total > 0 else 0.0

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration,
            "effect_name": self.get_effect_name(),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_retries": 0,
            "total_duration_ms": 0.0,
        }
        logger.debug(f"{self.get_effect_name()} metrics reset")


__all__ = ["BaseEffect"]
