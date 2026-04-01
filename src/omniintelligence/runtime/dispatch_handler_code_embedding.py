# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Dispatch handler for code entity embedding generation and Qdrant storage.

Generates embeddings using tiered fields (primary source-derived, secondary LLM-generated)
and stores in Qdrant for semantic search. Embedding is useful even without enrichment.

Architecture decisions:
    - Split file: NOT in dispatch_handlers.py (consistent with other split handlers)
    - Tiered fields: primary (entity_name, docstring, signature) always used;
      secondary (llm_description) appended when available
    - Point ID = entity UUID: upsert replaces, never duplicates
    - Qdrant unavailable => graceful skip (log warning, return zero counts)
    - Collection auto-creation via _ensure_collection
    - Batch timestamp update in Postgres after successful upserts

Related:
    - OMN-5665: Embedding generation and Qdrant storage
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "code_patterns"
EMBEDDING_BATCH_SIZE = 50
# Tiered fields: primary (source-derived) weighted higher
PRIMARY_FIELDS = ("entity_name", "docstring", "signature")
SECONDARY_FIELDS = ("llm_description",)


async def handle_code_embedding(
    *,
    repository: Any,  # RepositoryCodeEntity
    qdrant_client: QdrantClient | None = None,
    embedding_endpoint: str | None = None,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> dict[str, int]:
    """Generate embeddings for code entities and store in Qdrant.

    Returns dict with 'embedded_count' and 'failed_count'.
    """
    endpoint = embedding_endpoint or os.environ.get(
        "LLM_EMBEDDING_URL", "http://192.168.86.200:8100"
    )

    if qdrant_client is None:
        qdrant_host = os.environ["QDRANT_HOST"]
        qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
        try:
            qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        except Exception:
            logger.warning("Qdrant unavailable — skipping embedding")
            return {"embedded_count": 0, "failed_count": 0}

    _ensure_collection(qdrant_client)

    entities = await repository.get_entities_needing_embedding(limit=batch_size)
    if not entities:
        logger.info("No entities needing embedding")
        return {"embedded_count": 0, "failed_count": 0}

    embedded_ids: list[str] = []
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for entity in entities:
            try:
                text = build_embedding_text(entity)
                if not text.strip():
                    failed += 1
                    continue

                embedding = await _get_embedding(client, endpoint, text)
                if embedding is None:
                    failed += 1
                    continue

                point = PointStruct(
                    id=str(entity["id"]),
                    vector=embedding,
                    payload={
                        "entity_id": str(entity["id"]),
                        "entity_name": entity.get("entity_name", ""),
                        "entity_type": entity.get("entity_type", ""),
                        "qualified_name": entity.get("qualified_name", ""),
                        "source_repo": entity.get("source_repo", ""),
                        "source_path": entity.get("source_path", ""),
                        "classification": entity.get("classification"),
                        "docstring": (entity.get("docstring") or "")[:200],
                    },
                )
                qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=[point],
                )
                embedded_ids.append(str(entity["id"]))
            except Exception:
                logger.exception("Failed to embed entity %s", entity.get("entity_name"))
                failed += 1

    if embedded_ids:
        await repository.update_embedded_at(embedded_ids)

    logger.info("Embedding complete: %d embedded, %d failed", len(embedded_ids), failed)
    return {"embedded_count": len(embedded_ids), "failed_count": failed}


def build_embedding_text(entity: dict[str, Any]) -> str:
    """Build embedding text from tiered fields.

    Primary fields (source-derived, stable) are always included.
    Secondary fields (LLM-generated) are appended if available.
    """
    parts: list[str] = []

    # Primary fields
    if entity.get("entity_name"):
        parts.append(entity["entity_name"])
    if entity.get("signature"):
        parts.append(entity["signature"])
    if entity.get("docstring"):
        parts.append(entity["docstring"])

    primary_text = " ".join(parts)

    # Secondary fields (optional enrichment)
    secondary_parts: list[str] = []
    if entity.get("llm_description"):
        secondary_parts.append(entity["llm_description"])

    if secondary_parts:
        return f"{primary_text}\n{' '.join(secondary_parts)}"
    return primary_text


def _ensure_collection(client: QdrantClient) -> None:
    """Create Qdrant collection if it doesn't exist."""
    collections = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=4096,  # Qwen3-Embedding-8B dimension
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", QDRANT_COLLECTION)


async def _get_embedding(
    client: httpx.AsyncClient,
    endpoint: str,
    text: str,
) -> list[float] | None:
    """Get embedding vector from LLM endpoint."""
    try:
        response = await client.post(
            f"{endpoint}/v1/embeddings",
            json={"input": text, "model": "embedding"},
        )
        response.raise_for_status()
        data = response.json()
        embedding: list[float] = data["data"][0]["embedding"]
        return embedding
    except (httpx.HTTPError, KeyError, IndexError):
        logger.warning("Embedding generation failed")
        return None
