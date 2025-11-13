"""
ONEX Effect Node: Qdrant Vector Indexing for Pattern Learning Phase 1

Handles embedding generation and vector indexing of execution patterns
in Qdrant with HNSW optimization for <100ms search performance.

Uses Ollama nomic-embed-text model for local embedding generation.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct, UpdateStatus

# Import contract models from same package
from src.archon_services.pattern_learning.phase1_foundation.storage.model_contract_vector_index import (
    ModelContractBatchIndexEffect,
    ModelContractVectorDeleteEffect,
    ModelContractVectorIndexEffect,
    ModelContractVectorSearchEffect,
    ModelResultBatchIndexEffect,
    ModelResultVectorDeleteEffect,
    ModelResultVectorIndexEffect,
    ModelResultVectorSearchEffect,
    ModelVectorSearchHit,
)

# Import external API validation models
from src.models.external_api import (
    OllamaEmbeddingResponse,
    QdrantSearchResponse,
    QdrantUpsertResponse,
)

logger = logging.getLogger(__name__)


class TransactionManager:
    """Simple transaction manager for ONEX compliance."""

    @asynccontextmanager
    async def begin(self):
        """Begin a transaction context."""
        try:
            yield
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise


class NodeQdrantVectorIndexEffect:
    """
    ONEX Effect node for pattern vector indexing in Qdrant.

    Performance Targets:
    - Batch 100 patterns in <2s
    - Vector search in <100ms for 1000+ patterns
    - Automatic collection creation with optimal HNSW config

    ONEX Compliance:
    - Transaction support via TransactionManager
    - Performance metrics tracking
    - Proper error handling and logging
    """

    # Configuration Constants (read from environment)
    OLLAMA_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    VECTOR_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    DISTANCE_METRIC = models.Distance.COSINE
    DEFAULT_COLLECTION = "code_generation_patterns"

    # Optimal HNSW config for <100ms search with 10K+ vectors (768 dimensions)
    HNSW_CONFIG = models.HnswConfigDiff(
        m=16,  # Max connections per layer (balance memory/recall)
        ef_construct=100,  # Search list size during indexing
        full_scan_threshold=20000,  # Use exact search if fewer points
        max_indexing_threads=0,  # Use all available cores
    )

    # Optimizer config for high performance
    OPTIMIZERS_CONFIG = models.OptimizersConfigDiff(
        default_segment_number=4,  # More segments for parallelism
        max_segment_size=500000,  # Smaller segments for faster search
        memmap_threshold=100000,  # Earlier memory mapping
        indexing_threshold=5000,  # Earlier indexing for faster search
        flush_interval_sec=10,  # Less frequent flushes
    )

    def __init__(
        self,
        qdrant_url: str = None,
        ollama_base_url: str = None,
    ):
        """
        Initialize the vector indexing effect node.

        Args:
            qdrant_url: Qdrant server URL (default: from QDRANT_URL env or http://localhost:6333)
            ollama_base_url: Ollama server base URL (default: from EMBEDDING_MODEL_URL or OLLAMA_BASE_URL env)
        """
        # Read from environment if not provided
        if qdrant_url is None:
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        if ollama_base_url is None:
            # Prefer EMBEDDING_MODEL_URL (vLLM), fallback to OLLAMA_BASE_URL
            ollama_base_url = os.getenv("EMBEDDING_MODEL_URL") or os.getenv(
                "OLLAMA_BASE_URL", "http://192.168.86.200:11434"
            )

        self.qdrant_client = AsyncQdrantClient(url=qdrant_url)
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.transaction_manager = TransactionManager()
        self._metrics: Dict[str, Any] = {}

    def _record_metric(self, key: str, value: Any) -> None:
        """Record a performance metric."""
        self._metrics[key] = value

    def get_metrics(self) -> Dict[str, Any]:
        """Get recorded performance metrics."""
        return self._metrics.copy()

    async def _ensure_collection_exists(
        self, collection_name: str, correlation_id: Optional[UUID] = None
    ) -> None:
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

    async def _generate_embeddings(
        self, texts: List[str], correlation_id: Optional[UUID] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using OpenAI-compatible API.

        Supports both vLLM (preferred) and Ollama providers.
        Uses /v1/embeddings endpoint for OpenAI compatibility.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (dimensions match VECTOR_DIMENSIONS from env)

        Raises:
            Exception: If embedding generation fails
        """
        start_time = time.perf_counter()

        try:
            embeddings = []
            async with httpx.AsyncClient(timeout=30.0) as client:
                for text in texts:
                    # Use OpenAI-compatible /v1/embeddings endpoint
                    response = await client.post(
                        f"{self.ollama_base_url}/v1/embeddings",
                        json={"model": self.OLLAMA_EMBEDDING_MODEL, "input": text},
                    )
                    response.raise_for_status()

                    # Parse OpenAI-compatible response
                    raw_data = response.json()

                    # Extract embedding from OpenAI-compatible format
                    if "data" in raw_data and len(raw_data["data"]) > 0:
                        embedding = raw_data["data"][0]["embedding"]
                        embeddings.append(embedding)
                        logger.debug(
                            f"Embedding generated: {len(embedding)} dimensions"
                        )
                    else:
                        raise ValueError(
                            f"Invalid embedding response format. Expected 'data' array. "
                            f"Got: {list(raw_data.keys())}"
                        )

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Generated {len(texts)} embeddings in {duration_ms:.2f}ms "
                f"({duration_ms/len(texts):.2f}ms per embedding)"
            )

            self._record_metric("embedding_generation_ms", duration_ms)
            self._record_metric(
                "embeddings_per_second", len(texts) / (duration_ms / 1000)
            )

            return embeddings

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def execute_effect(
        self, contract: ModelContractVectorIndexEffect
    ) -> ModelResultVectorIndexEffect:
        """
        Execute vector indexing: embed patterns and index in Qdrant.

        Args:
            contract: Index effect contract with collection name and points

        Returns:
            Result with indexed count, point IDs, and performance metrics

        Raises:
            Exception: If indexing operation fails
        """
        logger.info(
            f"Starting vector indexing for {len(contract.points)} pattern points "
            f"into collection '{contract.collection_name}'."
        )
        start_time = time.perf_counter()

        async with self.transaction_manager.begin():
            # 1. Ensure the target collection exists with optimal config
            await self._ensure_collection_exists(contract.collection_name)

            # 2. Extract texts and generate embeddings in a single batch
            texts_to_embed = [point.payload["text"] for point in contract.points]
            vectors = await self._generate_embeddings(texts_to_embed)

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
            f"Successfully indexed {len(points_to_upsert)} pattern points in "
            f"{total_duration_ms:.2f}ms ({total_duration_ms/len(points_to_upsert):.2f}ms per point)"
        )

        self._record_metric("total_duration_ms", total_duration_ms)

        return ModelResultVectorIndexEffect(
            status="success",
            indexed_count=len(points_to_upsert),
            point_ids=point_ids,
            collection_name=contract.collection_name,
            duration_ms=total_duration_ms,
        )

    async def search_similar(
        self, contract: ModelContractVectorSearchEffect
    ) -> ModelResultVectorSearchEffect:
        """
        Search for similar patterns using vector similarity.

        Args:
            contract: Search contract with query text and parameters

        Returns:
            Search results with similar patterns and scores
        """
        logger.info(
            f"Searching for similar patterns in '{contract.collection_name}' "
            f"(limit: {contract.limit}, threshold: {contract.score_threshold})"
        )
        start_time = time.perf_counter()

        # Generate query embedding
        query_embedding = (await self._generate_embeddings([contract.query_text]))[0]

        # Search Qdrant
        search_start = time.perf_counter()
        search_results = await self.qdrant_client.search(
            collection_name=contract.collection_name,
            query_vector=query_embedding,
            limit=contract.limit,
            score_threshold=contract.score_threshold,
        )
        search_duration_ms = (time.perf_counter() - search_start) * 1000

        logger.info(
            f"Vector search completed in {search_duration_ms:.2f}ms, "
            f"found {len(search_results)} results"
        )

        self._record_metric("search_duration_ms", search_duration_ms)

        # Validate search results with Pydantic model
        try:
            # Convert raw Qdrant results to dict format for validation
            raw_results = [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in search_results
            ]

            validated_response = QdrantSearchResponse(results=raw_results)

            # Convert to application format using validated data
            hits = [
                ModelVectorSearchHit(
                    id=str(point.id), score=point.score, payload=point.payload or {}
                )
                for point in validated_response.results
            ]

            logger.debug(f"Qdrant search results validated: {len(hits)} hits")

        except ValidationError as ve:
            logger.error(f"Qdrant search response validation failed: {ve}")
            # Fallback: use unvalidated results but log warning
            logger.warning("Using unvalidated search results as fallback")
            hits = [
                ModelVectorSearchHit(
                    id=str(hit.id), score=hit.score, payload=hit.payload or {}
                )
                for hit in search_results
            ]

        (time.perf_counter() - start_time) * 1000

        return ModelResultVectorSearchEffect(
            hits=hits,
            search_time_ms=search_duration_ms,
            total_results=len(hits),
            collection_name=contract.collection_name,
        )

    async def delete_pattern(
        self, contract: ModelContractVectorDeleteEffect
    ) -> ModelResultVectorDeleteEffect:
        """
        Delete pattern points from the vector index.

        Args:
            contract: Delete contract with point IDs to remove

        Returns:
            Delete result with count and status
        """
        logger.info(
            f"Deleting {len(contract.point_ids)} pattern points from "
            f"'{contract.collection_name}'"
        )
        start_time = time.perf_counter()

        async with self.transaction_manager.begin():
            # Convert UUIDs to strings for Qdrant
            point_ids_str = [str(pid) for pid in contract.point_ids]

            operation_info = await self.qdrant_client.delete(
                collection_name=contract.collection_name,
                points_selector=models.PointIdsList(points=point_ids_str),
                wait=True,
            )

            if operation_info.status != UpdateStatus.COMPLETED:
                raise Exception(
                    f"Qdrant delete failed with status: {operation_info.status}"
                )

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Successfully deleted {len(contract.point_ids)} points in {duration_ms:.2f}ms"
        )

        return ModelResultVectorDeleteEffect(
            status="success",
            deleted_count=len(contract.point_ids),
            collection_name=contract.collection_name,
            duration_ms=duration_ms,
        )

    async def batch_index(
        self, contract: ModelContractBatchIndexEffect
    ) -> ModelResultBatchIndexEffect:
        """
        Index multiple batches of patterns sequentially.

        Args:
            contract: Batch index contract with multiple batches

        Returns:
            Batch result with total counts and status
        """
        logger.info(
            f"Starting batch indexing of {len(contract.batch_points)} batches "
            f"into '{contract.collection_name}'"
        )
        start_time = time.perf_counter()

        total_indexed = 0
        batches_processed = 0
        failed_batches = 0

        for i, batch in enumerate(contract.batch_points):
            try:
                batch_contract = ModelContractVectorIndexEffect(
                    collection_name=contract.collection_name, points=batch
                )
                result = await self.execute_effect(batch_contract)
                total_indexed += result.indexed_count
                batches_processed += 1
                logger.info(f"Batch {i+1}/{len(contract.batch_points)} completed")
            except Exception as e:
                logger.error(f"Batch {i+1} failed: {e}")
                failed_batches += 1

        total_duration_ms = (time.perf_counter() - start_time) * 1000

        status = (
            "success"
            if failed_batches == 0
            else "partial_success" if batches_processed > 0 else "failure"
        )

        logger.info(
            f"Batch indexing completed: {batches_processed}/{len(contract.batch_points)} "
            f"batches successful, {total_indexed} patterns indexed in {total_duration_ms:.2f}ms"
        )

        return ModelResultBatchIndexEffect(
            status=status,
            total_indexed=total_indexed,
            batches_processed=batches_processed,
            failed_batches=failed_batches,
            total_duration_ms=total_duration_ms,
            collection_name=contract.collection_name,
        )

    async def close(self):
        """Clean up resources."""
        await self.qdrant_client.close()
