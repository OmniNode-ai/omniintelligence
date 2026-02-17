# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Protocol adapters for intelligence dispatch handler dependencies.

Bridges omnibase_infra effect boundary (PostgresRepositoryRuntime,
StoreIdempotencyPostgres) and event bus to the protocol interfaces
expected by intelligence domain handlers.

Adapters:
    - AdapterPatternRepositoryRuntime: PostgresRepositoryRuntime -> ProtocolPatternRepository
    - AdapterIdempotencyStoreInfra: omnibase_infra idempotency store -> ProtocolIdempotencyStore
    - AdapterKafkaPublisher: event bus -> ProtocolKafkaPublisher
    - AdapterIntentClassifier: handle_intent_classification -> ProtocolIntentClassifier

Design:
    Each adapter is a thin explicit boundary that prevents accidental coupling
    to infrastructure-specific methods.  Protocol conformance is verified in
    tests, not at import time (avoids import-time landmines with optional deps).

Related:
    - OMN-2032: Wire real dependencies into dispatch handlers (Phase 2)
    - OMN-2326: Migrate intelligence DB writes to omnibase_infra effect boundary
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from omnibase_infra.idempotency.protocol_idempotency_store import (
        ProtocolIdempotencyStore as InfraProtocolIdempotencyStore,
    )
    from omnibase_infra.runtime.db import PostgresRepositoryRuntime

    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelClassificationConfig,
    )
    from omniintelligence.nodes.node_intent_classifier_compute.models.model_intent_classification_input import (
        ModelIntentClassificationInput,
    )
    from omniintelligence.nodes.node_intent_classifier_compute.models.model_intent_classification_output import (
        ModelIntentClassificationOutput,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Adapter Protocols
# =============================================================================


@runtime_checkable
class ProtocolEventBusPublish(Protocol):
    """Minimal protocol for event bus publish capability.

    Matches the publish signature used by EventBusKafka and EventBusInmemory.
    """

    async def publish(self, *, topic: str, key: bytes | None, value: bytes) -> None: ...


# =============================================================================
# AdapterPatternRepositoryRuntime
# =============================================================================


class AdapterPatternRepositoryRuntime:
    """Wraps PostgresRepositoryRuntime implementing ProtocolPatternRepository.

    Delegates fetch/fetchrow/execute to the runtime's underlying pool while
    preventing accidental use of driver-specific methods. This adapter
    sits behind the ONEX effect boundary -- all DB access flows through
    the infra layer.

    Note:
        Each call acquires and releases a connection from the pool.  There is
        no cross-call transaction guarantee.  Handlers relying on atomicity
        should use optimistic locking and idempotency patterns.
    """

    __slots__ = ("_runtime",)

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        self._runtime = runtime

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        """Execute query and return all rows via the runtime pool."""
        rows = await self._runtime._pool.fetch(query, *args)
        # Convert DB Records to dicts for protocol compatibility
        return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        """Execute query and return first row, or None."""
        row = await self._runtime._pool.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def execute(self, query: str, *args: object) -> str:
        """Execute query and return status string."""
        result = await self._runtime._pool.execute(query, *args)
        return str(result)


# Keep the old name as an alias for backwards compatibility in tests
AdapterPatternRepositoryPostgres = AdapterPatternRepositoryRuntime


# =============================================================================
# AdapterIdempotencyStoreInfra
# =============================================================================


class AdapterIdempotencyStoreInfra:
    """Bridges omnibase_infra idempotency store to intelligence ProtocolIdempotencyStore.

    The intelligence domain ProtocolIdempotencyStore expects:
        - check_and_record(request_id: UUID) -> bool  (True=duplicate)
        - exists(request_id: UUID) -> bool
        - record(request_id: UUID) -> None

    The omnibase_infra ProtocolIdempotencyStore expects:
        - check_and_record(message_id, domain, correlation_id) -> bool  (True=NEW)
        - is_processed(message_id, domain) -> bool
        - mark_processed(message_id, domain, correlation_id, processed_at) -> None

    This adapter bridges the interface differences, including the INVERTED
    boolean semantics of check_and_record (infra returns True for NEW,
    intelligence expects True for DUPLICATE).
    """

    __slots__ = ("_store",)

    def __init__(self, store: InfraProtocolIdempotencyStore) -> None:
        self._store = store

    async def check_and_record(self, request_id: UUID) -> bool:
        """Atomically check and record request_id.

        Returns:
            True if this is a DUPLICATE (already existed).
            False if this is NEW (just recorded).
        """
        # Infra returns True for NEW, intelligence expects True for DUPLICATE
        is_new = await self._store.check_and_record(
            message_id=request_id,
            domain="pattern_lifecycle",
        )
        return not is_new

    async def exists(self, request_id: UUID) -> bool:
        """Check if request_id has been recorded."""
        return await self._store.is_processed(
            message_id=request_id,
            domain="pattern_lifecycle",
        )

    async def record(self, request_id: UUID) -> None:
        """Record request_id as processed."""
        await self._store.mark_processed(
            message_id=request_id,
            domain="pattern_lifecycle",
        )


# Keep old name as alias for backwards compatibility in tests
AdapterIdempotencyStorePostgres = AdapterIdempotencyStoreInfra


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

    def __init__(self, event_bus: ProtocolEventBusPublish) -> None:
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
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
        await self._event_bus.publish(topic=topic, key=key_bytes, value=value_bytes)


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
        config: ModelClassificationConfig | None = None,
    ) -> None:
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
        )

        self._config = config if config is not None else DEFAULT_CLASSIFICATION_CONFIG

    async def compute(
        self,
        input_data: ModelIntentClassificationInput,
    ) -> ModelIntentClassificationOutput:
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
    "AdapterIdempotencyStoreInfra",
    "AdapterIdempotencyStorePostgres",
    "AdapterIntentClassifier",
    "AdapterKafkaPublisher",
    "AdapterPatternRepositoryPostgres",
    "AdapterPatternRepositoryRuntime",
    "ProtocolEventBusPublish",
]
