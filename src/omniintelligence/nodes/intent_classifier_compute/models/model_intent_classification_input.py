"""Input model for Intent Classifier Compute."""
from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class IntentContextDict(TypedDict, total=False):
    """Typed structure for intent classification context.

    Provides stronger typing for common context fields while allowing
    additional fields via dict[str, Any] union.
    """

    user_id: str
    session_id: str
    previous_intents: list[str]
    language: str
    domain: str
    conversation_history: list[dict[str, str]]
    custom_labels: list[str]
    confidence_threshold: float


class ModelIntentClassificationInput(BaseModel):
    """Input model for intent classification operations.

    This model represents the input for classifying user intents.
    """

    content: str = Field(
        ...,
        description="Content to classify intent from",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    context: IntentContextDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for intent classification",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntentClassificationInput", "IntentContextDict"]
