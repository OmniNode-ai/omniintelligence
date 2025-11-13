"""
Pattern Relationships API Models

Pydantic models for pattern relationship API requests and responses.
"""

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RelationshipInfo(BaseModel):
    """Information about a single relationship."""

    pattern_id: str = Field(description="Related pattern UUID")
    pattern_name: str = Field(description="Related pattern name")
    strength: float = Field(
        description="Relationship strength (0.0-1.0)", ge=0.0, le=1.0
    )
    description: Optional[str] = Field(None, description="Relationship description")
    context: Optional[Dict] = Field(None, description="Additional context metadata")


class PatternRelationshipsResponse(BaseModel):
    """Response model for GET /api/patterns/{pattern_id}/relationships."""

    pattern_id: str = Field(description="Pattern UUID")
    uses: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Patterns this pattern imports/uses",
    )
    used_by: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Patterns that import/use this pattern",
    )
    extends: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Patterns this pattern extends (inheritance)",
    )
    extended_by: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Patterns that extend this pattern",
    )
    similar_to: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Semantically similar patterns",
    )
    composed_of: List[RelationshipInfo] = Field(
        default_factory=list,
        description="Patterns this is composed of (function calls)",
    )


class GraphNode(BaseModel):
    """Node in the pattern graph."""

    id: str = Field(description="Pattern UUID")
    name: str = Field(description="Pattern name")
    metadata: Optional[Dict] = Field(
        default_factory=dict,
        description="Node metadata (pattern_type, language, etc.)",
    )


class GraphEdge(BaseModel):
    """Edge in the pattern graph."""

    source: str = Field(description="Source pattern UUID")
    target: str = Field(description="Target pattern UUID")
    type: str = Field(description="Relationship type (uses, extends, etc.)")
    strength: float = Field(
        description="Relationship strength (0.0-1.0)", ge=0.0, le=1.0
    )
    metadata: Optional[Dict] = Field(
        default_factory=dict,
        description="Edge metadata",
    )


class PatternGraphResponse(BaseModel):
    """Response model for GET /api/patterns/graph."""

    root_pattern_id: str = Field(description="Root pattern UUID")
    depth: int = Field(description="Graph depth", ge=1)
    nodes: List[GraphNode] = Field(description="Graph nodes")
    edges: List[GraphEdge] = Field(description="Graph edges")
    node_count: int = Field(description="Total number of nodes")
    edge_count: int = Field(description="Total number of edges")


class DependencyChainResponse(BaseModel):
    """Response model for dependency chain query."""

    source_pattern_id: str = Field(description="Source pattern UUID")
    target_pattern_id: str = Field(description="Target pattern UUID")
    chain: Optional[List[str]] = Field(
        None,
        description="Dependency chain (list of pattern UUIDs), None if no path exists",
    )
    chain_length: Optional[int] = Field(
        None,
        description="Length of dependency chain, None if no path exists",
    )


class CircularDependency(BaseModel):
    """Information about a circular dependency."""

    cycle: List[str] = Field(description="List of pattern UUIDs forming the cycle")
    cycle_length: int = Field(description="Length of the cycle")


class CircularDependenciesResponse(BaseModel):
    """Response model for circular dependency detection."""

    pattern_id: str = Field(
        description="Pattern UUID checked for circular dependencies"
    )
    has_circular_dependencies: bool = Field(
        description="Whether circular dependencies were found"
    )
    circular_dependencies: List[CircularDependency] = Field(
        default_factory=list,
        description="List of circular dependency cycles",
    )
    cycle_count: int = Field(description="Total number of cycles found")


class CreateRelationshipRequest(BaseModel):
    """Request model for creating a relationship."""

    source_pattern_id: str = Field(description="Source pattern UUID")
    target_pattern_id: str = Field(description="Target pattern UUID")
    relationship_type: str = Field(
        description="Relationship type (uses, extends, composed_of, similar_to)"
    )
    strength: float = Field(
        description="Relationship strength (0.0-1.0)", ge=0.0, le=1.0
    )
    description: Optional[str] = Field(None, description="Relationship description")
    context: Optional[Dict] = Field(None, description="Additional context metadata")


class CreateRelationshipResponse(BaseModel):
    """Response model for relationship creation."""

    relationship_id: str = Field(description="Created relationship UUID")
    source_pattern_id: str = Field(description="Source pattern UUID")
    target_pattern_id: str = Field(description="Target pattern UUID")
    relationship_type: str = Field(description="Relationship type")
    strength: float = Field(description="Relationship strength")


class DetectRelationshipsRequest(BaseModel):
    """Request model for automatic relationship detection."""

    pattern_id: str = Field(description="Pattern UUID to analyze")
    source_code: str = Field(description="Pattern source code")
    detect_types: Optional[List[str]] = Field(
        None,
        description="Relationship types to detect (default: all types)",
    )


class DetectRelationshipsResponse(BaseModel):
    """Response model for automatic relationship detection."""

    pattern_id: str = Field(description="Analyzed pattern UUID")
    detected_relationships: List[CreateRelationshipRequest] = Field(
        description="Detected relationships ready to store"
    )
    detection_count: int = Field(description="Number of relationships detected")
