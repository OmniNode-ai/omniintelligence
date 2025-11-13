"""Circuit breaker pattern for external service protection."""

from datetime import datetime, timedelta
from typing import Optional

from ..models.enum_circuit_breaker_state import EnumCircuitBreakerState


class CircuitBreaker:
    """
    Circuit breaker pattern for handling external service failures.

    CANONICAL PATTERN: Protects your system from cascading failures by
    temporarily disabling calls to failing services. After a timeout,
    allows limited test requests to check if service recovered.

    State Machine:
        CLOSED → (failures exceed threshold) → OPEN
        OPEN → (recovery timeout expires) → HALF_OPEN
        HALF_OPEN → (test succeeds) → CLOSED
        HALF_OPEN → (test fails) → OPEN

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60)

        if breaker.can_execute():
            try:
                result = await external_service_call()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            # Circuit is OPEN - skip call to prevent cascading failure
            raise ServiceUnavailableError("Circuit breaker is OPEN")

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout_seconds: Time to wait before testing recovery
        half_open_max_attempts: Number of test requests in HALF_OPEN state
        state: Current circuit breaker state
        failure_count: Current consecutive failure count
        last_failure_time: Timestamp of most recent failure
        half_open_attempts: Number of test requests made
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        half_open_max_attempts: int = 3,
    ):
        """
        Initialize circuit breaker with configuration.

        Args:
            failure_threshold: Failures needed to open circuit (default: 5)
            recovery_timeout_seconds: Wait time before testing recovery (default: 60s)
            half_open_max_attempts: Test requests in HALF_OPEN state (default: 3)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_attempts = half_open_max_attempts

        self.state = EnumCircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_attempts = 0

    def can_execute(self) -> bool:
        """
        Check if operation can be executed based on circuit breaker state.

        CANONICAL PATTERN: Always call this before attempting external service calls.
        Returns False when circuit is OPEN to prevent unnecessary failures.

        Returns:
            bool: True if operation can proceed, False if circuit is OPEN
        """
        now = datetime.now()

        if self.state == EnumCircuitBreakerState.CLOSED:
            return True

        if self.state == EnumCircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and now - self.last_failure_time > timedelta(
                seconds=self.recovery_timeout_seconds
            ):
                # Transition to HALF_OPEN to test recovery
                self.state = EnumCircuitBreakerState.HALF_OPEN
                self.half_open_attempts = 0
                return True
            return False

        # HALF_OPEN state - allow limited test requests
        return self.half_open_attempts < self.half_open_max_attempts

    def record_success(self) -> None:
        """
        Record a successful operation - may transition from HALF_OPEN to CLOSED.

        CANONICAL PATTERN: Call this after every successful external service call.
        """
        if self.state == EnumCircuitBreakerState.HALF_OPEN:
            # Success in HALF_OPEN - transition to CLOSED
            self.state = EnumCircuitBreakerState.CLOSED
            self.failure_count = 0
            self.half_open_attempts = 0
        elif self.state == EnumCircuitBreakerState.CLOSED:
            # Reduce failure count on success (gradual recovery)
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        """
        Record a failed operation - may transition to OPEN state.

        CANONICAL PATTERN: Call this after every failed external service call.
        """
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == EnumCircuitBreakerState.HALF_OPEN:
            # Failure in HALF_OPEN - transition back to OPEN
            self.state = EnumCircuitBreakerState.OPEN
            self.half_open_attempts = 0
        elif (
            self.state == EnumCircuitBreakerState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            # Exceeded threshold - transition to OPEN
            self.state = EnumCircuitBreakerState.OPEN
