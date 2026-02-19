"""Intent classification result model for UserPromptSubmit events."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelIntentResult(BaseModel):
    """Result of intent classification (for UserPromptSubmit events).

    This model captures the intent classification output when a
    UserPromptSubmit event is processed. Graph storage is handled
    downstream by omnimemory consuming the Kafka event.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    intent_category: str = Field(
        ...,
        description="Classified intent category (e.g., debugging, code_generation)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification (0.0-1.0)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords extracted from intent classification",
    )
    secondary_intents: list[dict[str, object]] = Field(
        default_factory=list,
        description="Secondary intents with lower confidence",
    )
    emitted_to_kafka: bool = Field(
        default=False,
        description="Whether the intent was emitted to Kafka",
    )


__all__ = ["ModelIntentResult"]
