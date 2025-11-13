"""
ONEX Contract Model: Feedback Loop Orchestration

Defines input/output contracts for feedback loop operations.

Author: Archon Intelligence Team
Date: 2025-10-02
Track: Track 3 Phase 4
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Enums
# ============================================================================


class FeedbackLoopStage(str, Enum):
    """Feedback loop workflow stages."""

    COLLECT = "collect"
    ANALYZE = "analyze"
    VALIDATE = "validate"
    APPLY = "apply"


# ============================================================================
# Input/Output Models (Pydantic)
# ============================================================================


class ModelFeedbackLoopInput(BaseModel):
    """
    Input contract for feedback loop orchestration.

    Used to trigger pattern improvement workflow based on usage feedback.
    """

    operation: str = Field(
        default="analyze_and_improve",
        description="Operation type: analyze_and_improve, collect_feedback, validate_improvement",
    )

    pattern_id: str = Field(..., description="Pattern ID to analyze and improve")

    feedback_type: str = Field(
        default="performance",
        description="Feedback type: performance, quality, usage, all",
    )

    time_window_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Time window for feedback analysis (1-90 days)",
    )

    auto_apply_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for auto-applying improvements (0.0-1.0)",
    )

    min_sample_size: int = Field(
        default=30,
        ge=10,
        description="Minimum sample size for statistical validation",
    )

    significance_level: float = Field(
        default=0.05,
        ge=0.001,
        le=0.1,
        description="Statistical significance level (p-value threshold)",
    )

    enable_ab_testing: bool = Field(
        default=True, description="Enable A/B testing for improvements"
    )

    stages_to_execute: List[FeedbackLoopStage] | None = Field(
        default=None, description="Specific stages to execute (None = all stages)"
    )

    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracking"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation": "analyze_and_improve",
                "pattern_id": "pattern_api_debug_v1",
                "feedback_type": "performance",
                "time_window_days": 7,
                "auto_apply_threshold": 0.95,
                "min_sample_size": 30,
                "significance_level": 0.05,
                "enable_ab_testing": True,
                "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
                "metadata": {},
            }
        }
    )


class ModelFeedbackLoopOutput(BaseModel):
    """
    Output contract for feedback loop orchestration.

    Returns results of pattern improvement workflow.
    """

    success: bool = Field(..., description="Whether operation succeeded")

    pattern_id: str = Field(..., description="Pattern ID analyzed")

    # Collection phase results
    feedback_collected: int = Field(
        default=0, description="Number of feedback items collected"
    )

    executions_analyzed: int = Field(
        default=0, description="Number of executions analyzed"
    )

    # Analysis phase results
    improvements_identified: int = Field(
        default=0, description="Number of improvements identified"
    )

    improvement_opportunities: List[Dict[str, Any]] = Field(
        default_factory=list, description="Detailed improvement opportunities"
    )

    # Validation phase results
    improvements_validated: int = Field(
        default=0, description="Number of improvements validated"
    )

    validation_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="A/B test validation results"
    )

    # Application phase results
    improvements_applied: int = Field(
        default=0, description="Number of improvements applied"
    )

    improvements_rejected: int = Field(
        default=0, description="Number of improvements rejected"
    )

    # Performance metrics
    performance_delta: float = Field(
        default=0.0, description="Overall performance improvement (%)"
    )

    baseline_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Baseline metrics before improvements"
    )

    improved_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Metrics after improvements"
    )

    # Statistical validation
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Statistical confidence (0.0-1.0)"
    )

    p_value: float | None = Field(
        default=None, description="Statistical p-value for significance"
    )

    statistically_significant: bool = Field(
        default=False, description="Whether results are statistically significant"
    )

    # Scheduling
    next_review_date: datetime | None = Field(
        default=None, description="When to next review this pattern"
    )

    # Workflow tracking
    workflow_stages: Dict[str, str] = Field(
        default_factory=dict, description="Status of each workflow stage"
    )

    # Error handling
    errors: List[str] = Field(
        default_factory=list, description="Any errors encountered"
    )

    warnings: List[str] = Field(default_factory=list, description="Any warnings")

    # Metadata
    correlation_id: UUID = Field(..., description="Correlation ID for tracking")

    duration_ms: float = Field(default=0.0, description="Total execution time (ms)")

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Output timestamp"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "pattern_id": "pattern_api_debug_v1",
                "feedback_collected": 150,
                "executions_analyzed": 150,
                "improvements_identified": 3,
                "improvement_opportunities": [
                    {
                        "type": "performance",
                        "description": "Add caching layer",
                        "expected_improvement": "60%",
                    }
                ],
                "improvements_validated": 2,
                "validation_results": [],
                "improvements_applied": 1,
                "improvements_rejected": 1,
                "performance_delta": 0.60,
                "baseline_metrics": {
                    "avg_execution_time_ms": 450.5,
                    "success_rate": 0.92,
                },
                "improved_metrics": {
                    "avg_execution_time_ms": 180.2,
                    "success_rate": 0.95,
                },
                "confidence_score": 0.98,
                "p_value": 0.003,
                "statistically_significant": True,
                "next_review_date": "2025-10-09T00:00:00Z",
                "workflow_stages": {
                    "collect": "completed",
                    "analyze": "completed",
                    "validate": "completed",
                    "apply": "completed",
                },
                "errors": [],
                "warnings": ["Small sample size for some improvements"],
                "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
                "duration_ms": 5432.1,
                "timestamp": "2025-10-02T20:00:00Z",
                "metadata": {},
            }
        }
    )


@dataclass
class ModelContractFeedbackLoop:
    """
    ONEX-compliant contract model for feedback loop orchestration.

    Dataclass version for use with ONEX nodes that expect dataclass contracts.
    """

    # Basic fields
    name: str = "feedback_loop_orchestration"
    operation: str = "analyze_and_improve"

    # Core parameters
    pattern_id: str = ""
    feedback_type: str = "performance"
    time_window_days: int = 7

    # Thresholds
    auto_apply_threshold: float = 0.95
    min_sample_size: int = 30
    significance_level: float = 0.05

    # Features
    enable_ab_testing: bool = True

    # Tracking
    correlation_id: UUID = field(default_factory=uuid4)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_input_model(self) -> ModelFeedbackLoopInput:
        """Convert to Pydantic input model."""
        return ModelFeedbackLoopInput(
            operation=self.operation,
            pattern_id=self.pattern_id,
            feedback_type=self.feedback_type,
            time_window_days=self.time_window_days,
            auto_apply_threshold=self.auto_apply_threshold,
            min_sample_size=self.min_sample_size,
            significance_level=self.significance_level,
            enable_ab_testing=self.enable_ab_testing,
            correlation_id=self.correlation_id,
            metadata=self.metadata,
        )
