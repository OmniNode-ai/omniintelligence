"""
Enhanced Search Strategy

Integrates with the new hybrid search service to provide:
- Vector + Graph + Relational search capabilities
- Intelligent result ranking with quality scores
- Multi-dimensional search results
- Performance optimized execution
"""

import asyncio
import os
from typing import Any, Optional

import httpx
from server.config.logfire_config import get_logger, safe_span
from server.services.search.base_search_strategy import BaseSearchStrategy
from supabase import Client

# Import caching system
try:
    from .search_cache import SearchCache, get_search_cache
except ImportError:
    # Fallback if cache is not available
    SearchCache = None
    get_search_cache = None

logger = get_logger(__name__)


class EnhancedSearchStrategy:
    """
    Enhanced search strategy that integrates with the hybrid search service
    to provide comprehensive knowledge discovery capabilities.
    """

    def __init__(self, supabase_client: Client, base_strategy: BaseSearchStrategy):
        """Initialize with database client and base strategy for fallback"""
        self.supabase_client = supabase_client
        self.base_strategy = base_strategy
        self.search_service_url = os.getenv(
            "SEARCH_SERVICE_URL", "http://archon-search:8055"
        )
        self.intelligence_service_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )

        # Initialize HTTP client with optimized settings for performance
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=2.0),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=200),
            http2=True,  # Enable HTTP/2 for better performance
        )

        # Performance optimization flags
        self._health_check_cache = {}
        self._health_check_ttl = 60  # Cache health checks for 60 seconds
        self._last_health_check = 0

        # Initialize cache system
        self.cache: Optional[SearchCache] = None
        self._cache_initialized = False

    async def _initialize_cache(self):
        """Initialize cache system if available"""
        if not self._cache_initialized and SearchCache:
            try:
                if get_search_cache:
                    self.cache = await get_search_cache()
                else:
                    # Initialize new cache instance
                    redis_url = os.getenv("REDIS_URL")
                    redis_password = os.getenv("REDIS_PASSWORD")
                    self.cache = SearchCache(
                        redis_url=redis_url,
                        redis_password=redis_password,
                        max_memory_cache_size=1000,
                        default_ttl_seconds=3600,
                        embedding_ttl_seconds=86400,
                    )
                    await self.cache.initialize()

                self._cache_initialized = True
                logger.info("Enhanced search strategy cache initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize search cache: {e}")
                self.cache = None
                self._cache_initialized = True  # Don't try again

    async def close(self):
        """Close HTTP client and cache"""
        await self.http_client.aclose()
        if self.cache:
            await self.cache.close()

    async def enhanced_search(
        self,
        query: str,
        match_count: int = 10,
        search_mode: str = "hybrid",
        entity_types: Optional[list[str]] = None,
        include_quality_scores: bool = False,  # Disabled by default for performance
        include_content: bool = True,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Perform enhanced search using the hybrid search service.

        Args:
            query: Search query string
            match_count: Number of results to return
            search_mode: Search mode (semantic, structural, relational, hybrid)
            entity_types: Filter by entity types (page, code_example, source)
            include_quality_scores: Whether to include quality assessment scores
            include_content: Whether to include full content in results
            filter_metadata: Additional metadata filters

        Returns:
            List of enhanced search results with quality scores and
            multi-dimensional data
        """
        with safe_span(
            "enhanced_search",
            query_length=len(query),
            mode=search_mode,
            match_count=match_count,
        ) as span:
            try:
                # Initialize cache if not already done
                if not self._cache_initialized:
                    await self._initialize_cache()

                # Check cache for existing results
                cache_key_data = {
                    "query": query,
                    "search_mode": search_mode,
                    "match_count": match_count,
                    "entity_types": entity_types,
                    "include_quality_scores": include_quality_scores,
                    "include_content": include_content,
                    "filter_metadata": filter_metadata,
                }

                if self.cache:
                    cached_results = await self.cache.get_cached_query_result(
                        query, search_mode, cache_key_data
                    )
                    if cached_results:
                        span.set_attribute("cache_hit", True)
                        span.set_attribute("results_returned", len(cached_results))
                        logger.info(
                            f"Enhanced search cache hit - "
                            f"{len(cached_results)} results returned"
                        )
                        return cached_results

                    span.set_attribute("cache_hit", False)

                # Prepare search request
                search_request = {
                    "query": query,
                    "mode": search_mode,
                    "limit": match_count,
                    "offset": 0,
                    "include_content": include_content,
                    "entity_types": entity_types or ["page", "code_example"],
                    "source_ids": (
                        filter_metadata.get("source_ids") if filter_metadata else None
                    ),
                }

                # Check if enhanced search service is available (with caching)
                search_available = await self._check_search_service_health_cached()

                if search_available:
                    # Use enhanced search service
                    search_results = await self._call_enhanced_search_service(
                        search_request
                    )
                    span.set_attribute("search_service_used", "enhanced")
                else:
                    # Fallback to base strategy
                    logger.warning(
                        "Enhanced search service unavailable, "
                        "falling back to base strategy"
                    )
                    search_results = await self._fallback_search(
                        query, match_count, filter_metadata
                    )
                    span.set_attribute("search_service_used", "fallback")

                # Add quality scores if requested and available
                if include_quality_scores and search_results:
                    search_results = await self._enhance_with_quality_scores(
                        search_results, query
                    )

                # Add search analytics metadata
                for result in search_results:
                    result["search_metadata"] = {
                        "search_mode": search_mode,
                        "query": query,
                        "has_quality_score": include_quality_scores
                        and "quality_score" in result,
                        "search_service": (
                            "enhanced" if search_available else "fallback"
                        ),
                    }

                # Cache results for future use
                if self.cache and search_results:
                    try:
                        await self.cache.cache_query_result(
                            query, search_mode, cache_key_data, search_results
                        )
                        span.set_attribute("results_cached", True)
                    except Exception as e:
                        logger.warning(f"Failed to cache search results: {e}")
                        span.set_attribute("results_cached", False)

                span.set_attribute("results_returned", len(search_results))
                span.set_attribute("quality_scores_included", include_quality_scores)

                return search_results

            except Exception as e:
                logger.error(f"Enhanced search failed: {e}")
                span.set_attribute("error", str(e))

                # Fallback to base strategy on error
                try:
                    fallback_results = await self._fallback_search(
                        query, match_count, filter_metadata
                    )
                    span.set_attribute("fallback_used", True)
                    return fallback_results
                except Exception as fallback_error:
                    logger.error(f"Fallback search also failed: {fallback_error}")
                    return []

    async def _check_search_service_health_cached(self) -> bool:
        """Check if the enhanced search service is available with caching"""
        import time

        current_time = time.time()

        # Return cached result if still valid
        if (current_time - self._last_health_check) < self._health_check_ttl:
            return self._health_check_cache.get("search_service", False)

        try:
            response = await self.http_client.get(
                f"{self.search_service_url}/health", timeout=2.0  # Faster timeout
            )
            is_healthy = response.status_code == 200
            self._health_check_cache["search_service"] = is_healthy
            self._last_health_check = current_time
            return is_healthy
        except Exception:
            self._health_check_cache["search_service"] = False
            self._last_health_check = current_time
            return False

    async def _check_search_service_health(self) -> bool:
        """Legacy method for compatibility - delegates to cached version"""
        return await self._check_search_service_health_cached()

    async def _call_enhanced_search_service(
        self, search_request: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Call the enhanced search service API"""
        try:
            response = await self.http_client.post(
                f"{self.search_service_url}/search",
                json=search_request,
                timeout=8.0,  # Reduced timeout
            )

            if response.status_code != 200:
                raise Exception(f"Search service returned {response.status_code}")

            search_response = response.json()
            results = search_response.get("results", [])

            # Convert enhanced search results to RAG format
            converted_results = []
            for result in results:
                converted_result = {
                    "id": result.get("entity_id"),
                    "content": result.get("content", ""),
                    "metadata": self._extract_metadata_from_enhanced_result(result),
                    "similarity": result.get("relevance_score", 0.0),
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "entity_type": result.get("entity_type", {}).get("value", "page"),
                    "source_id": result.get("source_id"),
                    "created_at": result.get("created_at"),
                    "updated_at": result.get("updated_at"),
                    # Enhanced search specific fields
                    "semantic_score": result.get("semantic_score"),
                    "structural_score": result.get("structural_score"),
                    "search_time_breakdown": {
                        "semantic_time_ms": search_response.get(
                            "semantic_search_time_ms"
                        ),
                        "graph_time_ms": search_response.get("graph_search_time_ms"),
                        "relational_time_ms": search_response.get(
                            "relational_search_time_ms"
                        ),
                        "total_time_ms": search_response.get("search_time_ms"),
                    },
                }
                converted_results.append(converted_result)

            return converted_results

        except Exception as e:
            logger.error(f"Failed to call enhanced search service: {e}")
            raise

    def _extract_metadata_from_enhanced_result(
        self, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract and format metadata from enhanced search result"""
        metadata = result.get("metadata", {})

        # Enhance metadata with search-specific information
        enhanced_metadata = {
            **metadata,
            "entity_type": result.get("entity_type", {}).get("value", "page"),
            "relevance_score": result.get("relevance_score", 0.0),
            "search_source": "enhanced_service",
        }

        # Add semantic and structural scores if available
        if result.get("semantic_score") is not None:
            enhanced_metadata["semantic_score"] = result.get("semantic_score")
        if result.get("structural_score") is not None:
            enhanced_metadata["structural_score"] = result.get("structural_score")

        return enhanced_metadata

    async def _fallback_search(
        self, query: str, match_count: int, filter_metadata: Optional[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fallback to base vector search when enhanced search is unavailable"""
        from ..embeddings.embedding_service import create_embedding

        # Create embedding for fallback search
        query_embedding = await create_embedding(query)
        if not query_embedding:
            return []

        # Use base strategy for vector search
        results = await self.base_strategy.vector_search(
            query_embedding=query_embedding,
            match_count=match_count,
            filter_metadata=filter_metadata,
        )

        return results

    async def _enhance_with_quality_scores(
        self, results: list[dict[str, Any]], query: str
    ) -> list[dict[str, Any]]:
        """Enhance search results with quality assessment scores"""
        try:
            # Check if intelligence service is available
            intelligence_available = await self._check_intelligence_service_health()

            if not intelligence_available:
                logger.warning(
                    "Intelligence service unavailable, skipping quality scoring"
                )
                return results

            # Process results in batches for quality assessment
            batch_size = 5
            enhanced_results = []

            for i in range(0, len(results), batch_size):
                batch = results[i : i + batch_size]
                batch_enhanced = await self._assess_result_quality_batch(batch, query)
                enhanced_results.extend(batch_enhanced)

            # Re-rank results based on combined quality and relevance scores
            enhanced_results = self._rank_results_with_quality(enhanced_results)

            return enhanced_results

        except Exception as e:
            logger.error(f"Failed to enhance with quality scores: {e}")
            return results

    async def _check_intelligence_service_health(self) -> bool:
        """Check if the intelligence service is available with caching"""
        import time

        current_time = time.time()

        # Return cached result if still valid
        if (current_time - self._last_health_check) < self._health_check_ttl:
            return self._health_check_cache.get("intelligence_service", False)

        try:
            response = await self.http_client.get(
                f"{self.intelligence_service_url}/health", timeout=2.0  # Faster timeout
            )
            is_healthy = response.status_code == 200
            self._health_check_cache["intelligence_service"] = is_healthy
            return is_healthy
        except Exception:
            self._health_check_cache["intelligence_service"] = False
            return False

    async def _assess_result_quality_batch(
        self, results: list[dict[str, Any]], query: str
    ) -> list[dict[str, Any]]:
        """Assess quality for a batch of results using the intelligence service"""
        try:
            # Prepare quality assessment requests
            assessment_requests = []
            for result in results:
                content = result.get("content", "")
                title = result.get("title", "")

                # Combine title and content for assessment
                assessment_content = f"{title}\n\n{content}"[
                    :2000
                ]  # Limit content length

                assessment_requests.append(
                    {
                        "content": assessment_content,
                        "source_path": result.get("url", ""),
                        "language": self._detect_content_language(result),
                        "context": {
                            "query": query,
                            "entity_type": result.get("entity_type", "page"),
                            "source_id": result.get("source_id"),
                        },
                    }
                )

            # Call intelligence service for batch quality assessment
            quality_response = await self.http_client.post(
                f"{self.intelligence_service_url}/assess/batch",
                json={
                    "assessments": assessment_requests,
                    "include_metrics": True,
                    "assessment_type": "search_relevance",
                },
                timeout=5.0,  # Reduced timeout for quality assessment
            )

            if quality_response.status_code != 200:
                logger.warning(
                    f"Quality assessment failed with status "
                    f"{quality_response.status_code}"
                )
                return results

            quality_data = quality_response.json()
            quality_scores = quality_data.get("assessments", [])

            # Enhance results with quality scores
            enhanced_results = []
            for i, result in enumerate(results):
                enhanced_result = result.copy()

                if i < len(quality_scores):
                    quality_info = quality_scores[i]
                    enhanced_result.update(
                        {
                            "quality_score": quality_info.get("overall_score", 0.0),
                            "quality_metrics": {
                                "relevance_score": quality_info.get(
                                    "relevance_score", 0.0
                                ),
                                "completeness_score": quality_info.get(
                                    "completeness_score", 0.0
                                ),
                                "clarity_score": quality_info.get("clarity_score", 0.0),
                                "technical_accuracy": quality_info.get(
                                    "technical_accuracy", 0.0
                                ),
                            },
                            "quality_assessment": {
                                "assessed_at": quality_info.get("assessed_at"),
                                "assessment_confidence": quality_info.get(
                                    "confidence", 0.0
                                ),
                                "key_strengths": quality_info.get("strengths", []),
                                "improvement_areas": quality_info.get(
                                    "improvements", []
                                ),
                            },
                        }
                    )

                enhanced_results.append(enhanced_result)

            return enhanced_results

        except Exception as e:
            logger.error(f"Quality assessment batch failed: {e}")
            return results

    def _detect_content_language(self, result: dict[str, Any]) -> str:
        """Detect content language for quality assessment"""
        # Simple language detection based on metadata or content analysis
        metadata = result.get("metadata", {})

        # Check for language in metadata
        if "language" in metadata:
            return metadata["language"]

        # Check for code examples
        entity_type = result.get("entity_type", "")
        if entity_type == "code_example":
            return metadata.get("programming_language", "unknown")

        # Default to natural language
        return "english"

    def _rank_results_with_quality(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Re-rank results combining relevance and quality scores"""
        try:
            for result in results:
                relevance_score = result.get("similarity", 0.0)
                quality_score = result.get("quality_score", 0.0)
                semantic_score = result.get("semantic_score", 0.0)
                structural_score = result.get("structural_score", 0.0)

                # Calculate composite score with weighted combination
                composite_score = (
                    relevance_score * 0.35
                    + quality_score * 0.25  # Base relevance
                    + semantic_score * 0.25  # Quality assessment
                    + structural_score  # Semantic understanding
                    * 0.15  # Structural relationships
                )

                result["composite_score"] = composite_score
                result["ranking_metadata"] = {
                    "relevance_weight": 0.35,
                    "quality_weight": 0.25,
                    "semantic_weight": 0.25,
                    "structural_weight": 0.15,
                    "final_score": composite_score,
                }

            # Sort by composite score
            results.sort(key=lambda r: r.get("composite_score", 0.0), reverse=True)

            return results

        except Exception as e:
            logger.error(f"Failed to rank results with quality: {e}")
            # Fallback to original similarity ranking
            results.sort(key=lambda r: r.get("similarity", 0.0), reverse=True)
            return results

    async def search_with_analytics(
        self,
        query: str,
        match_count: int = 10,
        search_mode: str = "hybrid",
        track_analytics: bool = True,
    ) -> dict[str, Any]:
        """
        Perform enhanced search with detailed analytics and performance metrics.

        Returns both results and comprehensive analytics data.
        """
        with safe_span(
            "enhanced_search_with_analytics", query=query, mode=search_mode
        ) as span:
            start_time = asyncio.get_event_loop().time()

            try:
                # Perform enhanced search
                results = await self.enhanced_search(
                    query=query,
                    match_count=match_count,
                    search_mode=search_mode,
                    include_quality_scores=True,
                )

                end_time = asyncio.get_event_loop().time()
                total_time_ms = (end_time - start_time) * 1000

                # Collect analytics
                analytics = {
                    "query": query,
                    "search_mode": search_mode,
                    "total_results": len(results),
                    "search_time_ms": total_time_ms,
                    "quality_scores_available": sum(
                        1 for r in results if "quality_score" in r
                    ),
                    "entity_type_distribution": self._analyze_entity_types(results),
                    "score_distribution": self._analyze_score_distribution(results),
                    "search_effectiveness": self._calculate_search_effectiveness(
                        results, query
                    ),
                }

                # Add performance breakdown if available
                if results and "search_time_breakdown" in results[0]:
                    analytics["performance_breakdown"] = results[0][
                        "search_time_breakdown"
                    ]

                span.set_attribute("analytics_generated", True)
                span.set_attribute(
                    "search_effectiveness", analytics["search_effectiveness"]
                )

                return {"results": results, "analytics": analytics, "success": True}

            except Exception as e:
                logger.error(f"Enhanced search with analytics failed: {e}")
                span.set_attribute("error", str(e))

                return {
                    "results": [],
                    "analytics": {
                        "query": query,
                        "search_mode": search_mode,
                        "error": str(e),
                        "success": False,
                    },
                    "success": False,
                }

    def _analyze_entity_types(self, results: list[dict[str, Any]]) -> dict[str, int]:
        """Analyze distribution of entity types in results"""
        distribution = {}
        for result in results:
            entity_type = result.get("entity_type", "unknown")
            distribution[entity_type] = distribution.get(entity_type, 0) + 1
        return distribution

    def _analyze_score_distribution(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze score distribution for results"""
        if not results:
            return {}

        relevance_scores = [r.get("similarity", 0.0) for r in results]
        quality_scores = [
            r.get("quality_score", 0.0) for r in results if "quality_score" in r
        ]
        composite_scores = [
            r.get("composite_score", 0.0) for r in results if "composite_score" in r
        ]

        return {
            "relevance_scores": {
                "min": min(relevance_scores) if relevance_scores else 0.0,
                "max": max(relevance_scores) if relevance_scores else 0.0,
                "avg": (
                    sum(relevance_scores) / len(relevance_scores)
                    if relevance_scores
                    else 0.0
                ),
            },
            "quality_scores": {
                "min": min(quality_scores) if quality_scores else 0.0,
                "max": max(quality_scores) if quality_scores else 0.0,
                "avg": (
                    sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
                ),
                "coverage": len(quality_scores) / len(results) if results else 0.0,
            },
            "composite_scores": {
                "min": min(composite_scores) if composite_scores else 0.0,
                "max": max(composite_scores) if composite_scores else 0.0,
                "avg": (
                    sum(composite_scores) / len(composite_scores)
                    if composite_scores
                    else 0.0
                ),
            },
        }

    def _calculate_search_effectiveness(
        self, results: list[dict[str, Any]], query: str
    ) -> float:
        """Calculate overall search effectiveness score"""
        if not results:
            return 0.0

        # Factors for effectiveness calculation
        result_count_factor = min(len(results) / 10.0, 1.0)  # Optimal around 10 results

        avg_relevance = sum(r.get("similarity", 0.0) for r in results) / len(results)

        quality_coverage = sum(1 for r in results if "quality_score" in r) / len(
            results
        )
        avg_quality = sum(
            r.get("quality_score", 0.0) for r in results if "quality_score" in r
        )
        avg_quality = avg_quality / max(
            1, sum(1 for r in results if "quality_score" in r)
        )

        # Composite effectiveness score
        effectiveness = (
            result_count_factor * 0.2
            + avg_relevance * 0.4
            + avg_quality * 0.3
            + quality_coverage * 0.1
        )

        return min(effectiveness, 1.0)
