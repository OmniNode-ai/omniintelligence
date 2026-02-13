"""Shared protocol definitions for OmniIntelligence handlers.

These protocols define the interfaces for database and event bus operations
used across multiple handler modules. Centralizing them prevents definition
drift and simplifies maintenance.

Reference:
    - OMN-2133: Protocol extraction to shared module
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the interface required for database operations
    in handler functions. It supports both asyncpg connections and
    mock implementations for testing.

    The methods mirror asyncpg.Connection semantics:
        - fetch: Execute query and return list of Records
        - fetchrow: Execute query and return single Record or None
        - execute: Execute query and return status string (e.g., "UPDATE 1")

    Note:
        Parameters use asyncpg-style positional placeholders ($1, $2, etc.)
        rather than named parameters.
    """

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, object]]:
        """Execute a query and return all results as Records."""
        ...

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, object] | None:
        """Execute a query and return first row, or None."""
        ...

    async def execute(self, query: str, *args: object) -> str:
        """Execute a query and return the status string."""
        ...


@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    """Protocol for Kafka event publishers.

    Defines a simplified interface for publishing events to Kafka topics.
    This protocol uses a dict-based value for flexibility, with serialization
    handled by the implementation.
    """

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        """Publish an event to a Kafka topic.

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary (serialized by implementation).
        """
        ...


# TODO: dispatch_handlers.py maintains local copies of ProtocolIdempotencyStore
# and ProtocolIntentClassifier to avoid circular imports with their handler modules
# (handler_transition.py and handler_claude_event.py). If those protocols are
# extracted here in the future, dispatch_handlers.py should import from this module.

__all__ = ["ProtocolKafkaPublisher", "ProtocolPatternRepository"]
