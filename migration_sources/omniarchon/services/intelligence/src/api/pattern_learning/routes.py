"""
Phase 2 Pattern Learning API Routes

FastAPI router for hybrid pattern matching and semantic analysis:
1. Pattern Similarity API - Compare and score pattern similarity
2. Hybrid Scoring API - Combine semantic and structural scoring
3. Semantic Analysis API - Langextract integration for semantic extraction
4. Cache Management API - Semantic cache operations and optimization
5. Metrics API - Pattern learning performance metrics

Performance Target: <100ms response time for pattern matching

Refactored to use shared response formatters for consistency and maintainability.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Pattern analytics and enrichment
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.pattern_learning.metadata_enrichment import MetadataEnrichmentService

# Tree integration
from src.api.pattern_learning.tree_integration import (
    clear_tree_cache,
    get_tree_cache_metrics,
    get_tree_info_for_pattern,
)

# Import shared response formatters
from src.api.utils.response_formatters import (
    health_response,
    processing_time_metadata,
    success_response,
)
from src.archon_services.pattern_learning.phase2_matching.client_langextract_http import (
    ClientLangextractHttp,
)
from src.archon_services.pattern_learning.phase2_matching.model_semantic_analysis import (
    SemanticAnalysisRequest,
)
from src.archon_services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (
    get_metrics_summary,
)

# Phase 2 imports
from src.archon_services.pattern_learning.phase2_matching.node_hybrid_scorer_compute import (
    NodeHybridScorerCompute,
)
from src.archon_services.pattern_learning.phase2_matching.node_pattern_similarity_compute import (
    NodePatternSimilarityCompute,
)
from src.archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    SemanticCacheReducer,
)

# Configure router
router = APIRouter(prefix="/api/pattern-learning", tags=["pattern-learning"])

# ============================================================================
# Request/Response Models
# ============================================================================


class PatternMatchRequest(BaseModel):
    """Request for pattern similarity matching"""

    pattern1: str = Field(..., description="First pattern to compare")
    pattern2: str = Field(..., description="Second pattern to compare")
    use_semantic: bool = Field(default=True, description="Include semantic similarity")
    use_structural: bool = Field(
        default=True, description="Include structural similarity"
    )


class HybridScoreRequest(BaseModel):
    """Request for hybrid scoring - combines multiple scoring dimensions"""

    pattern: Dict[str, Any] = Field(
        ...,
        description="Pattern data with metadata (quality_score, success_rate, etc.)",
    )
    context: Dict[str, Any] = Field(
        ..., description="User context (prompt, keywords, task_type, complexity)"
    )
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional custom weights for keyword, semantic, quality, success_rate",
    )
    include_tree_info: bool = Field(
        default=False,
        description="Include OnexTree file paths for pattern-related code",
    )


class SemanticAnalysisRequestApi(BaseModel):
    """API request for semantic analysis"""

    content: str = Field(..., description="Content to analyze")
    language: str = Field(default="en", description="Content language")
    extract_concepts: bool = Field(
        default=True, description="Extract semantic concepts"
    )
    extract_themes: bool = Field(default=True, description="Extract themes")
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )


class CacheStatsResponse(BaseModel):
    """Response for cache statistics"""

    total_entries: int
    hit_rate: float
    miss_rate: float
    evictions: int
    avg_lookup_time_ms: float
    memory_usage_bytes: int


class PatternEnrichmentRequest(BaseModel):
    """Request for pattern metadata enrichment"""

    pattern_id: str = Field(..., description="Pattern ID to enrich")
    pattern_data: Dict[str, Any] = Field(
        default_factory=dict, description="Base pattern data"
    )


class PatternMetricsResponse(BaseModel):
    """Response for pattern learning metrics"""

    timestamp: datetime
    total_matches: int
    avg_score: float
    cache_hit_rate: float
    avg_response_time_ms: float
    langextract_requests: int
    error_count: int


# ============================================================================
# Global Service Instances
# ============================================================================

# Initialize on first request (lazy loading)
_hybrid_scorer: Optional[NodeHybridScorerCompute] = None
_pattern_similarity: Optional[NodePatternSimilarityCompute] = None
_semantic_cache: Optional[SemanticCacheReducer] = None
_langextract_client: Optional[ClientLangextractHttp] = None
_analytics_service: Optional[PatternAnalyticsService] = None
_enrichment_service: Optional[MetadataEnrichmentService] = None


def get_hybrid_scorer() -> NodeHybridScorerCompute:
    """Get or create hybrid scorer instance"""
    global _hybrid_scorer
    if _hybrid_scorer is None:
        _hybrid_scorer = NodeHybridScorerCompute()
    return _hybrid_scorer


def get_pattern_similarity() -> NodePatternSimilarityCompute:
    """Get or create pattern similarity instance"""
    global _pattern_similarity
    if _pattern_similarity is None:
        _pattern_similarity = NodePatternSimilarityCompute()
    return _pattern_similarity


def get_semantic_cache() -> SemanticCacheReducer:
    """Get or create semantic cache instance"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCacheReducer()
    return _semantic_cache


