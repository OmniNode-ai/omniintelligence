"""
ONEX Effect Node: Qdrant Vector Indexing

Generates embeddings and indexes documents in Qdrant vector database with
optimal HNSW configuration for <2s batch processing of 100 patterns.
"""

import logging
import time
from typing import List

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct, UpdateStatus

from ..base.node_base_effect import NodeBaseEffect
from ..contracts.qdrant_contracts import (
    ModelContractQdrantVectorIndexEffect,
    ModelResultQdrantVectorIndexEffect,
)

logger = logging.getLogger(__name__)


class NodeQdrantVectorIndexEffect(NodeBaseEffect):
    """
    ONEX Effect node to generate embeddings and index documents in Qdrant.

    Performance Targets:
    - Batch 100 patterns in <2s
    - Embedding generation + indexing pipeline
    - Automatic collection creation with optimal HNSW config
    """

    # Configuration Constants (should be externalized in production)
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
    VECTOR_DIMENSIONS = 1536
    DISTANCE_METRIC = models.Distance.COSINE

    # Optimal HNSW config for 10K vectors with <100ms search
    HNSW_CONFIG = models.HnswConfigDiff(
        m=16,  # Max connections per layer (balance memory/recall)
        ef_construct=100,  # Search list size during indexing
        full_scan_threshold=20000,  # Use exact search if fewer points
        max_indexing_threads=0,  # Use all available cores
    )

    # Optimizer config for better performance
    OPTIMIZERS_CONFIG = models.OptimizersConfigDiff(
        default_segment_number=4,  # More segments for parallelism
        max_segment_size=500000,  # Smaller segments for faster search
        memmap_threshold=100000,  # Earlier memory mapping
        indexing_threshold=5000,  # Earlier indexing for faster search
        flush_interval_sec=10,  # Less frequent flushes
    )

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        openai_client: AsyncOpenAI,
    ):
        """
        Initialize the vector indexing effect node.

        Args:
            qdrant_client: Async Qdrant client instance
            openai_client: Async OpenAI client instance
        """
        super().__init__()
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client

    async def _ensure_collection_exists(self, collection_name: str) -> None:
        """
        Idempotently create a Qdrant collection if it doesn't exist.

        Args:
            collection_name: Name of the collection to ensure exists
        """
        try:
            await self.qdrant_client.get_collection(collection_name=collection_name)
            logger.debug(f"Collection '{collection_name}' already exists.")
        except Exception:
            logger.info(f"Collection '{collection_name}' not found. Creating...")
            await self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.VECTOR_DIMENSIONS,
                    distance=self.DISTANCE_METRIC,
                ),
                hnsw_config=self.HNSW_CONFIG,
                optimizers_config=self.OPTIMIZERS_CONFIG,
            )
            logger.info(f"Collection '{collection_name}' created successfully.")

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using OpenAI.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If embedding generation fails
        """
        start_time = time.perf_counter()
        response = await self.openai_client.embeddings.create(
            input=texts, model=self.OPENAI_EMBEDDING_MODEL
        )
        embeddings = [item.embedding for item in response.data]
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Generated {len(texts)} embeddings in {duration_ms:.2f}ms "
            f"({duration_ms/len(texts):.2f}ms per embedding)"
        )

        self._record_metric("embedding_generation_ms", duration_ms)
        self._record_metric("embeddings_per_second", len(texts) / (duration_ms / 1000))

        return embeddings

    async def execute_effect(
        self, contract: ModelContractQdrantVectorIndexEffect
    ) -> ModelResultQdrantVectorIndexEffect:
        """
        Executes the vector indexing logic: embed, ensure collection, and upsert.

        Args:
            contract: Index effect contract with collection name and points

        Returns:
            Result with indexed count, point IDs, and performance metrics

        Raises:
            Exception: If indexing operation fails
        """
        logger.info(
            f"Starting vector indexing for {len(contract.points)} points "
            f"into collection '{contract.collection_name}'."
        )
        start_time = time.perf_counter()

        async with self.transaction_manager.begin():
            # 1. Ensure the target collection exists and is configured correctly
            await self._ensure_collection_exists(contract.collection_name)

            # 2. Extract texts and generate embeddings in a single batch
            texts_to_embed = [point.payload["text"] for point in contract.points]
            vectors = await self._get_embeddings(texts_to_embed)

            # 3. Prepare Qdrant PointStructs for upserting
            point_ids = [point.id for point in contract.points]
            points_to_upsert = [
                PointStruct(id=str(point.id), vector=vector, payload=point.payload)
                for point, vector in zip(contract.points, vectors)
            ]

            # 4. Upsert points into Qdrant
            upsert_start_time = time.perf_counter()
            operation_info = await self.qdrant_client.upsert(
                collection_name=contract.collection_name,
                points=points_to_upsert,
                wait=True,  # Ensure operation is complete before returning
            )
            upsert_duration_ms = (time.perf_counter() - upsert_start_time) * 1000

            logger.info(
                f"Qdrant upsert completed in {upsert_duration_ms:.2f}ms "
                f"with status: {operation_info.status}"
            )

            if operation_info.status != UpdateStatus.COMPLETED:
                raise Exception(
                    f"Qdrant upsert failed with status: {operation_info.status}"
                )

            self._record_metric("upsert_duration_ms", upsert_duration_ms)
            self._record_metric(
                "points_per_second", len(points_to_upsert) / (upsert_duration_ms / 1000)
            )

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Successfully indexed {len(points_to_upsert)} points in {total_duration_ms:.2f}ms "
            f"({total_duration_ms/len(points_to_upsert):.2f}ms per point)"
        )

        self._record_metric("total_duration_ms", total_duration_ms)

        return ModelResultQdrantVectorIndexEffect(
            status="success",
            indexed_count=len(points_to_upsert),
            point_ids=point_ids,
            collection_name=contract.collection_name,
            duration_ms=total_duration_ms,
        )
