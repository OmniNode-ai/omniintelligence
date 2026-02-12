# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for consuming pattern.discovered events from external systems.

This handler maps ModelPatternDiscoveredEvent (from external publishers like
omniclaude) to ModelPatternStorageInput and delegates to handle_store_pattern
for actual persistence.

Two-level idempotency:
1. discovery_id: exact replay protection (same event delivered twice)
   - Mapped to pattern_id so handle_store_pattern's check_exists_by_id catches it
2. signature_hash: semantic dedup (same pattern from different sessions)
   - Handled by handle_store_pattern's lineage key (domain, signature_hash)

Reference:
    - OMN-2059: DB-SPLIT-08 own learned_patterns + add pattern.discovered consumer
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import AsyncConnection

from omniintelligence.models.events.model_pattern_discovered_event import (
    ModelPatternDiscoveredEvent,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    ProtocolPatternStore,
    handle_store_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
    ModelPatternStoredEvent,
)

logger = logging.getLogger(__name__)


def _map_discovered_to_storage_input(
    event: ModelPatternDiscoveredEvent,
) -> ModelPatternStorageInput:
    """Map a ModelPatternDiscoveredEvent to ModelPatternStorageInput.

    The discovery_id becomes the pattern_id, providing first-level
    idempotency (exact replay protection) through handle_store_pattern's
    check_exists_by_id mechanism.

    Args:
        event: The discovered pattern event from an external system.

    Returns:
        ModelPatternStorageInput ready for handle_store_pattern.
    """
    # Build metadata from discovery event fields
    #
    # Reserved keys are set explicitly below and must not be overwritten
    # by arbitrary entries in event.metadata.
    _RESERVED_KEYS: frozenset[str] = frozenset({"source_agent"})

    additional_attrs: dict[str, str] = {}
    # Copy string-valued metadata entries, skipping reserved keys
    for key, value in event.metadata.items():
        if isinstance(value, str) and key not in _RESERVED_KEYS:
            additional_attrs[key] = value
    # Explicit source_agent always wins over any metadata entry
    if event.source_agent is not None:
        additional_attrs["source_agent"] = event.source_agent

    metadata = ModelPatternStorageMetadata(
        source_run_id=str(event.source_session_id),
        actor=event.source_system,
        learning_context="pattern_discovery",
        tags=["discovered", event.source_system],
        additional_attributes=additional_attrs,
    )

    return ModelPatternStorageInput(
        pattern_id=event.discovery_id,
        signature=event.pattern_signature,
        signature_hash=event.signature_hash,
        domain=event.domain,
        confidence=event.confidence,
        correlation_id=event.correlation_id,
        version=1,
        metadata=metadata,
        learned_at=event.discovered_at,
    )


async def handle_consume_discovered(
    event: ModelPatternDiscoveredEvent,
    *,
    pattern_store: ProtocolPatternStore,
    conn: AsyncConnection,
) -> ModelPatternStoredEvent:
    """Consume a pattern.discovered event and persist it via handle_store_pattern.

    This handler provides a thin mapping layer between the external discovery
    event schema and the internal pattern storage pipeline. All governance,
    idempotency, and version management is delegated to handle_store_pattern.

    Args:
        event: The pattern discovery event from an external system.
        pattern_store: Pattern store implementing ProtocolPatternStore.
        conn: Database connection for transaction control.

    Returns:
        ModelPatternStoredEvent with storage confirmation.

    Raises:
        ValueError: If governance validation fails (e.g., confidence below threshold).
        RuntimeError: If storage operation fails unexpectedly.
    """
    logger.info(
        "Consuming pattern.discovered event",
        extra={
            "discovery_id": str(event.discovery_id),
            "domain": event.domain,
            "signature_hash": event.signature_hash,
            "source_system": event.source_system,
            "source_session_id": str(event.source_session_id),
            "confidence": event.confidence,
            "correlation_id": str(event.correlation_id),
        },
    )

    # Map discovered event to storage input
    storage_input = _map_discovered_to_storage_input(event)

    # Delegate to existing store handler (handles governance, idempotency, versioning)
    stored_event = await handle_store_pattern(
        storage_input,
        pattern_store=pattern_store,
        conn=conn,
    )

    logger.info(
        "Pattern.discovered event consumed and stored",
        extra={
            "discovery_id": str(event.discovery_id),
            "pattern_id": str(stored_event.pattern_id),
            "domain": stored_event.domain,
            "version": stored_event.version,
            "correlation_id": str(event.correlation_id),
        },
    )

    return stored_event


__all__ = [
    "handle_consume_discovered",
]
