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
    GovernanceResult,
    ProtocolPatternStore,
    StorePatternResult,
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
    # Reserved keys are set explicitly by this mapping function (either as
    # top-level ModelPatternStorageMetadata fields or written into
    # additional_attributes).  They must not be overwritten by arbitrary
    # entries in event.metadata.
    #
    # NOTE: If a reserved key carries a non-string value it is dropped by
    # the isinstance(value, str) guard below *and* skipped by this check,
    # so the drop is silent.  This is intentional — we treat non-string
    # reserved values the same as string ones: discard them.
    _RESERVED_KEYS: frozenset[str] = frozenset(
        {
            # Written into additional_attributes explicitly
            "source_agent",
            # Top-level ModelPatternStorageMetadata fields set by this mapper
            "source_run_id",
            "actor",
            "learning_context",
            "tags",
            "additional_attributes",
        }
    )

    additional_attrs: dict[str, str] = {}
    # Copy string-valued metadata entries, skipping reserved keys
    for key, value in event.metadata.items():
        if key in _RESERVED_KEYS:
            continue
        if isinstance(value, str):
            additional_attrs[key] = value
        else:
            logger.debug(
                "Dropping non-string metadata value for key %r "
                "(type=%s, discovery_id=%s)",
                key,
                type(value).__name__,
                event.discovery_id,
            )
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
) -> ModelPatternStoredEvent | GovernanceResult:
    """Consume a pattern.discovered event and persist it via handle_store_pattern.

    This handler provides a thin mapping layer between the external discovery
    event schema and the internal pattern storage pipeline. All governance,
    idempotency, and version management is delegated to handle_store_pattern.

    Governance rejections are returned as GovernanceResult (valid=False) rather
    than raised as exceptions, following the ONEX handler pattern where domain
    errors are data, not exceptions.

    Args:
        event: The pattern discovery event from an external system.
        pattern_store: Pattern store implementing ProtocolPatternStore.
        conn: Database connection for transaction control.

    Returns:
        ModelPatternStoredEvent with storage confirmation on success, or
        GovernanceResult (valid=False) when governance validation rejects
        the pattern.

    Raises:
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
    store_result: StorePatternResult = await handle_store_pattern(
        storage_input,
        pattern_store=pattern_store,
        conn=conn,
    )

    if not store_result.success:
        logger.info(
            "Pattern.discovered event rejected by governance",
            extra={
                "discovery_id": str(event.discovery_id),
                "error": store_result.error_message,
                "violations": [
                    v.rule for v in (store_result.governance_violations or [])
                ],
                "correlation_id": str(event.correlation_id),
            },
        )
        return GovernanceResult(
            valid=False,
            violations=store_result.governance_violations or [],
        )

    stored_event = store_result.event
    assert stored_event is not None  # Invariant: success=True implies event is set

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
