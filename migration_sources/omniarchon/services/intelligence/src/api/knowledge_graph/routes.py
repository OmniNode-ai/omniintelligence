"""
Knowledge Graph API Routes

FastAPI router for knowledge graph visualization and querying.
Provides endpoints to retrieve graph structure (nodes and edges) from Memgraph
for dashboard visualization.

Performance Target: <2s response time for graph queries
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import shared response formatters
from src.api.utils.response_formatters import (
    health_response,
    processing_time_metadata,
    success_response,
)

# Configure router
router = APIRouter(prefix="/api/intelligence/knowledge", tags=["knowledge-graph"])

# ============================================================================
# Request/Response Models
# ============================================================================


class GraphNode(BaseModel):
    """
    Represents a node in the knowledge graph.

    Nodes can be patterns, files, concepts, themes, or other entities.
    """

    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display label for the node")
    type: str = Field(
        ..., description="Node type (pattern, file, concept, theme, etc.)"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional node properties"
    )


class GraphEdge(BaseModel):
    """
    Represents an edge (relationship) in the knowledge graph.

    Edges connect nodes with typed relationships.
    """

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relationship: str = Field(
        ..., description="Relationship type (uses, depends_on, has_concept, etc.)"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional edge properties"
    )


class KnowledgeGraphResponse(BaseModel):
    """
    Complete knowledge graph response.

    Contains all nodes and edges for visualization.
    """

    nodes: List[GraphNode] = Field(
        default_factory=list, description="List of graph nodes"
    )
    edges: List[GraphEdge] = Field(
        default_factory=list, description="List of graph edges"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Query metadata and statistics"
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/graph", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(
    limit: int = Query(100, ge=1, le=1000, description="Maximum nodes to return"),
    node_types: Optional[str] = Query(
        None, description="Comma-separated node types to include (e.g., 'pattern,file')"
    ),
    min_quality_score: float = Query(
        0.0, ge=0.0, le=1.0, description="Minimum quality score for files"
    ),
    project_name: Optional[str] = Query(None, description="Filter by project name"),
) -> KnowledgeGraphResponse:
    """
    Get knowledge graph structure for visualization.

    **Query Strategy:**
    - Fetch nodes from Memgraph (Files, Concepts, Themes, Patterns)
    - Fetch relationships between nodes
    - Apply filters (node type, quality, project)
    - Format for D3.js/Cytoscape visualization

    **Performance:**
    - Target: <2s for 1000 nodes
    - Uses indexed Cypher queries

    **Returns:**
    - KnowledgeGraphResponse with nodes and edges

    **Example Response:**
    ```json
    {
        "nodes": [
            {
                "id": "file_1",
                "label": "auth.py",
                "type": "file",
                "properties": {
                    "quality_score": 0.87,
                    "onex_type": "effect"
                }
            },
            {
                "id": "concept_1",
                "label": "authentication",
                "type": "concept",
                "properties": {}
            }
        ],
        "edges": [
            {
                "source": "file_1",
                "target": "concept_1",
                "relationship": "HAS_CONCEPT",
                "properties": {
                    "confidence": 0.92
                }
            }
        ],
        "metadata": {
            "query_time_ms": 450,
            "node_count": 2,
            "edge_count": 1
        }
    }
    ```

    **Errors:**
    - 400: Invalid query parameters
    - 500: Graph query failed
    - 503: Memgraph unavailable
    """
    start_time = time.perf_counter()

    try:
        logger.info(
            f"GET /api/intelligence/knowledge/graph - "
            f"limit={limit}, node_types={node_types}, "
            f"min_quality_score={min_quality_score}, project_name={project_name}"
        )

        # Parse comma-separated node types
        node_type_list = None
        if node_types:
            node_type_list = [t.strip() for t in node_types.split(",")]

        # Import service (lazy import to avoid circular dependencies)
        from .service import KnowledgeGraphService

        # Initialize service
        service = KnowledgeGraphService()

        # Query graph data
        graph_data = await service.get_graph_data(
            limit=limit,
            node_types=node_type_list,
            min_quality_score=min_quality_score,
            project_name=project_name,
        )

        # Calculate query time
        query_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Add metadata
        graph_data["metadata"] = {
            "query_time_ms": query_time_ms,
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", [])),
            "limit_applied": limit,
            "filters": {
                "node_types": node_type_list,
                "min_quality_score": min_quality_score,
                "project_name": project_name,
            },
        }

        logger.info(
            f"Knowledge graph query completed - "
            f"nodes={len(graph_data.get('nodes', []))}, "
            f"edges={len(graph_data.get('edges', []))}, "
            f"query_time={query_time_ms}ms"
        )

        return KnowledgeGraphResponse(**graph_data)

    except ValueError as e:
        logger.error(f"Validation error during graph query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except ConnectionError as e:
        logger.error(f"Memgraph connection error: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Memgraph service unavailable: {str(e)}"
        )

    except Exception as e:
        logger.error(
            f"Graph query failed with unexpected error: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint for knowledge graph API.

    Returns:
        Status of knowledge graph service and Memgraph connectivity
    """
    from .service import KnowledgeGraphService

    service = KnowledgeGraphService()
    health_status = await service.check_health()

    return health_response(
        status=health_status.get("status", "unknown"),
        service="knowledge-graph-api",
        checks=health_status,
    )
