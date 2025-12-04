"""
Qdrant Vector Effect Node - ONEX Effect Node for Vector Storage in Qdrant.

This Effect node provides:
- Vector storage and retrieval in Qdrant vector database
- Collection creation and management
- Similarity search with configurable metrics
- Batch operations for efficiency
- Automatic retry logic with exponential backoff
- Connection pooling and health checks

ONEX Compliance:
- Suffix-based naming: NodeQdrantVectorEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling

Vector Flow:
1. Receive vector data (collection, operation, embeddings, metadata)
2. Connect to Qdrant server
3. Ensure collection exists (auto-create if needed)
4. Execute operation (upsert, search, delete)
5. Return result with operation metadata

Created: 2025-12-01
Reference: Vectorization Compute Node, Kafka Event Effect Node
"""

import logging
import os
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Input/Output Models (ONEX Contract Compliance)
# ============================================================================


class ModelQdrantVectorInput(BaseModel):
    """
    Input model for Qdrant vector operations.

    Attributes:
        operation: Operation type (upsert, search, delete, create_collection)
        collection: Qdrant collection name
        vector_id: Vector ID for upsert/delete operations
        embeddings: Vector embeddings (1536D for OpenAI)
        metadata: Vector metadata/payload
        search_params: Search parameters (top_k, score_threshold, filters)
        correlation_id: Correlation ID for tracing
    """

    operation: str = Field(
        ...,
        description="Operation type",
        examples=["upsert", "search", "delete", "create_collection"],
    )

    collection: str = Field(
        ...,
        description="Qdrant collection name",
        examples=["archon_vectors", "quality_vectors", "semantic_embeddings"],
    )

    vector_id: str | None = Field(
        default=None,
        description="Vector ID (required for upsert/delete)",
    )

    embeddings: list[float] | None = Field(
        default=None,
        description="Vector embeddings",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Vector metadata/payload",
    )

    search_params: dict[str, Any] | None = Field(
        default=None,
        description="Search parameters (query_vector, top_k, score_threshold, filter)",
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for tracing",
    )


class ModelQdrantVectorOutput(BaseModel):
    """
    Output model for Qdrant vector operations.

    Attributes:
        success: Whether operation succeeded
        operation: Operation that was executed
        vector_id: ID of the vector (for upsert operations)
        results: Search results (for search operation)
        error: Error message if failed
        correlation_id: Correlation ID from input
        metadata: Additional operation metadata
    """

    success: bool = Field(
        ...,
        description="Whether operation succeeded",
    )

    operation: str = Field(
        ...,
        description="Operation that was executed",
    )

    vector_id: str | None = Field(
        default=None,
        description="ID of the vector",
    )

    results: list[dict[str, Any]] | None = Field(
        default=None,
        description="Search results (for search operation)",
    )

    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from input",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional operation metadata",
    )


class ModelQdrantVectorConfig(BaseModel):
    """
    Configuration model for Qdrant vector effect node.

    Attributes:
        qdrant_url: Qdrant server URL
        qdrant_api_key: Optional API key for Qdrant Cloud
        default_collection: Default collection name
        vector_dimension: Vector dimension (default 1536 for OpenAI)
        distance_metric: Distance metric (Cosine, Euclid, Dot)
        batch_size: Batch size for bulk operations
        max_retries: Maximum retry attempts
        retry_backoff_ms: Retry backoff in milliseconds
        timeout_seconds: Request timeout in seconds
        auto_create_collection: Auto-create collection if not exists
    """

    qdrant_url: str = Field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"),
        description="Qdrant server URL",
    )

    qdrant_api_key: str | None = Field(
        default_factory=lambda: os.getenv("QDRANT_API_KEY"),
        description="Optional API key for Qdrant Cloud",
    )

    default_collection: str = Field(
        default_factory=lambda: os.getenv("QDRANT_COLLECTION", "archon_vectors"),
        description="Default collection name",
    )

    vector_dimension: int = Field(
        default=1536,
        description="Vector dimension",
    )

    distance_metric: str = Field(
        default="Cosine",
        description="Distance metric (Cosine, Euclid, Dot)",
    )

    batch_size: int = Field(
        default=100,
        description="Batch size for bulk operations",
    )

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )

    retry_backoff_ms: int = Field(
        default=1000,
        description="Retry backoff in milliseconds",
    )

    timeout_seconds: int = Field(
        default=30,
        description="Request timeout in seconds",
    )

    auto_create_collection: bool = Field(
        default=True,
        description="Auto-create collection if not exists",
    )


# ============================================================================
# Qdrant Vector Effect Node (ONEX Pattern)
# ============================================================================


