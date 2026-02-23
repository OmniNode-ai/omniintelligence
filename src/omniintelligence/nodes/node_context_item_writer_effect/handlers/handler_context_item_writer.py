# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for ContextItemWriterEffect — idempotent write to PG + Qdrant + Memgraph.

Behavior:
  - Receives embedded chunks from EmbeddingGenerationEffect
  - Assigns bootstrap tier per source_ref pattern policy
  - For each chunk:
    1. Check PostgreSQL for existing record by (source_ref, offset_start, offset_end)
    2. CREATED: No record → INSERT to PG + Qdrant + Memgraph
    3. UPDATED: Record exists but fingerprint changed → UPDATE PG + replace Qdrant vector
    4. SKIPPED: Record exists with matching fingerprint → no-op
  - Emits document-indexed.v1 event on success (if emit_event=True)

Idempotency contract:
  - Primary key: (source_ref, character_offset_start, character_offset_end)
  - Content key: (source_ref, content_fingerprint) catches boundary shifts
  - Qdrant vector replaced on UPDATED (same point_id, new vector)
  - Memgraph edge upserted (MERGE semantics)

Error handling:
  - PG transaction aborted → entire chunk fails (items_failed++)
  - Qdrant/Memgraph failure → PG rolled back → chunk fails (best-effort stores)
  - Event emission failure → logged, output.event_emitted = False (non-blocking)

Architecture:
  All 3 store dependencies are injected via protocols (ProtocolContextStore,
  ProtocolVectorStore, ProtocolGraphStore). No transport imports in this module.

