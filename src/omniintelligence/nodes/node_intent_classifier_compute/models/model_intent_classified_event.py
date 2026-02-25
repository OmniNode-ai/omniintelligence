"""Event envelope for onex.evt.intent.classified.v1.

This frozen event model is published to the intent-classified topic
whenever classification runs. It is preview-safe: no full prompt text
is included in the payload.

Schema Rules:
    - frozen=True (events are immutable after emission)
    - extra="ignore" (forward compatibility)
    - emitted_at must be injected by caller (no datetime.now() defaults)
    - No prompt text in payload (preview-safe)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)


class ModelIntentClassifiedEvent(BaseModel):
    """Frozen event envelope for onex.evt.intent.classified.v1.

    Published whenever the intent classifier produces a typed result.
    Preview-safe: contains no full prompt text.

    Attributes:
        event_type: Literal event type identifier.
        session_id: Session ID from the originating hook event.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The typed intent class from the 8-class system.
        confidence: Classification confidence score (0.0 to 1.0).
        fallback: Whether ANALYSIS fallback was applied.
        model_hint: Recommended model from the config table.
        temperature: Recommended temperature from the config table.
        validator_set: Validators to apply from the config table.
        sandbox: Sandbox enforcement flag from the config table.
        emitted_at: Timestamp injected by the caller at emission time.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: str = Field(
        default="IntentClassified",
        description="Literal event type identifier",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the originating hook event",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for distributed tracing (UUID string)",
    )
    intent_class: EnumIntentClass = Field(
        ...,
        description="Typed intent class from the 8-class system",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classification confidence score (0.0 to 1.0)",
    )
    fallback: bool = Field(
        default=False,
        description="True when ANALYSIS fallback was applied due to low confidence",
    )
    model_hint: str = Field(
        ...,
        description="Recommended model from the config table",
    )
    temperature: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recommended temperature from the config table",
    )
    validator_set: list[str] = Field(
        default_factory=list,
        description="Validators to apply from the config table",
    )
    sandbox: bool = Field(
        default=False,
        description="Sandbox enforcement flag from the config table",
    )
    emitted_at: datetime = Field(
        ...,
        description=(
            "Timestamp injected by the caller at emission time. "
            "Must NOT use datetime.now() as default — callers must inject explicitly "
            "for deterministic testing."
        ),
    )

    @classmethod
    def from_typed_intent(
        cls,
        *,
        session_id: str,
        correlation_id: UUID,
        intent_class: EnumIntentClass,
        confidence: float,
        fallback: bool,
        model_hint: str,
        temperature: float,
        validator_set: list[str],
        sandbox: bool,
        emitted_at: datetime,
    ) -> ModelIntentClassifiedEvent:
        """Build event envelope from typed intent components.

        Args:
            session_id: Session ID from the originating hook event.
            correlation_id: Correlation UUID for tracing.
            intent_class: The resolved typed intent class.
            confidence: Classification confidence score.
            fallback: Whether ANALYSIS fallback was applied.
            model_hint: Recommended model from the config table.
            temperature: Recommended temperature from the config table.
            validator_set: Validators to apply.
            sandbox: Sandbox enforcement flag.
            emitted_at: Timestamp injected by the caller (not datetime.now()).

        Returns:
            Frozen ModelIntentClassifiedEvent ready for Kafka publication.
        """
        return cls(
            session_id=session_id,
            correlation_id=str(correlation_id),
            intent_class=intent_class,
            confidence=confidence,
            fallback=fallback,
            model_hint=model_hint,
            temperature=temperature,
            validator_set=validator_set,
            sandbox=sandbox,
            emitted_at=emitted_at,
        )


__all__ = ["ModelIntentClassifiedEvent"]
