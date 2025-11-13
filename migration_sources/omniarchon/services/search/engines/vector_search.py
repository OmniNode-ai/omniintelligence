"""
Vector Search Engine for Semantic Similarity

Handles vector embeddings and semantic search using embedding service (vLLM).
Enhanced with Qdrant integration for high-performance vector operations.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from engines.embedding_client import EmbeddingClient, create_embedding_client
from engines.qdrant_adapter import QdrantAdapter
from engines.search_cache import get_search_cache
from models.search_models import SearchRequest, SearchResult
from sklearn.metrics.pairwise import cosine_similarity

# Import timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from config import get_http_timeout

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """
    Vector search engine using embedding service (vLLM) for semantic similarity.
    Enhanced with Qdrant integration for high-performance vector operations.

    Provides semantic search capabilities by:
    1. Generating embeddings for queries and content
    2. High-performance vector storage and retrieval with Qdrant
    3. Quality-weighted indexing with ONEX compliance scoring
    4. Batch processing for large-scale indexing
    """

    def __init__(
        self,
        embedding_base_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        qdrant_url: str = "http://qdrant:6333",
        use_qdrant: bool = True,
        client_type: str = "auto",
    ):
        """
        Initialize vector search engine.

        Args:
            embedding_base_url: Embedding service URL (reads from EMBEDDING_MODEL_URL env if not provided)
            embedding_model: Embedding model name (reads from EMBEDDING_MODEL env if not provided)
            embedding_dim: Embedding vector dimension (reads from EMBEDDING_DIMENSIONS env if not provided)
            qdrant_url: Qdrant service URL
            use_qdrant: Whether to use Qdrant for vector storage
            client_type: "ollama", "openai", or "auto" (auto-detect)
        """
        # Read configuration from environment if not explicitly provided
        self.embedding_base_url = (
            embedding_base_url
            or os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")
        ).rstrip("/")
        self.embedding_model = embedding_model or os.getenv(
            "EMBEDDING_MODEL", "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
        )
        self.embedding_dim = (
            embedding_dim
            if embedding_dim is not None
            else int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        )
        self.use_qdrant = use_qdrant
        self.http_client = httpx.AsyncClient(timeout=get_http_timeout("search"))

        # Create polymorphic embedding client
        self.embedding_client: EmbeddingClient = create_embedding_client(
            base_url=self.embedding_base_url,
            model=self.embedding_model,
            http_client=self.http_client,
            timeout=get_http_timeout("search"),
            client_type=client_type,
        )

        # Qdrant is now required - no fallback mode
        if not self.use_qdrant:
            raise ValueError(
                "Qdrant vector database is required. "
                "In-memory fallback has been disabled to ensure proper vector operations. "
                "Please set use_qdrant=True and ensure Qdrant is running."
            )

        self.qdrant_adapter = QdrantAdapter(
            qdrant_url=qdrant_url, embedding_dim=embedding_dim
        )

        # Initialize empty vector cache for compatibility
        # This ensures existing methods can still reference _vector_cache
        self._vector_cache = {}

        # Search cache for embedding optimization
        self.search_cache = None

    async def initialize(self):
        """Initialize vector search engine - Qdrant is required"""
        try:
            # Qdrant adapter must be initialized - no fallback
            await self.qdrant_adapter.initialize()

            # Initialize search cache for embedding optimization
            try:
                self.search_cache = await get_search_cache()
                if self.search_cache:
                    logger.info("Vector search engine initialized with caching support")
                else:
                    logger.warning("Search cache not available for vector engine")
            except Exception as e:
                logger.warning(f"Failed to initialize search cache: {e}")

            logger.info("Vector search engine initialized successfully with Qdrant")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant vector database: {e}")
            logger.error("Vector search engine requires Qdrant - no fallback available")
            raise RuntimeError(
                f"Qdrant vector database initialization failed: {e}. "
                "Please ensure Qdrant is running and properly configured."
            ) from e

    async def close(self):
        """Close HTTP client and Qdrant adapter"""
        if self.http_client:
            await self.http_client.aclose()
        if self.qdrant_adapter:
            await self.qdrant_adapter.close()

    async def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding vector for text using polymorphic embedding client.

        Args:
            text: Input text to embed

        Returns:
            Numpy array of embedding vector or None if failed
        """
        # Check cache first for performance optimization
        if self.search_cache:
            cached_embedding = await self.search_cache.get_cached_embedding(
                text=text, model=self.embedding_model
            )
            if cached_embedding is not None:
                logger.debug(f"Using cached embedding for text (length: {len(text)})")
                return cached_embedding

        try:
            # Use polymorphic embedding client
            embedding_array = await self.embedding_client.generate_embedding(text)

            if embedding_array is None:
                return None

            # Cache the generated embedding for future use (async, don't wait)
            if self.search_cache:
                asyncio.create_task(
                    self.search_cache.cache_embedding(
                        text=text,
                        model=self.embedding_model,
                        embedding=embedding_array,
                        ttl=86400,  # Cache embeddings for 24 hours
                    )
                )

            return embedding_array

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def generate_embeddings(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        Generate embedding vectors for multiple texts using embedding service.

        Args:
            texts: List of input texts to embed

        Returns:
            List of numpy arrays (embedding vectors) or None for failed embeddings
        """
        try:
            # Process texts concurrently with some throttling
            batch_size = 5  # Limit concurrent requests to embedding service
            embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                # Create tasks for concurrent embedding generation
                tasks = [self.generate_embedding(text) for text in batch]
                batch_embeddings = await asyncio.gather(*tasks, return_exceptions=True)

                # Handle results and exceptions
                for embedding in batch_embeddings:
                    if isinstance(embedding, Exception):
                        logger.error(f"Batch embedding error: {embedding}")
                        embeddings.append(None)
                    else:
                        embeddings.append(embedding)

                # Small delay between batches to avoid overwhelming Ollama
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)

    async def index_entity(
        self, entity_id: str, content: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Index an entity for vector search.

        Args:
            entity_id: Unique entity identifier
            content: Content to embed and index
            metadata: Entity metadata (type, title, url, etc.)

        Returns:
            True if indexing successful
        """
        try:
            # Fail fast if Qdrant is not available - no fallback mode for individual indexing
            if not (self.use_qdrant and self.qdrant_adapter):
                raise RuntimeError(
                    "Qdrant vector database is required for entity indexing. "
                    "In-memory fallback has been disabled to ensure proper vector storage. "
                    "Please ensure Qdrant is running and properly configured."
                )

            # Generate embedding for content
            embedding = await self.generate_embedding(content)
            if embedding is None:
                return False

            # Index directly to Qdrant using the adapter
            success = await self.qdrant_adapter.index_entity(
                entity_id, embedding, metadata
            )
            if success:
                logger.debug(
                    f"Indexed entity {entity_id} with embedding shape {embedding.shape}"
                )
            return success

        except Exception as e:
            logger.error(f"Failed to index entity {entity_id}: {e}")
            return False

    async def batch_index_entities(
        self, entities: List[Tuple[str, str, Dict[str, Any]]], quality_scorer=None
    ) -> int:
        """
        Index multiple entities in batch with optional quality scoring.

        Args:
            entities: List of (entity_id, content, metadata) tuples
            quality_scorer: Optional function to calculate quality scores

        Returns:
            Number of successfully indexed entities
        """
        # Use Qdrant batch indexing if available
        if self.use_qdrant and self.qdrant_adapter:
            return await self.qdrant_adapter.batch_index_entities(
                entities=entities,
                embedding_generator=self.generate_embedding,
                batch_size=50,  # Larger batch for Qdrant
                quality_scorer=quality_scorer,
            )

        # Fail fast if Qdrant is not available - no fallback mode
        raise RuntimeError(
            "Qdrant vector database is required for batch indexing. "
            "In-memory fallback has been disabled to ensure proper vector storage. "
            "Please ensure Qdrant is running and properly configured."
        )

    async def semantic_search(
        self, query: str, request: SearchRequest
    ) -> List[SearchResult]:
        """
        Perform semantic vector search with Qdrant or fallback to in-memory.

        Args:
            query: Search query text
            request: Search request with parameters

        Returns:
            List of semantically similar search results
        """
        start_time = time.time()

        try:
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            if query_embedding is None:
                logger.error("Failed to generate query embedding")
                return []

            # Use Qdrant if available
            if self.use_qdrant and self.qdrant_adapter:
                results = await self.qdrant_adapter.similarity_search(
                    query_embedding, request
                )
                search_time = (time.time() - start_time) * 1000
                logger.info(
                    f"Qdrant semantic search completed in {search_time:.2f}ms, found {len(results)} results"
                )
                return results

            # Fail fast if Qdrant is not available - no fallback mode
            raise RuntimeError(
                "Qdrant vector database is required for semantic search. "
                "In-memory fallback has been disabled to ensure proper vector operations. "
                "Please ensure Qdrant is running and properly configured."
            )

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def get_similar_entities(
        self, entity_id: str, limit: int = 10, threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Find entities similar to a given entity using Qdrant.

        Args:
            entity_id: Reference entity ID
            limit: Maximum number of similar entities
            threshold: Minimum similarity threshold

        Returns:
            List of (entity_id, similarity_score) tuples
        """
        try:
            # Use Qdrant for similar entity search if available
            if self.use_qdrant and self.qdrant_adapter:
                return await self.qdrant_adapter.get_similar_entities(
                    entity_id, limit, threshold
                )

            # Fallback: check if entity exists in local cache
            if entity_id not in self._vector_cache:
                logger.warning(
                    f"Entity {entity_id} not found - Qdrant unavailable and not in local cache"
                )
                return []

            reference_embedding = self._vector_cache[entity_id]
            similarities = []

            for other_id, other_embedding in self._vector_cache.items():
                if other_id == entity_id:
                    continue

                similarity = cosine_similarity(
                    reference_embedding.reshape(1, -1), other_embedding.reshape(1, -1)
                )[0][0]

                if similarity >= threshold:
                    similarities.append((other_id, similarity))

            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:limit]

        except Exception as e:
            logger.error(f"Failed to find similar entities for {entity_id}: {e}")
            return []

    async def quality_weighted_search(
        self, query: str, request: SearchRequest, quality_weight: float = 0.3
    ) -> List[SearchResult]:
        """
        Perform quality-weighted similarity search.

        Args:
            query: Search query text
            request: Search request with parameters
            quality_weight: Weight for quality scores (0.0-1.0)

        Returns:
            List of quality-weighted search results
        """
        if self.use_qdrant and self.qdrant_adapter:
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            if query_embedding is None:
                logger.error("Failed to generate query embedding")
                return []

            # Perform quality-weighted search using Qdrant
            return await self.qdrant_adapter.quality_weighted_search(
                query_embedding, request, quality_weight
            )
        else:
            # Fallback to regular semantic search for in-memory mode
            logger.warning(
                "Quality-weighted search not available without Qdrant, using semantic search"
            )
            return await self.semantic_search(query, request)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get vector cache statistics"""
        stats = {
            "use_qdrant": self.use_qdrant,
            "embedding_dimension": self.embedding_dim,
            "in_memory_entities": (
                len(self._vector_cache) if hasattr(self, "_vector_cache") else 0
            ),
            "memory_usage_mb": (
                (
                    sum(embedding.nbytes for embedding in self._vector_cache.values())
                    / 1024
                    / 1024
                )
                if hasattr(self, "_vector_cache") and self._vector_cache
                else 0.0
            ),
        }

        # Add Qdrant stats if available
        if self.use_qdrant and self.qdrant_adapter:
            try:
                # Note: This would need to be made async in practice
                stats["qdrant_available"] = True
            except:
                stats["qdrant_available"] = False

        return stats

    async def health_check(self) -> Dict[str, bool]:
        """Check health of embedding service and Qdrant"""
        health_status = {
            "embedding_service_connected": False,
            "qdrant_connected": False,
        }

        try:
            # Use polymorphic embedding client for health check
            health_status["embedding_service_connected"] = (
                await self.embedding_client.health_check()
            )
        except Exception as e:
            logger.debug(f"Embedding service health check failed: {e}")
            health_status["embedding_service_connected"] = False

        try:
            # Check Qdrant if enabled
            if self.use_qdrant and self.qdrant_adapter:
                health_status["qdrant_connected"] = (
                    await self.qdrant_adapter.health_check()
                )
            else:
                health_status["qdrant_connected"] = None  # Not configured
        except:
            pass

        return health_status