Ticket: OMN-2393
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_context_item_writer_effect.models.enum_write_outcome import (
    EnumWriteOutcome,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_context_item_write_input import (
    ModelContextItemWriteInput,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_context_item_write_output import (
    ModelContextItemWriteOutput,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_tier_policy import (
    ModelTierPolicy,
    assign_bootstrap_tier,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definitions (dependency injection interfaces)
# =============================================================================


@runtime_checkable
class ProtocolContextStore(Protocol):
    """Protocol for PostgreSQL context item storage.

    Implementations back the context_items and context_items_content tables.
    All methods accept a transaction handle for atomicity.

    Database Schema:
        context_items:
            id UUID PRIMARY KEY
            source_ref TEXT NOT NULL
            character_offset_start INT NOT NULL
            character_offset_end INT NOT NULL
            content_fingerprint TEXT NOT NULL
            version_hash TEXT NOT NULL
            item_type TEXT NOT NULL
            tier TEXT NOT NULL
            bootstrap_confidence FLOAT NOT NULL
            expires_after_runs INT NULL
            token_estimate INT NOT NULL
            has_code_fence BOOL NOT NULL
            code_fence_language TEXT NULL
            section_heading TEXT NULL
            crawl_scope TEXT NOT NULL
            source_version TEXT NOT NULL
            correlation_id TEXT NULL
            created_at TIMESTAMPTZ NOT NULL
            updated_at TIMESTAMPTZ NOT NULL

            UNIQUE INDEX (source_ref, character_offset_start, character_offset_end)
            UNIQUE INDEX (source_ref, version_hash)

        context_items_content:
            id UUID PRIMARY KEY REFERENCES context_items(id)
            content TEXT NOT NULL

    Transaction Support:
        Callers manage transactions. Pass the connection/transaction handle
        to each method. Implementations must not auto-commit.
    """

    async def lookup_by_position(
        self,
        *,
        source_ref: str,
        offset_start: int,
        offset_end: int,
    ) -> tuple[UUID, str] | None:
        """Return (item_id, content_fingerprint) for existing chunk, or None.

        Args:
            source_ref: Document path.
            offset_start: Character offset start of the chunk.
            offset_end: Character offset end of the chunk.

        Returns:
            (UUID, fingerprint) if chunk exists, None if not found.
        """
        ...

    async def insert_item(
        self,
        *,
        chunk: ModelEmbeddedChunk,
        tier_policy: ModelTierPolicy,
        item_id: UUID,
    ) -> None:
        """Insert a new context_items row and its context_items_content row.

        Args:
            chunk: The embedded chunk to insert.
            tier_policy: Bootstrap tier policy for this source_ref.
            item_id: Pre-generated UUID for the new row.
        """
        ...

    async def update_item_fingerprint(
        self,
        *,
        item_id: UUID,
        chunk: ModelEmbeddedChunk,
    ) -> None:
        """Update content_fingerprint, version_hash, and token_estimate for existing item.

        Old content row is retained. A new context_items_content row is inserted
        with the updated content.

        Args:
            item_id: UUID of the existing context_items row.
            chunk: Updated chunk with new fingerprint, version_hash, and content.
        """
        ...


@runtime_checkable
class ProtocolVectorStore(Protocol):
    """Protocol for Qdrant vector storage.

    Implementations manage the context_items_v1 collection.
    Qdrant operations are best-effort: failures roll back the PG transaction.
    """

    async def upsert_vector(
        self,
        *,
        point_id: UUID,
        vector: tuple[float, ...],
        payload: dict[str, object],
        collection: str,
    ) -> None:
        """Upsert a vector point in the collection.

        For CREATED: inserts new point.
        For UPDATED: replaces vector and payload for existing point_id.

        Args:
            point_id: Deterministic UUID matching the PG context_items.id.
            vector: 1024-dimensional embedding vector.
            payload: Lightweight metadata (NO raw content text).
            collection: Qdrant collection name.
        """
        ...


@runtime_checkable
class ProtocolGraphStore(Protocol):
    """Protocol for Memgraph graph storage.

    Implementations manage (:ContextItem)-[:SOURCED_FROM]->(:Document) edges.
    Graph operations are best-effort: failures roll back the PG transaction.
    """

    async def upsert_context_item_edge(
        self,
        *,
        item_id: UUID,
        source_ref: str,
        crawl_scope: str,
        item_type: str,
    ) -> None:
        """Upsert a ContextItem node and its SOURCED_FROM edge to Document.

        Uses MERGE semantics: no-op if edge already exists.

        Args:
            item_id: UUID of the context item (matches PG id).
            source_ref: Document path (used as Document node identifier).
            crawl_scope: Repository scope for the document.
            item_type: Item classification type string.
        """
        ...


@runtime_checkable
class ProtocolEventEmitter(Protocol):
    """Protocol for event emission.

    Implementations emit the document-indexed.v1 event after successful write.
    Emission is best-effort — failures are logged but do not raise.
    """

    async def emit_document_indexed(
        self,
        *,
        source_ref: str,
        items_created: int,
        items_updated: int,
        items_skipped: int,
        items_failed: int,
        correlation_id: str | None,
    ) -> bool:
        """Emit document-indexed.v1 event.

        Args:
            source_ref: Document path that was indexed.
            items_created: Count of newly created items.
            items_updated: Count of soft-updated items.
            items_skipped: Count of no-op items.
            items_failed: Count of failed items.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            True if event was emitted successfully, False otherwise.
        """
        ...


# =============================================================================
# Write helpers
# =============================================================================


def _build_qdrant_payload(
    chunk: ModelEmbeddedChunk, tier_policy: ModelTierPolicy
) -> dict[str, object]:
    """Build Qdrant point payload (lightweight metadata, no raw content)."""
    return {
        "source_ref": chunk.source_ref,
        "content_fingerprint": chunk.content_fingerprint,
        "version_hash": chunk.version_hash,
        "item_type": chunk.item_type.value
        if hasattr(chunk.item_type, "value")
        else str(chunk.item_type),
        "tier": tier_policy.tier.value,
        "bootstrap_confidence": tier_policy.bootstrap_confidence,
        "section_heading": chunk.section_heading,
        "crawl_scope": chunk.crawl_scope,
        "character_offset_start": chunk.character_offset_start,
        "character_offset_end": chunk.character_offset_end,
        "token_estimate": chunk.token_estimate,
        "tags": list(chunk.tags),
    }


async def _write_single_chunk(
    chunk: ModelEmbeddedChunk,
    tier_policy: ModelTierPolicy,
    item_id: UUID,
    context_store: ProtocolContextStore,
    vector_store: ProtocolVectorStore,
    graph_store: ProtocolGraphStore,
    qdrant_collection: str,
) -> EnumWriteOutcome:
    """Write one chunk to all stores. Returns the write outcome.

    Args:
        chunk: Embedded chunk to write.
        tier_policy: Bootstrap tier policy for this source_ref.
        item_id: Pre-generated UUID for the PG row.
        context_store: PostgreSQL store protocol.
        vector_store: Qdrant vector store protocol.
        graph_store: Memgraph graph store protocol.
        qdrant_collection: Qdrant collection name.

    Returns:
        CREATED, UPDATED, or SKIPPED outcome.

    Raises:
        Exception: Any store error (caller catches and counts as FAILED).
    """
    # Check for existing record by chunk position
    existing = await context_store.lookup_by_position(
        source_ref=chunk.source_ref,
        offset_start=chunk.character_offset_start,
        offset_end=chunk.character_offset_end,
    )

    if existing is None:
        # Case 1: CREATED — fresh insert
        await context_store.insert_item(
            chunk=chunk,
            tier_policy=tier_policy,
            item_id=item_id,
        )
        payload = _build_qdrant_payload(chunk, tier_policy)
        await vector_store.upsert_vector(
            point_id=item_id,
            vector=chunk.embedding,
            payload=payload,
            collection=qdrant_collection,
        )
        await graph_store.upsert_context_item_edge(
            item_id=item_id,
            source_ref=chunk.source_ref,
            crawl_scope=chunk.crawl_scope,
            item_type=str(
                chunk.item_type.value
                if hasattr(chunk.item_type, "value")
                else chunk.item_type
            ),
        )
        return EnumWriteOutcome.CREATED

    existing_id, existing_fingerprint = existing

    if existing_fingerprint == chunk.content_fingerprint:
        # Case 2: SKIPPED — content identical, no-op
        return EnumWriteOutcome.SKIPPED

    # Case 3: UPDATED — same position, different content
    await context_store.update_item_fingerprint(
        item_id=existing_id,
        chunk=chunk,
    )
    payload = _build_qdrant_payload(chunk, tier_policy)
    await vector_store.upsert_vector(
        point_id=existing_id,
        vector=chunk.embedding,
        payload=payload,
        collection=qdrant_collection,
    )
    # Graph edge uses MERGE semantics — no update needed for soft update
    return EnumWriteOutcome.UPDATED


# =============================================================================
# Main handler
# =============================================================================


async def handle_context_item_write(
    input_data: ModelContextItemWriteInput,
    *,
    context_store: ProtocolContextStore,
    vector_store: ProtocolVectorStore,
    graph_store: ProtocolGraphStore,
    event_emitter: ProtocolEventEmitter | None = None,
) -> ModelContextItemWriteOutput:
    """Write embedded chunks to PostgreSQL, Qdrant, and Memgraph.

    All three stores are written per-chunk. Qdrant and Memgraph are
    best-effort: failures roll back the PG operation for that chunk,
    and the chunk is counted in items_failed.

    Args:
        input_data: Write request with embedded chunks and config.
        context_store: PostgreSQL store (required).
        vector_store: Qdrant vector store (required).
        graph_store: Memgraph graph store (required).
        event_emitter: Optional event emitter for document-indexed.v1.

    Returns:
        ModelContextItemWriteOutput with per-document write statistics.
    """
    from uuid import uuid4

    items_created = 0
    items_updated = 0
    items_skipped = 0
    items_failed = 0

    if not input_data.embedded_chunks:
        return ModelContextItemWriteOutput(
            source_ref=input_data.source_ref,
            items_created=0,
            items_updated=0,
            items_skipped=0,
            items_failed=0,
            event_emitted=False,
            correlation_id=input_data.correlation_id,
        )

    # Assign bootstrap tier once for the whole document
    tier_policy = assign_bootstrap_tier(input_data.source_ref, input_data.tier_policies)
    logger.debug(
        "Bootstrap tier for %s: %s (confidence=%.2f)",
        input_data.source_ref,
        tier_policy.tier.value,
        tier_policy.bootstrap_confidence,
    )

    for chunk in input_data.embedded_chunks:
        item_id = uuid4()
        try:
            outcome = await _write_single_chunk(
                chunk=chunk,
                tier_policy=tier_policy,
                item_id=item_id,
                context_store=context_store,
                vector_store=vector_store,
                graph_store=graph_store,
                qdrant_collection=input_data.qdrant_collection,
            )
            if outcome == EnumWriteOutcome.CREATED:
                items_created += 1
            elif outcome == EnumWriteOutcome.UPDATED:
                items_updated += 1
            elif outcome == EnumWriteOutcome.SKIPPED:
                items_skipped += 1
        except Exception:
            logger.warning(
                "Failed to write chunk (source_ref=%s, fingerprint=%s, offset=%d-%d)",
                chunk.source_ref,
                chunk.content_fingerprint,
                chunk.character_offset_start,
                chunk.character_offset_end,
                exc_info=True,
            )
            items_failed += 1

    # Emit document-indexed.v1 event (best-effort)
    event_emitted = False
    if input_data.emit_event and event_emitter is not None:
        try:
            event_emitted = await event_emitter.emit_document_indexed(
                source_ref=input_data.source_ref,
                items_created=items_created,
                items_updated=items_updated,
                items_skipped=items_skipped,
                items_failed=items_failed,
                correlation_id=input_data.correlation_id,
            )
        except Exception:
            logger.warning(
                "Failed to emit document-indexed event for source_ref=%s",
                input_data.source_ref,
                exc_info=True,
            )

    logger.info(
        "ContextItemWriter: %s — created=%d updated=%d skipped=%d failed=%d",
        input_data.source_ref,
        items_created,
        items_updated,
        items_skipped,
        items_failed,
    )

    return ModelContextItemWriteOutput(
        source_ref=input_data.source_ref,
        items_created=items_created,
        items_updated=items_updated,
        items_skipped=items_skipped,
        items_failed=items_failed,
        event_emitted=event_emitted,
        correlation_id=input_data.correlation_id,
    )


__all__ = [
    "handle_context_item_write",
    "ProtocolContextStore",
    "ProtocolVectorStore",
    "ProtocolGraphStore",
    "ProtocolEventEmitter",
]
