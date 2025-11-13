#!/usr/bin/env python3
"""
Pattern Lineage Node Model - ONEX Compliant

Represents a pattern instance in the lineage graph with complete
version tracking, parent-child relationships, and lifecycle management.

Part of Track 3 Phase 4 - Pattern Traceability & Continuous Learning.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enums
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class EnumPatternLineageStatus(str, Enum):
    """Pattern lineage node lifecycle status."""

    ACTIVE = "active"  # Currently active and usable
    DEPRECATED = "deprecated"  # Deprecated but still available
    MERGED = "merged"  # Merged into another pattern
    ARCHIVED = "archived"  # Archived and no longer available
    DRAFT = "draft"  # Draft pattern, not yet validated


class EnumPatternEvolutionType(str, Enum):
    """Type of pattern evolution from parent."""

    CREATED = "created"  # Initial pattern creation (root pattern)
    REFINED = "refined"  # Refined version of parent
    REFINEMENT = "refinement"  # Improved version of parent
    SPECIALIZATION = "specialization"  # More specific variant
    GENERALIZATION = "generalization"  # More general variant
    FORK = "fork"  # Divergent evolution
    MERGE = "merge"  # Combination of multiple patterns


# ============================================================================
# Pattern Lineage Node Model
# ============================================================================


class ModelPatternLineageNode(BaseModel):
    """
    Represents a pattern instance in the lineage graph.

    This model tracks the complete lifecycle and evolution of a pattern,
    including versioning, parent-child relationships, and status transitions.

    Architecture:
        - PostgreSQL: Full lineage data with JSONB metadata
        - Memgraph: Graph representation for traversal queries
        - Qdrant: Semantic search across pattern lineage
    """

    # Primary identification
    node_id: UUID = Field(
        default_factory=uuid4, description="Unique node identifier in lineage graph"
    )

    pattern_id: UUID = Field(..., description="Reference to pattern in ModelPattern")

    # Version tracking
    version: int = Field(
        default=1, ge=1, description="Pattern version number (monotonically increasing)"
    )

    version_label: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Human-readable version label (e.g., 'v1.2-beta', 'stable')",
    )

    # Authorship and creation
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this version was created (UTC)",
    )

    created_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Who or what created this version (user ID or system)",
    )

    # Evolution relationships
    parent_ids: List[UUID] = Field(
        default_factory=list,
        description="Parent pattern node IDs (empty for root patterns)",
    )

    child_ids: List[UUID] = Field(
        default_factory=list,
        description="Child pattern node IDs derived from this version",
    )

    evolution_type: Optional[EnumPatternEvolutionType] = Field(
        default=None,
        description="Type of evolution from parent (None for root patterns)",
    )

    # Lifecycle status
    status: EnumPatternLineageStatus = Field(
        default=EnumPatternLineageStatus.DRAFT,
        description="Current lifecycle status of this pattern version",
    )

    deprecated_at: Optional[datetime] = Field(
        default=None,
        description="When pattern was deprecated (UTC, None if not deprecated)",
    )

    deprecated_reason: Optional[str] = Field(
        default=None, description="Reason for deprecation"
    )

    replaced_by_node_id: Optional[UUID] = Field(
        default=None,
        description="Node ID of replacement pattern (if deprecated/merged)",
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata storage for lineage tracking",
    )

    tags: List[str] = Field(
        default_factory=list, description="Tags for categorization and filtering"
    )

    # Performance tracking
    avg_execution_time_ms: Optional[float] = Field(
        default=None, ge=0.0, description="Average execution time for this version"
    )

    success_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Success rate for this version (0.0-1.0)",
    )

    usage_count: int = Field(
        default=0, ge=0, description="Number of times this version has been used"
    )

    # Timestamps
    last_used_at: Optional[datetime] = Field(
        default=None, description="When this version was last used (UTC)"
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp (UTC)",
    )

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "node_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_id": "660e8400-e29b-41d4-a716-446655440001",
                "version": 2,
                "version_label": "v2.0-stable",
                "created_at": "2025-10-02T12:00:00Z",
                "created_by": "agent-debug-intelligence",
                "parent_ids": ["440e8400-e29b-41d4-a716-446655440002"],
                "child_ids": [],
                "evolution_type": "refinement",
                "status": "active",
                "deprecated_at": None,
                "deprecated_reason": None,
                "replaced_by_node_id": None,
                "metadata": {
                    "improvement_description": "Optimized query performance",
                    "breaking_changes": False,
                },
                "tags": ["performance", "stable"],
                "avg_execution_time_ms": 450.5,
                "success_rate": 0.95,
                "usage_count": 142,
                "last_used_at": "2025-10-02T14:30:00Z",
                "updated_at": "2025-10-02T14:30:00Z",
            }
        },
    )

    @field_validator("success_rate")
    @classmethod
    def validate_success_rate(cls, v: Optional[float]) -> Optional[float]:
        """Validate success_rate is within 0.0-1.0 range."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("success_rate must be between 0.0 and 1.0")
        return v

    @field_validator("avg_execution_time_ms")
    @classmethod
    def validate_execution_time(cls, v: Optional[float]) -> Optional[float]:
        """Validate execution time is non-negative."""
        if v is not None and v < 0:
            raise ValueError("avg_execution_time_ms must be non-negative")
        return v

    # ========================================================================
    # Lifecycle Management Methods
    # ========================================================================

    def deprecate(self, reason: str, replaced_by: Optional[UUID] = None) -> None:
        """
        Mark this pattern version as deprecated.

        Args:
            reason: Reason for deprecation
            replaced_by: Optional node ID of replacement pattern
        """
        self.status = EnumPatternLineageStatus.DEPRECATED
        self.deprecated_at = datetime.now(timezone.utc)
        self.deprecated_reason = reason
        self.replaced_by_node_id = replaced_by
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        """Mark this pattern version as active."""
        if self.status == EnumPatternLineageStatus.DEPRECATED:
            # Clear deprecation info when reactivating
            self.deprecated_at = None
            self.deprecated_reason = None
            self.replaced_by_node_id = None

        self.status = EnumPatternLineageStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        """Archive this pattern version (permanent removal from active use)."""
        self.status = EnumPatternLineageStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)

    def merge_into(self, target_node_id: UUID) -> None:
        """
        Mark this pattern as merged into another pattern.

        Args:
            target_node_id: Node ID of the pattern this was merged into
        """
        self.status = EnumPatternLineageStatus.MERGED
        self.replaced_by_node_id = target_node_id
        self.updated_at = datetime.now(timezone.utc)

    # ========================================================================
    # Usage Tracking Methods
    # ========================================================================

    def record_usage(self, execution_time_ms: float, success: bool) -> None:
        """
        Record a usage of this pattern version.

        Updates usage_count, avg_execution_time_ms, success_rate, and last_used_at.

        Args:
            execution_time_ms: Execution time for this usage
            success: Whether the execution was successful
        """
        # Update usage count
        old_count = self.usage_count
        self.usage_count += 1

        # Update average execution time (running average)
        if self.avg_execution_time_ms is None:
            self.avg_execution_time_ms = execution_time_ms
        else:
            total_time = self.avg_execution_time_ms * old_count + execution_time_ms
            self.avg_execution_time_ms = total_time / self.usage_count

        # Update success rate (running average)
        if self.success_rate is None:
            self.success_rate = 1.0 if success else 0.0
        else:
            total_successes = self.success_rate * old_count + (1.0 if success else 0.0)
            self.success_rate = total_successes / self.usage_count

        # Update timestamps
        self.last_used_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    # ========================================================================
    # Relationship Management Methods
    # ========================================================================

    def add_parent(self, parent_node_id: UUID) -> None:
        """
        Add a parent node to this pattern.

        Args:
            parent_node_id: Node ID of parent pattern
        """
        if parent_node_id not in self.parent_ids:
            self.parent_ids.append(parent_node_id)
            self.updated_at = datetime.now(timezone.utc)

    def add_child(self, child_node_id: UUID) -> None:
        """
        Add a child node to this pattern.

        Args:
            child_node_id: Node ID of child pattern
        """
        if child_node_id not in self.child_ids:
            self.child_ids.append(child_node_id)
            self.updated_at = datetime.now(timezone.utc)

    def remove_child(self, child_node_id: UUID) -> None:
        """
        Remove a child node from this pattern.

        Args:
            child_node_id: Node ID of child pattern to remove
        """
        if child_node_id in self.child_ids:
            self.child_ids.remove(child_node_id)
            self.updated_at = datetime.now(timezone.utc)

    # ========================================================================
    # Query Helper Methods
    # ========================================================================

    def is_root(self) -> bool:
        """Check if this is a root pattern (no parents)."""
        return len(self.parent_ids) == 0

    def is_leaf(self) -> bool:
        """Check if this is a leaf pattern (no children)."""
        return len(self.child_ids) == 0

    def is_deprecated(self) -> bool:
        """Check if this pattern version is deprecated."""
        return self.status == EnumPatternLineageStatus.DEPRECATED

    def is_active(self) -> bool:
        """Check if this pattern version is active."""
        return self.status == EnumPatternLineageStatus.ACTIVE

    def has_replacement(self) -> bool:
        """Check if this pattern has a replacement."""
        return self.replaced_by_node_id is not None

    def to_graph_node(self) -> Dict[str, Any]:
        """
        Convert to Memgraph node properties.

        Returns:
            Dictionary suitable for Memgraph node creation
        """
        return {
            "node_id": str(self.node_id),
            "pattern_id": str(self.pattern_id),
            "version": self.version,
            "version_label": self.version_label,
            "status": self.status.value,
            "created_at": int(self.created_at.timestamp()),
            "created_by": self.created_by,
            "evolution_type": (
                self.evolution_type.value if self.evolution_type else None
            ),
            "tags": self.tags,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "avg_execution_time_ms": self.avg_execution_time_ms,
        }
