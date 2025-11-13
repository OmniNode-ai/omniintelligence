"""Circuit breaker manager for HTTP client fallback scenarios."""

import logging
import os
from typing import Optional

from .circuit_breaker import CircuitBreaker
from .enum_circuit_breaker_state import EnumCircuitBreakerState

logger = logging.getLogger(__name__)


class HTTPClientCircuitBreakerManager:
    """
    Circuit breaker manager for HTTP client fallback scenarios.

    Protects against cascading failures when shared HTTP client becomes unavailable
    and one-off clients need to be created repeatedly.

    Configuration (Environment Variables):
        HTTP_CLIENT_CB_FAILURE_THRESHOLD: Failures before circuit opens (default: 3)
        HTTP_CLIENT_CB_RECOVERY_TIMEOUT: Recovery timeout in seconds (default: 30)
        HTTP_CLIENT_CB_HALF_OPEN_ATTEMPTS: Test attempts in HALF_OPEN state (default: 2)

    Usage:
        manager = HTTPClientCircuitBreakerManager()

        # In fallback scenario
        if manager.can_create_fallback_client():
            try:
                async with httpx.AsyncClient() as client:
                    result = await client.post(url, json=data)
                    manager.record_success()
            except Exception as e:
                manager.record_failure(e)
                raise
        else:
            # Circuit is OPEN - fail fast instead of creating clients
            raise ServiceUnavailableError("HTTP client circuit breaker is OPEN")
    """

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_timeout_seconds: Optional[int] = None,
        half_open_max_attempts: Optional[int] = None,
    ):
        """
        Initialize HTTP client circuit breaker manager.

        Args:
            failure_threshold: Failures before opening circuit (default: from env or 3)
            recovery_timeout_seconds: Recovery timeout (default: from env or 30)
            half_open_max_attempts: Test attempts in HALF_OPEN (default: from env or 2)
        """
        # Load configuration from environment or use defaults
        self.failure_threshold = failure_threshold or int(
            os.getenv("HTTP_CLIENT_CB_FAILURE_THRESHOLD", "3")
        )
        self.recovery_timeout = recovery_timeout_seconds or int(
            os.getenv("HTTP_CLIENT_CB_RECOVERY_TIMEOUT", "30")
        )
        self.half_open_attempts = half_open_max_attempts or int(
            os.getenv("HTTP_CLIENT_CB_HALF_OPEN_ATTEMPTS", "2")
        )

        # Create circuit breaker instance
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.failure_threshold,
            recovery_timeout_seconds=self.recovery_timeout,
            half_open_max_attempts=self.half_open_attempts,
        )

        # Metrics tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_opens = 0
        self.circuit_closes = 0
        self.rejected_requests = 0

        logger.info(
            f"🔒 [CIRCUIT BREAKER] HTTP client circuit breaker initialized | "
            f"failure_threshold={self.failure_threshold} | "
            f"recovery_timeout={self.recovery_timeout}s | "
            f"half_open_attempts={self.half_open_attempts}"
        )

    def can_create_fallback_client(self) -> bool:
        """
        Check if fallback HTTP client creation is allowed.

        Returns:
            bool: True if fallback client can be created, False if circuit is OPEN

        Raises:
            None: Never raises, returns False when circuit is OPEN
        """
        self.total_requests += 1

        if not self.circuit_breaker.can_execute():
            self.rejected_requests += 1
            logger.warning(
                f"⚠️ [CIRCUIT BREAKER] HTTP client creation rejected - circuit is OPEN | "
                f"state={self.circuit_breaker.state.value} | "
                f"failure_count={self.circuit_breaker.failure_count}/{self.failure_threshold} | "
                f"rejected_requests={self.rejected_requests}"
            )
            return False

        return True

    def record_success(self) -> None:
        """
        Record successful HTTP client operation.

        Tracks success metrics and transitions circuit breaker state if needed.
        """
        previous_state = self.circuit_breaker.state

        self.circuit_breaker.record_success()
        self.successful_requests += 1

        # Log state transition
        if previous_state != self.circuit_breaker.state:
            self.circuit_closes += 1
            logger.info(
                f"✅ [CIRCUIT BREAKER] HTTP client circuit CLOSED | "
                f"previous_state={previous_state.value} | "
                f"new_state={self.circuit_breaker.state.value} | "
                f"successful_requests={self.successful_requests} | "
                f"circuit_closes={self.circuit_closes}"
            )

    def record_failure(self, error: Exception) -> None:
        """
        Record failed HTTP client operation.

        Args:
            error: Exception that caused the failure

        Tracks failure metrics and transitions circuit breaker state if needed.
        """
        previous_state = self.circuit_breaker.state

        self.circuit_breaker.record_failure()
        self.failed_requests += 1

        # Log state transition
        if previous_state != self.circuit_breaker.state:
            self.circuit_opens += 1
            logger.error(
                f"❌ [CIRCUIT BREAKER] HTTP client circuit OPENED | "
                f"previous_state={previous_state.value} | "
                f"new_state={self.circuit_breaker.state.value} | "
                f"failure_count={self.circuit_breaker.failure_count} | "
                f"failed_requests={self.failed_requests} | "
                f"circuit_opens={self.circuit_opens} | "
                f"error={str(error)}"
            )
        else:
            logger.warning(
                f"⚠️ [CIRCUIT BREAKER] HTTP client failure recorded | "
                f"state={self.circuit_breaker.state.value} | "
                f"failure_count={self.circuit_breaker.failure_count}/{self.failure_threshold} | "
                f"error={str(error)}"
            )

    def get_state(self) -> dict:
        """
        Get current circuit breaker state and metrics.

        Returns:
            dict: Comprehensive state information including:
                - circuit_breaker: Circuit breaker state details
                - metrics: Request and state transition metrics
                - health: Circuit health indicators
        """
        cb_state = self.circuit_breaker.get_state()

        success_rate = (
            (self.successful_requests / self.total_requests * 100)
            if self.total_requests > 0
            else 0.0
        )

        rejection_rate = (
            (self.rejected_requests / self.total_requests * 100)
            if self.total_requests > 0
            else 0.0
        )

        return {
            "circuit_breaker": cb_state,
            "metrics": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "rejected_requests": self.rejected_requests,
                "success_rate_percent": round(success_rate, 2),
                "rejection_rate_percent": round(rejection_rate, 2),
            },
            "state_transitions": {
                "circuit_opens": self.circuit_opens,
                "circuit_closes": self.circuit_closes,
            },
            "health": {
                "is_healthy": cb_state["state"] == EnumCircuitBreakerState.CLOSED.value,
                "is_testing": cb_state["state"]
                == EnumCircuitBreakerState.HALF_OPEN.value,
                "is_failing": cb_state["state"] == EnumCircuitBreakerState.OPEN.value,
            },
            "configuration": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout,
                "half_open_max_attempts": self.half_open_attempts,
            },
        }

    def reset(self) -> None:
        """
        Reset circuit breaker to initial state.

        WARNING: Use with caution. Only reset when you're certain the underlying
        issue has been resolved externally.
        """
        self.circuit_breaker.state = EnumCircuitBreakerState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.last_failure_time = None
        self.circuit_breaker.half_open_attempts = 0

        logger.warning(
            f"🔄 [CIRCUIT BREAKER] HTTP client circuit breaker manually reset | "
            f"total_requests={self.total_requests} | "
            f"success_rate={(self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0:.1f}%"
        )


# Global circuit breaker instance for HTTP client fallback
http_client_circuit_breaker = HTTPClientCircuitBreakerManager()
