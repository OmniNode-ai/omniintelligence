# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Dispatch handler for embedding code entities to Qdrant and graphing to Memgraph.

Consumes code-entities-extracted.v1 events (parallel with persist handler),
embeds entity text via LLM_EMBEDDING_URL, stores in Qdrant code_patterns
collection, and writes entity nodes + relationship edges to Memgraph.

Graceful degradation: if Qdrant or Memgraph is unavailable, logs a warning
and continues. Postgres (persist handler) is the source of truth.

Related:
    - OMN-5717: Dispatch handler — embed to Qdrant + graph to Memgraph
    - OMN-5720: AST-based code pattern extraction (epic)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

import httpx
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.contract_topics import canonical_topic_to_dispatch_alias
from omniintelligence.topics import IntentTopic

logger = logging.getLogger(__name__)

# =============================================================================
# Protocols for external clients
# =============================================================================


@runtime_checkable
class ProtocolQdrantClient(Protocol):
    """Minimal protocol for Qdrant upsert operations."""

    async def upsert(
        self,
        collection_name: str,
        points: list[Any],
    ) -> Any: ...


@runtime_checkable
class ProtocolBoltHandler(Protocol):
    """Minimal protocol for Memgraph write operations."""

    async def write(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> Any: ...


# =============================================================================
# Dispatch alias
# =============================================================================

DISPATCH_ALIAS_CODE_ENTITIES_EXTRACTED_EMBED = canonical_topic_to_dispatch_alias(
    IntentTopic.CODE_ENTITIES_EXTRACTED_EMBED
)
"""Dispatch-compatible alias for code-entities-extracted → embed+graph handler."""

QDRANT_COLLECTION = "code_patterns"
"""Qdrant collection name for code entity embeddings."""


# =============================================================================
# Handler Factory
# =============================================================================


def create_code_embed_graph_dispatch_handler(
    *,
    qdrant_client: ProtocolQdrantClient | None = None,
    bolt_handler: ProtocolBoltHandler | None = None,
    embedding_url: str | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch handler that embeds entities in Qdrant and graphs in Memgraph.

    Consumes code-entities-extracted.v1 events (same event as persist handler —
    parallel consumption).

    Args:
        qdrant_client: Optional Qdrant client for vector storage.
        bolt_handler: Optional Memgraph/Neo4j handler for graph storage.
        embedding_url: LLM embedding endpoint. Defaults to LLM_EMBEDDING_URL env var.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """
    _embedding_url = embedding_url or os.environ.get(
        "LLM_EMBEDDING_URL", "http://192.168.86.200:8100"
    )

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
            ModelCodeEntitiesExtractedEvent,
        )

        payload = envelope.payload
        if not isinstance(payload, dict):
            msg = f"Unexpected payload type {type(payload).__name__} for code-entities-extracted"
            logger.warning(msg)
            raise ValueError(msg)

        event = ModelCodeEntitiesExtractedEvent(**payload)

        # Embed entities in Qdrant
        if qdrant_client is not None:
            await _embed_entities(qdrant_client, event, _embedding_url)

        # Write to Memgraph
        if bolt_handler is not None:
            await _graph_entities(bolt_handler, event)

        logger.info(
            "Embed+graph complete: %d entities (qdrant=%s, memgraph=%s, file=%s:%s)",
            event.entity_count,
            qdrant_client is not None,
            bolt_handler is not None,
            event.repo_name,
            event.file_path,
        )

        return "ok"

    return _handle


async def _embed_entities(
    qdrant_client: ProtocolQdrantClient,
    event: Any,
    embedding_url: str,
) -> None:
    """Embed entities in Qdrant. Graceful degradation on failure."""
    try:
        points = []
        for entity in event.entities:
            # Compose text for embedding
            parts = [entity.name]
            if entity.docstring:
                parts.append(entity.docstring)
            if entity.bases:
                parts.append(f"bases: {', '.join(entity.bases)}")
            if entity.methods:
                parts.append(f"methods: {', '.join(entity.methods)}")
            text = " | ".join(parts)

            # Get embedding from LLM
            embedding = await _get_embedding(text, embedding_url)
            if embedding is None:
                continue

            points.append(
                {
                    "id": str(uuid4()),
                    "vector": embedding,
                    "payload": {
                        "entity_id": entity.entity_id,
                        "entity_type": entity.entity_type.value
                        if hasattr(entity.entity_type, "value")
                        else str(entity.entity_type),
                        "name": entity.name,
                        "file_path": entity.file_path,
                        "source_repo": entity.source_repo,
                        "line_start": entity.line_start,
                    },
                }
            )

        if points:
            await qdrant_client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=points,
            )
            logger.debug("Embedded %d entities in Qdrant", len(points))
    except Exception:
        logger.warning(
            "Qdrant embedding failed for %s:%s (graceful degradation)",
            event.repo_name,
            event.file_path,
            exc_info=True,
        )


async def _get_embedding(text: str, embedding_url: str) -> list[float] | None:
    """Get embedding vector from LLM endpoint."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{embedding_url}/v1/embeddings",
                json={"input": text, "model": "default"},
            )
            response.raise_for_status()
            embedding: list[float] = response.json()["data"][0]["embedding"]
            return embedding
    except Exception:
        logger.warning("Embedding request failed for text preview: %.50s...", text)
        return None


async def _graph_entities(
    bolt_handler: ProtocolBoltHandler,
    event: Any,
) -> None:
    """Write entity nodes and relationship edges to Memgraph. Graceful degradation."""
    try:
        # MERGE entity nodes
        for entity in event.entities:
            entity_type_str = (
                entity.entity_type.value
                if hasattr(entity.entity_type, "value")
                else str(entity.entity_type)
            )
            await bolt_handler.write(
                "MERGE (e:CodeEntity {entity_id: $entity_id}) "
                "SET e.name = $name, e.entity_type = $entity_type, "
                "e.file_path = $file_path, e.source_repo = $source_repo",
                parameters={
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "entity_type": entity_type_str,
                    "file_path": entity.file_path,
                    "source_repo": entity.source_repo,
                },
            )

        # MERGE relationship edges
        for rel in event.relationships:
            rel_type_str = (
                rel.relationship_type.value
                if hasattr(rel.relationship_type, "value")
                else str(rel.relationship_type)
            )
            await bolt_handler.write(
                "MATCH (s:CodeEntity {entity_id: $source_id}) "
                "MATCH (t:CodeEntity {entity_id: $target_id}) "
                f"MERGE (s)-[r:{rel_type_str} {{confidence: $confidence, trust_tier: $trust_tier}}]->(t)",
                parameters={
                    "source_id": rel.source_entity_id,
                    "target_id": rel.target_entity_id,
                    "confidence": rel.confidence,
                    "trust_tier": rel.trust_tier,
                },
            )

        logger.debug(
            "Wrote %d nodes, %d edges to Memgraph",
            len(event.entities),
            len(event.relationships),
        )
    except Exception:
        logger.warning(
            "Memgraph write failed for %s:%s (graceful degradation)",
            event.repo_name,
            event.file_path,
            exc_info=True,
        )


__all__ = [
    "DISPATCH_ALIAS_CODE_ENTITIES_EXTRACTED_EMBED",
    "QDRANT_COLLECTION",
    "create_code_embed_graph_dispatch_handler",
]
