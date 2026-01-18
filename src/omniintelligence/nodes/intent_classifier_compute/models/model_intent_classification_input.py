"""Input model for Intent Classifier Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelIntentClassificationInput(BaseModel):
    """Input model for intent classification operations.

    This model represents the input for classifying user intents.
    """

    content: str = Field(
        ...,
        description="Content to classify intent from",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for intent classification",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntentClassificationInput"]
