#!/usr/bin/env python3
"""
Hybrid Score Models - ONEX Compliant

Defines comprehensive structure for hybrid scoring that combines
vector similarity and pattern similarity with adaptive weights.

Part of Track 3 Phase 2 - Pattern Learning Engine.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enums for Adaptive Strategies
# ============================================================================


class EnumAdaptiveStrategy(str, Enum):
    """Strategy for adaptive weight adjustment."""

    FIXED = "fixed"  # No adaptation, use default weights
    COMPLEXITY_BASED = "complexity_based"  # Adjust based on task complexity
    DOMAIN_BASED = "domain_based"  # Adjust based on domain specificity
    CONFIDENCE_BASED = "confidence_based"  # Adjust based on score confidence
    HYBRID = "hybrid"  # Combine multiple strategies


# ============================================================================
# Configuration Model
# ============================================================================


@dataclass
class ModelHybridScoreConfig:
    """
    Configuration for hybrid scoring.

    Defines default weights and adaptive scoring strategies.
    """

    default_vector_weight: float = 0.7
    default_pattern_weight: float = 0.3
    enable_adaptive_weights: bool = True
    adaptive_strategy: EnumAdaptiveStrategy = EnumAdaptiveStrategy.COMPLEXITY_BASED
    min_weight: float = 0.1  # Minimum weight for any component
    max_weight: float = 0.9  # Maximum weight for any component
    confidence_threshold: float = 0.5  # Minimum confidence for high-confidence scoring

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Ensure weights sum to 1.0
        total = self.default_vector_weight + self.default_pattern_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total}. "
                f"vector_weight={self.default_vector_weight}, "
                f"pattern_weight={self.default_pattern_weight}"
            )

        # Validate weight ranges
        if not (0.0 <= self.default_vector_weight <= 1.0):
            raise ValueError(
                f"default_vector_weight must be in [0.0, 1.0], got {self.default_vector_weight}"
            )
        if not (0.0 <= self.default_pattern_weight <= 1.0):
            raise ValueError(
                f"default_pattern_weight must be in [0.0, 1.0], got {self.default_pattern_weight}"
            )

        # Validate min/max constraints
        if self.min_weight < 0.0 or self.min_weight > 0.5:
            raise ValueError(f"min_weight must be in [0.0, 0.5], got {self.min_weight}")
        if self.max_weight < 0.5 or self.max_weight > 1.0:
            raise ValueError(f"max_weight must be in [0.5, 1.0], got {self.max_weight}")
        if self.min_weight + self.min_weight > 1.0:
            raise ValueError(
                f"min_weight * 2 cannot exceed 1.0, got {self.min_weight * 2}"
            )


# ============================================================================
# Hybrid Score Model
# ============================================================================


class ModelHybridScore(BaseModel):
    """
    Hybrid score result combining vector and pattern similarity.

    Contains the combined score, individual component scores,
    weights used, and confidence metrics.
    """

    # Scores
    hybrid_score: float = Field(
        description="Final hybrid score (0.0-1.0)", ge=0.0, le=1.0
    )
    vector_score: float = Field(
        description="Vector similarity score (0.0-1.0)", ge=0.0, le=1.0
    )
    pattern_score: float = Field(
        description="Pattern similarity score (0.0-1.0)", ge=0.0, le=1.0
    )

    # Weights applied
    vector_weight: float = Field(
        description="Weight applied to vector score", ge=0.0, le=1.0
    )
    pattern_weight: float = Field(
        description="Weight applied to pattern score", ge=0.0, le=1.0
    )
    weights_adjusted: bool = Field(
        default=False, description="Whether weights were adapted from defaults"
    )
    adjustment_reason: Optional[str] = Field(
        default=None, description="Reason for weight adjustment if applied"
    )

    # Confidence metrics
    confidence: float = Field(
        description="Confidence in hybrid score (0.0-1.0)", ge=0.0, le=1.0
    )
    score_agreement: float = Field(
        description="Agreement between vector and pattern scores (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    # Metadata
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracking"
    )
    calculated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When score was calculated"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional calculation metadata"
    )

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "hybrid_score": 0.75,
                "vector_score": 0.80,
                "pattern_score": 0.60,
                "vector_weight": 0.7,
                "pattern_weight": 0.3,
                "weights_adjusted": False,
                "confidence": 0.85,
                "score_agreement": 0.80,
            }
        },
    )

    @field_validator("vector_weight", "pattern_weight")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Validate weight is in valid range."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Weight must be in [0.0, 1.0], got {v}")
        return v


# ============================================================================
# Input/Output Models
# ============================================================================


class ModelHybridScoreInput(BaseModel):
    """Input for hybrid score calculation."""

    vector_similarity: float = Field(
        description="Vector similarity score from Phase 1", ge=0.0, le=1.0
    )
    pattern_similarity: float = Field(
        description="Pattern similarity score from langextract", ge=0.0, le=1.0
    )

    # Task characteristics for adaptive weighting
    task_characteristics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Task characteristics for adaptive weight adjustment",
    )

    # Optional override
    config: Optional[ModelHybridScoreConfig] = Field(
        default=None, description="Optional config override"
    )

    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracing"
    )

    @field_validator("vector_similarity", "pattern_similarity")
    @classmethod
    def validate_scores(cls, v: float) -> float:
        """Validate scores are in valid range."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Score must be in [0.0, 1.0], got {v}")
        return v


class ModelHybridScoreOutput(BaseModel):
    """Output from hybrid score calculation."""

    result: ModelHybridScore = Field(description="Hybrid score result")
    processing_time_ms: float = Field(description="Calculation processing time in ms")
    correlation_id: UUID = Field(description="Correlation ID for tracing")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
