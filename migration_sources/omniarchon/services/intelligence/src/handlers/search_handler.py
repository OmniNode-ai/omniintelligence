"""
Search Event Handler

Handles SEARCH_REQUESTED events and publishes SEARCH_COMPLETED/FAILED responses.
Implements multi-source search orchestration (RAG, Vector, Knowledge Graph) with
result aggregation, ranking, and graceful degradation.

Created: 2025-10-22
Purpose: Event-driven search integration for multi-source intelligence queries
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from neo4j import GraphDatabase
from pydantic import ValidationError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.events.models.search_events import (
    EnumSearchErrorCode,
    EnumSearchType,
    ModelSearchResultItem,
    create_completed_event,
    create_failed_event,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

# Import external API validation models
from src.models.external_api import (
    MemgraphQueryResponse,
    OllamaEmbeddingResponse,
    QdrantSearchResponse,
    RAGSearchResponse,
)

logger = logging.getLogger(__name__)


class SearchHandler(BaseResponsePublisher):
    """
    Handle SEARCH_REQUESTED events and publish search results.

    This handler implements multi-source search orchestration, consuming
    search requests from the event bus and publishing aggregated results.

    Event Flow:
        1. Consume SEARCH_REQUESTED event
        2. Extract query, search_type, filters, and options
        3. Perform parallel searches across RAG, Vector, Knowledge Graph
        4. Aggregate and rank results
        5. Publish SEARCH_COMPLETED (success) or SEARCH_FAILED (error)

    Topics:
        - Request: dev.archon-intelligence.intelligence.search-requested.v1
        - Completed: dev.archon-intelligence.intelligence.search-completed.v1
        - Failed: dev.archon-intelligence.intelligence.search-failed.v1
    """

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.search-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.search-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.search-failed.v1"

    # Service endpoints
    RAG_SEARCH_URL = "http://archon-search:8055/search"
    QDRANT_URL = "http://archon-qdrant:6333"
    MEMGRAPH_URI = "bolt://archon-memgraph:7687"
    EMBEDDING_MODEL_URL = os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")

    def __init__(
        self,
        rag_search_url: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        memgraph_uri: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize Search handler.

        Args:
            rag_search_url: Optional RAG search service URL
            qdrant_url: Optional Qdrant service URL
            memgraph_uri: Optional Memgraph connection URI
            http_client: Optional HTTP client instance
        """
        super().__init__()
        self.rag_search_url = rag_search_url or self.RAG_SEARCH_URL
        self.qdrant_url = qdrant_url or self.QDRANT_URL
        self.memgraph_uri = memgraph_uri or self.MEMGRAPH_URI
        self.http_client = http_client  # Will be created on demand if None
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "searches_completed": 0,
            "searches_failed": 0,
            "cache_hits": 0,
            "rag_queries": 0,
            "vector_queries": 0,
            "kg_queries": 0,
        }

    async def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector using Ollama.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If embedding generation fails
        """
        try:
            # Create HTTP client if not provided
            if self.http_client is None:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.EMBEDDING_MODEL_URL}/api/embeddings",
                        json={
                            "model": "nomic-embed-text",
                            "prompt": text,
                        },
                    )
                    response.raise_for_status()
                    raw_data = response.json()
            else:
                response = await self.http_client.post(
                    f"{self.EMBEDDING_MODEL_URL}/api/embeddings",
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                raw_data = response.json()

            # Validate response with Pydantic model
            try:
                validated_response = OllamaEmbeddingResponse.model_validate(raw_data)
                return validated_response.embedding
            except ValidationError as ve:
                logger.error(
                    f"Ollama embedding response validation failed: {ve}. "
                    f"Raw keys: {list(raw_data.keys())}"
                )
                # Fallback: try direct extraction with warning
                if "embedding" in raw_data and isinstance(raw_data["embedding"], list):
                    logger.warning("Using unvalidated embedding as fallback")
                    return raw_data["embedding"]
                else:
                    raise ValueError(
                        f"Invalid Ollama response format. Expected 'embedding' field. "
                        f"Got: {list(raw_data.keys())}"
                    )

        except ValidationError as ve:
            logger.error(f"Embedding validation failed: {ve}")
            raise ValueError(f"Invalid embedding response: {ve}")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is SEARCH_REQUESTED
        """
        return event_type in [
            "SEARCH_REQUESTED",
            "intelligence.search-requested",
            "omninode.intelligence.event.search_requested.v1",  # Full event type from Kafka
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle SEARCH_REQUESTED event.

        Extracts search parameters from the event payload, performs multi-source
        search, aggregates results, and publishes the appropriate response event.

        Args:
            event: Event envelope with SEARCH_REQUESTED payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            # Extract required fields from payload
            query = payload.get("query")
            search_type_str = payload.get("search_type", "HYBRID")
            project_id = payload.get("project_id")
            max_results = payload.get("max_results", 10)
            filters = payload.get("filters", {})
            quality_weight = payload.get("quality_weight")
            include_context = payload.get("include_context", True)
            enable_caching = payload.get("enable_caching", True)

            # Validate required fields
            if not query:
                logger.error(
                    f"Missing query in SEARCH_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    query="",
                    search_type=EnumSearchType.HYBRID,
                    error_code=EnumSearchErrorCode.INVALID_QUERY,
                    error_message="Missing required field: query",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                self.metrics["searches_failed"] += 1
                return False

            # Parse search type enum
            try:
                search_type = EnumSearchType(search_type_str)
            except ValueError:
                search_type = EnumSearchType.HYBRID

            logger.info(
                f"Processing SEARCH_REQUESTED | correlation_id={correlation_id} | "
                f"query={query} | search_type={search_type.value} | "
                f"max_results={max_results} | project_id={project_id}"
            )

            # Perform multi-source search
            search_result = await self._perform_search(
                query=query,
                search_type=search_type,
                project_id=project_id,
                max_results=max_results,
                filters=filters,
                quality_weight=quality_weight,
                include_context=include_context,
                enable_caching=enable_caching,
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed_response(
                correlation_id=correlation_id,
                query=query,
                search_type=search_type,
                search_result=search_result,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["searches_completed"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            if search_result.get("cache_hit", False):
                self.metrics["cache_hits"] += 1

            logger.info(
                f"SEARCH_COMPLETED published | correlation_id={correlation_id} | "
                f"total_results={search_result['total_results']} | "
                f"sources={search_result['sources_queried']} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Search handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish error response
            try:
                if correlation_id:
                    # Extract payload data for error response (may not be available if early failure)
                    payload = self._get_payload(event) if event else {}
                    query = payload.get("query", "unknown")
                    search_type_str = payload.get("search_type", "HYBRID")
                    try:
                        search_type = EnumSearchType(search_type_str)
                    except ValueError:
                        search_type = EnumSearchType.HYBRID

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        query=query,
                        search_type=search_type,
                        error_code=EnumSearchErrorCode.INTERNAL_ERROR,
                        error_message=f"Search failed: {str(e)}",
                        retry_allowed=True,
                        processing_time_ms=duration_ms,
                        error_details={"exception_type": type(e).__name__},
                    )
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish error response | correlation_id={correlation_id} | "
                    f"error={publish_error}",
                    exc_info=True,
                )

            self.metrics["events_failed"] += 1
            self.metrics["searches_failed"] += 1
            return False

    async def _perform_search(
        self,
        query: str,
        search_type: EnumSearchType,
        project_id: Optional[str],
        max_results: int,
        filters: Dict[str, Any],
        quality_weight: Optional[float],
        include_context: bool,
        enable_caching: bool,
    ) -> Dict[str, Any]:
        """
        Perform multi-source search with graceful degradation.

        Args:
            query: Search query text
            search_type: Type of search to perform
            project_id: Optional project filter
            max_results: Maximum results to return
            filters: Search filters
            quality_weight: Optional quality weight
            include_context: Include context in results
            enable_caching: Enable caching

        Returns:
            Search result dictionary with aggregated results
        """
        service_timings = {}
        all_results = []
        sources_queried = []
        failed_services = []

        # Determine which sources to query based on search_type
        should_query_rag = search_type in [
            EnumSearchType.SEMANTIC,
            EnumSearchType.HYBRID,
        ]
        should_query_vector = search_type in [
            EnumSearchType.VECTOR,
            EnumSearchType.HYBRID,
        ]
        should_query_kg = search_type in [
            EnumSearchType.KNOWLEDGE_GRAPH,
            EnumSearchType.HYBRID,
        ]

        # Query all sources in parallel
        tasks = []
        if should_query_rag:
            tasks.append(self._search_rag(query, max_results, filters))
        if should_query_vector:
            tasks.append(self._search_vector(query, max_results, filters))
        if should_query_kg:
            tasks.append(self._search_knowledge_graph(query, max_results, filters))

        # Execute all searches in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process RAG results
            if should_query_rag:
                rag_result = results[0] if len(results) > 0 else Exception("No result")
                if isinstance(rag_result, Exception):
                    logger.warning(f"RAG search failed: {rag_result}")
                    failed_services.append("rag")
                else:
                    all_results.extend(rag_result["results"])
                    sources_queried.append("rag")
                    service_timings["rag_search_ms"] = rag_result["timing_ms"]
                    self.metrics["rag_queries"] += 1
                results = results[1:] if len(results) > 1 else []

            # Process Vector results
            if should_query_vector:
                vector_result = (
                    results[0] if len(results) > 0 else Exception("No result")
                )
                if isinstance(vector_result, Exception):
                    logger.warning(f"Vector search failed: {vector_result}")
                    failed_services.append("vector")
                else:
                    all_results.extend(vector_result["results"])
                    sources_queried.append("vector")
                    service_timings["vector_search_ms"] = vector_result["timing_ms"]
                    self.metrics["vector_queries"] += 1
                results = results[1:] if len(results) > 1 else []

            # Process Knowledge Graph results
            if should_query_kg:
                kg_result = results[0] if len(results) > 0 else Exception("No result")
                if isinstance(kg_result, Exception):
                    logger.warning(f"Knowledge graph search failed: {kg_result}")
                    failed_services.append("knowledge_graph")
                else:
                    all_results.extend(kg_result["results"])
                    sources_queried.append("knowledge_graph")
                    service_timings["knowledge_graph_ms"] = kg_result["timing_ms"]
                    self.metrics["kg_queries"] += 1

        # If all sources failed, raise error
        if not sources_queried:
            raise ValueError(f"All search sources failed: {failed_services}")

        # Deduplicate and rank results
        ranking_start = time.perf_counter()
        ranked_results = self._deduplicate_and_rank(
            all_results, max_results, quality_weight
        )
        service_timings["ranking_ms"] = (time.perf_counter() - ranking_start) * 1000

        return {
            "total_results": len(ranked_results),
            "results": ranked_results,
            "sources_queried": sources_queried,
            "service_timings": service_timings,
            "cache_hit": False,  # TODO: Implement caching
            "aggregation_strategy": (
                "weighted_score" if quality_weight else "score_based"
            ),
        }

    async def _search_rag(
        self, query: str, max_results: int, filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search RAG service.

        Args:
            query: Search query
            max_results: Maximum results
            filters: Search filters

        Returns:
            Search results and timing
        """
        start_time = time.perf_counter()

        try:
            # Create HTTP client if not provided
            if self.http_client is None:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        self.rag_search_url,
                        json={
                            "query": query,
                            "limit": max_results,
                            "filters": filters,
                        },
                    )
                    response.raise_for_status()
                    raw_data = response.json()
            else:
                response = await self.http_client.post(
                    self.rag_search_url,
                    json={
                        "query": query,
                        "limit": max_results,
                        "filters": filters,
                    },
                )
                response.raise_for_status()
                raw_data = response.json()

            # Validate response with Pydantic model
            try:
                validated_response = RAGSearchResponse.model_validate(raw_data)

                # Convert validated results to standard format
                results = [
                    ModelSearchResultItem(
                        source_path=r.get_path(),
                        score=r.score,
                        content=r.content,
                        metadata=r.metadata.model_dump() if r.metadata else {},
                    )
                    for r in validated_response.results
                ]

                logger.debug(f"RAG search results validated: {len(results)} items")

            except ValidationError as ve:
                logger.error(f"RAG search response validation failed: {ve}")
                # Fallback: use unvalidated data with warning
                logger.warning("Using unvalidated RAG search results as fallback")
                results = [
                    ModelSearchResultItem(
                        source_path=r.get("path", r.get("source_path", "unknown")),
                        score=r.get("score", 0.8),
                        content=r.get("content", ""),
                        metadata=r.get("metadata", {}),
                    )
                    for r in raw_data.get("results", [])
                ]

            timing_ms = (time.perf_counter() - start_time) * 1000

            return {
                "results": results,
                "timing_ms": timing_ms,
            }

        except ValidationError as ve:
            logger.error(f"RAG search validation failed: {ve}")
            raise ValueError(f"Invalid RAG search response: {ve}")
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            raise

    async def _search_vector(
        self, query: str, max_results: int, filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search Qdrant vector database.

        Args:
            query: Search query
            max_results: Maximum results
            filters: Search filters

        Returns:
            Search results and timing
        """
        start_time = time.perf_counter()

        try:
            # Generate query embedding using Ollama
            query_embedding = await self._generate_embedding(query)

            # Connect to Qdrant and search
            client = QdrantClient(url=self.qdrant_url)

            # Build Qdrant filter if project_id provided
            qdrant_filter = None
            if filters.get("project_id"):
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                qdrant_filter = Filter(
                    must=[
                        FieldCondition(
                            key="project_id",
                            match=MatchValue(value=filters["project_id"]),
                        )
                    ]
                )

            # Search for similar vectors
            search_result = client.search(
                collection_name="archon_documents",
                query_vector=query_embedding,
                query_filter=qdrant_filter,
                limit=max_results,
                with_payload=True,
            )

            # Validate search results with Pydantic model
            try:
                # Convert raw Qdrant results to dict format for validation
                raw_results = [
                    {
                        "id": str(hit.id),
                        "score": hit.score,
                        "payload": hit.payload,
                    }
                    for hit in search_result
                ]

                validated_response = QdrantSearchResponse(results=raw_results)

                # Convert validated results to standard format
                results = [
                    ModelSearchResultItem(
                        source_path=(
                            point.payload.get("source_path", "unknown")
                            if point.payload
                            else "unknown"
                        ),
                        score=point.score,
                        content=(
                            point.payload.get("content", "") if point.payload else ""
                        ),
                        metadata=point.payload or {},
                    )
                    for point in validated_response.results
                ]

                logger.debug(
                    f"Qdrant vector search results validated: {len(results)} items"
                )

            except ValidationError as ve:
                logger.error(f"Qdrant search response validation failed: {ve}")
                # Fallback: use unvalidated results with warning
                logger.warning("Using unvalidated Qdrant search results as fallback")
                results = [
                    ModelSearchResultItem(
                        source_path=(
                            hit.payload.get("source_path", "unknown")
                            if hit.payload
                            else "unknown"
                        ),
                        score=hit.score,
                        content=hit.payload.get("content", "") if hit.payload else "",
                        metadata=hit.payload or {},
                    )
                    for hit in search_result
                ]

            timing_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Vector search completed: {len(results)} results in {timing_ms:.2f}ms"
            )

            return {
                "results": results,
                "timing_ms": timing_ms,
            }

        except ValidationError as ve:
            logger.error(f"Vector search validation failed: {ve}")
            raise ValueError(f"Invalid vector search response: {ve}")
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    async def _search_knowledge_graph(
        self, query: str, max_results: int, filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search Memgraph knowledge graph.

        Args:
            query: Search query
            max_results: Maximum results
            filters: Search filters

        Returns:
            Search results and timing
        """
        start_time = time.perf_counter()

        try:
            # Connect to Memgraph
            driver = GraphDatabase.driver(self.memgraph_uri)

            # Build Cypher query for entity/relationship search
            # Search for entities with names or descriptions matching the query
            cypher_query = """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($query)
               OR toLower(n.description) CONTAINS toLower($query)
               OR toLower(n.content) CONTAINS toLower($query)
            """

            # Add project filter if provided
            if filters.get("project_id"):
                cypher_query += " AND n.project_id = $project_id"

            cypher_query += """
            RETURN n.name AS name,
                   n.description AS description,
                   n.content AS content,
                   n.source_path AS source_path,
                   n.entity_type AS entity_type,
                   labels(n) AS labels
            LIMIT $limit
            """

            # Execute query
            with driver.session() as session:
                result = session.run(
                    cypher_query,
                    {
                        "query": query,
                        "project_id": filters.get("project_id"),
                        "limit": max_results,
                    },
                )

                # Collect raw results
                raw_records = []
                for record in result:
                    raw_records.append(
                        {
                            "data": {
                                "name": record.get("name"),
                                "description": record.get("description"),
                                "content": record.get("content"),
                                "source_path": record.get("source_path"),
                                "entity_type": record.get("entity_type"),
                                "labels": record.get("labels", []),
                            }
                        }
                    )

            driver.close()

            # Validate results with Pydantic model
            try:
                validated_response = MemgraphQueryResponse(records=raw_records)

                # Convert validated results to standard format
                results = []
                for record in validated_response.records:
                    # Calculate relevance score based on match quality
                    score = 0.7  # Default score for KG matches
                    name = record.get("name")
                    if name and query.lower() in name.lower():
                        score = 0.9

                    results.append(
                        ModelSearchResultItem(
                            source_path=record.get("source_path", "knowledge_graph"),
                            score=score,
                            content=record.get("content")
                            or record.get("description", ""),
                            metadata={
                                "name": name,
                                "entity_type": record.get("entity_type"),
                                "labels": record.get("labels", []),
                                "source": "knowledge_graph",
                            },
                        )
                    )

                logger.debug(f"Memgraph results validated: {len(results)} items")

            except ValidationError as ve:
                logger.error(f"Memgraph response validation failed: {ve}")
                # Fallback: use unvalidated results with warning
                logger.warning("Using unvalidated Memgraph results as fallback")
                results = []
                for raw_record in raw_records:
                    data = raw_record.get("data", {})
                    score = 0.7
                    if data.get("name") and query.lower() in data["name"].lower():
                        score = 0.9

                    results.append(
                        ModelSearchResultItem(
                            source_path=data.get("source_path", "knowledge_graph"),
                            score=score,
                            content=data.get("content") or data.get("description", ""),
                            metadata={
                                "name": data.get("name"),
                                "entity_type": data.get("entity_type"),
                                "labels": data.get("labels", []),
                                "source": "knowledge_graph",
                            },
                        )
                    )

            timing_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Knowledge graph search completed: {len(results)} results in {timing_ms:.2f}ms"
            )

            return {
                "results": results,
                "timing_ms": timing_ms,
            }

        except ValidationError as ve:
            logger.error(f"Knowledge graph validation failed: {ve}")
            raise ValueError(f"Invalid Memgraph response: {ve}")
        except Exception as e:
            logger.error(f"Knowledge graph search failed: {e}")
            raise

    def _deduplicate_and_rank(
        self,
        results: list[ModelSearchResultItem],
        max_results: int,
        quality_weight: Optional[float],
    ) -> list[ModelSearchResultItem]:
        """
        Deduplicate results by source_path and rank by score.

        Args:
            results: All search results
            max_results: Maximum results to return
            quality_weight: Optional quality weight for ranking

        Returns:
            Deduplicated and ranked results
        """
        seen_paths: Dict[str, ModelSearchResultItem] = {}

        for result in results:
            path = result.source_path
            score = result.score

            # Apply quality weighting if specified
            if quality_weight and "quality_score" in result.metadata:
                quality_score = result.metadata.get("quality_score", 0.0)
                weighted_score = (
                    1 - quality_weight
                ) * score + quality_weight * quality_score
                # Create new result with weighted score
                result = ModelSearchResultItem(
                    source_path=result.source_path,
                    score=weighted_score,
                    content=result.content,
                    metadata=result.metadata,
                )

            # Keep highest scoring result for each path
            if path not in seen_paths or seen_paths[path].score < result.score:
                seen_paths[path] = result

        # Sort by score descending
        ranked = sorted(seen_paths.values(), key=lambda x: x.score, reverse=True)

        return ranked[:max_results]

    async def _publish_completed_response(
        self,
        correlation_id: UUID,
        query: str,
        search_type: EnumSearchType,
        search_result: Dict[str, Any],
        processing_time_ms: float,
    ) -> None:
        """
        Publish SEARCH_COMPLETED event.

        Args:
            correlation_id: Correlation ID from request
            query: Original search query
            search_type: Type of search performed
            search_result: Search result dictionary
            processing_time_ms: Processing time in milliseconds
        """
        try:
            await self._ensure_router_initialized()

            # Create completed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_completed_event(
                query=query,
                search_type=search_type,
                total_results=search_result["total_results"],
                results=search_result["results"],
                sources_queried=search_result["sources_queried"],
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                service_timings=search_result.get("service_timings", {}),
                cache_hit=search_result.get("cache_hit", False),
                aggregation_strategy=search_result.get("aggregation_strategy"),
            )

            # Publish the ONEX-compliant envelope directly (no wrapper needed)
            await self._router.publish(
                topic=self.COMPLETED_TOPIC,
                event=event_envelope,  # Pass envelope dict directly
                key=str(correlation_id),
            )

            logger.info(
                f"Published SEARCH_COMPLETED | topic={self.COMPLETED_TOPIC} | "
                f"correlation_id={correlation_id} | total_results={search_result['total_results']}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_failed_response(
        self,
        correlation_id: UUID,
        query: str,
        search_type: EnumSearchType,
        error_code: EnumSearchErrorCode,
        error_message: str,
        retry_allowed: bool = False,
        processing_time_ms: float = 0.0,
        failed_services: Optional[list[str]] = None,
        partial_results: Optional[list[ModelSearchResultItem]] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish SEARCH_FAILED event.

        Args:
            correlation_id: Correlation ID from request
            query: Search query that failed
            search_type: Type of search attempted
            error_code: Error code enum value
            error_message: Human-readable error message
            retry_allowed: Whether the operation can be retried
            processing_time_ms: Time taken before failure
            failed_services: Services that failed
            partial_results: Partial results if available
            error_details: Optional error context
        """
        try:
            await self._ensure_router_initialized()

            # Create failed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_failed_event(
                query=query,
                search_type=search_type,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                failed_services=failed_services or [],
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                partial_results=partial_results,
                error_details=error_details or {},
            )

            # Publish the ONEX-compliant envelope directly (no wrapper needed)
            await self._router.publish(
                topic=self.FAILED_TOPIC,
                event=event_envelope,  # Pass envelope dict directly
                key=str(correlation_id),
            )

            logger.warning(
                f"Published SEARCH_FAILED | topic={self.FAILED_TOPIC} | "
                f"correlation_id={correlation_id} | error_code={error_code.value} | "
                f"error_message={error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "SearchHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "handler_name": self.get_handler_name(),
        }
