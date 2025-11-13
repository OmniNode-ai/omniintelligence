"""
Qdrant Vector Database Adapter

High-performance vector operations adapter for Qdrant with quality-weighted indexing
and advanced similarity search capabilities.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
import numpy as np
from models.search_models import EntityType, SearchRequest, SearchResult
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    Match,
    MatchAny,
    MatchValue,
    PointStruct,
    Range,
    SearchParams,
    VectorParams,
)


# Safe entity type normalization function
def normalize_entity_type(entity_type):
    """
    Safe entity type normalization that avoids typing.Union issues.

    Args:
        entity_type: String or EntityType enum value

    Returns:
        EntityType enum value
    """
    # If it's already an EntityType enum, return it
    if isinstance(entity_type, EntityType):
        return entity_type

    # If it's a string, try to convert it
    if isinstance(entity_type, str):
        entity_type_lower = entity_type.lower()

        # Direct mapping for common types
        type_mapping = {
            "document": EntityType.DOCUMENT,
            "source": EntityType.SOURCE,
            "project": EntityType.PROJECT,
            "page": EntityType.PAGE,
            "code_example": EntityType.CODE_EXAMPLE,
            "function": EntityType.FUNCTION,
            "class": EntityType.CLASS,
            "variable": EntityType.VARIABLE,
            "entity": EntityType.ENTITY,
        }

        # Try direct mapping first
        if entity_type_lower in type_mapping:
            return type_mapping[entity_type_lower]

        # Try to match with EntityType enum values
        try:
            for enum_value in EntityType:
                if enum_value.value == entity_type_lower:
                    return enum_value
        except Exception:
            pass

        # Default fallback
        return EntityType.ENTITY

    # For any other type, default to ENTITY
    return EntityType.ENTITY


def _convert_glob_to_regex(path_pattern: str) -> str:
    """
    Convert glob pattern to regex pattern for path matching.

    Args:
        path_pattern: Glob pattern (e.g., "services/**/*.py")

    Returns:
        Regex pattern string

    Examples:
        >>> _convert_glob_to_regex("services/**/*.py")
        'services/.*/[^/]*\\.py'
        >>> _convert_glob_to_regex("*.py")
        '[^/]*\\.py'
    """
    import re

    # First, replace glob patterns with placeholders to protect them
    # This prevents the dots in ** from being escaped
    # Handle **/ as a unit to avoid double slashes
    escaped = path_pattern
    escaped = escaped.replace("**/", "<<<GLOBSTAR_SLASH>>>")
    escaped = escaped.replace("**", "<<<GLOBSTAR>>>")
    escaped = escaped.replace("*", "<<<STAR>>>")
    escaped = escaped.replace("?", "<<<QUESTION>>>")

    # Now escape regex special characters
    regex_special_chars = r"\.+^$()[]{}|"
    for char in regex_special_chars:
        escaped = escaped.replace(char, "\\" + char)

    # Convert glob placeholders to regex
    # **/ matches zero or more directory levels (as a unit)
    escaped = escaped.replace("<<<GLOBSTAR_SLASH>>>", "(?:.*/)?")
    # ** matches zero or more directory levels (at end of pattern)
    escaped = escaped.replace("<<<GLOBSTAR>>>", ".*")
    # * matches any characters except /
    escaped = escaped.replace("<<<STAR>>>", "[^/]*")
    # ? matches single character
    escaped = escaped.replace("<<<QUESTION>>>", ".")

    return escaped


def _matches_path_pattern(file_path: str, pattern: str) -> bool:
    """
    Check if a file path matches a glob pattern.

    This is used for client-side filtering when Qdrant doesn't support
    regex matching natively in filters.

    Args:
        file_path: File path to check
        pattern: Glob pattern (e.g., "services/**/*.py")

    Returns:
        True if path matches pattern, False otherwise

    Examples:
        >>> _matches_path_pattern("services/search/app.py", "services/**/*.py")
        True
        >>> _matches_path_pattern("tests/test_foo.py", "services/**/*.py")
        False
        >>> _matches_path_pattern("app.py", "*.py")
        True
        >>> _matches_path_pattern("services/app.py", "*.py")
        False
    """
    import re

    regex_pattern = _convert_glob_to_regex(pattern)

    # If pattern contains **, it can match anywhere in the path
    # Otherwise, anchor it to match the full path
    if "**" in pattern or pattern.startswith("*"):
        # For patterns with ** or starting with *, match anywhere
        # But if it doesn't start with **, anchor to start
        if not pattern.startswith("**") and not pattern.startswith("*"):
            # Pattern like "services/**/*.py" - anchor to start
            regex_pattern = "^" + regex_pattern
        # If it ends with a specific pattern, anchor to end
        if not pattern.endswith("**"):
            regex_pattern = regex_pattern + "$"
    else:
        # For simple patterns without **, match full path
        regex_pattern = "^" + regex_pattern + "$"

    return bool(re.match(regex_pattern, file_path))


def _build_path_pattern_filter(path_pattern: str) -> Optional[str]:
    """
    Build path pattern for filtering (returns pattern for client-side filtering).

    Note: Qdrant doesn't natively support regex in filters, so we return the pattern
    to be used for client-side filtering after vector search. The embedding-based
    approach (with path emphasis) handles the primary ranking.

    Args:
        path_pattern: Glob pattern for matching file paths. Supports:
            - ** : Match any subdirectories (e.g., "services/**/*.py")
            - *  : Match any characters except / (e.g., "services/*.py")
            - ?  : Match single character (e.g., "test_?.py")

    Returns:
        Pattern string for client-side filtering, or None if pattern invalid

    Examples:
        >>> _build_path_pattern_filter("services/intelligence/*.py")
        'services/intelligence/*.py'
        >>> _build_path_pattern_filter("**/models/*.py")
        '**/models/*.py'
    """
    if not path_pattern:
        return None

    try:
        # Validate pattern by converting to regex
        _convert_glob_to_regex(path_pattern)
        return path_pattern
    except Exception as e:
        logger.warning(f"Invalid path pattern '{path_pattern}': {e}")
        return None


logger = logging.getLogger(__name__)


class QdrantAdapter:
    """
    High-performance Qdrant vector database adapter.

    Provides advanced vector search capabilities with:
    1. Quality-weighted vector indexing
    2. High-performance similarity search (<100ms for 10K+ vectors)
    3. Batch processing for large-scale indexing
    4. ONEX compliance scoring integration
    """

    def __init__(
        self,
        qdrant_url: str = "http://qdrant:6333",
        embedding_dim: Optional[int] = None,
        collection_name: str = "archon_vectors",
        quality_collection: str = "quality_vectors",
    ):
        """
        Initialize Qdrant adapter.

        Args:
            qdrant_url: Qdrant service URL
            embedding_dim: Embedding vector dimension (reads from EMBEDDING_DIMENSIONS env if not provided)
            collection_name: Primary collection name
            quality_collection: Quality-weighted collection name
        """
        self.qdrant_url = qdrant_url.rstrip("/")
        # Read from environment if not explicitly provided
        self.embedding_dim = (
            embedding_dim
            if embedding_dim is not None
            else int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        )
        self.collection_name = collection_name
        self.quality_collection = quality_collection

        # Initialize Qdrant client
        self.client = QdrantClient(url=qdrant_url)
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def initialize(self):
        """Initialize collections and ensure proper setup"""
        try:
            await self._ensure_collections_exist()
            logger.info("Qdrant adapter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant adapter: {e}")
            raise

    async def close(self):
        """Close connections and cleanup"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Qdrant adapter closed")

    def _build_payload(
        self, entity_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build Qdrant payload from entity metadata.

        Args:
            entity_id: Unique entity identifier
            metadata: Entity metadata dictionary

        Returns:
            Qdrant-compatible payload dictionary with all fields
        """
        payload = {
            "entity_id": entity_id,
            "entity_type": metadata.get("entity_type", "entity"),
            "title": metadata.get("title", ""),
            "content": metadata.get("content", ""),
            "url": metadata.get("url"),
            "source_id": metadata.get("source_id"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "chunk_number": metadata.get("chunk_number", 0),
            # Quality and ONEX fields
            "quality_score": metadata.get("quality_score"),
            "onex_compliance": metadata.get("onex_compliance"),
            "onex_type": metadata.get("onex_type"),
            "concepts": metadata.get("concepts", []),
            "themes": metadata.get("themes", []),
            "relative_path": metadata.get("relative_path"),
            "project_name": metadata.get("project_name"),
            "project_id": metadata.get("project_id"),
            "content_hash": metadata.get("content_hash"),
            # Language field
            "language": metadata.get("language", "unknown"),
            # Pattern intelligence fields
            "pattern_type": metadata.get("pattern_type"),
            "pattern_name": metadata.get("pattern_name"),
            "pattern_confidence": metadata.get("pattern_confidence"),
            "node_types": metadata.get("node_types", []),
            "use_cases": metadata.get("use_cases", []),
            "examples": metadata.get("examples", []),
            "file_path": metadata.get("file_path"),
        }
        return payload

    async def _ensure_collections_exist(self):
        """Ensure required collections exist with proper configuration"""
        collections = [
            {
                "name": self.collection_name,
                "description": "Main document embeddings with metadata",
            },
            {
                "name": self.quality_collection,
                "description": "Quality-weighted vectors with ONEX compliance scores",
            },
        ]

        for collection_info in collections:
            try:
                # Check if collection exists
                collection_exists = False
                try:
                    self.client.get_collection(collection_info["name"])
                    collection_exists = True
                    logger.info(f"Collection {collection_info['name']} already exists")
                except:
                    pass

                if not collection_exists:
                    # Create collection with optimized HNSW parameters
                    self.client.create_collection(
                        collection_name=collection_info["name"],
                        vectors_config=VectorParams(
                            size=self.embedding_dim,
                            distance=Distance.COSINE,
                            hnsw_config=models.HnswConfigDiff(
                                m=32,  # Increased connections for better recall
                                ef_construct=128,  # Reduced for faster indexing
                                full_scan_threshold=20000,  # Higher threshold for brute force
                                max_indexing_threads=0,  # Use all available cores
                            ),
                        ),
                        optimizers_config=models.OptimizersConfigDiff(
                            default_segment_number=4,  # More segments for better parallelism
                            max_segment_size=500000,  # Smaller segments for faster search
                            memmap_threshold=100000,  # Earlier memory mapping for performance
                            indexing_threshold=5000,  # Earlier indexing for faster search
                            flush_interval_sec=10,  # Less frequent flushes to reduce I/O
                        ),
                    )
                    logger.info(f"Created collection {collection_info['name']}")

            except Exception as e:
                logger.error(
                    f"Failed to ensure collection {collection_info['name']}: {e}"
                )
                raise

    async def index_vectors(
        self,
        vectors: List[Tuple[str, np.ndarray, Dict[str, Any]]],
        collection_name: Optional[str] = None,
        quality_scores: Optional[List[float]] = None,
    ) -> int:
        """
        Index multiple vectors with metadata.

        Args:
            vectors: List of (entity_id, vector, metadata) tuples
            collection_name: Target collection (defaults to main collection)
            quality_scores: Optional quality scores for quality-weighted indexing

        Returns:
            Number of successfully indexed vectors
        """
        if not vectors:
            logger.debug("[QDRANT STORAGE] index_vectors called with empty vector list")
            return 0

        collection = collection_name or self.collection_name
        import time

        start_time = time.time()

        # Log start of indexing operation
        logger.info(
            f"📊 [QDRANT STORAGE] Starting vector indexing | "
            f"vector_count={len(vectors)} | "
            f"collection={collection} | "
            f"with_quality_scores={quality_scores is not None} | "
            f"entity_ids={[v[0] for v in vectors[:5]]}"
        )

        try:
            points = []
            for i, (entity_id, vector, metadata) in enumerate(vectors):
                # Log before each vector preparation
                logger.debug(
                    f"📊 [QDRANT STORAGE] Preparing vector {i+1}/{len(vectors)} | "
                    f"entity_id={entity_id} | "
                    f"vector_dim={len(vector)} | "
                    f"entity_type={metadata.get('entity_type', 'unknown')}"
                )

                # Prepare payload with metadata using centralized builder
                payload = self._build_payload(entity_id, metadata)

                # Override quality scores if explicitly provided (for backward compatibility)
                if quality_scores and i < len(quality_scores):
                    payload["quality_score"] = quality_scores[i]
                    payload["onex_compliance"] = quality_scores[i]  # For compatibility
                    logger.debug(
                        f"📊 [QDRANT STORAGE] Added quality score | "
                        f"entity_id={entity_id} | "
                        f"quality_score={quality_scores[i]:.3f}"
                    )

                # Create point
                point_id = str(uuid4())
                point = PointStruct(
                    id=point_id,  # Generate unique UUID for Qdrant
                    vector=vector.tolist(),
                    payload=payload,
                )
                points.append(point)

                logger.debug(
                    f"✅ [QDRANT STORAGE] Point prepared | "
                    f"point_id={point_id} | "
                    f"entity_id={entity_id} | "
                    f"payload_fields={list(payload.keys())}"
                )

            # Log before batch upsert
            logger.info(
                f"📊 [QDRANT STORAGE] Executing batch upsert | "
                f"collection={collection} | "
                f"point_count={len(points)} | "
                f"wait=True"
            )

            # Batch upsert for performance
            upsert_result = self.client.upsert(
                collection_name=collection,
                points=points,
                wait=True,  # Wait for operation completion
            )

            duration_ms = (time.time() - start_time) * 1000
            indexed_count = len(points)

            # Log successful upsert
            logger.info(
                f"✅ [QDRANT STORAGE] Vector indexing completed | "
                f"collection={collection} | "
                f"indexed={indexed_count} | "
                f"duration_ms={duration_ms:.2f} | "
                f"upsert_operation_id={getattr(upsert_result, 'operation_id', 'N/A')} | "
                f"status={getattr(upsert_result, 'status', 'N/A')}"
            )

            return indexed_count

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"❌ [QDRANT STORAGE] Failed to index vectors | "
                f"collection={collection} | "
                f"vector_count={len(vectors)} | "
                f"duration_ms={duration_ms:.2f} | "
                f"error={str(e)} | "
                f"error_type={type(e).__name__}",
                exc_info=True,
            )
            return 0

    async def index_entity(
        self,
        entity_id: str,
        vector: np.ndarray,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None,
    ) -> bool:
        """
        Index a single entity vector with metadata.

        Args:
            entity_id: Unique entity identifier
            vector: Pre-computed embedding vector
            metadata: Entity metadata
            collection_name: Target collection (defaults to main collection)

        Returns:
            True if indexing successful
        """
        try:
            # Index the single vector
            indexed_count = await self.index_vectors(
                [(entity_id, vector, metadata)], collection_name=collection_name
            )
            return indexed_count > 0

        except Exception as e:
            logger.error(f"Failed to index entity {entity_id}: {e}")
            return False

    async def batch_index_entities(
        self,
        entities: List[Tuple[str, str, Dict[str, Any]]],
        embedding_generator,
        batch_size: int = 50,
        quality_scorer=None,
    ) -> int:
        """
        Index entities with automatic embedding generation and quality scoring.

        Args:
            entities: List of (entity_id, content, metadata) tuples
            embedding_generator: Function to generate embeddings from content
            batch_size: Batch size for processing
            quality_scorer: Optional function to calculate quality scores

        Returns:
            Number of successfully indexed entities
        """
        total_indexed = 0

        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]

            try:
                # Generate embeddings for batch
                batch_vectors = []
                batch_quality_scores = []

                for entity_id, content, metadata in batch:
                    # Generate embedding
                    embedding = await embedding_generator(content)
                    if embedding is None:
                        logger.warning(f"Failed to generate embedding for {entity_id}")
                        continue

                    batch_vectors.append((entity_id, embedding, metadata))

                    # Calculate quality score if scorer provided
                    if quality_scorer:
                        quality_score = await quality_scorer(content, metadata)
                        batch_quality_scores.append(quality_score)

                # Index the batch
                if batch_vectors:
                    # Index in main collection
                    main_indexed = await self.index_vectors(batch_vectors)
                    total_indexed += main_indexed

                    # Index in quality collection if quality scores available
                    if quality_scorer and batch_quality_scores:
                        quality_indexed = await self.index_vectors(
                            batch_vectors,
                            collection_name=self.quality_collection,
                            quality_scores=batch_quality_scores,
                        )
                        logger.debug(
                            f"Indexed {quality_indexed} vectors in quality collection"
                        )

                # Small delay between batches to avoid overwhelming
                if i + batch_size < len(entities):
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to process batch {i}-{i+batch_size}: {e}")
                continue

        logger.info(f"Batch indexed {total_indexed}/{len(entities)} entities")
        return total_indexed

    def build_metadata_filter(
        self, filters: Optional[Dict[str, Any]]
    ) -> Optional[Filter]:
        """
        Build Qdrant filter from metadata dictionary.

        Args:
            filters: Metadata filters with key-value pairs. Supports:
                - Exact match: {"language": "python", "file_type": "source"}
                - Range queries: {"quality_score": {"gte": 0.8, "lte": 1.0}}
                - List match (any): {"tags": ["api", "performance"]}

        Returns:
            Qdrant Filter object or None if no filters provided

        Examples:
            >>> # Exact match
            >>> build_metadata_filter({"language": "python"})
            >>> # Range query
            >>> build_metadata_filter({"quality_score": {"gte": 0.8}})
            >>> # Combined filters
            >>> build_metadata_filter({
            ...     "language": "python",
            ...     "quality_score": {"gte": 0.7}
            ... })
        """
        if not filters:
            return None

        conditions = []

        for key, value in filters.items():
            try:
                if isinstance(value, dict):
                    # Range query (e.g., {"gte": 0.8, "lte": 1.0})
                    range_conditions = {}

                    if "gte" in value:
                        range_conditions["gte"] = value["gte"]
                    if "gt" in value:
                        range_conditions["gt"] = value["gt"]
                    if "lte" in value:
                        range_conditions["lte"] = value["lte"]
                    if "lt" in value:
                        range_conditions["lt"] = value["lt"]

                    if range_conditions:
                        conditions.append(
                            FieldCondition(key=key, range=Range(**range_conditions))
                        )

                elif isinstance(value, list):
                    # Match any value in list
                    conditions.append(
                        FieldCondition(key=key, match=MatchAny(any=value))
                    )

                else:
                    # Exact match for string, number, boolean
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to build filter condition for {key}={value}: {e}"
                )
                continue

        # Return combined filter or None if no valid conditions
        return Filter(must=conditions) if conditions else None

    async def similarity_search(
        self,
        query_vector: np.ndarray,
        request: SearchRequest,
        collection_name: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Perform high-performance similarity search.

        Args:
            query_vector: Query embedding vector
            request: Search request with parameters
            collection_name: Target collection (defaults to main collection)

        Returns:
            List of similar search results with <100ms response time
        """
        collection = collection_name or self.collection_name
        start_time = time.time()

        try:
            # Build filter conditions
            filter_conditions = []

            # Entity type filter (with error handling for Union type issues)
            if request.entity_types:
                try:
                    entity_types = [
                        et.value if hasattr(et, "value") else str(et)
                        for et in request.entity_types
                    ]
                    filter_conditions.append(
                        FieldCondition(key="entity_type", match=Match(any=entity_types))
                    )
                except Exception as e:
                    logger.warning(f"Skipping entity_types filter due to error: {e}")
                    # Continue without entity type filtering

            # Source filter
            if request.source_ids:
                filter_conditions.append(
                    FieldCondition(key="source_id", match=Match(any=request.source_ids))
                )

            # Quality score filter (if using quality collection)
            if collection == self.quality_collection and hasattr(
                request, "min_quality_score"
            ):
                filter_conditions.append(
                    FieldCondition(
                        key="quality_score",
                        range=Range(gte=getattr(request, "min_quality_score", 0.0)),
                    )
                )

            # Add metadata filters if provided
            if hasattr(request, "filters") and request.filters:
                metadata_filter = self.build_metadata_filter(request.filters)
                if metadata_filter and metadata_filter.must:
                    filter_conditions.extend(metadata_filter.must)

            # Combine filters
            query_filter = Filter(must=filter_conditions) if filter_conditions else None

            # Perform search with optimized parameters
            search_result = self.client.search(
                collection_name=collection,
                query_vector=query_vector.tolist(),
                query_filter=query_filter,
                limit=min(
                    request.max_semantic_results, 1000
                ),  # Cap at reasonable limit
                score_threshold=request.semantic_threshold,
                search_params=SearchParams(
                    hnsw_ef=64,  # Reduced search width for faster queries
                    exact=False,  # Use approximate search for speed
                ),
            )

            # Convert to SearchResult objects
            results = []
            for point in search_result:
                payload = point.payload

                result = SearchResult(
                    entity_id=payload.get("entity_id", ""),
                    entity_type=normalize_entity_type(
                        payload.get("entity_type", "entity")
                    ),
                    title=payload.get("title", "Untitled"),
                    content=payload.get("content") if request.include_content else None,
                    url=payload.get("url"),
                    relevance_score=float(point.score),
                    semantic_score=float(point.score),
                    source_id=payload.get("source_id"),
                    project_id=payload.get("project_id"),
                    created_at=payload.get("created_at"),
                    updated_at=payload.get("updated_at"),
                    # Quality and ONEX fields
                    quality_score=payload.get("quality_score"),
                    onex_compliance=payload.get("onex_compliance"),
                    onex_type=payload.get("onex_type"),
                    concepts=payload.get("concepts"),
                    themes=payload.get("themes"),
                    relative_path=payload.get("relative_path"),
                    project_name=payload.get("project_name"),
                    content_hash=payload.get("content_hash"),
                    # Pattern intelligence fields
                    pattern_type=payload.get("pattern_type"),
                    pattern_name=payload.get("pattern_name"),
                    pattern_confidence=payload.get("pattern_confidence"),
                    node_types=payload.get("node_types"),
                    use_cases=payload.get("use_cases"),
                    examples=payload.get("examples"),
                    file_path=payload.get("file_path"),
                )
                results.append(result)

            # Apply client-side path pattern filtering if specified
            if hasattr(request, "path_pattern") and request.path_pattern:
                path_pattern = _build_path_pattern_filter(request.path_pattern)
                if path_pattern:
                    original_count = len(results)
                    results = [
                        r
                        for r in results
                        if r.file_path
                        and _matches_path_pattern(r.file_path, path_pattern)
                    ]
                    logger.debug(
                        f"Path pattern filter '{path_pattern}' reduced results "
                        f"from {original_count} to {len(results)}"
                    )

            search_time = (time.time() - start_time) * 1000
            logger.info(
                f"Qdrant similarity search completed in {search_time:.2f}ms, "
                f"found {len(results)} results"
            )

            return results

        except Exception as e:
            logger.error(f"Qdrant similarity search failed: {e}")
            return []

    async def quality_weighted_search(
        self,
        query_vector: np.ndarray,
        request: SearchRequest,
        quality_weight: float = 0.3,
    ) -> List[SearchResult]:
        """
        Perform quality-weighted similarity search combining semantic and quality scores.

        Args:
            query_vector: Query embedding vector
            request: Search request with parameters
            quality_weight: Weight for quality scores (0.0-1.0)

        Returns:
            List of quality-weighted search results
        """
        # Search in quality collection
        results = await self.similarity_search(
            query_vector, request, self.quality_collection
        )

        # Re-weight scores combining semantic similarity and quality
        for result in results:
            if result.quality_score is not None:
                semantic_weight = 1.0 - quality_weight
                combined_score = (
                    semantic_weight * result.semantic_score
                    + quality_weight * result.quality_score
                )
                result.relevance_score = combined_score

        # Re-sort by combined score
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        return results

    async def search_patterns(
        self,
        query_vector: np.ndarray,
        query: str,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 50,
        collection_name: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search for patterns with optional filtering by type and confidence.

        Args:
            query_vector: Query embedding vector
            query: Original query text (for logging)
            pattern_type: Filter by pattern type ('code', 'execution', 'document')
            min_confidence: Minimum pattern confidence threshold (0.0-1.0)
            limit: Maximum number of results
            collection_name: Target collection (defaults to main collection)

        Returns:
            List of pattern search results with metadata
        """
        collection = collection_name or self.collection_name
        start_time = time.time()

        try:
            # Build pattern-specific filters
            filter_conditions = []

            # Filter by pattern_type if provided
            if pattern_type:
                filter_conditions.append(
                    FieldCondition(
                        key="pattern_type", match=MatchValue(value=pattern_type)
                    )
                )

            # Filter by minimum confidence
            if min_confidence > 0.0:
                filter_conditions.append(
                    FieldCondition(
                        key="pattern_confidence", range=Range(gte=min_confidence)
                    )
                )

            # Combine filters
            query_filter = Filter(must=filter_conditions) if filter_conditions else None

            # Perform search with pattern filters
            search_result = self.client.search(
                collection_name=collection,
                query_vector=query_vector.tolist(),
                query_filter=query_filter,
                limit=limit,
                score_threshold=0.0,  # No score threshold for pattern search
                search_params=SearchParams(
                    hnsw_ef=64,
                    exact=False,
                ),
            )

            # Convert to SearchResult objects
            results = []
            for point in search_result:
                payload = point.payload

                result = SearchResult(
                    entity_id=payload.get("entity_id", ""),
                    entity_type=normalize_entity_type(
                        payload.get("entity_type", "entity")
                    ),
                    title=payload.get("title", "Untitled"),
                    content=payload.get("content"),
                    url=payload.get("url"),
                    relevance_score=float(point.score),
                    semantic_score=float(point.score),
                    source_id=payload.get("source_id"),
                    project_id=payload.get("project_id"),
                    created_at=payload.get("created_at"),
                    updated_at=payload.get("updated_at"),
                    # Quality and ONEX fields
                    quality_score=payload.get("quality_score"),
                    onex_compliance=payload.get("onex_compliance"),
                    onex_type=payload.get("onex_type"),
                    concepts=payload.get("concepts"),
                    themes=payload.get("themes"),
                    relative_path=payload.get("relative_path"),
                    project_name=payload.get("project_name"),
                    content_hash=payload.get("content_hash"),
                    # Pattern intelligence fields
                    pattern_type=payload.get("pattern_type"),
                    pattern_name=payload.get("pattern_name"),
                    pattern_confidence=payload.get("pattern_confidence"),
                    node_types=payload.get("node_types"),
                    use_cases=payload.get("use_cases"),
                    examples=payload.get("examples"),
                    file_path=payload.get("file_path"),
                )
                results.append(result)

            search_time = (time.time() - start_time) * 1000
            logger.info(
                f"Pattern search completed in {search_time:.2f}ms, "
                f"found {len(results)} patterns | "
                f"pattern_type={pattern_type} | min_confidence={min_confidence}"
            )

            return results

        except Exception as e:
            logger.error(f"Pattern search failed: {e}")
            return []

    async def get_similar_entities(
        self,
        entity_id: str,
        limit: int = 10,
        threshold: float = 0.7,
        collection_name: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Find entities similar to a reference entity.

        Args:
            entity_id: Reference entity ID
            limit: Maximum number of similar entities
            threshold: Minimum similarity threshold
            collection_name: Target collection

        Returns:
            List of (entity_id, similarity_score) tuples
        """
        collection = collection_name or self.collection_name

        try:
            # First, find the reference entity vector
            scroll_result = self.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="entity_id", match=Match(value=entity_id))]
                ),
                limit=1,
                with_vectors=True,
            )

            if not scroll_result[0]:  # No points found
                logger.warning(
                    f"Entity {entity_id} not found in collection {collection}"
                )
                return []

            reference_point = scroll_result[0][0]
            reference_vector = reference_point.vector

            # Search for similar entities
            search_result = self.client.search(
                collection_name=collection,
                query_vector=reference_vector,
                limit=limit + 1,  # +1 to exclude the reference entity itself
                score_threshold=threshold,
            )

            # Filter out the reference entity and return results
            similar_entities = []
            for point in search_result:
                similar_entity_id = point.payload.get("entity_id")
                if similar_entity_id != entity_id:
                    similar_entities.append((similar_entity_id, float(point.score)))

            return similar_entities[:limit]

        except Exception as e:
            logger.error(f"Failed to find similar entities for {entity_id}: {e}")
            return []

    async def get_collection_stats(
        self, collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get collection statistics and performance metrics"""
        collection = collection_name or self.collection_name

        try:
            info = self.client.get_collection(collection)
            return {
                "collection_name": collection,
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "segments_count": len(info.segments) if info.segments else 0,
                "disk_data_size": info.disk_data_size,
                "ram_data_size": info.ram_data_size,
                "config": {
                    "distance": info.config.params.vectors.distance.name,
                    "vector_size": info.config.params.vectors.size,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats for {collection}: {e}")
            return {}

    async def health_check(self) -> bool:
        """Check if Qdrant service is available and responsive"""
        try:
            # Use Qdrant's readiness endpoint instead of generic /health
            response = await self.http_client.get(
                f"{self.qdrant_url}/readyz", timeout=5.0
            )
            if response.status_code == 200:
                # Double-check with liveness endpoint
                liveness_response = await self.http_client.get(
                    f"{self.qdrant_url}/livez", timeout=5.0
                )
                return liveness_response.status_code == 200
            return False
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    async def optimize_collection(self, collection_name: Optional[str] = None):
        """Optimize collection for better search performance"""
        collection = collection_name or self.collection_name

        try:
            # Trigger optimization
            self.client.update_collection(
                collection_name=collection,
                optimizer_config=models.OptimizersConfigDiff(
                    indexing_threshold=1000,  # Lower threshold for faster indexing
                    flush_interval_sec=5,  # More frequent flushes
                ),
            )
            logger.info(f"Triggered optimization for collection {collection}")
        except Exception as e:
            logger.error(f"Failed to optimize collection {collection}: {e}")
