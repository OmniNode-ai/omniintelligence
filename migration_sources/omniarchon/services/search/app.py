"""
Enhanced Search Service for Archon

Combines vector similarity search, graph traversal, and relational queries
to provide intelligent and comprehensive search capabilities.
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

# Add python lib to path for config validator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from engines.search_cache import initialize_search_cache
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from models.search_models import (
    EntityType,
    HealthStatus,
    RelationshipSearchRequest,
    RelationshipSearchResponse,
    SearchAnalytics,
    SearchMode,
    SearchRequest,
    SearchResponse,
)
from orchestration.hybrid_search import HybridSearchOrchestrator

# Import comprehensive logging infrastructure
from search_logging.search_logger import SearchLogger
from utils.document_chunker import DocumentChunker

from python.lib.config_validator import validate_required_env_vars
from shared.logging.pipeline_correlation import (
    CorrelationHeaders,
    get_pipeline_correlation,
)

# Configure logging with comprehensive search logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize comprehensive search logger
search_service_logger = SearchLogger("search_orchestrator")

# Global orchestrator
search_orchestrator = None

# Global document chunker for handling large documents
document_chunker = None


def determine_collection_for_document(metadata: Dict[str, Any]) -> str:
    """
    Determine which Qdrant collection to use based on document type.

    Args:
        metadata: Document metadata containing document_type

    Returns:
        Collection name to use for indexing
    """
    document_type = metadata.get("document_type", "").lower()

    # Quality-related documents go to quality_vectors collection
    quality_document_types = {
        "technical_diagnosis",
        "quality_assessment",
        "code_review",
        "execution_report",
        "quality_report",
        "compliance_check",
        "performance_analysis",
    }

    if document_type in quality_document_types:
        return "quality_vectors"

    # All other documents go to main collection
    return "archon_vectors"


def detect_language_from_extension(
    file_extension: str = None, source_path: str = None
) -> str:
    """
    Detect programming language from file extension.

    Args:
        file_extension: File extension (with or without leading dot)
        source_path: Full file path (fallback if file_extension not provided)

    Returns:
        Detected language name or "unknown" if not recognized
    """
    if file_extension:
        ext = file_extension.lower().lstrip(".")
    elif source_path:
        ext = source_path.split(".")[-1].lower() if "." in source_path else ""
    else:
        return "unknown"

    language_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "jsx": "javascript",
        "java": "java",
        "cpp": "cpp",
        "c": "c",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "php": "php",
        "swift": "swift",
        "kt": "kotlin",
        "cs": "csharp",
        "md": "markdown",
        "txt": "text",
        "yaml": "yaml",
        "yml": "yaml",
        "json": "json",
        "toml": "toml",
        "sh": "bash",
        "sql": "sql",
        "html": "html",
        "css": "css",
        "xml": "xml",
    }
    return language_map.get(ext, ext or "unknown")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup search service components"""
    global search_orchestrator, document_chunker

    # Validate environment variables before any initialization
    validate_required_env_vars()

    try:
        # Get environment variables
        # Architecture: Direct PostgreSQL + Memgraph + Qdrant
        memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
        embedding_model_url = os.getenv(
            "EMBEDDING_MODEL_URL", "http://192.168.86.201:8002"
        )
        bridge_service_url = os.getenv(
            "BRIDGE_SERVICE_URL", "http://archon-bridge:8054"
        )
        intelligence_service_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )

        # Initialize search cache system first (for performance optimization)
        redis_url = os.getenv("REDIS_URL")  # Optional Redis for distributed caching
        redis_password = os.getenv("REDIS_PASSWORD")  # Optional Redis password

        try:
            await initialize_search_cache(
                redis_url=redis_url,
                redis_password=redis_password,
                max_memory_cache_size=2000,  # Larger cache for search service
                default_ttl_seconds=1800,  # 30 minutes
                embedding_ttl_seconds=86400,  # 24 hours
                enable_compression=True,
            )
            logger.info("Search cache system initialized successfully")
        except Exception as e:
            logger.warning(
                f"Search cache initialization failed, proceeding without caching: {e}"
            )

        # Initialize document chunker for large document handling
        try:
            max_chunk_tokens = int(os.getenv("CHUNK_MAX_TOKENS", "7500"))
            chunk_overlap = int(os.getenv("CHUNK_OVERLAP_TOKENS", "200"))
            document_chunker = DocumentChunker(
                max_tokens=max_chunk_tokens, chunk_overlap=chunk_overlap
            )
            logger.info(
                f"Document chunker initialized (max_tokens={max_chunk_tokens}, "
                f"overlap={chunk_overlap})"
            )
        except Exception as e:
            logger.warning(
                f"Document chunker initialization failed, chunking disabled: {e}"
            )
            document_chunker = None

        # Initialize search orchestrator
        search_orchestrator = HybridSearchOrchestrator(
            memgraph_uri=memgraph_uri,
            ollama_base_url=embedding_model_url,
            bridge_service_url=bridge_service_url,
            intelligence_service_url=intelligence_service_url,
        )

        await search_orchestrator.initialize()
        logger.info("Enhanced search service initialized successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to initialize search service: {e}")
        raise
    finally:
        # Cleanup
        if search_orchestrator:
            await search_orchestrator.close()
        logger.info("Enhanced search service shutdown complete")


