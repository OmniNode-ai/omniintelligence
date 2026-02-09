# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Protocol adapters for intelligence dispatch handler dependencies.

Bridges available infrastructure (asyncpg.Pool, event bus) to the protocol
interfaces expected by intelligence domain handlers.

Adapters:
    - AdapterPatternRepositoryPostgres: asyncpg.Pool → ProtocolPatternRepository
    - AdapterIdempotencyStorePostgres: asyncpg.Pool → ProtocolIdempotencyStore
    - AdapterKafkaPublisher: event bus → ProtocolKafkaPublisher
    - AdapterIntentClassifier: handle_intent_classification → ProtocolIntentClassifier

Design:
    Each adapter is a thin explicit boundary that prevents accidental coupling
    to infrastructure-specific methods.  Protocol conformance is verified in
    tests, not at import time (avoids import-time landmines with optional deps).

Related:
    - OMN-2032: Wire real dependencies into dispatch handlers (Phase 2)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# =============================================================================
# SQL Constants (idempotency store)
# =============================================================================

SQL_ENSURE_IDEMPOTENCY_TABLE = """\
CREATE TABLE IF NOT EXISTS pattern_idempotency_keys (
    request_id UUID PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SQL_IDEMPOTENCY_EXISTS = """\
SELECT 1 FROM pattern_idempotency_keys WHERE request_id = $1;
"""

SQL_IDEMPOTENCY_RECORD = """\
INSERT INTO pattern_idempotency_keys (request_id)
VALUES ($1)
ON CONFLICT (request_id) DO NOTHING;
"""

SQL_IDEMPOTENCY_CHECK_AND_RECORD = """\
INSERT INTO pattern_idempotency_keys (request_id)
VALUES ($1)
ON CONFLICT (request_id) DO NOTHING
RETURNING request_id;
"""


# =============================================================================
# AdapterPatternRepositoryPostgres
# =============================================================================


class AdapterPatternRepositoryPostgres:
    """Thin wrapper around asyncpg.Pool implementing ProtocolPatternRepository.

    Delegates fetch/fetchrow/execute to the pool while preventing accidental
    use of asyncpg-specific methods (fetchval, copy_records_to_table, etc.).

    Note:
        Each call acquires and releases a connection from the pool.  There is
        no cross-call transaction guarantee.  Handlers relying on atomicity
        should use optimistic locking and idempotency patterns.
    """

    __slots__ = ("_pool",)

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        """Execute query and return all rows."""
        return await self._pool.fetch(query, *args)  # type: ignore[return-value]

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        """Execute query and return first row, or None."""
        return await self._pool.fetchrow(query, *args)  # type: ignore[return-value]

    async def execute(self, query: str, *args: Any) -> str:
        """Execute query and return status string."""
        return await self._pool.execute(query, *args)


# =============================================================================
# AdapterIdempotencyStorePostgres
# =============================================================================


class AdapterIdempotencyStorePostgres:
    """PostgreSQL-backed idempotency store for pattern lifecycle transitions.

    Uses a dedicated ``pattern_idempotency_keys`` table with UUID primary key.
    Table creation is handled by ``ensure_table()`` which is safe to call
    repeatedly (CREATE TABLE IF NOT EXISTS).

    Transitional:
        Table creation via ensure_table() is a bootstrap convenience.  A proper
        migration mechanism should replace this in a follow-up ticket.
    """

    __slots__ = ("_pool", "_table_ensured")

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._table_ensured = False

    async def ensure_table(self) -> None:
        """Create the idempotency keys table if it does not exist.

        Safe to call multiple times.  Logs on first successful creation.
        """
        await self._pool.execute(SQL_ENSURE_IDEMPOTENCY_TABLE)
        if not self._table_ensured:
            logger.info(
                "Idempotency table 'pattern_idempotency_keys' ensured "
                "(CREATE TABLE IF NOT EXISTS)"
            )
            self._table_ensured = True

    async def exists(self, request_id: UUID) -> bool:
        """Check if request_id has been recorded (without recording).

        Args:
            request_id: Idempotency key to check.

        Returns:
            True if request_id exists, False otherwise.
        """
        row = await self._pool.fetchrow(SQL_IDEMPOTENCY_EXISTS, request_id)
        return row is not None

    async def record(self, request_id: UUID) -> None:
        """Record request_id as processed (idempotent, no-op if exists).

        Args:
            request_id: Idempotency key to record.
        """
        await self._pool.execute(SQL_IDEMPOTENCY_RECORD, request_id)

    async def check_and_record(self, request_id: UUID) -> bool:
        """Atomically check and record request_id.

        Args:
            request_id: Idempotency key to check and record.

        Returns:
            True if this is a DUPLICATE (already existed).
            False if this is NEW (just recorded).
        """
        # INSERT ... ON CONFLICT DO NOTHING RETURNING request_id
        # If the row was inserted (new), RETURNING yields the row.
        # If conflict (duplicate), RETURNING yields nothing.
        row = await self._pool.fetchrow(
            SQL_IDEMPOTENCY_CHECK_AND_RECORD, request_id
        )
        return row is None  # None = conflict = duplicate


# =============================================================================
# AdapterKafkaPublisher
# =============================================================================


class AdapterKafkaPublisher:
    """Wraps an event bus to implement ProtocolKafkaPublisher.

    Normalizes the ProtocolKafkaPublisher interface (topic, key: str, value: dict)
    to the event bus interface (topic, key: bytes, value: bytes).

    Serialization:
        - key: UTF-8 encoded bytes
        - value: compact JSON bytes (no whitespace, non-ASCII preserved)
    """

    __slots__ = ("_event_bus",)

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish event to Kafka topic via event bus.

        Args:
            topic: Target topic name.
            key: Message key (for partitioning).
            value: Event payload dict (serialized to JSON bytes).
        """
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._event_bus.publish(
            topic=topic, key=key_bytes, value=value_bytes
        )


# =============================================================================
# AdapterIntentClassifier
# =============================================================================


class AdapterIntentClassifier:
    """Pure-compute intent classifier implementing ProtocolIntentClassifier.

    Wraps the TF-IDF based ``handle_intent_classification`` function as an
    async protocol-conformant object.  No I/O, no external dependencies.
    """

    __slots__ = ("_config",)

    def __init__(
        self,
        config: Any | None = None,
    ) -> None:
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
        )

        self._config = config if config is not None else DEFAULT_CLASSIFICATION_CONFIG

    async def compute(
        self,
        input_data: Any,
    ) -> Any:
        """Classify user intent via TF-IDF.

        Args:
            input_data: ModelIntentClassificationInput instance.

        Returns:
            ModelIntentClassificationOutput with classified intents.
        """
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            handle_intent_classification,
        )

        return handle_intent_classification(
            input_data=input_data,
            config=self._config,
        )


__all__ = [
    "AdapterIdempotencyStorePostgres",
    "AdapterIntentClassifier",
    "AdapterKafkaPublisher",
    "AdapterPatternRepositoryPostgres",
]
