"""Shared protocol definitions for OmniIntelligence handlers.

These protocols define the interfaces for database and event bus operations
used across multiple handler modules. Centralizing them prevents definition
drift and simplifies maintenance.

Reference:
    - OMN-2133: Protocol extraction to shared module
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from omniintelligence.nodes.node_intent_classifier_compute.models.model_intent_classification_input import (
        ModelIntentClassificationInput,
    )
    from omniintelligence.nodes.node_intent_classifier_compute.models.model_intent_classification_output import (
        ModelIntentClassificationOutput,
    )


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

    # any-ok: asyncpg Record values are dynamically typed
    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        """Execute a query and return all results as Records."""
        ...

    # any-ok: asyncpg Record values are dynamically typed
    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
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


@runtime_checkable
class ProtocolIdempotencyStore(Protocol):
    """Protocol for idempotency key tracking.

    This protocol defines the interface for checking and recording
    idempotency keys (request_id values) to prevent duplicate transitions.

    The implementation may use PostgreSQL, Redis, or in-memory storage
    depending on the deployment environment.

    Idempotency Timing:
        To ensure operations are retriable on failure, the idempotency key
        should be recorded AFTER successful completion:

        1. Call exists() to check for duplicates
        2. If duplicate, return cached success
        3. Perform the operation
        4. On SUCCESS, call record() to mark as processed
        5. On FAILURE, do NOT record - allows retry

        This ensures that failed operations can be retried with the same
        request_id, while preventing duplicate processing of successful ones.
    """

    async def check_and_record(self, request_id: UUID) -> bool:
        """Check if request_id exists, and if not, record it atomically.

        This operation must be atomic (check-and-set) to prevent race
        conditions between concurrent requests with the same request_id.

        Args:
            request_id: The idempotency key to check and record.

        Returns:
            True if this is a DUPLICATE (request_id already existed).
            False if this is NEW (request_id was just recorded).
        """
        ...

    async def exists(self, request_id: UUID) -> bool:
        """Check if request_id exists without recording.

        Args:
            request_id: The idempotency key to check.

        Returns:
            True if request_id exists, False otherwise.
        """
        ...

    async def record(self, request_id: UUID) -> None:
        """Record a request_id as processed (without checking).

        This should be called AFTER successful operation completion to
        prevent replay of the same request_id.

        Args:
            request_id: The idempotency key to record.

        Note:
            If the request_id already exists, this is a no-op (idempotent).
        """
        ...


@runtime_checkable
class ProtocolPatternUpsertStore(Protocol):
    """Protocol for idempotent pattern storage (ON CONFLICT DO NOTHING).

    Used by the dispatch bridge handler for pattern-learned and
    pattern.discovered events. Returns the UUID if inserted, None if
    duplicate (conflict).
    """

    async def upsert_pattern(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain_id: str,
        domain_version: str,
        confidence: float,
        version: int,
        source_session_ids: list[UUID],
    ) -> UUID | None:
        """Idempotently insert a pattern.

        Returns:
            UUID if inserted, None if duplicate.
        """
        ...


@runtime_checkable
class ProtocolIntentClassifier(Protocol):
    """Protocol for intent classification compute nodes.

    Defines a simplified interface for classifying user prompt intent.
    The implementation delegates to a compute node that performs
    pattern-matching-based classification.

    NOTE: ModelIntentClassificationInput/Output are TYPE_CHECKING-only to avoid
    circular imports at runtime. isinstance() checks against this protocol verify
    method name presence only, as documented for @runtime_checkable protocols.
    Full type fidelity is enforced by static analysis only.
    """

    async def compute(
        self, input_data: ModelIntentClassificationInput
    ) -> ModelIntentClassificationOutput: ...


__all__ = [
    "ProtocolIdempotencyStore",
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "ProtocolPatternUpsertStore",
]