def get_langextract_client() -> ClientLangextractHttp:
    """Get or create langextract client instance"""
    global _langextract_client
    if _langextract_client is None:
        # Default to localhost, override with env var if needed
        _langextract_client = ClientLangextractHttp(
            base_url="http://archon-langextract:8156"
        )
    return _langextract_client


def get_analytics_service() -> PatternAnalyticsService:
    """Get or create analytics service instance"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = PatternAnalyticsService()
    return _analytics_service


def get_enrichment_service() -> MetadataEnrichmentService:
    """Get or create metadata enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        analytics_service = get_analytics_service()
        _enrichment_service = MetadataEnrichmentService(
            analytics_service=analytics_service
        )
    return _enrichment_service


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/pattern/match", response_model=Dict[str, Any])
async def match_patterns(
    request: PatternMatchRequest, correlation_id: Optional[UUID] = None
):
    """
    Compare two patterns and return similarity score

    Performance: <100ms for cached results, <300ms for uncached
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/pattern/match | correlation_id={correlation_id}"
    )

    try:
        get_pattern_similarity()

        # Use the pattern similarity compute node
        # For now, return a simple structural comparison
        # TODO: Implement full pattern matching with semantic analysis

        data = {
            "pattern1": request.pattern1,
            "pattern2": request.pattern2,
            "similarity_score": 0.0,  # Placeholder
            "confidence": 0.0,
            "method": "structural" if not request.use_semantic else "hybrid",
        }

        return success_response(data, metadata=processing_time_metadata(start_time))

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Pattern matching failed: {str(e)}"
        )


@router.post("/hybrid/score", response_model=Dict[str, Any])
async def calculate_hybrid_score(
    request: HybridScoreRequest, correlation_id: Optional[UUID] = None
):
    """
    Calculate hybrid score combining keyword, semantic, quality, and success rate

    Combines multiple scoring dimensions:
    - Keyword matching: Pattern keywords vs context keywords
    - Semantic similarity: Pattern relevance to user prompt
    - Quality score: Pattern quality from metadata
    - Success rate: Historical pattern success rate

    Performance: <50ms target
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/hybrid/score | correlation_id={correlation_id}"
    )

    try:
        # Extract metadata from pattern
        pattern_metadata = request.pattern.get("metadata", {})
        quality_score = float(pattern_metadata.get("quality_score", 0.5))
        success_rate = float(pattern_metadata.get("success_rate", 0.5))
        confidence_score = float(pattern_metadata.get("confidence_score", 0.5))

        # Calculate keyword matching score
        pattern_keywords = set(kw.lower() for kw in request.pattern.get("keywords", []))
        context_keywords = set(kw.lower() for kw in request.context.get("keywords", []))

        if pattern_keywords and context_keywords:
            # Jaccard similarity: intersection / union
            intersection = len(pattern_keywords & context_keywords)
            union = len(pattern_keywords | context_keywords)
            keyword_score = intersection / union if union > 0 else 0.0
        else:
            keyword_score = 0.0

        # Use semantic score from pattern metadata (calculated by vector search)
        # or use confidence_score as fallback
        semantic_score = float(pattern_metadata.get("semantic_score", confidence_score))

        # Apply weights (default or custom)
        default_weights = {
            "keyword": 0.25,
            "semantic": 0.35,
            "quality": 0.20,
            "success_rate": 0.20,
        }
        weights = request.weights or default_weights

        # Normalize weights to sum to 1.0
        weight_sum = sum(weights.values())
        if weight_sum > 0:
            normalized_weights = {k: v / weight_sum for k, v in weights.items()}
        else:
            normalized_weights = default_weights

        # Calculate hybrid score
        hybrid_score = (
            keyword_score * normalized_weights.get("keyword", 0.25)
            + semantic_score * normalized_weights.get("semantic", 0.35)
            + quality_score * normalized_weights.get("quality", 0.20)
            + success_rate * normalized_weights.get("success_rate", 0.20)
        )

        # Calculate confidence based on score agreement
        scores = [keyword_score, semantic_score, quality_score, success_rate]
        avg_score = sum(scores) / len(scores)
        score_variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        # High confidence when scores agree (low variance) and average is high
        confidence = avg_score * (1.0 - min(score_variance, 1.0))

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        data = {
            "hybrid_score": round(hybrid_score, 4),
            "breakdown": {
                "keyword_score": round(keyword_score, 4),
                "semantic_score": round(semantic_score, 4),
                "quality_score": round(quality_score, 4),
                "success_rate_score": round(success_rate, 4),
            },
            "confidence": round(confidence, 4),
            "metadata": {
                "processing_time_ms": round(processing_time_ms, 2),
                "weights_used": normalized_weights,
                "keyword_matches": (
                    len(pattern_keywords & context_keywords)
                    if pattern_keywords and context_keywords
                    else 0
                ),
                "pattern_keywords_count": len(pattern_keywords),
                "context_keywords_count": len(context_keywords),
            },
        }

        # Add tree info if requested
        if request.include_tree_info:
            try:
                # Extract pattern name and type from pattern data
                pattern_name = request.pattern.get("name") or request.pattern.get(
                    "pattern_name", "unknown"
                )
                pattern_type = request.pattern.get("type") or request.pattern.get(
                    "pattern_type", "onex"
                )
                node_type = request.pattern.get("node_type")

                # Retrieve tree info
                tree_info = await get_tree_info_for_pattern(
                    pattern_name=pattern_name,
                    pattern_type=pattern_type,
                    node_type=node_type,
                    correlation_id=correlation_id,
                )

                # Add to response
                data["tree_info"] = tree_info.model_dump()

                logger.info(
                    f"Tree info added: pattern={pattern_name}, "
                    f"files={len(tree_info.relevant_files)}, "
                    f"from_cache={tree_info.from_cache}, "
                    f"tree_query_time={tree_info.query_time_ms:.2f}ms"
                )

            except Exception as e:
                logger.warning(f"Failed to retrieve tree info: {e}", exc_info=True)
                # Don't fail the entire request, just log the error
                data["tree_info"] = {
                    "error": str(e),
                    "relevant_files": [],
                    "tree_metadata": {
                        "total_files": 0,
                        "node_types": [],
                        "pattern_locations": [],
                    },
                }

        logger.info(
            f"Hybrid score calculated: {hybrid_score:.4f} "
            f"(keyword={keyword_score:.2f}, semantic={semantic_score:.2f}, "
            f"quality={quality_score:.2f}, success_rate={success_rate:.2f}) "
            f"in {processing_time_ms:.2f}ms"
        )

        return success_response(data, metadata=processing_time_metadata(start_time))

    except ValueError as e:
        logger.error(f"Invalid input for hybrid scoring: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e
    except Exception as e:
        logger.error(f"Hybrid scoring failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Hybrid scoring failed: {str(e)}"
        ) from e


@router.post("/semantic/analyze", response_model=Dict[str, Any])
async def analyze_semantic_content(
    request: SemanticAnalysisRequestApi, correlation_id: Optional[UUID] = None
):
    """
    Perform semantic analysis using Langextract service

    Performance: <500ms (depends on Langextract response time)
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/semantic/analyze | correlation_id={correlation_id}"
    )

    try:
        get_langextract_client()
        get_semantic_cache()

        # Check cache first
        # TODO: Implement cache lookup

        # Prepare request for Langextract
        SemanticAnalysisRequest(
            content=request.content,
            language=request.language,
            min_confidence=request.min_confidence,
        )

        # TODO: Call Langextract service
        # For now, return placeholder result

        data = {
            "content_preview": request.content[:100],
            "language": request.language,
            "concepts": [],  # Placeholder
            "themes": [],  # Placeholder
            "domains": [],  # Placeholder
            "confidence": 0.0,
            "from_cache": False,
        }

        return success_response(data, metadata=processing_time_metadata(start_time))

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Semantic analysis failed: {str(e)}"
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(correlation_id: Optional[UUID] = None):
    """
    Get semantic cache statistics and performance metrics
    """
    logger.info(
        f"GET /api/pattern-learning/cache/stats | correlation_id={correlation_id}"
    )

    try:
        get_semantic_cache()

        # TODO: Get actual cache stats
        stats = CacheStatsResponse(
            total_entries=0,
            hit_rate=0.0,
            miss_rate=0.0,
            evictions=0,
            avg_lookup_time_ms=0.0,
            memory_usage_bytes=0,
        )

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )


@router.delete("/cache/clear")
async def clear_cache(correlation_id: Optional[UUID] = None):
    """
    Clear the semantic cache (admin operation)
    """
    logger.info(
        f"DELETE /api/pattern-learning/cache/clear | correlation_id={correlation_id}"
    )

    try:
        get_semantic_cache()
        # TODO: Implement cache clear
        return success_response({"message": "Cache cleared"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_pattern_metrics(correlation_id: Optional[UUID] = None):
    """
    Get comprehensive pattern learning metrics

    Returns Prometheus-compatible metrics summary
    """
    logger.info(f"GET /api/pattern-learning/metrics | correlation_id={correlation_id}")

    try:
        # Use the monitoring module to get metrics
        metrics = get_metrics_summary()

        return success_response(metrics, metadata={"status": "operational"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/tree-cache/metrics", response_model=Dict[str, Any])
async def get_tree_cache_metrics_endpoint(correlation_id: Optional[UUID] = None):
    """
    Get tree info cache metrics and performance statistics
    """
    logger.info(
        f"GET /api/pattern-learning/tree-cache/metrics | correlation_id={correlation_id}"
    )

    try:
        metrics = get_tree_cache_metrics()
        return success_response(
            metrics,
            metadata={
                "description": "Tree info cache performance metrics",
                "ttl_seconds": 300,  # 5 minutes
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get tree cache metrics: {str(e)}"
        )


@router.delete("/tree-cache/clear")
async def clear_tree_cache_endpoint(correlation_id: Optional[UUID] = None):
    """
    Clear the tree info cache (admin operation)
    """
    logger.info(
        f"DELETE /api/pattern-learning/tree-cache/clear | correlation_id={correlation_id}"
    )

    try:
        clear_tree_cache()
        return success_response(
            {"message": "Tree info cache cleared"},
            metadata={"status": "success"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear tree cache: {str(e)}"
        )


@router.post("/pattern/enrich", response_model=Dict[str, Any])
async def enrich_pattern_metadata(
    request: PatternEnrichmentRequest, correlation_id: Optional[UUID] = None
):
    """
    Enrich pattern with analytics metadata

    Adds success_rate, usage_count, avg_quality_score, and confidence_score
    to pattern data based on historical feedback.

    Performance: <20ms target
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/pattern/enrich | "
        f"pattern_id={request.pattern_id} | correlation_id={correlation_id}"
    )

    try:
        enrichment_service = get_enrichment_service()

        # Enrich pattern with analytics metadata
        enriched_pattern = await enrichment_service.enrich_pattern_with_analytics(
            pattern_id=request.pattern_id,
            pattern_data=request.pattern_data,
        )

        # Get enrichment stats
        stats = enrichment_service.get_statistics()

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Pattern enriched | pattern_id={request.pattern_id} | "
            f"enriched={enriched_pattern.get('enriched', False)} | "
            f"time_ms={processing_time_ms:.2f}"
        )

        return success_response(
            enriched_pattern,
            metadata={
                **processing_time_metadata(start_time),
                "enrichment_stats": stats,
            },
        )

    except Exception as e:
        logger.error(
            f"Pattern enrichment failed | pattern_id={request.pattern_id} | error={str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Pattern enrichment failed: {str(e)}"
        )


