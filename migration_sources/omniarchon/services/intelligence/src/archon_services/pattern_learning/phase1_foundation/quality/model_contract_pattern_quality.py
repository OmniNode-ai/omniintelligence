"""
ONEX Contract Models: Pattern Quality Assessment

Purpose: Type-safe contracts for pattern quality assessment operations
Pattern: ONEX Contract-Driven Architecture
File: model_contract_pattern_quality.py

ONEX Compliant: Naming convention (Model<Name>), type safety, Pydantic models
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ============================================================================
# Quality Metrics Model
# ============================================================================


class ModelQualityMetrics(BaseModel):
    """
    Quality metrics for a pattern.

    All scores are normalized to 0.0-1.0 range (except complexity_score).
    """

    # Core quality metrics
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pattern reliability and confidence (0.0-1.0)",
    )
    usage_count: int = Field(
        default=0, ge=0, description="Number of times pattern has been used"
    )
    success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated success rate (0.0-1.0)"
    )

    # Code quality metrics
    complexity_score: int = Field(
        default=1, ge=1, description="Cyclomatic complexity (integer, typically 1-20+)"
    )
    maintainability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Code maintainability score (0.0-1.0)",
    )
    performance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated performance score (0.0-1.0)"
    )

    # Overall metrics
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score (0.0-1.0)"
    )
    onex_compliance_score: float = Field(
        ..., ge=0.0, le=1.0, description="ONEX compliance score (0.0-1.0)"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional quality metrics and analysis details",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "confidence_score": 0.92,
                "usage_count": 0,
                "success_rate": 0.88,
                "complexity_score": 5,
                "maintainability_score": 0.85,
                "performance_score": 0.90,
                "quality_score": 0.87,
                "onex_compliance_score": 0.95,
                "metadata": {
                    "relevance_score": 0.8,
                    "architectural_era": "modern_onex",
                    "legacy_indicators": [],
                },
            }
        }


# ============================================================================
# Pattern Quality Contract
# ============================================================================


class ModelContractPatternQuality(BaseModel):
    """
    Contract for pattern quality assessment operations.

    Used by NodePatternQualityAssessorCompute to define input for quality analysis.
    """

    # Contract identification
    name: str = Field(..., description="Contract name (operation identifier)")
    version: str = Field(
        default="1.0.0", description="Contract version (semantic versioning)"
    )
    description: Optional[str] = Field(default=None, description="Contract description")

    # Correlation tracking
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for distributed tracing"
    )

    # Pattern identification
    pattern_name: str = Field(..., description="Pattern name")
    pattern_type: str = Field(
        ..., description="Pattern type (code, architecture, etc.)"
    )
    language: str = Field(..., description="Programming language (python, etc.)")

    # Pattern content
    pattern_code: str = Field(..., description="Pattern source code to analyze")
    description: Optional[str] = Field(
        default=None, description="Pattern description (for confidence scoring)"
    )

    # Temporal metadata (optional, for relevance scoring)
    file_last_modified: Optional[datetime] = Field(
        default=None, description="File last modified timestamp"
    )
    git_commit_date: Optional[datetime] = Field(
        default=None, description="Git commit date"
    )

    # Additional context
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for quality assessment"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "name": "assess_database_writer",
                "version": "1.0.0",
                "pattern_name": "DatabaseWriterPattern",
                "pattern_type": "code",
                "language": "python",
                "pattern_code": "async def execute_effect(...): ...",
                "description": "ONEX Effect pattern for database writes",
            }
        }


# ============================================================================
# Result Model
# ============================================================================


class ModelResult(BaseModel):
    """
    Standard result model for all ONEX operations.

    Provides consistent success/failure reporting with metadata.
    """

    success: bool = Field(..., description="Operation success status")
    data: Optional[Any] = Field(default=None, description="Result data (if successful)")
    error: Optional[str] = Field(default=None, description="Error message (if failed)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional operation metadata"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True  # Allow ModelQualityMetrics as data
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "confidence_score": 0.92,
                    "quality_score": 0.87,
                },
                "metadata": {
                    "correlation_id": "a06eb29a-8922-4fdf-bb27-96fc40fae415",
                    "duration_ms": 250.5,
                },
            }
        }
