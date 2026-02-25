# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Production client implementations for NavigationRetrieverEffect.

These implementations wrap the actual Qwen3-Embedding client and
Qdrant client. Separated into this module to keep handler_navigation_retrieve
free of transport dependencies (ARCH-002 compliance).

Injected via dependency injection in the main handler for production use.
Replaced with mocks in tests.

Ticket: OMN-2579
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProductionNavigationEmbedder:
    """Production embedder using EmbeddingClient for Qwen3-Embedding-8B.

    Wraps the existing EmbeddingClient with the ProtocolNavigationEmbedder
    interface for dependency injection.

    Args:
        embedding_url: Base URL for the embedding server.
    """

    def __init__(self, embedding_url: str) -> None:
        self._embedding_url = embedding_url

    async def embed_text(self, text: str) -> list[float]:
        """Embed text using the production EmbeddingClient.

        Args:
            text: Text to embed.

        Returns:
            1024-dimensional embedding vector.

        Raises:
            EmbeddingClientError: On failure.
        """
        from omniintelligence.clients.embedding_client import EmbeddingClient
        from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
            ModelEmbeddingClientConfig,
        )

        config = ModelEmbeddingClientConfig(base_url=self._embedding_url)
        async with EmbeddingClient(config) as client:
            return await client.get_embedding(text)


class ProductionNavigationVectorStore:
    """Production vector store using qdrant-client for navigation paths.

    Wraps the qdrant_client library with the ProtocolNavigationVectorStore
    interface for dependency injection.

    Args:
        qdrant_url: Base URL for the Qdrant instance.
    """

    def __init__(self, qdrant_url: str) -> None:
        self._qdrant_url = qdrant_url

    async def ensure_collection(
        self, collection: str, dimension: int, distance: str
    ) -> bool:
        """Ensure the Qdrant collection exists, creating it if needed.

        Args:
            collection: Collection name.
            dimension: Embedding dimension.
            distance: Distance metric name (e.g., "Cosine").

        Returns:
            True if collection exists or was created, False on error.
        """
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams

            distance_map: dict[str, Distance] = {
                "Cosine": Distance.COSINE,
                "Euclid": Distance.EUCLID,
                "Dot": Distance.DOT,
            }
            qdrant_distance = distance_map.get(distance, Distance.COSINE)

            async with AsyncQdrantClient(url=self._qdrant_url) as client:
                collections = await client.get_collections()
                collection_names = [c.name for c in collections.collections]

                if collection not in collection_names:
                    logger.info(
                        "Creating Qdrant collection '%s' (dim=%d, distance=%s)",
                        collection,
                        dimension,
                        distance,
                    )
                    await client.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(
                            size=dimension,
                            distance=qdrant_distance,
                        ),
                    )
                    logger.info("Created Qdrant collection '%s'", collection)

                return True

        except Exception as exc:
            logger.warning(
                "Failed to ensure Qdrant collection '%s': %s", collection, exc
            )
            return False

    async def search_similar(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filter_must: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar navigation paths in Qdrant.

        Args:
            collection: Collection name.
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filter_must: Optional list of filter conditions.

        Returns:
            List of result dicts with keys: id, score, payload.
        """
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            qdrant_filter: Filter | None = None
            if filter_must:
                conditions = []
                for condition in filter_must:
                    key = condition.get("key", "")
                    match_value = condition.get("match", {}).get("value")
                    if key and match_value is not None:
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=match_value),
                            )
                        )
                if conditions:
                    qdrant_filter = Filter(must=conditions)

            async with AsyncQdrantClient(url=self._qdrant_url) as client:
                results = await client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )

            return [
                {
                    "id": str(result.id),
                    "score": result.score,
                    "payload": result.payload or {},
                }
                for result in results
            ]

        except Exception as exc:
            logger.warning(
                "Qdrant search failed for collection '%s': %s", collection, exc
            )
            return []


__all__ = [
    "ProductionNavigationEmbedder",
    "ProductionNavigationVectorStore",
]
