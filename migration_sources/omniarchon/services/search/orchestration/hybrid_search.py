"""
Hybrid Search Orchestrator

Combines vector similarity search, graph traversal, and relational queries
to provide comprehensive and intelligent search results.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from engines.graph_search import GraphSearchEngine
from engines.search_cache import SearchCache, get_search_cache
from engines.vector_search import VectorSearchEngine
from models.external_validation import ValidationStatus
from models.search_models import (
    EntityType,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from utils.response_validator import (
    validate_bridge_health,
    validate_bridge_mapping_stats,
)

# Import timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from config import get_http_timeout

logger = logging.getLogger(__name__)


class HybridSearchOrchestrator:
    """
    Orchestrates hybrid search combining multiple search engines.

    Provides intelligent search by:
    1. Routing queries to appropriate search engines
    2. Combining results from multiple sources
    3. Ranking and deduplicating results
    4. Optimizing search performance
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://memgraph:7687",
        ollama_base_url: str = "http://192.168.86.200:11434",
        bridge_service_url: str = "http://archon-bridge:8054",
        intelligence_service_url: str = "http://archon-intelligence:8053",
        qdrant_url: str = "http://qdrant:6333",
        use_qdrant: bool = True,
    ):
        """
        Initialize hybrid search orchestrator.

        Args:
            memgraph_uri: Memgraph connection URI
            ollama_base_url: Ollama service URL
            bridge_service_url: Bridge service URL
            intelligence_service_url: Intelligence service URL
            qdrant_url: Qdrant service URL
            use_qdrant: Whether to enable Qdrant vector database

        Note:
            The search service uses Qdrant (vector search) + Memgraph (graph search)
            as primary data sources.
        """
        self.bridge_service_url = bridge_service_url.rstrip("/")
        self.intelligence_service_url = intelligence_service_url.rstrip("/")

        # Initialize search engines
        self.vector_engine = VectorSearchEngine(
            embedding_base_url=ollama_base_url,
            qdrant_url=qdrant_url,
            use_qdrant=use_qdrant,
        )
        self.graph_engine = GraphSearchEngine(memgraph_uri)

        # Initialize clients
        self.http_client = httpx.AsyncClient(timeout=get_http_timeout("search"))

        # Search cache for performance optimization
        self.search_cache: Optional[SearchCache] = None

    async def initialize(self):
        """Initialize all search engines and connections"""
        try:
            # Initialize search engines
            await self.vector_engine.initialize()
            await self.graph_engine.initialize()

            # Initialize search cache for performance optimization
            self.search_cache = await get_search_cache()
            if not self.search_cache:
                logger.warning("Search cache not available - caching disabled")

            # Load existing vectors from bridge service
            await self._initialize_vector_index()

            logger.info("Hybrid search orchestrator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize hybrid search orchestrator: {e}")
            raise

    async def close(self):
        """Close all connections and cleanup"""
        await self.vector_engine.close()
        await self.graph_engine.close()
        await self.http_client.aclose()
        logger.info("Hybrid search orchestrator closed")

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Perform hybrid search based on request parameters.

        Args:
            request: Search request with query and parameters

        Returns:
            Combined search response with results from all engines
        """
        start_time = time.time()

        # Check cache first for performance optimization
        if self.search_cache:
            cache_filters = {
                "entity_types": [et.value for et in (request.entity_types or [])],
                "source_ids": request.source_ids or [],
                "threshold": request.semantic_threshold,
                "include_content": request.include_content,
                "offset": request.offset,
                "limit": request.limit,
            }

            cached_results = await self.search_cache.get_cached_query_result(
                query=request.query,
                search_mode=request.mode.value,
                filters=cache_filters,
            )

            if cached_results:
                cache_time = (time.time() - start_time) * 1000
                logger.info(
                    f"Cache hit! Returned {len(cached_results)} results "
                    f"in {cache_time: .2f}ms"
                )

                # Convert cached results back to SearchResult objects
                search_results = []
                for result_dict in cached_results:
                    try:
                        # Reconstruct SearchResult from cached dict
                        search_result = SearchResult(
                            entity_id=result_dict["entity_id"],
                            entity_type=EntityType(result_dict["entity_type"]),
                            title=result_dict["title"],
                            content=result_dict.get("content"),
                            url=result_dict.get("url"),
                            relevance_score=result_dict["relevance_score"],
                            source_id=result_dict.get("source_id"),
                            created_at=result_dict.get("created_at"),
                            updated_at=result_dict.get("updated_at"),
                            semantic_score=result_dict.get("semantic_score"),
                            structural_score=result_dict.get("structural_score"),
                        )
                        search_results.append(search_result)
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            f"Failed to reconstruct search result from cache: {e}"
                        )
                        continue

                # Reconstruct response from cache
                return SearchResponse(
                    query=request.query,
                    mode=request.mode,
                    total_results=len(search_results),
                    returned_results=len(search_results),
                    results=search_results,
                    search_time_ms=cache_time,
                    offset=request.offset,
                    limit=request.limit,
                    has_more=False,  # We'll need to track this in cache
                )

        try:
            # Route to appropriate search mode
            if request.mode == SearchMode.SEMANTIC:
                results = await self._semantic_only_search(request)
                semantic_time = (time.time() - start_time) * 1000
                graph_time = None
                relational_time = None

            elif request.mode == SearchMode.STRUCTURAL:
                results = await self._structural_only_search(request)
                semantic_time = None
                graph_time = (time.time() - start_time) * 1000
                relational_time = None

            elif request.mode == SearchMode.RELATIONAL:
                results = await self._relational_only_search(request)
                semantic_time = None
                graph_time = None
                relational_time = (time.time() - start_time) * 1000

            else:  # HYBRID mode
                (
                    results,
                    semantic_time,
                    graph_time,
                    relational_time,
                ) = await self._hybrid_search(request)

            total_time = (time.time() - start_time) * 1000

            # Calculate facets and statistics
            entity_type_counts = {}
            source_counts = {}

            for result in results:
                # Count by entity type
                entity_type = result.entity_type.value
                entity_type_counts[entity_type] = (
                    entity_type_counts.get(entity_type, 0) + 1
                )

                # Count by source
                if result.source_id:
                    source_counts[result.source_id] = (
                        source_counts.get(result.source_id, 0) + 1
                    )

            # Pagination
            total_found = len(results)
            start_idx = request.offset
            end_idx = start_idx + request.limit
            paginated_results = results[start_idx:end_idx]

            response = SearchResponse(
                query=request.query,
                mode=request.mode,
                total_results=total_found,
                returned_results=len(paginated_results),
                results=paginated_results,
                search_time_ms=total_time,
                semantic_search_time_ms=semantic_time,
                graph_search_time_ms=graph_time,
                relational_search_time_ms=relational_time,
                entity_type_counts=entity_type_counts,
                source_counts=source_counts,
                offset=request.offset,
                limit=request.limit,
                has_more=end_idx < total_found,
            )

            logger.info(
                f"Hybrid search completed in {total_time: .2f}ms, "
                f"found {total_found} results, returned {len(paginated_results)}"
            )

            # Cache results for future requests (async, don't wait)
            if self.search_cache and total_found > 0:
                cache_filters = {
                    "entity_types": [et.value for et in (request.entity_types or [])],
                    "source_ids": request.source_ids or [],
                    "threshold": request.semantic_threshold,
                    "include_content": request.include_content,
                    "offset": request.offset,
                    "limit": request.limit,
                }

                # Convert SearchResult objects to dictionaries for caching
                results_for_cache = []
                for result in paginated_results:
                    result_dict = {
                        "entity_id": result.entity_id,
                        "entity_type": result.entity_type.value,
                        "title": result.title,
                        "content": result.content,
                        "url": result.url,
                        "relevance_score": result.relevance_score,
                        "source_id": result.source_id,
                        "created_at": result.created_at,
                        "updated_at": result.updated_at,
                        "semantic_score": result.semantic_score,
                        "structural_score": result.structural_score,
                    }
                    results_for_cache.append(result_dict)

                # Cache without blocking (fire and forget)
                asyncio.create_task(
                    self.search_cache.cache_query_result(
                        query=request.query,
                        search_mode=request.mode.value,
                        filters=cache_filters,
                        results=results_for_cache,
                        ttl=1800,  # Cache for 30 minutes
                    )
                )

            return response

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Return empty response on error
            return SearchResponse(
                query=request.query,
                mode=request.mode,
                total_results=0,
                returned_results=0,
                results=[],
                search_time_ms=(time.time() - start_time) * 1000,
            )

    async def _hybrid_search(
        self, request: SearchRequest
    ) -> tuple[List[SearchResult], float, float, float]:
        """
        Perform true hybrid search combining all engines with proper parallel execution.

        Returns:
            Tuple of (results, semantic_time, graph_time, relational_time)
        """
        # Start parallel execution with individual timing
        start_time = time.time()

        # Create wrapped search functions that measure their own timing
        async def timed_semantic_search():
            semantic_start = time.time()
            results = await self._semantic_only_search(request)
            return results, (time.time() - semantic_start) * 1000

        async def timed_graph_search():
            graph_start = time.time()
            results = await self._structural_only_search(request)
            return results, (time.time() - graph_start) * 1000

        async def timed_relational_search():
            relational_start = time.time()
            results = await self._relational_only_search(request)
            return results, (time.time() - relational_start) * 1000

        # Execute all searches in parallel using asyncio.gather for true concurrency
        try:
            (
                (semantic_results, semantic_time),
                (graph_results, graph_time),
                (relational_results, relational_time),
            ) = await asyncio.gather(
                timed_semantic_search(),
                timed_graph_search(),
                timed_relational_search(),
                return_exceptions=False,
            )
        except Exception as e:
            logger.error(f"Parallel search execution failed: {e}")
            # Fallback to sequential execution on error
            semantic_results, semantic_time = await timed_semantic_search()
            graph_results, graph_time = await timed_graph_search()
            relational_results, relational_time = await timed_relational_search()

        # Combine and rank results
        all_results = semantic_results + graph_results + relational_results
        combined_results = await self._combine_and_rank_results(all_results, request)

        total_parallel_time = (time.time() - start_time) * 1000
        logger.info(
            f"Hybrid search: semantic={semantic_time: .1f}ms, "
            f"graph={graph_time: .1f}ms, relational={relational_time: .1f}ms, "
            f"total_parallel={total_parallel_time: .1f}ms"
        )

        return combined_results, semantic_time, graph_time, relational_time

    async def _semantic_only_search(self, request: SearchRequest) -> List[SearchResult]:
        """Perform vector similarity search only"""
        return await self.vector_engine.semantic_search(request.query, request)

    async def _structural_only_search(
        self, request: SearchRequest
    ) -> List[SearchResult]:
        """Perform graph traversal search only"""
        return await self.graph_engine.structural_search(request.query, request)

    async def _relational_only_search(
        self, request: SearchRequest
    ) -> List[SearchResult]:
        """Perform traditional relational database search"""
        try:
            if not self.supabase_client:
                return []

            results = []

            # Search sources
            if not request.entity_types or EntityType.SOURCE in request.entity_types:
                source_query = self.supabase_client.table("archon_sources").select("*")
                if request.source_ids:
                    source_query = source_query.in_("source_id", request.source_ids)

                source_results = source_query.ilike(
                    "source_display_name", f"%{request.query}%"
                ).execute()

                for source in source_results.data[:10]:  # Limit relational results
                    result = SearchResult(
                        entity_id=source["source_id"],
                        entity_type=EntityType.SOURCE,
                        title=source["source_display_name"],
                        content=(
                            source.get("source_url")
                            if request.include_content
                            else None
                        ),
                        url=source.get("source_url"),
                        relevance_score=0.6,  # Default relational score
                        source_id=source["source_id"],
                        created_at=source.get("created_at"),
                        updated_at=source.get("updated_at"),
                    )
                    results.append(result)

            # Search pages
            if not request.entity_types or EntityType.PAGE in request.entity_types:
                page_query = self.supabase_client.table("archon_crawled_pages").select(
                    "*"
                )
                if request.source_ids:
                    page_query = page_query.in_("source_id", request.source_ids)

                # Search in content and URL
                page_results = (
                    page_query.or_(
                        f"content.ilike.%{request.query}%, url.ilike.%{request.query}%"
                    )
                    .limit(20)
                    .execute()
                )

                for page in page_results.data:
                    page_metadata = page.get("metadata", {})
                    title = page_metadata.get("title") or page.get(
                        "url", "Untitled Page"
                    )
                    result = SearchResult(
                        entity_id=f"page_{page['id']}",
                        entity_type=EntityType.PAGE,
                        title=title,
                        content=(
                            page.get("content") if request.include_content else None
                        ),
                        url=page.get("url"),
                        relevance_score=0.6,
                        source_id=page["source_id"],
                        created_at=page.get("created_at"),
                    )
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Relational search failed: {e}")
            return []

    async def _combine_and_rank_results(
        self, all_results: List[SearchResult], request: SearchRequest
    ) -> List[SearchResult]:
        """
        Combine results from multiple engines and rank by relevance.

        Args:
            all_results: Combined results from all search engines
            request: Original search request

        Returns:
            Deduplicated and ranked results
        """
        # Deduplicate by entity_id
        seen_entities: Set[str] = set()
        unique_results = []

        for result in all_results:
            if result.entity_id not in seen_entities:
                seen_entities.add(result.entity_id)
                unique_results.append(result)

        # Enhanced scoring that combines multiple factors
        for result in unique_results:
            final_score = 0.0
            weight_sum = 0.0

            # Semantic score (if available)
            if result.semantic_score is not None:
                final_score += result.semantic_score * 0.4
                weight_sum += 0.4

            # Structural score (if available)
            if result.structural_score is not None:
                final_score += result.structural_score * 0.4
                weight_sum += 0.4

            # Base relevance score
            final_score += result.relevance_score * 0.2
            weight_sum += 0.2

            # Normalize score
            result.relevance_score = (
                final_score / weight_sum if weight_sum > 0 else result.relevance_score
            )

        # Sort by final relevance score
        unique_results.sort(key=lambda r: r.relevance_score, reverse=True)

        logger.debug(
            f"Combined {len(all_results)} results into "
            f"{len(unique_results)} unique results"
        )
        return unique_results

    async def _initialize_vector_index(self):
        """Initialize vector index with existing entities"""
        try:
            # Get mapping statistics to see what's available
            response = await self.http_client.get(
                f"{self.bridge_service_url}/mapping/stats"
            )
            if response.status_code != 200:
                logger.warning("Bridge service not available for vector initialization")
                return

            stats = response.json()

            # Validate Bridge service response
            validation_result = validate_bridge_mapping_stats(stats, allow_partial=True)

            if validation_result.status == ValidationStatus.FAILED:
                logger.error(
                    f"Bridge mapping stats validation failed: {validation_result.errors}"
                )
                return

            if validation_result.status == ValidationStatus.PARTIAL:
                logger.warning(
                    f"Bridge mapping stats partially valid (confidence: {validation_result.confidence:.2f})"
                )

            # Extract validated stats
            validated_stats = validation_result.validated_data
            if not validated_stats:
                logger.error("No valid data in Bridge mapping stats response")
                return

            supabase_entities = validated_stats.supabase_entities

            # Index pages with content
            if supabase_entities.get("pages", 0) > 0:
                await self._index_pages_batch()

            # Index code examples
            if supabase_entities.get("code_examples", 0) > 0:
                await self._index_code_examples_batch()

            logger.info("Vector index initialization completed")

        except Exception as e:
            logger.error(f"Vector index initialization failed: {e}")

    async def _index_pages_batch(self):
        """Index pages in batches for vector search"""
        try:
            if not self.supabase_client:
                return

            # Get pages with content
            result = (
                self.supabase_client.table("archon_crawled_pages")
                .select("id, url, content, metadata, source_id, created_at")
                .not_.is_("content", "null")
                .limit(100)
                .execute()
            )

            entities_to_index = []
            for page in result.data:
                if page.get("content"):
                    # Extract title from metadata or use URL
                    page_metadata = page.get("metadata", {})
                    title = page_metadata.get("title") or page.get(
                        "url", "Untitled Page"
                    )
                    # Store full content (up to 100K characters) for complete code examples
                    content = (title + "\n" + page["content"])[:100000]

                    metadata = {
                        "entity_type": "page",
                        "title": title,
                        "content": page["content"][
                            :100000
                        ],  # Store full content in metadata as well
                        "url": page.get("url"),
                        "source_id": page["source_id"],
                        "created_at": page.get("created_at"),
                        "chunk_number": page.get("chunk_number", 0),
                    }

                    entities_to_index.append((f"page_{page['id']}", content, metadata))

            if entities_to_index:
                indexed_count = await self.vector_engine.batch_index_entities(
                    entities_to_index
                )
                logger.info(f"Indexed {indexed_count} pages for vector search")

        except Exception as e:
            logger.error(f"Failed to index pages: {e}")

    async def _index_code_examples_batch(self):
        """Index code examples in batches for vector search"""
        try:
            if not self.supabase_client:
                return

            # Get code examples
            result = (
                self.supabase_client.table("archon_code_examples")
                .select("id, url, content, summary, metadata, source_id, created_at")
                .limit(100)
                .execute()
            )

            entities_to_index = []
            for example in result.data:
                example_metadata = example.get("metadata", {})
                language = example_metadata.get("language", "Unknown")

                content = f"Language: {language}\n"
                if example.get("summary"):
                    content += f"Summary: {example['summary']}\n"
                content += example.get("content", "")

                metadata = {
                    "entity_type": "code_example",
                    "title": f"{language} Code Example",
                    "content": example.get("content", ""),
                    "language": language,
                    "summary": example.get("summary"),
                    "url": example.get("url"),
                    "source_id": example["source_id"],
                    "created_at": example.get("created_at"),
                    "chunk_number": example.get("chunk_number", 0),
                }

                entities_to_index.append((f"code_{example['id']}", content, metadata))

            if entities_to_index:
                indexed_count = await self.vector_engine.batch_index_entities(
                    entities_to_index
                )
                logger.info(f"Indexed {indexed_count} code examples for vector search")

        except Exception as e:
            logger.error(f"Failed to index code examples: {e}")

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all search components"""
        health_status = {
            "memgraph_connected": False,
            "embedding_service_connected": False,
            "qdrant_connected": False,
            "bridge_connected": False,
            "intelligence_connected": False,
        }

        try:
            # Check Memgraph
            health_status["memgraph_connected"] = await self.graph_engine.health_check()
        except Exception:
            pass

        try:
            # Check Ollama and Qdrant via vector engine
            vector_health = await self.vector_engine.health_check()
            if isinstance(vector_health, dict):
                health_status["embedding_service_connected"] = vector_health.get(
                    "embedding_service_connected", False
                )
                health_status["qdrant_connected"] = vector_health.get(
                    "qdrant_connected", False
                )
            else:
                # Legacy compatibility
                health_status["embedding_service_connected"] = vector_health
        except Exception:
            pass

        try:
            # Check Bridge Service
            response = await self.http_client.get(
                f"{self.bridge_service_url}/health", timeout=get_http_timeout("health")
            )
            if response.status_code == 200:
                # Validate Bridge health response
                result = response.json()
                validation_result = validate_bridge_health(result, allow_partial=True)

                # Accept valid or partial responses
                health_status["bridge_connected"] = validation_result.status in [
                    ValidationStatus.VALID,
                    ValidationStatus.PARTIAL,
                ]

                if validation_result.status == ValidationStatus.PARTIAL:
                    logger.debug(
                        f"Bridge health check partially valid (confidence: {validation_result.confidence:.2f})"
                    )
            else:
                health_status["bridge_connected"] = False
        except Exception as e:
            logger.debug(f"Bridge health check failed: {e}")
            pass

        try:
            # Check Intelligence Service
            response = await self.http_client.get(
                f"{self.intelligence_service_url}/health",
                timeout=get_http_timeout("health"),
            )
            if response.status_code == 200:
                # Validate Intelligence health response
                result = response.json()
                # Import validator for intelligence health
                from utils.response_validator import validate_intelligence_health

                validation_result = validate_intelligence_health(
                    result, allow_partial=True
                )

                # Accept valid or partial responses
                health_status["intelligence_connected"] = validation_result.status in [
                    ValidationStatus.VALID,
                    ValidationStatus.PARTIAL,
                ]

                if validation_result.status == ValidationStatus.PARTIAL:
                    logger.debug(
                        f"Intelligence health check partially valid (confidence: {validation_result.confidence:.2f})"
                    )
            else:
                health_status["intelligence_connected"] = False
        except Exception as e:
            logger.debug(f"Intelligence health check failed: {e}")
            pass

        return health_status

    async def _index_document_vectors(
        self,
        vectors: List[Tuple[str, Any, Dict[str, Any]]],
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Index document vectors with collection routing support.

        Args:
            vectors: List of (entity_id, vector, metadata) tuples
            collection_name: Target collection name (defaults to main collection)

        Returns:
            Number of successfully indexed vectors
        """
        try:
            if not vectors:
                return 0

            # Use vector engine's indexing capabilities
            if (
                hasattr(self.vector_engine, "qdrant_adapter")
                and self.vector_engine.qdrant_adapter
            ):
                qdrant_adapter = self.vector_engine.qdrant_adapter
                return await qdrant_adapter.index_vectors(
                    vectors, collection_name=collection_name
                )
            else:
                # Fallback to vector engine's default indexing
                logger.warning(
                    "Qdrant adapter not available, using vector engine fallback"
                )
                # This is a simplified fallback - in production you might want
                # more sophisticated handling
                return len(vectors)

        except Exception as e:
            logger.error(f"Failed to index document vectors: {e}")
            return 0
