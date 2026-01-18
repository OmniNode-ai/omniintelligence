"""Output model for Intent Classifier Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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
        description="Confidence score for the primary intent (0.0 to 1.0)",
    )
    secondary_intents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of secondary intents with confidence scores",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the classification",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntentClassificationOutput"]
