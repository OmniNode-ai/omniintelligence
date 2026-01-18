"""Output model for Intent Classifier Compute."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class SecondaryIntentDict(TypedDict, total=False):
    """Typed structure for secondary intent entries.

    Provides stronger typing for intent classification results.
    """

    intent_category: str
    confidence: float
    description: str
    keywords: list[str]
    parent_intent: str | None


class IntentMetadataDict(TypedDict, total=False):
    """Typed structure for intent classification metadata."""

    classifier_version: str
    classification_time_ms: float
    model_name: str
    token_count: int
    threshold_used: float
    raw_scores: dict[str, float]


class ModelIntentClassificationOutput(BaseModel):
    """Output model for intent classification operations.

    This model represents the result of classifying intents.
    """

    success: bool = Field(
        ...,
        description="Whether intent classification succeeded",
    )
    intent_category: str = Field(
        default="unknown",
        description="Primary intent category",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the primary intent (0.0 to 1.0)",
    )
    secondary_intents: list[SecondaryIntentDict] = Field(
        default_factory=list,
        description="List of secondary intents with confidence scores. Uses SecondaryIntentDict "
        "with total=False, allowing any subset of typed fields per entry.",
    )
    metadata: IntentMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the classification. Uses IntentMetadataDict "
        "with total=False, allowing any subset of typed fields.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "IntentMetadataDict",
    "ModelIntentClassificationOutput",
    "SecondaryIntentDict",
]