# FastAPI application
app = FastAPI(
    title="Archon Enhanced Search Service",
    description="Intelligent search combining vector similarity, graph traversal, and relational queries",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS Configuration (environment-based for production security)
def get_cors_origins() -> list[str]:
    """
    Get CORS allowed origins from environment with production validation.

    Returns:
        List of allowed origins. Defaults to localhost for development.
    """
    # Check both CORS_ALLOWED_ORIGINS and ALLOWED_ORIGINS (for backward compatibility)
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS")
    environment = os.getenv("ENVIRONMENT", "development")

    # Development defaults (localhost variants)
    dev_origins = [
        "http://localhost:3737",
        "http://localhost:8181",
        "http://127.0.0.1:3737",
        "http://127.0.0.1:8181",
    ]

    if not origins_env:
        if environment == "production":
            logger.warning(
                "⚠️  SECURITY WARNING: CORS_ALLOWED_ORIGINS not set in production! "
                "Using restrictive defaults. Set CORS_ALLOWED_ORIGINS environment variable."
            )
            return dev_origins  # Fail-safe: use localhost only
        else:
            logger.info("CORS: Using development defaults (localhost)")
            return dev_origins

    # Wildcard check for production
    if origins_env == "*":
        if environment == "production":
            logger.error(
                "❌ SECURITY ERROR: Wildcard CORS (*) is NOT allowed in production! "
                "Set CORS_ALLOWED_ORIGINS to specific domains. Using restrictive defaults."
            )
            return dev_origins  # Fail-safe: reject wildcard in production
        else:
            logger.warning("CORS: Using wildcard (*) - development only")
            return ["*"]

    # Parse comma-separated origins
    origins = [origin.strip() for origin in origins_env.split(",")]
    logger.info(f"CORS: Configured {len(origins)} allowed origins for {environment}")

    return origins


cors_origins = get_cors_origins()

# CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthStatus)
async def health_check(request: Request):
    """Enhanced search service health check endpoint with comprehensive logging"""
    time.time()

    # Extract correlation headers
    correlation_headers = CorrelationHeaders.extract_headers(dict(request.headers))
    search_service_logger.set_request_context(
        request_id=correlation_headers.get("request_id"),
        correlation_id=correlation_headers.get("correlation_id"),
        pipeline_correlation_id=correlation_headers.get("pipeline_id"),
    )

    try:
        if not search_orchestrator:
            health_status = {
                "status": "unhealthy",
                "error": "Search orchestrator not initialized",
                "memgraph_connected": False,
                "intelligence_connected": False,
                "bridge_connected": False,
                "embedding_service_connected": False,
                "vector_index_ready": False,
                "service_version": "1.0.0",
            }
            search_service_logger.log_health_check(health_status)
            return HealthStatus(**health_status)

        # Check all component health
        component_health = await search_orchestrator.health_check()

        # Determine overall status
        # Core required services: Memgraph (graph), Qdrant (vectors), Ollama (embeddings)
        # Optional services: Bridge, Intelligence
        core_services_healthy = (
            component_health.get("memgraph_connected", False)
            and component_health.get("qdrant_connected", False)
            and component_health.get("embedding_service_connected", False)
        )
        status = "healthy" if core_services_healthy else "degraded"

        health_status = {
            "status": status,
            "memgraph_connected": component_health.get("memgraph_connected", False),
            "intelligence_connected": component_health.get(
                "intelligence_connected", False
            ),
            "bridge_connected": component_health.get("bridge_connected", False),
            "embedding_service_connected": component_health.get(
                "embedding_service_connected", False
            ),
            "vector_index_ready": True,  # Assume ready if orchestrator initialized
            "service_version": "1.0.0",
        }

        # Log health check results
        search_service_logger.log_health_check(health_status)

        return HealthStatus(**health_status)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status = {
            "status": "unhealthy",
            "memgraph_connected": False,
            "intelligence_connected": False,
            "bridge_connected": False,
            "embedding_service_connected": False,
            "vector_index_ready": False,
            "service_version": "1.0.0",
            "error": str(e),
        }
        search_service_logger.log_health_check(health_status)
        return HealthStatus(**health_status)


@app.post("/search", response_model=SearchResponse)
async def enhanced_search(
    request: SearchRequest, http_request: Request
) -> SearchResponse:
    """
    Perform enhanced search with multiple modes.

    Supports:
    - Semantic search using vector embeddings
    - Structural search using graph traversal
    - Relational search using traditional database queries
    - Hybrid search combining all methods
    """
    time.time()

    # Extract correlation headers and set context
    correlation_headers = CorrelationHeaders.extract_headers(dict(http_request.headers))
    search_service_logger.set_request_context(
        request_id=correlation_headers.get("request_id"),
        correlation_id=correlation_headers.get("correlation_id"),
        pipeline_correlation_id=correlation_headers.get("pipeline_id"),
    )

    # Log search query start
    search_params = {
        "entity_types": (
            [et.value for et in request.entity_types] if request.entity_types else []
        ),
        "limit": request.limit,
        "offset": request.offset,
        "include_content": request.include_content,
        "similarity_threshold": getattr(request, "similarity_threshold", None),
    }

    request_id = search_service_logger.log_search_query_start(
        query=request.query, search_mode=request.mode.value, search_params=search_params
    )

    try:
        if not search_orchestrator:
            search_service_logger.log_search_query_error(
                query=request.query,
                search_mode=request.mode.value,
                error=Exception("Search service not initialized"),
                error_stage="initialization_check",
                request_id=request_id,
            )
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        # Perform the search with orchestrator
        response = await search_orchestrator.search(request)

        # Extract search component information for logging
        search_components = {
            "total_results": len(response.results),
            "vector_results": len(
                [r for r in response.results if hasattr(r, "similarity_score")]
            ),
            "graph_results": len(
                [r for r in response.results if hasattr(r, "relationships")]
            ),
            "mode_used": request.mode.value,
        }

        # Log successful completion
        search_service_logger.log_search_query_complete(
            query=request.query,
            search_mode=request.mode.value,
            results_count=len(response.results),
            search_components=search_components,
            request_id=request_id,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        search_service_logger.log_search_query_error(
            query=request.query,
            search_mode=request.mode.value,
            error=e,
            error_stage="search_execution",
            request_id=request_id,
        )
        logger.error(f"Enhanced search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=SearchResponse)
async def quick_search(
    q: str = Query(..., description="Search query"),
    mode: SearchMode = Query(SearchMode.HYBRID, description="Search mode"),
    entity_types: Optional[List[EntityType]] = Query(
        None, description="Filter by entity types"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    http_request: Request = None,
) -> SearchResponse:
    """
    Quick search endpoint with query parameters.

    Convenient GET endpoint for simple searches.
    """
    request = SearchRequest(
        query=q, mode=mode, entity_types=entity_types, limit=limit, offset=offset
    )

    return await enhanced_search(request, http_request)


@app.post("/search/patterns")
async def search_patterns(
    query: str,
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 50,
    http_request: Request = None,
) -> Dict[str, Any]:
    """
    Search for code and execution patterns with intelligent filtering.

    Args:
        query: Search query for pattern matching
        pattern_type: Filter by pattern type ('code', 'execution', 'document')
        min_confidence: Minimum pattern confidence score (0.0-1.0)
        limit: Maximum number of results (default: 50)

    Returns:
        Pattern search results with metadata including:
        - query: Original search query
        - pattern_type: Pattern type filter (if applied)
        - results: List of matching patterns with confidence scores
        - count: Total number of results
    """
    start_time = time.time()

    # Extract correlation headers and set context
    correlation_headers = CorrelationHeaders.extract_headers(dict(http_request.headers))
    search_service_logger.set_request_context(
        request_id=correlation_headers.get("request_id"),
        correlation_id=correlation_headers.get("correlation_id"),
        pipeline_correlation_id=correlation_headers.get("pipeline_id"),
    )

    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        # Validate pattern_type if provided
        if pattern_type and pattern_type not in ["code", "execution", "document"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pattern_type: {pattern_type}. Must be 'code', 'execution', or 'document'",
            )

        # Validate min_confidence
        if not 0.0 <= min_confidence <= 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid min_confidence: {min_confidence}. Must be between 0.0 and 1.0",
            )

        logger.info(
            f"Pattern search request | query={query} | "
            f"pattern_type={pattern_type} | min_confidence={min_confidence} | limit={limit}"
        )

        # Generate embedding for the query
        vector_engine = search_orchestrator.vector_engine
        embeddings = await vector_engine.generate_embeddings([query])

        if not embeddings or len(embeddings) == 0:
            raise HTTPException(
                status_code=500, detail="Failed to generate query embedding"
            )

        # Check if individual embedding is None
        if embeddings[0] is None:
            logger.error(
                f"❌ [EMBEDDING FAILED] Pattern search query embedding failed | "
                f"query={query} | reason=embedding_generation_failed"
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to generate query embedding - query may exceed token limit",
            )

        query_vector = embeddings[0]

        # Get Qdrant adapter and perform pattern search
        qdrant_adapter = (
            vector_engine.qdrant_adapter
            if hasattr(vector_engine, "qdrant_adapter")
            else None
        )

        if not qdrant_adapter:
            raise HTTPException(
                status_code=503, detail="Vector search adapter not available"
            )

        # Perform pattern search
        results = await qdrant_adapter.search_patterns(
            query_vector=query_vector,
            query=query,
            pattern_type=pattern_type,
            min_confidence=min_confidence,
            limit=limit,
        )

        search_time = (time.time() - start_time) * 1000

        logger.info(
            f"Pattern search completed | results={len(results)} | "
            f"search_time_ms={search_time:.2f}"
        )

        return {
            "query": query,
            "pattern_type": pattern_type,
            "min_confidence": min_confidence,
            "results": [
                {
                    "entity_id": r.entity_id,
                    "title": r.title,
                    "content": r.content,
                    "pattern_type": r.pattern_type,
                    "pattern_name": r.pattern_name,
                    "pattern_confidence": r.pattern_confidence,
                    "node_types": r.node_types,
                    "use_cases": r.use_cases,
                    "examples": r.examples,
                    "file_path": r.file_path,
                    "relevance_score": r.relevance_score,
                    "quality_score": r.quality_score,
                    "onex_compliance": r.onex_compliance,
                    "onex_type": r.onex_type,
                    "project_name": r.project_name,
                    "relative_path": r.relative_path,
                }
                for r in results
            ],
            "count": len(results),
            "search_time_ms": search_time,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pattern search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/relationships", response_model=RelationshipSearchResponse)
async def relationship_search(
    request: RelationshipSearchRequest,
) -> RelationshipSearchResponse:
    """
    Find entity relationships using graph traversal.

    Discovers connections and paths between entities in the knowledge graph.
    """
    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        response = await search_orchestrator.graph_engine.relationship_search(request)
        return response

    except Exception as e:
        logger.error(f"Relationship search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/similar/{entity_id}")
async def find_similar_entities(
    entity_id: str,
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    """
    Find entities similar to a given entity using vector similarity.
    """
    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        similar_entities = await search_orchestrator.vector_engine.get_similar_entities(
            entity_id, limit, threshold
        )

        return {
            "entity_id": entity_id,
            "similar_entities": [
                {"entity_id": eid, "similarity_score": score}
                for eid, score in similar_entities
            ],
            "count": len(similar_entities),
        }

    except Exception as e:
        logger.error(f"Similar entity search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/related/{entity_id}")
async def find_related_entities(
    entity_id: str,
    max_depth: int = Query(3, ge=1, le=5),
    relationship_types: Optional[List[str]] = Query(None),
) -> Dict[str, Any]:
    """
    Find entities related to a given entity through graph relationships.
    """
    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        related_entities = await search_orchestrator.graph_engine.find_related_entities(
            entity_id, max_depth, relationship_types
        )

        return {
            "entity_id": entity_id,
            "related_entities": related_entities,
            "count": len(related_entities),
            "max_depth": max_depth,
        }

    except Exception as e:
        logger.error(f"Related entity search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/path/{source_id}/{target_id}")
async def find_entity_path(
    source_id: str, target_id: str, max_depth: int = Query(5, ge=1, le=10)
) -> Dict[str, Any]:
    """
    Find shortest path between two entities in the knowledge graph.
    """
    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        path = await search_orchestrator.graph_engine.find_shortest_path(
            source_id, target_id, max_depth
        )

        return {
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "path": path,
            "path_length": len(path) - 1 if path else None,
            "found": path is not None,
        }

    except Exception as e:
        logger.error(f"Path finding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/analytics", response_model=SearchAnalytics)
async def get_search_analytics(
    time_period_days: int = Query(30, ge=1, le=365),
    entity_types: Optional[List[EntityType]] = Query(None),
) -> SearchAnalytics:
    """
    Get search analytics and usage statistics.

    Note: This is a placeholder implementation.
    Production would track actual search patterns and usage.
    """
    # REAL IMPLEMENTATION: Get actual analytics from search statistics
    try:
        # Get real search statistics from the database or cache
        stats = search_service_stats()

        # Extract real analytics data
        total_searches = stats.get("total_requests", 0)

        # Get popular queries from actual search logs (if available)
        popular_queries = []
        if hasattr(qdrant_adapter, "get_popular_queries"):
            popular_queries = qdrant_adapter.get_popular_queries(limit=10)

        # Get search mode usage from stats
        search_modes_usage = stats.get("search_capabilities", {})

        # Calculate average response time from recent searches
        response_times = stats.get("performance_metrics", {})
        average_response_time = response_times.get("average_search_time_ms", 0.0)

        # Get entity type preferences from usage patterns
        entity_preferences = {}
        if hasattr(qdrant_adapter, "get_entity_usage_stats"):
            entity_preferences = qdrant_adapter.get_entity_usage_stats()

        return SearchAnalytics(
            total_searches=total_searches,
            popular_queries=popular_queries,
            search_modes_usage=search_modes_usage,
            average_response_time_ms=average_response_time,
            entity_type_preferences=entity_preferences,
        )

    except Exception as e:
        logger.error(f"Failed to get real analytics: {e}")
        # Fallback to minimal real data structure
        return SearchAnalytics(
            total_searches=0,
            popular_queries=[],
            search_modes_usage={},
            average_response_time_ms=0.0,
            entity_type_preferences={},
        )


@app.get("/search/stats")
async def get_search_stats() -> Dict[str, Any]:
    """
    Get current search service statistics and performance metrics.
    """
    try:
        if not search_orchestrator:
            return {"error": "Search service not initialized"}

        # Get vector cache stats
        vector_stats = search_orchestrator.vector_engine.get_cache_stats()

        # Get health status
        health_status = await search_orchestrator.health_check()

        return {
            "service_status": "operational",
            "vector_index": vector_stats,
            "component_health": health_status,
            "search_capabilities": {
                "semantic_search": health_status.get(
                    "embedding_service_connected", False
                ),
                "graph_search": health_status.get("memgraph_connected", False),
                "hybrid_search": all(
                    [
                        health_status.get("embedding_service_connected", False),
                        health_status.get("memgraph_connected", False),
                    ]
                ),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        return {"error": str(e)}


def _prepare_embedding_content(
    content: str, metadata: Dict[str, Any], source_path: str
) -> str:
    """
    Prepare content for embedding generation with enhanced file path emphasis.

    This function extracts file path components and creates a path emphasis block
    that gets prepended to the content. The path information is repeated 2x to
    increase its weight in the embedding, improving file path search recall.

    Args:
        content: Original document content
        metadata: Document metadata dictionary
        source_path: File path (absolute or relative)

    Returns:
        Enhanced content with path emphasis block prepended

    Example:
        Input: content="def foo(): pass", source_path="services/search/utils.py"
        Output:
            FILE_PATH: services/search/utils.py
            FILE_NAME: utils.py
            FILE_NAME_NO_EXT: utils
            DIRECTORY: services/search
            FILE_EXTENSION: .py
            PATH_COMPONENTS: services search utils.py
            SEARCHABLE_PATH: services search utils py

            FILE_PATH: services/search/utils.py
            FILE_NAME: utils.py
            ...

            def foo(): pass
    """
    from pathlib import Path

    # Extract path components
    try:
        path_obj = Path(source_path)
        filename = path_obj.name
        filename_no_ext = path_obj.stem
        extension = path_obj.suffix
        directory = str(path_obj.parent) if path_obj.parent != Path(".") else ""

        # Get all path components (directory parts + filename)
        path_components = list(path_obj.parts)

        # Create searchable path (replace separators and dots with spaces)
        searchable_path = (
            source_path.replace("/", " ").replace("\\", " ").replace(".", " ")
        )

        # Build path emphasis block
        path_block = f"""FILE_PATH: {source_path}
FILE_NAME: {filename}
FILE_NAME_NO_EXT: {filename_no_ext}
DIRECTORY: {directory}
FILE_EXTENSION: {extension}
PATH_COMPONENTS: {" ".join(path_components)}
SEARCHABLE_PATH: {searchable_path}"""

        # Repeat path block 2x for higher embedding weight
        repeated_path_block = f"{path_block}\n\n{path_block}"

        # Prepend to content
        enhanced_content = f"{repeated_path_block}\n\n{content}"

        return enhanced_content

    except Exception as e:
        logger.warning(
            f"Failed to extract path components from {source_path}: {e}. "
            "Using original content without path emphasis."
        )
        return content


@app.post("/vectorize/document")
async def vectorize_document(
    request: Dict[str, Any], http_request: Request
) -> Dict[str, Any]:
    """
    Vectorize and index a document for real-time RAG availability.

    This endpoint is called by the intelligence service to immediately
    vectorize new documents and make them searchable.

    Args:
        request: Vectorization request with fields:
            - document_id: Unique document identifier
            - project_id: Associated project ID
            - content: Full document content (text)
            - metadata: Document metadata
            - source_path: Document source path
            - entities: Extracted entities (optional)
    """
    vectorization_start_time = time.time()

    # Extract correlation headers and set context
    correlation_headers = CorrelationHeaders.extract_headers(dict(http_request.headers))
    search_service_logger.set_request_context(
        request_id=correlation_headers.get("request_id"),
        correlation_id=correlation_headers.get("correlation_id"),
        pipeline_correlation_id=correlation_headers.get("pipeline_id"),
    )

    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        # Extract required fields
        document_id = request.get("document_id")
        project_id = request.get("project_id")
        content = request.get("content", "")
        metadata = request.get("metadata", {})
        source_path = request.get("source_path", "")
        entities = request.get("entities", [])

        if not document_id or not content:
            raise HTTPException(
                status_code=400, detail="document_id and content are required"
            )

        # Log pipeline correlation for document processing
        search_service_logger.log_pipeline_correlation(
            document_id=document_id,
            pipeline_stage="vectorization_start",
            upstream_correlation_id=correlation_headers.get("correlation_id"),
        )

        logger.info(
            f"🎯 [INDEXING PIPELINE] Vectorizing document | document_id={document_id} | "
            f"content_length={len(content)} | entities_count={len(entities)} | source_path={source_path}"
        )

        # Prepare content with file path emphasis for better path-based search
        enhanced_content = _prepare_embedding_content(content, metadata, source_path)
        logger.debug(
            f"📝 [INDEXING PIPELINE] Enhanced content with path emphasis | "
            f"document_id={document_id} | original_length={len(content)} | "
            f"enhanced_length={len(enhanced_content)}"
        )

        # Check if chunking is enabled and needed
        enable_chunking = os.getenv("ENABLE_CHUNKING", "true").lower() == "true"
        vector_engine = search_orchestrator.vector_engine

        # Determine if document needs chunking
        chunks_to_process = []
        if enable_chunking and document_chunker:
            # Check if document needs chunking
            if document_chunker.needs_chunking(enhanced_content):
                # Chunk the document
                chunks = document_chunker.chunk_document(enhanced_content, document_id)
                logger.info(
                    f"📄 [CHUNKING] Document exceeds token limit, splitting into {len(chunks)} chunks | "
                    f"document_id={document_id}"
                )
                chunks_to_process = chunks
            else:
                # Document is within token limits, no chunking needed
                logger.debug(
                    f"📄 [CHUNKING] Document within token limits, no chunking needed | "
                    f"document_id={document_id}"
                )
                chunks_to_process = []
        else:
            # Chunking disabled or not available
            if not enable_chunking:
                logger.debug(
                    "📄 [CHUNKING] Chunking disabled via ENABLE_CHUNKING=false"
                )
            chunks_to_process = []

        # Process document: either as chunks or as single document
        if chunks_to_process:
            # CHUNKED PROCESSING: Generate embeddings for each chunk
            logger.info(
                f"🧮 [INDEXING PIPELINE] Generating embeddings for {len(chunks_to_process)} chunks | "
                f"document_id={document_id}"
            )

            indexed_chunks = 0
            failed_chunks = 0

            for chunk in chunks_to_process:
                try:
                    # Extract chunk data (chunks are dictionaries)
                    chunk_text = chunk["chunk_text"]
                    chunk_index = chunk["chunk_index"]
                    total_chunks = chunk["total_chunks"]
                    chunk_token_count = chunk["token_count"]

                    # Generate embedding for this chunk
                    chunk_embedding = await vector_engine.generate_embeddings(
                        [chunk_text]
                    )

                    if (
                        not chunk_embedding
                        or len(chunk_embedding) == 0
                        or chunk_embedding[0] is None
                    ):
                        logger.warning(
                            f"⚠️ [CHUNK {chunk_index + 1}/{total_chunks}] "
                            f"Embedding generation failed | document_id={document_id}"
                        )
                        failed_chunks += 1
                        continue

                    # Create chunk-specific metadata
                    chunk_metadata = {
                        **metadata,
                        "document_id": document_id,
                        "project_id": project_id,
                        "entity_type": "page",
                        "title": metadata.get("title", f"Document {document_id}"),
                        "content": chunk_text[:100000],
                        "source_path": source_path,
                        "created_at": metadata.get("created_at"),
                        "updated_at": metadata.get("updated_at"),
                        "entity_count": len(entities),
                        "document_type": metadata.get("document_type"),
                        "quality_score": request.get("quality_score")
                        or metadata.get("quality_score"),
                        "onex_compliance": request.get("onex_compliance")
                        or metadata.get("onex_compliance"),
                        "onex_type": request.get("onex_type")
                        or metadata.get("onex_type"),
                        "concepts": request.get("concepts")
                        or metadata.get("concepts", []),
                        "themes": request.get("themes") or metadata.get("themes", []),
                        "relative_path": request.get("relative_path")
                        or metadata.get("relative_path"),
                        "project_name": request.get("project_name")
                        or metadata.get("project_name"),
                        "content_hash": request.get("content_hash")
                        or metadata.get("content_hash"),
                        "language": detect_language_from_extension(
                            metadata.get("file_extension"), source_path
                        ),
                        # Chunk-specific metadata
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                        "is_chunk": True,
                        "parent_document_id": document_id,
                        "chunk_token_count": chunk_token_count,
                    }

                    # Add entity information to metadata
                    if entities:
                        entity_names = [entity.get("name", "") for entity in entities]
                        entity_types = [
                            entity.get("entity_type", "") for entity in entities
                        ]
                        chunk_metadata["entity_names"] = entity_names[:20]
                        chunk_metadata["entity_types"] = list(set(entity_types))

                    # Determine target collection
                    target_collection = determine_collection_for_document(metadata)

                    # Create chunk-specific vector ID
                    chunk_vector_id = f"{document_id}:chunk:{chunk_index}"

                    # Index the chunk
                    qdrant_adapter = (
                        vector_engine.qdrant_adapter
                        if hasattr(vector_engine, "qdrant_adapter")
                        else None
                    )

                    if qdrant_adapter:
                        chunk_indexed_count = await qdrant_adapter.index_vectors(
                            [(chunk_vector_id, chunk_embedding[0], chunk_metadata)],
                            collection_name=target_collection,
                        )
                    else:
                        chunk_indexed_count = (
                            await search_orchestrator._index_document_vectors(
                                [(chunk_vector_id, chunk_embedding[0], chunk_metadata)],
                                collection_name=target_collection,
                            )
                        )

                    if chunk_indexed_count > 0:
                        indexed_chunks += 1
                        logger.info(
                            f"✅ [CHUNK {chunk_index + 1}/{total_chunks}] "
                            f"Embedded successfully | document_id={document_id} | "
                            f"vector_id={chunk_vector_id} | tokens={chunk_token_count}"
                        )
                    else:
                        failed_chunks += 1
                        logger.warning(
                            f"❌ [CHUNK {chunk_index + 1}/{total_chunks}] "
                            f"Indexing failed | document_id={document_id}"
                        )

                except Exception as chunk_error:
                    failed_chunks += 1
                    logger.error(
                        f"❌ [CHUNK {chunk_index + 1}/{total_chunks}] "
                        f"Processing failed | document_id={document_id} | error={chunk_error}"
                    )

            # Auto-refresh vector index
            try:
                await _auto_refresh_vector_index()
                index_refreshed = True
            except Exception as refresh_error:
                logger.warning(f"Auto-refresh of vector index failed: {refresh_error}")
                index_refreshed = False

            # Calculate total vectorization duration
            vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000

            # Log successful chunked document vectorization
            if indexed_chunks > 0:
                search_service_logger.log_document_vectorization(
                    document_id=document_id,
                    vector_id=f"{document_id}:chunked",
                    content_length=len(content),
                    embedding_dimensions=(
                        len(chunk_embedding[0])
                        if chunk_embedding and chunk_embedding[0] is not None
                        else 0
                    ),
                    collection_name=target_collection,
                    success=True,
                    duration_ms=vectorization_duration_ms,
                )

                search_service_logger.log_pipeline_correlation(
                    document_id=document_id,
                    pipeline_stage="vectorization_complete",
                    downstream_correlation_id=search_service_logger.generate_correlation_id(),
                )

                logger.info(
                    f"✅ [CHUNKING] Document chunked and vectorized successfully | "
                    f"document_id={document_id} | chunks_indexed={indexed_chunks}/{len(chunks_to_process)} | "
                    f"failed_chunks={failed_chunks} | index_refreshed={index_refreshed}"
                )

                return {
                    "success": True,
                    "document_id": document_id,
                    "project_id": project_id,
                    "vector_id": f"{document_id}:chunked",
                    "embedding_dimension": (
                        len(chunk_embedding[0])
                        if chunk_embedding and chunk_embedding[0] is not None
                        else 0
                    ),
                    "indexed": True,
                    "index_refreshed": index_refreshed,
                    "chunked": True,
                    "total_chunks": len(chunks_to_process),
                    "indexed_chunks": indexed_chunks,
                    "failed_chunks": failed_chunks,
                    "message": f"Document chunked into {len(chunks_to_process)} pieces and vectorized successfully",
                }
            else:
                # All chunks failed
                search_service_logger.log_document_vectorization(
                    document_id=document_id,
                    vector_id=f"{document_id}:chunked",
                    content_length=len(content),
                    embedding_dimensions=0,
                    collection_name=target_collection,
                    success=False,
                    duration_ms=vectorization_duration_ms,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"All {len(chunks_to_process)} chunks failed to index",
                )

        # STANDARD PROCESSING: Single document (no chunking)
        logger.info(
            f"🧮 [INDEXING PIPELINE] Generating embeddings | document_id={document_id}"
        )
        embedding = await vector_engine.generate_embeddings([enhanced_content])

        if not embedding or len(embedding) == 0:
            logger.error(
                f"❌ [INDEXING PIPELINE] Failed to generate embedding | document_id={document_id}"
            )
            raise HTTPException(
                status_code=500, detail="Failed to generate document embedding"
            )

        # Check if individual embedding is None (graceful degradation)
        if embedding[0] is None:
            logger.warning(
                f"❌ [EMBEDDING FAILED] Document vectorization skipped | "
                f"document_id={document_id} | reason=embedding_generation_failed | "
                f"content_length={len(content)} | possible_cause=token_limit_exceeded"
            )

            # Log failed vectorization with detailed metrics
            vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000
            search_service_logger.log_document_vectorization(
                document_id=document_id,
                vector_id=document_id,
                content_length=len(content),
                embedding_dimensions=0,
                collection_name="documents",
                success=False,
                duration_ms=vectorization_duration_ms,
            )

            return {
                "success": False,
                "document_id": document_id,
                "error": "Embedding generation failed - document may exceed token limit",
                "embedding_dimensions": 0,
                "content_length": len(content),
            }

        logger.info(
            f"✅ [INDEXING PIPELINE] Embedding generated | document_id={document_id} | dimension={len(embedding[0])}"
        )

        # Prepare vector metadata
        vector_metadata = {
            **metadata,
            "document_id": document_id,
            "project_id": project_id,
            "entity_type": "page",
            "title": metadata.get("title", f"Document {document_id}"),
            "content": content[
                :100000
            ],  # Store up to 100K characters (increased from 2K for full code examples)
            "source_path": source_path,
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "entity_count": len(entities),
            "document_type": metadata.get(
                "document_type"
            ),  # Ensure document_type is preserved
            # Quality and ONEX fields (from request metadata or top-level fields)
            "quality_score": request.get("quality_score")
            or metadata.get("quality_score"),
            "onex_compliance": request.get("onex_compliance")
            or metadata.get("onex_compliance"),
            "onex_type": request.get("onex_type") or metadata.get("onex_type"),
            "concepts": request.get("concepts") or metadata.get("concepts", []),
            "themes": request.get("themes") or metadata.get("themes", []),
            "relative_path": request.get("relative_path")
            or metadata.get("relative_path"),
            "project_name": request.get("project_name") or metadata.get("project_name"),
            "content_hash": request.get("content_hash") or metadata.get("content_hash"),
            "language": detect_language_from_extension(
                metadata.get("file_extension"), source_path
            ),
        }

        # Add entity information to metadata
        if entities:
            entity_names = [entity.get("name", "") for entity in entities]
            entity_types = [entity.get("entity_type", "") for entity in entities]
            vector_metadata["entity_names"] = entity_names[
                :20
            ]  # Limit for metadata size
            vector_metadata["entity_types"] = list(set(entity_types))

        # Determine target collection based on document type
        target_collection = determine_collection_for_document(metadata)
        logger.info(
            f"🎯 [INDEXING PIPELINE] Routing to collection | document_id={document_id} | collection={target_collection} | document_type={metadata.get('document_type', 'unknown')}"
        )

        # Index the vector
        logger.info(
            f"🗃️ [INDEXING PIPELINE] Indexing vector | document_id={document_id}"
        )
        qdrant_adapter = (
            vector_engine.qdrant_adapter
            if hasattr(vector_engine, "qdrant_adapter")
            else None
        )

        if qdrant_adapter:
            logger.info(
                f"📥 [INDEXING PIPELINE] Using Qdrant adapter for indexing | document_id={document_id} | collection={target_collection}"
            )
            indexed_count = await qdrant_adapter.index_vectors(
                [(document_id, embedding[0], vector_metadata)],
                collection_name=target_collection,
            )
            logger.info(
                f"✅ [INDEXING PIPELINE] Vector indexed in Qdrant | document_id={document_id} | collection={target_collection} | indexed_count={indexed_count}"
            )
        else:
            logger.warning(
                f"⚠️ [INDEXING PIPELINE] Qdrant adapter not available, using orchestrator fallback | document_id={document_id}"
            )
            # Fallback to orchestrator's vector indexing
            indexed_count = await search_orchestrator._index_document_vectors(
                [(document_id, embedding[0], vector_metadata)],
                collection_name=target_collection,
            )
            logger.info(
                f"✅ [INDEXING PIPELINE] Vector indexed via orchestrator | document_id={document_id} | collection={target_collection} | indexed_count={indexed_count}"
            )

        if indexed_count > 0:
            # Auto-refresh vector index for immediate availability
            try:
                await _auto_refresh_vector_index()
                index_refreshed = True
            except Exception as refresh_error:
                logger.warning(f"Auto-refresh of vector index failed: {refresh_error}")
                index_refreshed = False

            # Calculate total vectorization duration
            vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000

            # Log successful document vectorization
            search_service_logger.log_document_vectorization(
                document_id=document_id,
                vector_id=document_id,
                content_length=len(content),
                embedding_dimensions=len(embedding[0]),
                collection_name="documents",  # Default collection
                success=True,
                duration_ms=vectorization_duration_ms,
            )

            # Log pipeline correlation completion
            search_service_logger.log_pipeline_correlation(
                document_id=document_id,
                pipeline_stage="vectorization_complete",
                downstream_correlation_id=search_service_logger.generate_correlation_id(),
            )

            logger.info(
                f"Document vectorized successfully | document_id={document_id} | "
                f"vector_indexed={indexed_count > 0} | index_refreshed={index_refreshed}"
            )

            return {
                "success": True,
                "document_id": document_id,
                "project_id": project_id,
                "vector_id": document_id,
                "embedding_dimension": len(embedding[0]),
                "indexed": True,
                "index_refreshed": index_refreshed,
                "message": "Document vectorized and indexed successfully",
            }
        else:
            # Log failed vectorization
            vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000
            search_service_logger.log_document_vectorization(
                document_id=document_id,
                vector_id=document_id,
                content_length=len(content),
                embedding_dimensions=len(embedding[0]) if embedding else 0,
                collection_name="documents",
                success=False,
                duration_ms=vectorization_duration_ms,
            )
            raise HTTPException(
                status_code=500, detail="Failed to index document vector"
            )

    except HTTPException:
        raise
    except Exception as e:
        # Log vectorization error
        vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000
        document_id = request.get("document_id", "unknown")
        content = request.get("content", "")

        search_service_logger.log_document_vectorization(
            document_id=document_id,
            vector_id=document_id,
            content_length=len(content),
            embedding_dimensions=0,
            collection_name="documents",
            success=False,
            duration_ms=vectorization_duration_ms,
        )

        logger.error(f"Document vectorization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _auto_refresh_vector_index():
    """
    Auto-refresh vector indexes after new content is added.

    This ensures that newly indexed documents are immediately
    available in search results without manual intervention.
    """
    try:
        if not search_orchestrator:
            return

        # Check if auto-refresh is enabled
        auto_refresh_enabled = (
            os.getenv("AUTO_REFRESH_ENABLED", "true").lower() == "true"
        )
        if not auto_refresh_enabled:
            return

        # Refresh vector engine cache/indexes
        vector_engine = search_orchestrator.vector_engine

        if hasattr(vector_engine, "refresh_cache"):
            await vector_engine.refresh_cache()

        # Refresh Qdrant collections if available
        if hasattr(vector_engine, "qdrant_adapter"):
            qdrant_adapter = vector_engine.qdrant_adapter
            if qdrant_adapter:
                # Trigger optimization for better performance
                await qdrant_adapter.optimize_collection()
                await qdrant_adapter.optimize_collection(
                    qdrant_adapter.quality_collection
                )

        logger.debug("Vector index auto-refresh completed")

    except Exception as e:
        logger.warning(f"Auto-refresh failed: {e}")
        # Don't raise - this is a nice-to-have optimization


@app.post("/search/index/refresh")
async def refresh_vector_index() -> Dict[str, Any]:
    """
    Refresh the vector search index with latest data.

    Useful after new content has been added to the knowledge base.
    """
    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        # Re-initialize vector index
        await search_orchestrator._initialize_vector_index()

        # Get updated stats
        vector_stats = search_orchestrator.vector_engine.get_cache_stats()

        return {
            "success": True,
            "message": "Vector index refreshed successfully",
            "index_stats": vector_stats,
        }

    except Exception as e:
        logger.error(f"Vector index refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """Get comprehensive cache performance statistics."""
    request_id = get_pipeline_correlation().request_id
    search_service_logger.log_request(request_id, "cache_stats", {})

    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        # Get cache stats from search cache
        cache_stats = {}
        if (
            hasattr(search_orchestrator, "search_cache")
            and search_orchestrator.search_cache
        ):
            cache_metrics = await search_orchestrator.search_cache.get_cache_stats()
            cache_stats = {
                "cache_hits": cache_metrics.cache_hits,
                "cache_misses": cache_metrics.cache_misses,
                "total_requests": cache_metrics.total_requests,
                "hit_rate": cache_metrics.hit_rate,
                "miss_rate": cache_metrics.miss_rate,
                "average_response_time_ms": cache_metrics.average_response_time_ms,
                "memory_usage_mb": cache_metrics.memory_usage_mb,
                "redis_connected": cache_metrics.redis_connected,
                "last_updated": cache_metrics.last_updated.isoformat(),
            }
        else:
            cache_stats = {"error": "Search cache not initialized"}

        # Get vector engine cache stats
        vector_stats = search_orchestrator.vector_engine.get_cache_stats()

        return {
            "cache_performance": cache_stats,
            "vector_cache": vector_stats,
            "timestamp": time.time(),
        }

    except Exception as e:
        search_service_logger.log_error(
            error=e,
            error_stage="cache_stats",
            request_id=request_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )


@app.post("/cache/invalidate")
async def invalidate_cache(pattern: str = "*"):
    """Invalidate cache entries matching pattern for cache management."""
    request_id = get_pipeline_correlation().request_id
    search_service_logger.log_request(
        request_id, "cache_invalidate", {"pattern": pattern}
    )

    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        if (
            not hasattr(search_orchestrator, "search_cache")
            or not search_orchestrator.search_cache
        ):
            return {"message": "Search cache not available", "invalidated_count": 0}

        invalidated_count = await search_orchestrator.search_cache.invalidate_cache(
            pattern
        )

        return {
            "message": "Cache invalidated successfully",
            "pattern": pattern,
            "invalidated_count": invalidated_count,
        }

    except Exception as e:
        search_service_logger.log_error(
            error=e,
            error_stage="cache_invalidate",
            request_id=request_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to invalidate cache: {str(e)}"
        )


@app.post("/cache/optimize")
async def optimize_cache():
    """Optimize cache performance and clean up expired entries."""
    request_id = get_pipeline_correlation().request_id
    search_service_logger.log_request(request_id, "cache_optimize", {})

    try:
        if not search_orchestrator:
            raise HTTPException(
                status_code=503, detail="Search service not initialized"
            )

        if (
            not hasattr(search_orchestrator, "search_cache")
            or not search_orchestrator.search_cache
        ):
            return {"message": "Search cache not available", "optimization_stats": {}}

        optimization_stats = await search_orchestrator.search_cache.optimize_cache()

        return {
            "message": "Cache optimization completed",
            "optimization_stats": optimization_stats,
        }

    except Exception as e:
        search_service_logger.log_error(
            error=e,
            error_stage="cache_optimize",
            request_id=request_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to optimize cache: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SEARCH_SERVICE_PORT", 8055))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True, log_level="info")