@router.post("/pattern/enrich/batch", response_model=Dict[str, Any])
async def enrich_patterns_batch(
    patterns: list[Dict[str, Any]], correlation_id: Optional[UUID] = None
):
    """
    Enrich multiple patterns with analytics metadata

    Each pattern dict must have 'pattern_id' field.

    Performance: <20ms per pattern target
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/pattern/enrich/batch | "
        f"count={len(patterns)} | correlation_id={correlation_id}"
    )

    try:
        enrichment_service = get_enrichment_service()

        # Enrich all patterns
        enriched_patterns = await enrichment_service.enrich_multiple_patterns(patterns)

        # Get enrichment stats
        stats = enrichment_service.get_statistics()

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Batch enrichment complete | count={len(enriched_patterns)} | "
            f"time_ms={processing_time_ms:.2f} | "
            f"avg_per_pattern_ms={processing_time_ms / len(patterns) if patterns else 0:.2f}"
        )

        return success_response(
            {
                "enriched_patterns": enriched_patterns,
                "total_count": len(enriched_patterns),
            },
            metadata={
                **processing_time_metadata(start_time),
                "enrichment_stats": stats,
                "avg_time_per_pattern_ms": (
                    processing_time_ms / len(patterns) if patterns else 0
                ),
            },
        )

    except Exception as e:
        logger.error(
            f"Batch enrichment failed | count={len(patterns)} | error={str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Batch enrichment failed: {str(e)}"
        )


@router.get("/health")
async def health_check(correlation_id: Optional[UUID] = None):
    """
    Health check for pattern learning components
    """
    start_time = time.time()
    logger.info(f"GET /api/pattern-learning/health | correlation_id={correlation_id}")

    status = "healthy"
    checks = {}

    # Check each component
    try:
        get_hybrid_scorer()
        checks["hybrid_scorer"] = "operational"
    except Exception as e:
        checks["hybrid_scorer"] = f"error: {str(e)}"
        status = "degraded"

    try:
        get_pattern_similarity()
        checks["pattern_similarity"] = "operational"
    except Exception as e:
        checks["pattern_similarity"] = f"error: {str(e)}"
        status = "degraded"

    try:
        get_semantic_cache()
        checks["semantic_cache"] = "operational"
    except Exception as e:
        checks["semantic_cache"] = f"error: {str(e)}"
        status = "degraded"

    try:
        get_langextract_client()
        checks["langextract_client"] = "operational"
    except Exception as e:
        checks["langextract_client"] = f"error: {str(e)}"
        status = "degraded"

    # Check tree integration
    try:
        tree_metrics = get_tree_cache_metrics()
        checks["tree_cache"] = (
            f"operational (hit_rate={tree_metrics.get('hit_rate', 0.0):.2%})"
        )
    except Exception as e:
        checks["tree_cache"] = f"error: {str(e)}"
        status = "degraded"

    # Add response time to checks
    checks["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    return health_response(status=status, checks=checks, service="pattern-learning")
