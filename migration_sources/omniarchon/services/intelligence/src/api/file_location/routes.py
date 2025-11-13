"""
File Location API Routes

FastAPI router for intelligent file search, project indexing, and status queries.
Integrates OnexTree, Metadata Stamping, and Archon Intelligence services.

Performance Targets:
- Indexing: <5 minutes for 1000 files
- Search (cold): <2s
- Search (warm/cache): <500ms
"""

import logging
import os
import time
from typing import Dict, List, Optional, Protocol

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from src.models.file_location import (
    ErrorResponse,
    FileSearchResult,
    ProjectIndexRequest,
    ProjectIndexResult,
    ProjectIndexStatus,
)

logger = logging.getLogger(__name__)

# Configure router
router = APIRouter(prefix="/api/intelligence/file-location", tags=["file-location"])

# ============================================================================
# TreeStampingBridge Protocol Interface
# ============================================================================


class TreeStampingBridgeProtocol(Protocol):
    """
    Protocol defining the interface for TreeStampingBridge implementations.

    This protocol allows both mock and real implementations to be used
    interchangeably via dependency injection.
    """

    async def index_project(
        self,
        project_path: str,
        project_name: str,
        include_tests: bool = True,
        force_reindex: bool = False,
    ) -> Dict:
        """Index entire project with full intelligence pipeline."""
        ...

    async def search_files(
        self,
        query: str,
        projects: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10,
    ) -> Dict:
        """Search for files across projects using semantic + quality ranking."""
        ...

    async def get_indexing_status(
        self, project_name: Optional[str] = None
    ) -> List[Dict]:
        """Get indexing status for projects."""
        ...


# ============================================================================
# Mock TreeStampingBridge (for testing/development)
# ============================================================================


class MockTreeStampingBridge:
    """
    Mock implementation of TreeStampingBridge for testing/development.

    Used when USE_MOCK_BRIDGE environment variable is set to "true".
    Provides stub responses that match the expected interface.
    """

    async def index_project(
        self,
        project_path: str,
        project_name: str,
        include_tests: bool = True,
        force_reindex: bool = False,
    ) -> ProjectIndexResult:
        """Mock project indexing."""
        logger.info(
            f"[MOCK] Indexing project: {project_name} at {project_path} "
            f"(include_tests={include_tests}, force_reindex={force_reindex})"
        )

        # Simulate processing time
        import asyncio

        await asyncio.sleep(0.5)

        return ProjectIndexResult(
            success=True,
            project_name=project_name,
            files_discovered=0,
            files_indexed=0,
            vector_indexed=0,
            graph_indexed=0,
            cache_warmed=False,
            duration_ms=500,
            errors=[],
            warnings=[
                "Using mock implementation - real TreeStampingBridge not yet integrated"
            ],
        )

    async def search_files(
        self,
        query: str,
        projects: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10,
    ) -> FileSearchResult:
        """Mock file search."""
        logger.info(
            f"[MOCK] Searching files: query='{query}', projects={projects}, "
            f"min_quality_score={min_quality_score}, limit={limit}"
        )

        # Simulate processing time
        import asyncio

        await asyncio.sleep(0.2)

        return FileSearchResult(
            success=True,
            results=[],
            query_time_ms=200,
            cache_hit=False,
            total_results=0,
            error=None,
        )

    async def get_indexing_status(
        self, project_name: Optional[str] = None
    ) -> List[ProjectIndexStatus]:
        """Mock indexing status."""
        logger.info(f"[MOCK] Getting indexing status for: {project_name or 'all'}")

        if project_name:
            return [
                ProjectIndexStatus(
                    project_name=project_name,
                    indexed=False,
                    file_count=0,
                    indexed_at=None,
                    last_updated=None,
                    status="unknown",
                )
            ]
        else:
            return []


# ============================================================================
# Bridge Dependency Injection
# ============================================================================


def get_bridge() -> TreeStampingBridgeProtocol:
    """
    Get TreeStampingBridge implementation based on environment configuration.

    Returns:
        Mock implementation if USE_MOCK_BRIDGE=true, otherwise real implementation

    Environment Variables:
        USE_MOCK_BRIDGE: Set to "true" to use mock bridge (default: "false")
    """
    use_mock = os.getenv("USE_MOCK_BRIDGE", "false").lower() == "true"

    if use_mock:
        logger.info("Using MockTreeStampingBridge (USE_MOCK_BRIDGE=true)")
        return MockTreeStampingBridge()
    else:
        logger.info("Using real TreeStampingBridge implementation")
        # Import here to avoid circular dependencies
        from ...integrations.tree_stamping_bridge import TreeStampingBridge

        return TreeStampingBridge()


