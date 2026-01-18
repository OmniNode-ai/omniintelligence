"""Input model for Intent Classifier Compute."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class ConversationMessageDict(TypedDict):
    """Typed structure for a conversation message."""

    role: str  # e.g., "user", "assistant", "system"
    content: str


class IntentContextDict(TypedDict, total=False):
    """Typed structure for intent classification context.

    Provides stronger typing for common context fields while allowing
    additional fields via dict[str, Any] union. Use this typed dict
    for better IDE support and type checking.
    """

    # User and session tracking
    user_id: str
    session_id: str
    request_id: str

    # Intent classification context
    previous_intents: list[str]
    language: str
    domain: str
    conversation_history: list[ConversationMessageDict]

    # Classification parameters
    custom_labels: list[str]
    confidence_threshold: float
    max_intents: int
    include_confidence_scores: bool

    # Source metadata
    source_system: str
    timestamp_utc: str


class ModelIntentClassificationInput(BaseModel):
    """Input model for intent classification operations.

    This model represents the input for classifying user intents.
    """

    content: str = Field(
        ...,
        min_length=1,
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


__all__ = [
    "ConversationMessageDict",
    "IntentContextDict",
    "ModelIntentClassificationInput",
]
