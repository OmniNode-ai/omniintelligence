"""
ONEX Qdrant Service Layer

Provides high-level service interface for Qdrant vector operations with
automatic client management and configuration.
"""

import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from .config import ONEXQdrantConfig, get_config
from .contracts.qdrant_contracts import (
    ModelContractQdrantHealthEffect,
    ModelContractQdrantSearchEffect,
    ModelContractQdrantUpdateEffect,
    ModelContractQdrantVectorIndexEffect,
    ModelQdrantHealthResult,
    ModelQdrantSearchResult,
    ModelQdrantUpdateResult,
    ModelResultQdrantVectorIndexEffect,
    QdrantIndexPoint,
)
from .effects.node_qdrant_health_effect import NodeQdrantHealthEffect
from .effects.node_qdrant_search_effect import NodeQdrantSearchEffect
from .effects.node_qdrant_update_effect import NodeQdrantUpdateEffect
from .effects.node_qdrant_vector_index_effect import NodeQdrantVectorIndexEffect

logger = logging.getLogger(__name__)


class ONEXQdrantService:
    """
    High-level service for ONEX Qdrant vector operations.

    Manages:
    - Client lifecycle (Qdrant + OpenAI)
    - Effect node instantiation
    - Configuration management
    - Resource cleanup
    """

    def __init__(self, config: Optional[ONEXQdrantConfig] = None):
        """
        Initialize the ONEX Qdrant service.

        Args:
            config: Optional configuration. If None, loads from environment.
        """
        self.config = config or get_config()

        # Initialize clients
        self.qdrant_client = AsyncQdrantClient(
            url=self.config.qdrant.url,
            api_key=self.config.qdrant.api_key,
        )

        self.openai_client = AsyncOpenAI(
            api_key=self.config.openai.api_key,
            max_retries=self.config.openai.max_retries,
            timeout=self.config.openai.timeout,
        )

        # Initialize effect nodes
        self.index_effect = NodeQdrantVectorIndexEffect(
            qdrant_client=self.qdrant_client,
            openai_client=self.openai_client,
        )

        self.search_effect = NodeQdrantSearchEffect(
            qdrant_client=self.qdrant_client,
            openai_client=self.openai_client,
        )

        self.update_effect = NodeQdrantUpdateEffect(
            qdrant_client=self.qdrant_client,
            openai_client=self.openai_client,
        )

        self.health_effect = NodeQdrantHealthEffect(
            qdrant_client=self.qdrant_client,
        )

        logger.info("ONEXQdrantService initialized successfully")

    async def close(self):
        """Close all client connections and cleanup resources."""
        await self.qdrant_client.close()
        await self.openai_client.close()
        logger.info("ONEXQdrantService closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()

    # =========================================================================
    # High-Level API Methods
    # =========================================================================

    async def index_patterns(
        self,
        patterns: List[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> ModelResultQdrantVectorIndexEffect:
        """
        Index multiple patterns with automatic embedding generation.

        Args:
            patterns: List of pattern dictionaries with 'text' and metadata
            collection_name: Optional collection name (uses default if None)

        Returns:
            Index result with counts and performance metrics

        Example:
            >>> patterns = [
            ...     {"text": "User authentication pattern", "type": "security"},
            ...     {"text": "Database connection pooling", "type": "performance"}
            ... ]
            >>> result = await service.index_patterns(patterns)
        """
        collection = collection_name or self.config.qdrant.collection_name

        # Convert patterns to QdrantIndexPoint models
        points = [QdrantIndexPoint(payload=pattern) for pattern in patterns]

        # Validate batch size
        if len(points) > self.config.performance.max_batch_size:
            logger.warning(
                f"Batch size {len(points)} exceeds maximum {self.config.performance.max_batch_size}. "
                f"Consider processing in smaller batches."
            )

        contract = ModelContractQdrantVectorIndexEffect(
            collection_name=collection,
            points=points,
        )

        return await self.index_effect.execute_effect(contract)

    async def search_patterns(
        self,
        query_text: str,
        collection_name: Optional[str] = None,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        hnsw_ef: Optional[int] = None,
    ) -> ModelQdrantSearchResult:
        """
        Perform semantic search for similar patterns.

        Args:
            query_text: Search query text
            collection_name: Optional collection name (uses default if None)
            limit: Maximum results (uses default if None)
            score_threshold: Minimum similarity score (0.0-1.0)
            filters: Optional Qdrant filters
            hnsw_ef: Optional HNSW search parameter for speed/accuracy trade-off

        Returns:
            Search results with hits and performance metrics

        Example:
            >>> result = await service.search_patterns(
            ...     "authentication security",
            ...     limit=5,
            ...     score_threshold=0.7
            ... )
        """
        collection = collection_name or self.config.qdrant.collection_name
        result_limit = limit or self.config.performance.default_search_limit

        search_params = None
        if hnsw_ef:
            search_params = {"hnsw_ef": hnsw_ef}
        elif not search_params:
            search_params = {"hnsw_ef": self.config.performance.default_hnsw_ef}

        contract = ModelContractQdrantSearchEffect(
            collection_name=collection,
            query_text=query_text,
            limit=result_limit,
            score_threshold=score_threshold,
            filters=filters,
            search_params=search_params,
        )

        return await self.search_effect.execute_effect(contract)

    async def update_pattern(
        self,
        point_id: str,
        collection_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        text_for_embedding: Optional[str] = None,
    ) -> ModelQdrantUpdateResult:
        """
        Update an existing pattern's metadata and/or embedding.

        Args:
            point_id: ID of the point to update
            collection_name: Optional collection name (uses default if None)
            payload: Updated metadata payload
            text_for_embedding: New text to generate embedding from (optional)

        Returns:
            Update result with status and performance metrics

        Example:
            >>> result = await service.update_pattern(
            ...     point_id="123e4567-e89b-12d3-a456-426614174000",
            ...     payload={"type": "security", "reviewed": True}
            ... )
        """
        collection = collection_name or self.config.qdrant.collection_name

        contract = ModelContractQdrantUpdateEffect(
            collection_name=collection,
            point_id=point_id,
            payload=payload,
            text_for_embedding=text_for_embedding,
        )

        return await self.update_effect.execute_effect(contract)

    async def health_check(
        self,
        collection_name: Optional[str] = None,
    ) -> ModelQdrantHealthResult:
        """
        Check health and get statistics for Qdrant collection(s).

        Args:
            collection_name: Optional specific collection (checks all if None)

        Returns:
            Health result with service status and collection statistics

        Example:
            >>> result = await service.health_check()
            >>> if result.service_ok:
            ...     for collection in result.collections:
            ...         print(f"{collection.name}: {collection.points_count} points")
        """
        contract = ModelContractQdrantHealthEffect(
            collection_name=collection_name,
        )

        return await self.health_effect.execute_effect(contract)
