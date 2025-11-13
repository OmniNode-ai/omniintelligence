"""
Pattern Relationships API Routes

FastAPI router for pattern relationship queries and graph operations.
Part of Pattern Relationship Detection and Graph Engine.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query
from src.api.pattern_relationships.models import (
    CircularDependenciesResponse,
    CreateRelationshipRequest,
    CreateRelationshipResponse,
    DependencyChainResponse,
    DetectRelationshipsRequest,
    DetectRelationshipsResponse,
    PatternGraphResponse,
    PatternRelationshipsResponse,
)
from src.api.pattern_relationships.service import PatternRelationshipsService
from src.api.utils import api_error_handler, handle_not_found

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/patterns", tags=["Pattern Relationships"])

# Initialize service
pattern_relationships_service = PatternRelationshipsService()


@router.get(
    "/{pattern_id}/relationships",
    response_model=PatternRelationshipsResponse,
    summary="Get Pattern Relationships",
    description=(
        "Get all relationships for a pattern, grouped by relationship type. "
        "Returns both outgoing relationships (uses, extends, composed_of, similar_to) "
        "and incoming relationships (used_by, extended_by)."
    ),
)
@api_error_handler("get_pattern_relationships")
async def get_pattern_relationships(
    pattern_id: str = Path(
        ...,
        description="Pattern UUID",
    ),
):
    """
    Get all relationships for a pattern.

    **Path Parameters:**
    - pattern_id: Pattern UUID

    **Response:**
    - uses: Patterns this pattern imports/uses
    - used_by: Patterns that import/use this pattern
    - extends: Patterns this pattern extends (inheritance)
    - extended_by: Patterns that extend this pattern
    - similar_to: Semantically similar patterns
    - composed_of: Patterns this is composed of (function calls)
    """
    try:
        result = await pattern_relationships_service.get_pattern_relationships(
            pattern_id
        )
        return PatternRelationshipsResponse(**result)
    except Exception as e:
        logger.error(f"Error getting relationships for pattern {pattern_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/graph",
    response_model=PatternGraphResponse,
    summary="Build Pattern Dependency Graph",
    description=(
        "Build a pattern dependency graph starting from a root pattern. "
        "Returns nodes and edges representing the knowledge graph. "
        "Supports configurable depth and relationship type filtering."
    ),
)
@api_error_handler("build_pattern_graph")
async def build_pattern_graph(
    root_pattern_id: str = Query(
        ...,
        description="Root pattern UUID to start graph traversal",
    ),
    depth: int = Query(
        2,
        ge=1,
        le=5,
        description="Maximum graph depth (default: 2)",
    ),
    relationship_types: Optional[List[str]] = Query(
        None,
        description="Filter by relationship types (default: all types)",
    ),
):
    """
    Build pattern dependency graph.

    **Query Parameters:**
    - root_pattern_id: Starting pattern UUID (required)
    - depth: Maximum graph depth (1-5, default: 2)
    - relationship_types: Filter by relationship types (optional)

    **Response:**
    - root_pattern_id: Starting pattern UUID
    - depth: Actual graph depth
    - nodes: List of graph nodes with metadata
    - edges: List of graph edges with relationship info
    - node_count: Total number of nodes
    - edge_count: Total number of edges
    """
    try:
        result = await pattern_relationships_service.build_pattern_graph(
            root_pattern_id=root_pattern_id,
            depth=depth,
            relationship_types=relationship_types,
        )
        return PatternGraphResponse(**result)
    except Exception as e:
        logger.error(f"Error building graph for pattern {root_pattern_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dependency-chain",
    response_model=DependencyChainResponse,
    summary="Find Dependency Chain",
    description=(
        "Find the shortest dependency chain between two patterns using BFS. "
        "Returns the chain of pattern UUIDs forming the path, or null if no path exists."
    ),
)
@api_error_handler("find_dependency_chain")
async def find_dependency_chain(
    source_pattern_id: str = Query(
        ...,
        description="Source pattern UUID",
    ),
    target_pattern_id: str = Query(
        ...,
        description="Target pattern UUID",
    ),
):
    """
    Find dependency chain between two patterns.

    **Query Parameters:**
    - source_pattern_id: Starting pattern UUID (required)
    - target_pattern_id: Target pattern UUID (required)

    **Response:**
    - source_pattern_id: Starting pattern UUID
    - target_pattern_id: Target pattern UUID
    - chain: List of pattern UUIDs forming the path (null if no path)
    - chain_length: Length of the chain (null if no path)
    """
    try:
        result = await pattern_relationships_service.find_dependency_chain(
            source_pattern_id=source_pattern_id,
            target_pattern_id=target_pattern_id,
        )
        return DependencyChainResponse(**result)
    except Exception as e:
        logger.error(
            f"Error finding dependency chain from {source_pattern_id} to {target_pattern_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{pattern_id}/circular-dependencies",
    response_model=CircularDependenciesResponse,
    summary="Detect Circular Dependencies",
    description=(
        "Detect circular dependencies involving a pattern using DFS. "
        "Returns all circular dependency cycles found, with warnings for patterns in cycles."
    ),
)
@api_error_handler("detect_circular_dependencies")
async def detect_circular_dependencies(
    pattern_id: str = Path(
        ...,
        description="Pattern UUID to check for circular dependencies",
    ),
):
    """
    Detect circular dependencies for a pattern.

    **Path Parameters:**
    - pattern_id: Pattern UUID (required)

    **Response:**
    - pattern_id: Checked pattern UUID
    - has_circular_dependencies: Whether circular dependencies were found
    - circular_dependencies: List of circular dependency cycles
    - cycle_count: Total number of cycles found
    """
    try:
        result = await pattern_relationships_service.detect_circular_dependencies(
            pattern_id
        )
        return CircularDependenciesResponse(**result)
    except Exception as e:
        logger.error(
            f"Error detecting circular dependencies for pattern {pattern_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/relationships",
    response_model=CreateRelationshipResponse,
    summary="Create Relationship",
    description=(
        "Create a relationship between two patterns. "
        "Validates relationship strength and prevents self-relationships."
    ),
    status_code=201,
)
@api_error_handler("create_relationship")
async def create_relationship(
    request: CreateRelationshipRequest,
):
    """
    Create a relationship between two patterns.

    **Request Body:**
    - source_pattern_id: Source pattern UUID
    - target_pattern_id: Target pattern UUID
    - relationship_type: Type (uses, extends, composed_of, similar_to)
    - strength: Relationship strength (0.0-1.0)
    - description: Optional description
    - context: Optional context metadata

    **Response:**
    - relationship_id: Created relationship UUID
    - source_pattern_id: Source pattern UUID
    - target_pattern_id: Target pattern UUID
    - relationship_type: Relationship type
    - strength: Relationship strength
    """
    try:
        result = await pattern_relationships_service.create_relationship(request)
        return CreateRelationshipResponse(**result)
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{pattern_id}/detect-relationships",
    response_model=DetectRelationshipsResponse,
    summary="Detect Relationships Automatically",
    description=(
        "Automatically detect relationships from pattern source code using AST analysis. "
        "Detects USES (imports), EXTENDS (inheritance), and COMPOSED_OF (function calls) relationships. "
        "Returns detected relationships ready to store."
    ),
)
@api_error_handler("detect_relationships")
async def detect_relationships(
    request: DetectRelationshipsRequest,
    pattern_id: str = Path(
        ...,
        description="Pattern UUID",
    ),
):
    """
    Automatically detect relationships from source code.

    **Path Parameters:**
    - pattern_id: Pattern UUID

    **Request Body:**
    - source_code: Pattern source code
    - detect_types: Relationship types to detect (optional)

    **Response:**
    - pattern_id: Analyzed pattern UUID
    - detected_relationships: List of detected relationships
    - detection_count: Number of relationships detected
    """
    try:
        # Get pattern name from database
        # For now, use pattern_id as name (should be looked up from database)
        pattern_name = pattern_id

        result = await pattern_relationships_service.detect_relationships_for_pattern(
            pattern_id=request.pattern_id,
            source_code=request.source_code,
            pattern_name=pattern_name,
            detect_types=request.detect_types,
        )
        return DetectRelationshipsResponse(**result)
    except Exception as e:
        logger.error(f"Error detecting relationships for pattern {pattern_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
