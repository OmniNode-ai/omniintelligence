"""
Pattern Learning Engine - Main Pattern Model

PostgreSQL source of truth with Qdrant payload generation.
Dual-database architecture: PostgreSQL (ACID) + Qdrant (semantic search).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.archon_services.pattern_learning.phase1_foundation.models.model_success_criteria import (
    ModelSuccessCriteria,
)


# NOTE: correlation_id support enabled for tracing
class PatternStatus(str, Enum):
    """Pattern lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DRAFT = "draft"
    ARCHIVED = "archived"


class ModelPattern(BaseModel):
    """
    Main Pattern model for PostgreSQL storage and Qdrant indexing.

    This model serves as the single source of truth for pattern data,
    with methods to generate Qdrant payloads for semantic search.

    Architecture:
        - PostgreSQL: Full pattern data with JSONB fields
        - Qdrant: Vector embeddings + metadata payload for fast search
    """

    # Primary identification
    pattern_id: UUID = Field(
        default_factory=uuid4,
        description="Unique pattern identifier (UUID for distributed systems)",
    )

    pattern_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Pattern category (e.g., 'debugging', 'api_design', 'performance')",
    )

    name: str = Field(..., min_length=1, description="Unique pattern name")

    description: Optional[str] = Field(
        default=None, description="Detailed pattern description"
    )

    # Versioning and evolution
    version: int = Field(
        default=1, ge=1, description="Pattern version for evolution tracking"
    )

    parent_pattern_id: Optional[UUID] = Field(
        default=None,
        description="Parent pattern ID for evolution chain (self-referencing)",
    )

    context_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash for duplicate detection",
    )

    # Execution details (JSONB in PostgreSQL)
    execution_trace: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete execution trace with hooks, endpoints, and timing",
    )

    success_criteria: ModelSuccessCriteria = Field(
        default_factory=ModelSuccessCriteria,
        description="Nested success criteria model for type-safe validation",
    )

    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Quality scores and ONEX compliance metrics"
    )

    performance_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Performance statistics (duration, resource usage, etc.)",
    )

    # Categorization
    tags: List[str] = Field(
        default_factory=list, description="Tags for filtering and categorization"
    )

    status: PatternStatus = Field(
        default=PatternStatus.ACTIVE, description="Pattern lifecycle status"
    )

    # Timestamps (timezone-aware)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Pattern creation timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp (UTC)",
    )

    last_matched_at: Optional[datetime] = Field(
        default=None, description="Last time pattern was matched (UTC)"
    )

    # Usage tracking
    match_count: int = Field(
        default=0, ge=0, description="Number of times pattern has been matched"
    )

    success_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Historical success rate (0.0-1.0)"
    )

    @field_validator("success_rate")
    @classmethod
    def validate_success_rate(cls, v: Optional[float]) -> Optional[float]:
        """Validate success_rate is within 0.0-1.0 range."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("success_rate must be between 0.0 and 1.0")
        return v

    def to_qdrant_payload(self) -> Dict[str, Any]:
        """
        Generate Qdrant payload metadata for semantic search.

        Returns metadata fields for filtering during vector search.
        This replaces the need for a separate PatternMetadata model.

        Returns:
            Dictionary with Qdrant-compatible metadata fields
        """
        return {
            "pattern_id": str(self.pattern_id),
            "pattern_type": self.pattern_type,
            "version": self.version,
            "status": self.status.value,
            "tags": self.tags,
            "quality_score": self.quality_metrics.get("overall_score", 0.0),
            "success_rate": self.success_rate or 0.0,
            "match_count": self.match_count,
            "created_at": int(self.created_at.timestamp()),
            "last_matched_at": (
                int(self.last_matched_at.timestamp()) if self.last_matched_at else None
            ),
        }

    def increment_match_count(self) -> None:
        """
        Increment match count and update last_matched_at timestamp.

        Should be called whenever pattern is matched to a user request.
        """
        self.match_count += 1
        self.last_matched_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_success_rate(self, new_outcome: bool) -> None:
        """
        Update success rate based on new pattern usage outcome.

        Uses running average calculation to update success_rate.

        Args:
            new_outcome: True if pattern usage was successful, False otherwise
        """
        if self.success_rate is None:
            # First usage
            self.success_rate = 1.0 if new_outcome else 0.0
        else:
            # Running average: (old_rate * old_count + new_outcome) / new_count
            total_successes = self.success_rate * (self.match_count - 1)
            if new_outcome:
                total_successes += 1
            self.success_rate = total_successes / self.match_count

        self.updated_at = datetime.now(timezone.utc)

    model_config = ConfigDict(
        use_enum_values=False,
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_type": "debugging",
                "name": "api_performance_debug_pattern",
                "description": "Pattern for debugging API performance issues with RAG intelligence",
                "version": 1,
                "parent_pattern_id": None,
                "context_hash": "a" * 64,
                "execution_trace": {
                    "agent": "agent-debug-intelligence",
                    "hooks": ["PreToolUse", "PostToolUse"],
                    "endpoints": ["/api/rag/query", "/api/intelligence/quality"],
                },
                "success_criteria": {
                    "execution_completed": True,
                    "no_errors": True,
                    "hooks_succeeded": True,
                    "quality_gates_passed": True,
                    "within_performance_thresholds": True,
                    "no_timeouts": True,
                    "intelligence_gathered": True,
                    "patterns_identified": True,
                    "user_confirmed_success": True,
                },
                "quality_metrics": {"overall_score": 0.92, "onex_compliance": 0.95},
                "performance_data": {"avg_duration_ms": 450, "p95_duration_ms": 650},
                "tags": ["debugging", "performance", "api"],
                "status": "active",
                "created_at": "2025-10-02T12:00:00Z",
                "updated_at": "2025-10-02T12:00:00Z",
                "last_matched_at": None,
                "match_count": 0,
                "success_rate": None,
            }
        },
    )