# Initialize bridge via dependency injection
_bridge = get_bridge()


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/index", response_model=ProjectIndexResult)
async def index_project(request: ProjectIndexRequest) -> ProjectIndexResult:
    """
    Index a project's files with full intelligence pipeline.

    **Pipeline Steps:**
    1. Tree discovery (OnexTree)
    2. Intelligence generation (Bridge)
    3. Metadata stamping (Stamping)
    4. Vector indexing (Qdrant)
    5. Graph indexing (Memgraph)
    6. Cache warming (Valkey)

    **Performance:**
    - Target: <5 minutes for 1000 files
    - Batch size: 100 files

    **Returns:**
    - ProjectIndexResult with statistics

    **Errors:**
    - 400: Invalid request (bad project path)
    - 500: Indexing failed (service error)
    - 503: Required services unavailable
    """
    start_time = time.perf_counter()

    try:
        logger.info(
            f"POST /api/intelligence/file-location/index - "
            f"project_name={request.project_name}, path={request.project_path}"
        )

        # Call bridge service to index project
        result = await _bridge.index_project(
            project_path=request.project_path,
            project_name=request.project_name,
            include_tests=request.include_tests,
            force_reindex=request.force_reindex,
        )

        # Result is already a ProjectIndexResult object from the bridge
        logger.info(
            f"Project indexing completed - "
            f"project={request.project_name}, "
            f"files_indexed={result.files_indexed}, "
            f"duration={result.duration_ms}ms"
        )

        return result

    except ValueError as e:
        logger.error(f"Validation error during indexing: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except ConnectionError as e:
        logger.error(f"Service connection error during indexing: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Required service unavailable: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Indexing failed with unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.get("/search", response_model=FileSearchResult)
async def search_files(
    query: str = Query(..., description="Search query"),
    projects: Optional[str] = Query(None, description="Comma-separated project names"),
    min_quality_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(10, ge=1, le=100),
) -> FileSearchResult:
    """
    Search for files across projects using semantic + quality ranking.

    **Search Strategy:**
    - Semantic vector similarity (Qdrant)
    - Quality score filtering
    - Composite ranking (relevance + quality + compliance + recency)
    - Cache-first (5 min TTL)

    **Performance:**
    - Target (cold): <2s
    - Target (warm): <500ms

    **Returns:**
    - FileSearchResult with ranked matches

    **Errors:**
    - 400: Invalid query parameters
    - 500: Search failed
    - 503: Required services unavailable
    """
    start_time = time.perf_counter()

    try:
        logger.info(
            f"GET /api/intelligence/file-location/search - "
            f"query='{query}', projects={projects}, "
            f"min_quality_score={min_quality_score}, limit={limit}"
        )

        # Parse comma-separated projects
        project_list = projects.split(",") if projects else None

        # Call bridge service to search files
        result = await _bridge.search_files(
            query=query,
            projects=project_list,
            min_quality_score=min_quality_score,
            limit=limit,
        )

        # Result is already a FileSearchResult object from the bridge
        logger.info(
            f"File search completed - "
            f"results={len(result.results)}, "
            f"cache_hit={result.cache_hit}, "
            f"query_time={result.query_time_ms}ms"
        )

        return result

    except ValueError as e:
        logger.error(f"Validation error during search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except ConnectionError as e:
        logger.error(f"Service connection error during search: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Required service unavailable: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Search failed with unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/status", response_model=List[ProjectIndexStatus])
async def get_status(
    project_name: Optional[str] = Query(None, description="Project name filter")
) -> List[ProjectIndexStatus]:
    """
    Get indexing status for projects.

    **Data Source:**
    - Valkey cache (1 hour TTL)
    - Fallback: Qdrant query

    **Performance:**
    - Target: <100ms (from cache)

    **Returns:**
    - List of ProjectIndexStatus (all projects if name=None)

    **Errors:**
    - 500: Status check failed
    - 503: Required services unavailable
    """
    try:
        logger.info(
            f"GET /api/intelligence/file-location/status - "
            f"project_name={project_name or 'all'}"
        )

        # Call bridge service to get status
        statuses = await _bridge.get_indexing_status(project_name=project_name)

        logger.info(f"Status check completed - projects={len(statuses)}")

        # Bridge already returns List[ProjectIndexStatus] objects
        return statuses

    except ConnectionError as e:
        logger.error(f"Service connection error during status check: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Required service unavailable: {str(e)}"
        )

    except Exception as e:
        logger.error(
            f"Status check failed with unexpected error: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint for file location API.

    Returns:
        Status of file location service and dependencies
    """
    # Determine bridge implementation type
    bridge_impl = (
        "mock" if os.getenv("USE_MOCK_BRIDGE", "false").lower() == "true" else "real"
    )

    return {
        "status": "healthy",
        "service": "file-location-api",
        "bridge_implementation": bridge_impl,
        "endpoints": {
            "index": "/api/intelligence/file-location/index",
            "search": "/api/intelligence/file-location/search",
            "status": "/api/intelligence/file-location/status",
        },
    }
