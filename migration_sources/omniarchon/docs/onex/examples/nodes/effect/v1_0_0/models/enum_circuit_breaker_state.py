"""Circuit breaker state enum."""

from enum import Enum


class EnumCircuitBreakerState(Enum):
    """
    Circuit breaker states for external service failure handling.

    State machine: CLOSED ⇄ OPEN → HALF_OPEN → CLOSED
    """

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, rejecting all requests
    HALF_OPEN = "half_open"  # Testing recovery, limited requests
