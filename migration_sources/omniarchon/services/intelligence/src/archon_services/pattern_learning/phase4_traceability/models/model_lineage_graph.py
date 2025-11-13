"""
Phase 4 Traceability - Lineage Graph Models

Models for pattern evolution lineage tracking.
Supports directed graphs showing pattern relationships and evolution.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class LineageRelationType(str, Enum):
    """Types of relationships between patterns in lineage graph."""

    DERIVED_FROM = "derived_from"  # Pattern derived from parent
    MERGED_WITH = "merged_with"  # Pattern merged with another
    REPLACED_BY = "replaced_by"  # Pattern replaced by newer version
    SPLIT_INTO = "split_into"  # Pattern split into multiple patterns
    INSPIRED_BY = "inspired_by"  # Pattern inspired by another


class NodeStatus(str, Enum):
    """Status of nodes in lineage graph."""

    ACTIVE = "active"  # Currently active pattern
    DEPRECATED = "deprecated"  # No longer recommended
    MERGED = "merged"  # Merged into another pattern
    ARCHIVED = "archived"  # Historical archive


class ModelLineageNode(BaseModel):
    """
    A node in the pattern lineage graph.

    Represents a single pattern at a specific version in the evolution chain.
    """

    pattern_id: UUID = Field(..., description="Pattern UUID")

    pattern_name: str = Field(..., description="Pattern name for display")

    version: int = Field(default=1, ge=1, description="Pattern version number")

    status: NodeStatus = Field(
        default=NodeStatus.ACTIVE, description="Current node status"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Node creation timestamp",
    )

    usage_count: int = Field(
        default=0, ge=0, description="Number of times this pattern version was used"
    )

    success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Success rate for this pattern version"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional node metadata for visualization"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "version": 2,
                "status": "active",
                "created_at": "2025-10-02T12:00:00Z",
                "usage_count": 42,
                "success_rate": 0.92,
                "metadata": {"tags": ["debugging", "api"], "quality_score": 0.95},
            }
        }
    )


class ModelLineageEdge(BaseModel):
    """
    An edge in the pattern lineage graph.

    Represents a relationship between two patterns.
    """

    source_pattern_id: UUID = Field(..., description="Source pattern UUID")

    target_pattern_id: UUID = Field(..., description="Target pattern UUID")

    relation_type: LineageRelationType = Field(..., description="Type of relationship")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Edge creation timestamp",
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional edge metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "target_pattern_id": "660e8400-e29b-41d4-a716-446655440000",
                "relation_type": "derived_from",
                "created_at": "2025-10-02T12:00:00Z",
                "metadata": {"reason": "Improved error handling based on feedback"},
            }
        }
    )


class ModelLineageGraph(BaseModel):
    """
    Complete pattern lineage graph.

    Directed graph showing pattern evolution and relationships.
    Supports multiple disconnected subgraphs.
    """

    nodes: Dict[str, ModelLineageNode] = Field(
        default_factory=dict, description="Dictionary of pattern_id -> LineageNode"
    )

    edges: List[ModelLineageEdge] = Field(
        default_factory=list, description="List of edges between nodes"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Graph creation timestamp",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Graph last update timestamp",
    )

    def add_node(self, node: ModelLineageNode) -> None:
        """Add a node to the graph."""
        self.nodes[str(node.pattern_id)] = node
        self.updated_at = datetime.now(timezone.utc)

    def add_edge(self, edge: ModelLineageEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
        self.updated_at = datetime.now(timezone.utc)

    def get_node(self, pattern_id: UUID) -> Optional[ModelLineageNode]:
        """Get a node by pattern ID."""
        return self.nodes.get(str(pattern_id))

    def get_ancestors(self, pattern_id: UUID) -> List[ModelLineageNode]:
        """
        Get all ancestor nodes for a given pattern.

        Follows DERIVED_FROM and INSPIRED_BY relationships backwards.
        """
        ancestors = []
        visited: Set[str] = set()

        def traverse(pid: str):
            if pid in visited:
                return
            visited.add(pid)

            for edge in self.edges:
                if str(edge.target_pattern_id) == pid:
                    if edge.relation_type in [
                        LineageRelationType.DERIVED_FROM,
                        LineageRelationType.INSPIRED_BY,
                    ]:
                        source_id = str(edge.source_pattern_id)
                        if source_id in self.nodes:
                            ancestors.append(self.nodes[source_id])
                            traverse(source_id)

        traverse(str(pattern_id))
        return ancestors

    def get_descendants(self, pattern_id: UUID) -> List[ModelLineageNode]:
        """
        Get all descendant nodes for a given pattern.

        Follows DERIVED_FROM and INSPIRED_BY relationships forwards.
        """
        descendants = []
        visited: Set[str] = set()

        def traverse(pid: str):
            if pid in visited:
                return
            visited.add(pid)

            for edge in self.edges:
                if str(edge.source_pattern_id) == pid:
                    if edge.relation_type in [
                        LineageRelationType.DERIVED_FROM,
                        LineageRelationType.INSPIRED_BY,
                    ]:
                        target_id = str(edge.target_pattern_id)
                        if target_id in self.nodes:
                            descendants.append(self.nodes[target_id])
                            traverse(target_id)

        traverse(str(pattern_id))
        return descendants

    def get_active_patterns(self) -> List[ModelLineageNode]:
        """Get all active patterns."""
        return [
            node for node in self.nodes.values() if node.status == NodeStatus.ACTIVE
        ]

    def get_deprecated_patterns(self) -> List[ModelLineageNode]:
        """Get all deprecated patterns."""
        return [
            node for node in self.nodes.values() if node.status == NodeStatus.DEPRECATED
        ]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": {
                    "550e8400-e29b-41d4-a716-446655440000": {
                        "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                        "pattern_name": "api_debug_v1",
                        "version": 1,
                        "status": "deprecated",
                        "created_at": "2025-10-01T12:00:00Z",
                        "usage_count": 100,
                        "success_rate": 0.85,
                        "metadata": {},
                    }
                },
                "edges": [
                    {
                        "source_pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                        "target_pattern_id": "660e8400-e29b-41d4-a716-446655440000",
                        "relation_type": "derived_from",
                        "created_at": "2025-10-02T12:00:00Z",
                        "metadata": {},
                    }
                ],
                "created_at": "2025-10-01T12:00:00Z",
                "updated_at": "2025-10-02T12:00:00Z",
            }
        }
    )