class NodeQdrantVectorEffect:
    """
    Qdrant Vector Effect Node - ONEX Effect Node for Vector Storage.

    This ONEX Effect node stores and retrieves vectors in Qdrant with:
    - Vector storage with metadata (upsert operation)
    - Similarity search with configurable parameters
    - Collection creation and management
    - Batch operations for efficiency
    - Automatic retry logic with exponential backoff
    - Connection pooling for performance

    **Core Capabilities**:
    - Vector upsert: Store embeddings with metadata and deduplication
    - Similarity search: Find top-k similar vectors with score threshold
    - Collection management: Auto-create collections with proper config
    - Batch operations: Bulk upsert for efficiency
    - Connection health: Automatic health checks and reconnection

    **Operations Supported**:
    - upsert: Store or update a vector
    - search: Find similar vectors
    - delete: Remove vectors by ID
    - create_collection: Initialize collection with config

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.nodes.qdrant_vector_effect.v1_0_0.effect import (
        ...     NodeQdrantVectorEffect,
        ...     ModelQdrantVectorInput,
        ... )
        >>>
        >>> node = NodeQdrantVectorEffect(container=None)
        >>> await node.initialize()
        >>>
        >>> # Upsert a vector
        >>> input_data = ModelQdrantVectorInput(
        ...     operation="upsert",
        ...     collection="archon_vectors",
        ...     vector_id="doc-123",
        ...     embeddings=[0.1] * 1536,
        ...     metadata={
        ...         "document_id": "doc-123",
        ...         "file_path": "/path/to/file.py",
        ...         "content_hash": "abc123",
        ...     },
        ...     correlation_id=uuid4(),
        ... )
        >>>
        >>> output = await node.execute_effect(input_data)
        >>> assert output.success
        >>> assert output.vector_id == "doc-123"
        >>>
        >>> # Search similar vectors
        >>> search_input = ModelQdrantVectorInput(
        ...     operation="search",
        ...     collection="archon_vectors",
        ...     search_params={
        ...         "query_vector": [0.1] * 1536,
        ...         "top_k": 5,
        ...         "score_threshold": 0.7,
        ...     },
        ...     correlation_id=uuid4(),
        ... )
        >>>
        >>> search_output = await node.execute_effect(search_input)
        >>> assert search_output.success
        >>> assert len(search_output.results) <= 5
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Connection errors: Retry with exponential backoff
    - Collection not found: Auto-create if enabled
    - Invalid dimensions: Validate and reject
    - Timeout: Configurable timeout with retry

    Attributes:
        node_id: Unique node identifier
        config: Qdrant configuration
        client: Async Qdrant client
        metrics: Operation metrics
    """

    def __init__(
        self,
        container: Any,
        config: ModelQdrantVectorConfig | None = None,
    ):
        """
        Initialize Qdrant Vector Effect Node.

        Args:
            container: ONEX container for dependency injection
            config: Optional Qdrant configuration
        """
        self.container = container
        self.node_id = uuid4()
        self.config = config or ModelQdrantVectorConfig()

        # Qdrant client
        self.client: AsyncQdrantClient | None = None

        # Metrics
        self.metrics = {
            "vectors_upserted": 0,
            "searches_performed": 0,
            "vectors_deleted": 0,
            "collections_created": 0,
            "operations_failed": 0,
            "total_operation_time_ms": 0.0,
            "retries_attempted": 0,
        }

        logger.info(
            f"NodeQdrantVectorEffect initialized | "
            f"node_id={self.node_id} | "
            f"qdrant_url={self.config.qdrant_url} | "
            f"default_collection={self.config.default_collection}"
        )

    async def initialize(self) -> None:
        """
        Initialize Qdrant client.

        This method:
        1. Creates async Qdrant client
        2. Configures connection settings
        3. Verifies connectivity

        Raises:
            RuntimeError: If client initialization fails
        """
        try:
            self.client = AsyncQdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                timeout=self.config.timeout_seconds,
            )

            # Verify connection
            await self.client.get_collections()

            logger.info(
                f"Qdrant client initialized | "
                f"node_id={self.node_id} | "
                f"url={self.config.qdrant_url}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}", exc_info=True)
            raise RuntimeError(f"Qdrant client initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown Qdrant client.

        This method:
        1. Closes client connection
        2. Logs final metrics

        Does not raise exceptions - logs warnings on failure.
        """
        if self.client:
            try:
                await self.client.close()
                logger.info("Qdrant client connection closed")
            except Exception as e:
                logger.error(f"Error closing Qdrant client: {e}")

        logger.info(
            f"NodeQdrantVectorEffect shutdown complete | "
            f"node_id={self.node_id} | "
            f"final_metrics={self.metrics}"
        )

    async def execute_effect(
        self, input_data: ModelQdrantVectorInput
    ) -> ModelQdrantVectorOutput:
        """
        Execute Qdrant vector operation (ONEX Effect pattern method).

        This method:
        1. Validates operation and parameters
        2. Ensures collection exists (auto-create if needed)
        3. Executes operation (upsert, search, delete, create_collection)
        4. Retries on failure with exponential backoff
        5. Returns operation result

        Args:
            input_data: Qdrant vector operation input data

        Returns:
            ModelQdrantVectorOutput with operation result

        Raises:
            ValueError: If client not initialized or invalid parameters
        """
        # Check initialization
        if self.client is None:
            raise ValueError(
                "Qdrant client not initialized. Call initialize() first."
            )

        start_time = time.perf_counter()

        try:
            # Route to operation handler
            if input_data.operation == "upsert":
                result = await self._upsert_vector(input_data)
            elif input_data.operation == "search":
                result = await self._search_vectors(input_data)
            elif input_data.operation == "delete":
                result = await self._delete_vector(input_data)
            elif input_data.operation == "create_collection":
                result = await self._create_collection(input_data)
            else:
                return ModelQdrantVectorOutput(
                    success=False,
                    operation=input_data.operation,
                    error=f"Unknown operation: {input_data.operation}",
                    correlation_id=input_data.correlation_id,
                )

            # Update metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_operation_time_ms"] += elapsed_ms

            if result.success:
                logger.info(
                    f"Qdrant operation completed | "
                    f"operation={input_data.operation} | "
                    f"collection={input_data.collection} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"duration={elapsed_ms:.2f}ms"
                )
            else:
                logger.error(
                    f"Qdrant operation failed | "
                    f"operation={input_data.operation} | "
                    f"collection={input_data.collection} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"error={result.error}"
                )

            return result

        except Exception as e:
            self.metrics["operations_failed"] += 1

            logger.error(
                f"Qdrant operation error | "
                f"operation={input_data.operation} | "
                f"collection={input_data.collection} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={e}",
                exc_info=True,
            )

            return ModelQdrantVectorOutput(
                success=False,
                operation=input_data.operation,
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    @retry(
        retry=retry_if_exception_type((UnexpectedResponse, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _upsert_vector(
        self, input_data: ModelQdrantVectorInput
    ) -> ModelQdrantVectorOutput:
        """
        Upsert a vector to Qdrant collection.

        Args:
            input_data: Input data with vector and metadata

        Returns:
            Output with operation result

        Raises:
            ValueError: If required fields missing
        """
        if not input_data.vector_id:
            raise ValueError("vector_id is required for upsert operation")
        if not input_data.embeddings:
            raise ValueError("embeddings are required for upsert operation")

        # Validate vector dimension
        if len(input_data.embeddings) != self.config.vector_dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.config.vector_dimension}, "
                f"got {len(input_data.embeddings)}"
            )

        # Ensure collection exists
        await self._ensure_collection_exists(input_data.collection)

        # Type assertion for mypy
        assert self.client is not None

        # Prepare point
        point = models.PointStruct(
            id=input_data.vector_id,
            vector=input_data.embeddings,
            payload=input_data.metadata or {},
        )

        # Upsert point
        await self.client.upsert(
            collection_name=input_data.collection,
            points=[point],
        )

        self.metrics["vectors_upserted"] += 1

        return ModelQdrantVectorOutput(
            success=True,
            operation="upsert",
            vector_id=input_data.vector_id,
            correlation_id=input_data.correlation_id,
            metadata={
                "collection": input_data.collection,
                "dimension": len(input_data.embeddings),
            },
        )

    @retry(
        retry=retry_if_exception_type((UnexpectedResponse, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _search_vectors(
        self, input_data: ModelQdrantVectorInput
    ) -> ModelQdrantVectorOutput:
        """
        Search for similar vectors in Qdrant collection.

        Args:
            input_data: Input data with search parameters

        Returns:
            Output with search results

        Raises:
            ValueError: If required fields missing
        """
        if not input_data.search_params:
            raise ValueError("search_params are required for search operation")

        query_vector = input_data.search_params.get("query_vector")
        if not query_vector:
            raise ValueError("query_vector is required in search_params")

        top_k = input_data.search_params.get("top_k", 10)
        score_threshold = input_data.search_params.get("score_threshold")
        query_filter = input_data.search_params.get("filter")

        # Ensure collection exists
        await self._ensure_collection_exists(input_data.collection)

        # Type assertion for mypy
        assert self.client is not None

        # Prepare filter if provided
        qdrant_filter = None
        if query_filter:
            qdrant_filter = models.Filter(**query_filter)

        # Search using query_points (the modern API for AsyncQdrantClient)
        query_response = await self.client.query_points(
            collection_name=input_data.collection,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )

        # Format results - query_points returns QueryResponse with .points attribute
        results = [
            {
                "id": str(result.id),
                "score": result.score,
                "payload": result.payload,
            }
            for result in query_response.points
        ]

        self.metrics["searches_performed"] += 1

        return ModelQdrantVectorOutput(
            success=True,
            operation="search",
            results=results,
            correlation_id=input_data.correlation_id,
            metadata={
                "collection": input_data.collection,
                "results_count": len(results),
                "top_k": top_k,
            },
        )

    @retry(
        retry=retry_if_exception_type((UnexpectedResponse, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _delete_vector(
        self, input_data: ModelQdrantVectorInput
    ) -> ModelQdrantVectorOutput:
        """
        Delete a vector from Qdrant collection.

        Args:
            input_data: Input data with vector ID

        Returns:
            Output with operation result

        Raises:
            ValueError: If required fields missing
        """
        if not input_data.vector_id:
            raise ValueError("vector_id is required for delete operation")

        # Type assertion for mypy
        assert self.client is not None

        # Delete point
        await self.client.delete(
            collection_name=input_data.collection,
            points_selector=models.PointIdsList(
                points=[input_data.vector_id],
            ),
        )

        self.metrics["vectors_deleted"] += 1

        return ModelQdrantVectorOutput(
            success=True,
            operation="delete",
            vector_id=input_data.vector_id,
            correlation_id=input_data.correlation_id,
            metadata={
                "collection": input_data.collection,
            },
        )

    @retry(
        retry=retry_if_exception_type((UnexpectedResponse, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _create_collection(
        self, input_data: ModelQdrantVectorInput
    ) -> ModelQdrantVectorOutput:
        """
        Create a new Qdrant collection.

        Args:
            input_data: Input data with collection configuration

        Returns:
            Output with operation result
        """
        # Parse distance metric
        distance_map = {
            "Cosine": models.Distance.COSINE,
            "Euclid": models.Distance.EUCLID,
            "Dot": models.Distance.DOT,
        }
        distance = distance_map.get(
            self.config.distance_metric, models.Distance.COSINE
        )

        # Type assertion for mypy
        assert self.client is not None

        # Create collection
        await self.client.create_collection(
            collection_name=input_data.collection,
            vectors_config=models.VectorParams(
                size=self.config.vector_dimension,
                distance=distance,
            ),
        )

        self.metrics["collections_created"] += 1

        logger.info(
            f"Created Qdrant collection | "
            f"collection={input_data.collection} | "
            f"dimension={self.config.vector_dimension} | "
            f"distance={self.config.distance_metric}"
        )

        return ModelQdrantVectorOutput(
            success=True,
            operation="create_collection",
            correlation_id=input_data.correlation_id,
            metadata={
                "collection": input_data.collection,
                "dimension": self.config.vector_dimension,
                "distance": self.config.distance_metric,
            },
        )

    async def _ensure_collection_exists(self, collection_name: str) -> None:
        """
        Ensure collection exists, create if needed and auto-create enabled.

        Args:
            collection_name: Collection name to check

        Raises:
            RuntimeError: If collection doesn't exist and auto-create disabled
        """
        try:
            # Type assertion for mypy
            assert self.client is not None

            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if collection_name not in collection_names:
                if self.config.auto_create_collection:
                    logger.info(
                        f"Collection not found, auto-creating | collection={collection_name}"
                    )

                    # Parse distance metric
                    distance_map = {
                        "Cosine": models.Distance.COSINE,
                        "Euclid": models.Distance.EUCLID,
                        "Dot": models.Distance.DOT,
                    }
                    distance = distance_map.get(
                        self.config.distance_metric, models.Distance.COSINE
                    )

                    # Create collection
                    await self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=self.config.vector_dimension,
                            distance=distance,
                        ),
                    )

                    self.metrics["collections_created"] += 1
                else:
                    raise RuntimeError(
                        f"Collection '{collection_name}' does not exist and auto_create_collection is disabled"
                    )

        except Exception as e:
            logger.error(
                f"Error ensuring collection exists | collection={collection_name} | error={e}",
                exc_info=True,
            )
            raise

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - vectors_upserted: Total vectors stored
            - searches_performed: Total searches executed
            - vectors_deleted: Total vectors deleted
            - collections_created: Total collections created
            - operations_failed: Total failed operations
            - total_operation_time_ms: Cumulative operation time
            - avg_operation_time_ms: Average operation time
            - retries_attempted: Total retry attempts
        """
        total_ops = (
            self.metrics["vectors_upserted"]
            + self.metrics["searches_performed"]
            + self.metrics["vectors_deleted"]
            + self.metrics["collections_created"]
        )
        avg_operation_time = (
            self.metrics["total_operation_time_ms"] / total_ops if total_ops > 0 else 0.0
        )

        return {
            **self.metrics,
            "avg_operation_time_ms": avg_operation_time,
            "node_id": str(self.node_id),
        }


__all__ = [
    "ModelQdrantVectorConfig",
    "ModelQdrantVectorInput",
    "ModelQdrantVectorOutput",
    "NodeQdrantVectorEffect",
]
