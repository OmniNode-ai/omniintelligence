#!/usr/bin/env python3
"""
Lineage Edge Model - ONEX Compliant

Represents relationships between patterns in the lineage graph,
tracking evolution paths, merge operations, and replacement chains.

Part of Track 3 Phase 4 - Pattern Traceability & Continuous Learning.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enums
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class EnumLineageRelationshipType(str, Enum):
    """Type of relationship between patterns in lineage graph."""

    PARENT_OF = "parent_of"  # Source is parent of target
    CHILD_OF = "child_of"  # Source is child of target
    DERIVED_FROM = "derived_from"  # Child derived from parent
    MERGED_FROM = "merged_from"  # Pattern merged from another
    MERGED_WITH = "merged_with"  # Pattern merged with another
    REPLACED_BY = "replaced_by"  # Pattern replaced by another
    FORKED_FROM = "forked_from"  # Divergent fork from parent
    REFINED_FROM = "refined_from"  # Refinement of parent
    SPECIALIZED_FROM = "specialized_from"  # Specialization of parent
    GENERALIZED_FROM = "generalized_from"  # Generalization of parent


class EnumEdgeStrength(str, Enum):
    """Strength of relationship between patterns."""

    WEAK = "weak"  # Minor relationship (e.g., distant fork)
    MODERATE = "moderate"  # Moderate relationship (e.g., refinement)
    MEDIUM = "moderate"  # True alias for MODERATE (same value)
    STRONG = "strong"  # Strong relationship (e.g., direct derivation)


# ============================================================================
# Lineage Edge Model
# ============================================================================


class ModelLineageEdge(BaseModel):
    """
    Represents a relationship between patterns in the lineage graph.

    This model captures the type, strength, and metadata of relationships
    between pattern versions, enabling complex lineage queries and analytics.

    Architecture:
        - PostgreSQL: Relationship data with JSONB metadata
        - Memgraph: Graph edges for traversal queries
        - Analytics: Relationship strength and evolution tracking
    """

    # Primary identification
    edge_id: UUID = Field(default_factory=uuid4, description="Unique edge identifier")

    # Relationship endpoints
    source_node_id: UUID = Field(..., description="Source pattern node ID (from)")

    target_node_id: UUID = Field(..., description="Target pattern node ID (to)")

    source_pattern_id: UUID = Field(
        ..., description="Source pattern ID (for quick lookup)"
    )

    target_pattern_id: UUID = Field(
        ..., description="Target pattern ID (for quick lookup)"
    )

    # Relationship type and strength
    relationship_type: EnumLineageRelationshipType = Field(
        ..., description="Type of relationship between patterns"
    )

    edge_strength: EnumEdgeStrength = Field(
        default=EnumEdgeStrength.MODERATE,
        description="Strength/confidence of this relationship",
    )

    # Creation metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this relationship was created (UTC)",
    )

    created_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Who or what created this relationship (user ID or system)",
    )

    # Relationship metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata storage for relationship details",
    )

    # Similarity metrics (for merge/replacement edges)
    similarity_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity score between patterns (0.0-1.0, for merges)",
    )

    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in this relationship (0.0-1.0)",
    )

    # Change tracking
    change_summary: Optional[str] = Field(
        default=None, description="Summary of changes from source to target"
    )

    breaking_changes: bool = Field(
        default=False, description="Whether this evolution introduced breaking changes"
    )

    # Lifecycle
    is_active: bool = Field(
        default=True, description="Whether this relationship is currently active"
    )

    deactivated_at: Optional[datetime] = Field(
        default=None, description="When this relationship was deactivated (UTC)"
    )

    deactivation_reason: Optional[str] = Field(
        default=None, description="Reason for deactivation"
    )

    # Timestamps
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp (UTC)",
    )

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "edge_id": "770e8400-e29b-41d4-a716-446655440003",
                "source_node_id": "440e8400-e29b-41d4-a716-446655440002",
                "target_node_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_pattern_id": "660e8400-e29b-41d4-a716-446655440004",
                "target_pattern_id": "660e8400-e29b-41d4-a716-446655440001",
                "relationship_type": "refined_from",
                "edge_strength": "strong",
                "created_at": "2025-10-02T12:00:00Z",
                "created_by": "agent-debug-intelligence",
                "metadata": {
                    "refinement_type": "performance_optimization",
                    "performance_improvement": 0.35,
                },
                "similarity_score": 0.92,
                "confidence_score": 0.95,
                "change_summary": "Optimized database query logic",
                "breaking_changes": False,
                "is_active": True,
                "deactivated_at": None,
                "deactivation_reason": None,
                "updated_at": "2025-10-02T12:00:00Z",
            }
        },
    )

    @field_validator("similarity_score", "confidence_score")
    @classmethod
    def validate_scores(cls, v: Optional[float]) -> Optional[float]:
        """Validate scores are within 0.0-1.0 range."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Score must be between 0.0 and 1.0")
        return v

    @field_validator("source_node_id", "target_node_id")
    @classmethod
    def validate_different_nodes(cls, v: UUID, info) -> UUID:
        """Validate source and target are different nodes."""
        # Note: This validator runs per field, so we check in post_init
        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        if self.source_node_id == self.target_node_id:
            raise ValueError("source_node_id and target_node_id must be different")

    # ========================================================================
    # Lifecycle Management Methods
    # ========================================================================

    def deactivate(self, reason: str) -> None:
        """
        Deactivate this relationship edge.

        Args:
            reason: Reason for deactivation
        """
        self.is_active = False
        self.deactivated_at = datetime.now(timezone.utc)
        self.deactivation_reason = reason
        self.updated_at = datetime.now(timezone.utc)

    def reactivate(self) -> None:
        """Reactivate this relationship edge."""
        self.is_active = True
        self.deactivated_at = None
        self.deactivation_reason = None
        self.updated_at = datetime.now(timezone.utc)

    # ========================================================================
    # Metadata Management Methods
    # ========================================================================

    def update_similarity(self, score: float) -> None:
        """
        Update similarity score for this relationship.

        Args:
            score: New similarity score (0.0-1.0)

        Raises:
            ValueError: If score is not in valid range
        """
        if not (0.0 <= score <= 1.0):
            raise ValueError("Similarity score must be between 0.0 and 1.0")

        self.similarity_score = score
        self.updated_at = datetime.now(timezone.utc)

    def update_confidence(self, score: float) -> None:
        """
        Update confidence score for this relationship.

        Args:
            score: New confidence score (0.0-1.0)

        Raises:
            ValueError: If score is not in valid range
        """
        if not (0.0 <= score <= 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")

        self.confidence_score = score
        self.updated_at = datetime.now(timezone.utc)

    def set_change_summary(self, summary: str, breaking: bool = False) -> None:
        """
        Set change summary and breaking changes flag.

        Args:
            summary: Summary of changes
            breaking: Whether changes are breaking
        """
        self.change_summary = summary
        self.breaking_changes = breaking
        self.updated_at = datetime.now(timezone.utc)

    # ========================================================================
    # Query Helper Methods
    # ========================================================================

    def is_evolution_edge(self) -> bool:
        """Check if this is an evolution edge (derived/refined/specialized/generalized)."""
        evolution_types = {
            EnumLineageRelationshipType.DERIVED_FROM,
            EnumLineageRelationshipType.REFINED_FROM,
            EnumLineageRelationshipType.SPECIALIZED_FROM,
            EnumLineageRelationshipType.GENERALIZED_FROM,
            EnumLineageRelationshipType.FORKED_FROM,
        }
        return self.relationship_type in evolution_types

    def is_merge_edge(self) -> bool:
        """Check if this is a merge edge."""
        return self.relationship_type == EnumLineageRelationshipType.MERGED_WITH

    def is_replacement_edge(self) -> bool:
        """Check if this is a replacement edge."""
        return self.relationship_type == EnumLineageRelationshipType.REPLACED_BY

    def has_breaking_changes(self) -> bool:
        """Check if this relationship introduced breaking changes."""
        return self.breaking_changes

    def is_strong_relationship(self) -> bool:
        """Check if this is a strong relationship."""
        return self.edge_strength == EnumEdgeStrength.STRONG

    def get_confidence_category(self) -> str:
        """
        Get confidence category based on confidence score.

        Returns:
            Category: 'high', 'medium', 'low', or 'unknown'
        """
        if self.confidence_score is None:
            return "unknown"
        elif self.confidence_score >= 0.8:
            return "high"
        elif self.confidence_score >= 0.5:
            return "medium"
        else:
            return "low"

    def to_graph_edge(self) -> Dict[str, Any]:
        """
        Convert to Memgraph edge properties.

        Returns:
            Dictionary suitable for Memgraph edge creation
        """
        return {
            "edge_id": str(self.edge_id),
            "relationship_type": self.relationship_type.value,
            "edge_strength": self.edge_strength.value,
            "created_at": int(self.created_at.timestamp()),
            "created_by": self.created_by,
            "similarity_score": self.similarity_score,
            "confidence_score": self.confidence_score,
            "breaking_changes": self.breaking_changes,
            "is_active": self.is_active,
        }

    def get_weight(self) -> float:
        """
        Get edge weight for graph algorithms.

        Weight is based on edge strength, similarity, and confidence.

        Returns:
            Weight value (0.0-1.0)
        """
        # Base weight from edge strength
        strength_weights = {
            EnumEdgeStrength.WEAK: 0.3,
            EnumEdgeStrength.MEDIUM: 0.6,
            EnumEdgeStrength.MODERATE: 0.6,
            EnumEdgeStrength.STRONG: 0.9,
        }
        base_weight = strength_weights[self.edge_strength]

        # Adjust by similarity and confidence if available
        if self.similarity_score is not None and self.confidence_score is not None:
            # Weighted average: 50% strength, 25% similarity, 25% confidence
            return (
                0.5 * base_weight
                + 0.25 * self.similarity_score
                + 0.25 * self.confidence_score
            )
        elif self.similarity_score is not None:
            return 0.7 * base_weight + 0.3 * self.similarity_score
        elif self.confidence_score is not None:
            return 0.7 * base_weight + 0.3 * self.confidence_score
        else:
            return base_weight
