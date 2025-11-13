"""
Pattern Learning Engine - Provenance Model

Tracks pattern origin, evolution, and lineage for audit and traceability.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternProvenance(BaseModel):
    """
    Tracks pattern origin and evolution chain.

    Provides audit trail for pattern creation, modification, and evolution
    to understand how patterns were learned and refined over time.
    """

    # Source information
    source_correlation_id: UUID = Field(
        ...,
        description="Correlation ID of the execution trace that generated this pattern",
    )

    parent_pattern_id: Optional[UUID] = Field(
        default=None, description="Parent pattern ID if this is an evolved version"
    )

    version: int = Field(
        default=1, ge=1, description="Pattern version number (increments on evolution)"
    )

    # Evolution chain
    evolution_chain: List[UUID] = Field(
        default_factory=list,
        description="List of pattern_ids showing evolution lineage (oldest to newest)",
    )

    # Creator information
    created_by: str = Field(
        default="system",
        description="Entity that created the pattern (system, user_id, agent_id)",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Pattern creation timestamp (UTC)",
    )

    # Modification tracking
    modified_by: Optional[str] = Field(
        default=None, description="Entity that last modified the pattern"
    )

    modified_at: Optional[datetime] = Field(
        default=None, description="Last modification timestamp (UTC)"
    )

    # Additional metadata
    creation_method: str = Field(
        default="automatic",
        description="How pattern was created (automatic, manual, evolved, merged)",
    )

    evolution_reason: Optional[str] = Field(
        default=None, description="Reason for pattern evolution (if applicable)"
    )

    def add_to_evolution_chain(self, parent_id: UUID) -> None:
        """
        Add parent pattern to evolution chain.

        Args:
            parent_id: UUID of the parent pattern
        """
        if parent_id not in self.evolution_chain:
            self.evolution_chain.append(parent_id)

    def mark_modified(self, modified_by: str) -> None:
        """
        Update modification tracking.

        Args:
            modified_by: Entity making the modification
        """
        self.modified_by = modified_by
        self.modified_at = datetime.now(timezone.utc)

    def get_lineage_depth(self) -> int:
        """
        Get depth of evolution lineage.

        Returns:
            Number of ancestors in evolution chain
        """
        return len(self.evolution_chain)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_correlation_id": "123e4567-e89b-12d3-a456-426614174000",
                "parent_pattern_id": "456e7890-e89b-12d3-a456-426614174000",
                "version": 2,
                "evolution_chain": ["456e7890-e89b-12d3-a456-426614174000"],
                "created_by": "system",
                "created_at": "2025-10-02T12:00:00Z",
                "modified_by": "agent-pattern-optimizer",
                "modified_at": "2025-10-02T14:30:00Z",
                "creation_method": "evolved",
                "evolution_reason": "Improved success rate from 0.75 to 0.92 with optimized hook sequence",
            }
        }
    )
