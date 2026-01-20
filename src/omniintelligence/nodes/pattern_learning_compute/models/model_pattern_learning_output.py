"""Output model for Pattern Learning Compute (STUB)."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class LearnedPatternDict(TypedDict, total=False):
    """Typed structure for a learned pattern.

    Provides type-safe fields for pattern learning results.
    """

    # Identification
    pattern_id: str
    pattern_name: str
    pattern_type: str

    # Classification
    category: str
    subcategory: str
    tags: list[str]

    # Matching criteria
    signature: str
    keywords: list[str]
    confidence: float

    # Metadata
    source_count: int
    first_seen: str
    last_seen: str


class LearningMetadataDict(TypedDict, total=False):
    """Typed structure for learning metadata.

    Provides type-safe fields for pattern learning metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str
    model_version: str

    # Dataset info
    training_samples: int
    validation_samples: int

    # Quality indicators
    convergence_achieved: bool
    early_stopped: bool
    final_epoch: int


class ModelPatternLearningOutput(BaseModel):
    """Output model for pattern learning operations (STUB).

    This model represents the result of pattern learning operations.
    This is a stub implementation for forward compatibility.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether pattern learning succeeded",
    )
    learned_patterns: list[LearnedPatternDict] = Field(
        default_factory=list,
        description="List of learned patterns with typed fields",
    )
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Learning metrics (accuracy, loss, etc.)",
    )
    metadata: LearningMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the learning with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "LearnedPatternDict",
    "LearningMetadataDict",
    "ModelPatternLearningOutput",
]
