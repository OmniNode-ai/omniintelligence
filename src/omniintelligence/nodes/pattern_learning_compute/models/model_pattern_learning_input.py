"""Input model for Pattern Learning Compute (STUB)."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class TrainingDataItemDict(TypedDict, total=False):
    """Typed structure for a training data item.

    Provides type-safe fields for pattern learning training data.
    """

    # Identification
    item_id: str
    source_file: str
    language: str

    # Content
    code_snippet: str
    pattern_type: str
    pattern_name: str

    # Labels
    labels: list[str]
    confidence: float

    # Metadata
    context: str
    framework: str


class LearningParametersDict(TypedDict, total=False):
    """Typed structure for learning algorithm parameters.

    Provides type-safe fields for configuring pattern learning.
    """

    # Algorithm selection
    algorithm: str
    model_type: str

    # Training parameters
    learning_rate: float
    batch_size: int
    epochs: int
    early_stopping: bool

    # Thresholds
    min_confidence: float
    max_patterns: int

    # Options
    include_similar: bool
    deduplicate: bool


class ModelPatternLearningInput(BaseModel):
    """Input model for pattern learning operations (STUB).

    This model represents the input for pattern learning operations.
    This is a stub implementation for forward compatibility.

    All fields use strong typing without dict[str, Any].
    """

    training_data: list[TrainingDataItemDict] = Field(
        default_factory=list,
        description="Training data for pattern learning with typed items",
    )
    learning_parameters: LearningParametersDict = Field(
        default_factory=lambda: LearningParametersDict(),
        description="Parameters for the learning algorithm with typed fields",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "LearningParametersDict",
    "ModelPatternLearningInput",
    "TrainingDataItemDict",
]
