"""
Phase 4 Traceability - Pattern Feedback Models

Models for tracking pattern feedback, improvements, and validation results.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class FeedbackSentiment(str, Enum):
    """Sentiment classification for feedback."""

    POSITIVE = "positive"  # Pattern worked well
    NEUTRAL = "neutral"  # Mixed or informational feedback
    NEGATIVE = "negative"  # Pattern needs improvement


class ImprovementStatus(str, Enum):
    """Status of pattern improvement suggestions."""

    PROPOSED = "proposed"  # Improvement suggested
    VALIDATED = "validated"  # Improvement validated
    APPROVED = VALIDATED  # Alias for VALIDATED (same enum member)
    APPLIED = "applied"  # Improvement applied to pattern
    REJECTED = "rejected"  # Improvement rejected


class ModelPatternFeedback(BaseModel):
    """
    User feedback on pattern execution.

    Tracks user-provided feedback for pattern quality and effectiveness.
    """

    feedback_id: UUID = Field(
        default_factory=uuid4, description="Unique feedback identifier"
    )

    pattern_id: UUID = Field(..., description="Pattern UUID this feedback relates to")

    pattern_name: str = Field(default="", description="Pattern name for display")

    execution_id: Optional[str] = Field(
        default=None, description="Specific execution ID if available"
    )

    sentiment: FeedbackSentiment = Field(
        ..., description="Feedback sentiment classification"
    )

    feedback_text: str = Field(
        default="",
        description="User feedback text (empty for system-collected feedback)",
    )

    success_confirmed: Optional[bool] = Field(
        default=None, description="Did user confirm pattern success?"
    )

    # Execution feedback fields (for system-collected feedback)
    success: Optional[bool] = Field(
        default=None,
        description="Execution success status (for system-collected feedback)",
    )

    explicit_rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Explicit quality/performance rating (0.0-1.0)",
    )

    implicit_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Implicit feedback signals (execution time, retries, etc.)",
    )

    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score from execution (0.0-1.0)",
    )

    performance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Performance score from execution (0.0-1.0)",
    )

    quality_rating: Optional[float] = Field(
        default=None, ge=0.0, le=5.0, description="User quality rating (0-5 stars)"
    )

    context: Dict[str, Any] = Field(
        default_factory=dict, description="Execution context when feedback was given"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Feedback creation timestamp",
    )

    created_by: Optional[str] = Field(
        default=None, description="User who provided feedback"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feedback_id": "770e8400-e29b-41d4-a716-446655440000",
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "execution_id": "exec_123",
                "sentiment": "positive",
                "feedback_text": "Pattern helped identify N+1 query issue quickly",
                "success_confirmed": True,
                "quality_rating": 4.5,
                "context": {
                    "task_type": "debugging",
                    "agent": "agent-debug-intelligence",
                },
                "created_at": "2025-10-02T14:30:00Z",
                "created_by": "user_123",
            }
        }
    )


class ModelPatternImprovement(BaseModel):
    """
    Pattern improvement suggestion.

    Tracks suggested improvements to patterns based on feedback or validation.
    """

    improvement_id: UUID = Field(
        default_factory=uuid4, description="Unique improvement identifier"
    )

    pattern_id: UUID = Field(
        ..., description="Pattern UUID this improvement relates to"
    )

    pattern_name: str = Field(default="", description="Pattern name for display")

    status: ImprovementStatus = Field(
        default=ImprovementStatus.PROPOSED, description="Current status of improvement"
    )

    improvement_type: str = Field(
        ...,
        description="Type of improvement (e.g., 'performance', 'accuracy', 'usability')",
    )

    description: str = Field(
        ..., min_length=1, description="Detailed description of improvement"
    )

    source: str = Field(
        default="automated_analysis",
        description="Source of improvement (e.g., 'user_feedback', 'validation', 'automated_analysis')",
    )

    priority: str = Field(
        default="medium",
        description="Priority level: 'low', 'medium', 'high', 'critical'",
    )

    # Performance and validation metrics
    proposed_changes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Proposed changes to apply (configuration, code changes, etc.)",
    )

    baseline_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Baseline performance metrics before improvement",
    )

    improved_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Expected/actual performance metrics after improvement",
    )

    performance_delta: float = Field(
        default=0.0,
        description="Expected/actual performance improvement (0.0-1.0 = 0-100%)",
    )

    # Statistical validation
    p_value: Optional[float] = Field(
        default=None, description="Statistical p-value from A/B testing"
    )

    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in improvement (0.0-1.0)"
    )

    sample_size: int = Field(default=0, description="Sample size used for validation")

    test_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Detailed A/B test results"
    )

    impact_estimate: Optional[str] = Field(
        default=None, description="Estimated impact if applied"
    )

    implementation_notes: Optional[str] = Field(
        default=None, description="Notes on how to implement improvement"
    )

    validation_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validation test results if available (legacy field, use test_results for new code)",
    )

    applied_at: Optional[datetime] = Field(
        default=None, description="When improvement was applied"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Improvement proposal timestamp",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )

    created_by: Optional[str] = Field(
        default=None, description="Who proposed the improvement"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "improvement_id": "880e8400-e29b-41d4-a716-446655440000",
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "status": "validated",
                "improvement_type": "performance",
                "description": "Add caching layer for repeated RAG queries",
                "source": "automated_analysis",
                "priority": "high",
                "impact_estimate": "20-30% performance improvement",
                "implementation_notes": "Use Redis cache with 1-hour TTL",
                "validation_results": {
                    "test_passed": True,
                    "performance_gain": 0.25,
                    "success_rate_maintained": True,
                },
                "applied_at": None,
                "created_at": "2025-10-02T10:00:00Z",
                "updated_at": "2025-10-02T12:00:00Z",
                "created_by": "system",
            }
        }
    )
