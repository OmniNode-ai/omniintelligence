"""Async-compatible circuit breaker wrapper for HTTP clients.

This module provides an async-compatible wrapper around the base CircuitBreaker
for use with async HTTP clients and service calls.

ONEX Pattern: Infrastructure support for Effect nodes
"""

import asyncio
import functools
import os
import sys
from typing import Any, Callable, Coroutine, Optional, TypeVar

# Add config path for centralized timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from src.config.timeout_config import get_async_timeout

from .circuit_breaker import CircuitBreaker
from .enum_circuit_breaker_state import EnumCircuitBreakerState

T = TypeVar("T")


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker prevents operation execution."""

    pass


class AsyncCircuitBreaker:
    """
    Async-compatible circuit breaker wrapper.

    Wraps the base CircuitBreaker class to provide async-friendly API
    for use with async HTTP clients and service calls.

    CANONICAL PATTERN: Protects async operations from cascading failures.

    State Machine (inherited from base CircuitBreaker):
        CLOSED → (failures exceed threshold) → OPEN
        OPEN → (recovery timeout expires) → HALF_OPEN
        HALF_OPEN → (test succeeds) → CLOSED
        HALF_OPEN → (test fails) → OPEN

    Usage:
        breaker = AsyncCircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60)

        async def make_api_call():
            return await client.get("/api/endpoint")

        try:
            result = await breaker.call(make_api_call)
        except CircuitBreakerError:
            # Circuit is OPEN - handle gracefully
            logger.error("Circuit breaker prevented operation")

    Attributes:
        circuit_breaker: Underlying synchronous circuit breaker instance
        name: Optional name for logging/metrics
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: Optional[float] = None,
        half_open_max_attempts: int = 3,
        name: str = "async_circuit_breaker",
    ):
        """
        Initialize async circuit breaker.

        Args:
            failure_threshold: Failures needed to open circuit (default: 5)
            recovery_timeout_seconds: Wait time before testing recovery (default: from config, ~60s)
            half_open_max_attempts: Test requests in HALF_OPEN state (default: 3)
            name: Circuit breaker name for logging (default: "async_circuit_breaker")
        """
        # Use centralized configuration with fallback to 2x long timeout (default: 60s)
        effective_timeout = (
            recovery_timeout_seconds
            if recovery_timeout_seconds is not None
            else (2 * get_async_timeout("long"))
        )

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=effective_timeout,
            half_open_max_attempts=half_open_max_attempts,
        )
        self.name = name

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func execution

        Raises:
            CircuitBreakerError: Circuit is OPEN, operation not allowed
            Exception: Original exception from func if it fails

        Example:
            async def fetch_data(url: str) -> dict:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    return response.json()

            breaker = AsyncCircuitBreaker()
            try:
                data = await breaker.call(fetch_data, "https://api.example.com/data")
            except CircuitBreakerError:
                # Circuit is open - use fallback
                data = get_cached_data()
        """
        # Check if circuit allows execution
        if not self.circuit_breaker.can_execute():
            state = self.circuit_breaker.get_state()
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is {state['state']} - operation not allowed"
            )

        try:
            # Execute the async function
            result = await func(*args, **kwargs)

            # Record success
            self.circuit_breaker.record_success()

            return result

        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure()

            # Re-raise the original exception
            raise

    async def call_async(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Alias for call() to match pybreaker API.

        This method provides API compatibility with pybreaker's call_async method,
        making it a drop-in replacement.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func execution

        Raises:
            CircuitBreakerError: Circuit is OPEN, operation not allowed
            Exception: Original exception from func if it fails
        """
        return await self.call(func, *args, **kwargs)

    def can_execute(self) -> bool:
        """
        Check if circuit breaker allows execution.

        Returns:
            bool: True if operation can proceed, False if circuit is OPEN
        """
        return self.circuit_breaker.can_execute()

    def record_success(self) -> None:
        """Record a successful operation."""
        self.circuit_breaker.record_success()

    def record_failure(self) -> None:
        """Record a failed operation."""
        self.circuit_breaker.record_failure()

    @property
    def current_state(self) -> str:
        """
        Get current circuit breaker state.

        Returns:
            str: Current state ("closed", "open", or "half_open")
        """
        return self.circuit_breaker.state.value

    @property
    def state(self) -> EnumCircuitBreakerState:
        """
        Get current circuit breaker state enum.

        Returns:
            EnumCircuitBreakerState: Current state
        """
        return self.circuit_breaker.state

    def get_state(self) -> dict[str, Any]:
        """
        Get detailed circuit breaker state and statistics.

        Returns:
            dict: Current state information including:
                - state: Current circuit breaker state
                - failure_count: Number of consecutive failures
                - failure_threshold: Threshold for opening circuit
                - last_failure_time: Timestamp of last failure
                - half_open_attempts: Current test attempts in HALF_OPEN state
                - recovery_timeout_seconds: Recovery timeout configuration
        """
        return self.circuit_breaker.get_state()

    def reset(self) -> None:
        """
        Manually reset circuit breaker to CLOSED state.

        WARNING: Use with caution. Only reset when you're certain the
        underlying issue has been resolved.
        """
        self.circuit_breaker.state = EnumCircuitBreakerState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.half_open_attempts = 0


def circuit_breaker_decorator(
    failure_threshold: int = 5,
    recovery_timeout_seconds: Optional[float] = None,
    half_open_max_attempts: int = 3,
    name: str = "decorated_circuit_breaker",
) -> Callable:
    """
    Decorator for async functions with circuit breaker protection.

    Args:
        failure_threshold: Failures needed to open circuit (default: 5)
        recovery_timeout_seconds: Wait time before testing recovery (default: from config, ~60s)
        half_open_max_attempts: Test requests in HALF_OPEN state (default: 3)
        name: Circuit breaker name for logging (default: "decorated_circuit_breaker")

    Returns:
        Decorator function

    Example:
        @circuit_breaker_decorator(failure_threshold=3, name="api_calls")
        async def fetch_user_data(user_id: str) -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"/users/{user_id}")
                return response.json()

        try:
            user = await fetch_user_data("123")
        except CircuitBreakerError:
            # Circuit is open - use fallback
            user = get_cached_user("123")
    """
    # Use centralized configuration with fallback to 2x long timeout (default: 60s)
    effective_timeout = (
        recovery_timeout_seconds
        if recovery_timeout_seconds is not None
        else (2 * get_async_timeout("long"))
    )

    breaker = AsyncCircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=effective_timeout,
        half_open_max_attempts=half_open_max_attempts,
        name=name,
    )

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
