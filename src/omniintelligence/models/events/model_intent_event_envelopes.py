# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Kafka envelope schemas for the Intent Intelligence Framework topics.

Defines frozen Pydantic envelope models for all 4 Intent Intelligence topics:

    - ModelIntentClassifiedEnvelope  → onex.evt.intent.classified.v1
    - ModelIntentDriftDetectedEnvelope → onex.evt.intent.drift.detected.v1
    - ModelIntentOutcomeLabeledEnvelope → onex.evt.intent.outcome.labeled.v1
    - ModelIntentPatternPromotedEnvelope → onex.evt.intent.pattern.promoted.v1

Schema Rules:
    - frozen=True (events are immutable after emission)
    - extra="ignore" (forward compatibility with schema evolution)
    - from_attributes=True (pytest-xdist worker compatibility)
    - emitted_at required (no datetime.now() defaults — callers inject explicitly)
    - No full prompt text in any payload (preview-safe)

Reference: OMN-2487
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict, Field


class ModelIntentClassifiedEnvelope(BaseModel):
    """Frozen event envelope for onex.evt.intent.classified.v1.

    Published whenever the intent classifier assigns a class to a session prompt.
    Consumed by omnimemory for graph storage and by analytics consumers.

    Preview-safe: contains no full prompt text.

    Attributes:
        event_type: Literal event type discriminator.
        session_id: Session ID from the originating hook event.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The typed intent class from the 8-class system.
        confidence: Classification confidence score (0.0 to 1.0).
        fallback: True when ANALYSIS fallback was applied due to low confidence.
        emitted_at: Timestamp injected by the caller — no datetime.now() defaults.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: str = Field(
        default="IntentClassified",
        description="Literal event type discriminator",
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
    emitted_at: datetime = Field(
        ...,
        description=(
            "Timestamp injected by the caller at emission time. "
            "Must NOT use datetime.now() as default — callers must inject explicitly."
        ),
    )


class ModelIntentDriftDetectedEnvelope(BaseModel):
    """Frozen event envelope for onex.evt.intent.drift.detected.v1.

    Published when execution diverges from the declared intent class.
    Consumers may trigger alerts or model updates.

    Attributes:
        event_type: Literal event type discriminator.
        session_id: Session ID where drift was detected.
        correlation_id: Correlation ID for distributed tracing.
        declared_intent: The intent class originally declared for the session.
        observed_intent: The intent class inferred from actual execution.
        drift_score: Severity of divergence (0.0 = no drift, 1.0 = complete divergence).
        emitted_at: Timestamp injected by the caller — no datetime.now() defaults.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: str = Field(
        default="IntentDriftDetected",
        description="Literal event type discriminator",
    )
    session_id: str = Field(
        ...,
        description="Session ID where drift was detected",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for distributed tracing (UUID string)",
    )
    declared_intent: EnumIntentClass = Field(
        ...,
        description="The intent class originally declared for the session",
    )
    observed_intent: EnumIntentClass = Field(
        ...,
        description="The intent class inferred from actual execution",
    )
    drift_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Severity of divergence (0.0 = no drift, 1.0 = complete divergence)",
    )
    emitted_at: datetime = Field(
        ...,
        description=(
            "Timestamp injected by the caller at emission time. "
            "Must NOT use datetime.now() as default — callers must inject explicitly."
        ),
    )


class ModelIntentOutcomeLabeledEnvelope(BaseModel):
    """Frozen event envelope for onex.evt.intent.outcome.labeled.v1.

    Published when a session outcome is labeled as successful or failed.
    Used to update intent graph success rates and pattern confidence scores.

    Attributes:
        event_type: Literal event type discriminator.
        session_id: Session ID being labeled.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The intent class for the labeled session.
        success: True if the session outcome was successful.
        cost_usd: Accumulated token cost for the session in USD (0.0 if unknown).
        emitted_at: Timestamp injected by the caller — no datetime.now() defaults.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: str = Field(
        default="IntentOutcomeLabeled",
        description="Literal event type discriminator",
    )
    session_id: str = Field(
        ...,
        description="Session ID being labeled",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for distributed tracing (UUID string)",
    )
    intent_class: EnumIntentClass = Field(
        ...,
        description="The intent class for the labeled session",
    )
    success: bool = Field(
        ...,
        description="True if the session outcome was successful",
    )
    cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Accumulated token cost for the session in USD (0.0 if unknown)",
    )
    emitted_at: datetime = Field(
        ...,
        description=(
            "Timestamp injected by the caller at emission time. "
            "Must NOT use datetime.now() as default — callers must inject explicitly."
        ),
    )


class ModelIntentPatternPromotedEnvelope(BaseModel):
    """Frozen event envelope for onex.evt.intent.pattern.promoted.v1.

    Published when an intent-derived pattern is promoted into the learned-patterns
    corpus. Consumers may use this to refresh projection caches or update indices.

    Attributes:
        event_type: Literal event type discriminator.
        pattern_id: UUID of the promoted pattern.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The intent class associated with the promoted pattern.
        pattern_signature: Short content summary of the promoted pattern.
        promotion_confidence: Confidence score at time of promotion (0.0 to 1.0).
        emitted_at: Timestamp injected by the caller — no datetime.now() defaults.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: str = Field(
        default="IntentPatternPromoted",
        description="Literal event type discriminator",
    )
    pattern_id: UUID = Field(
        ...,
        description="UUID of the promoted pattern",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for distributed tracing (UUID string)",
    )
    intent_class: EnumIntentClass = Field(
        ...,
        description="The intent class associated with the promoted pattern",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Short content summary of the promoted pattern",
    )
    promotion_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score at time of promotion (0.0 to 1.0)",
    )
    emitted_at: datetime = Field(
        ...,
        description=(
            "Timestamp injected by the caller at emission time. "
            "Must NOT use datetime.now() as default — callers must inject explicitly."
        ),
    )


__all__ = [
    "ModelIntentClassifiedEnvelope",
    "ModelIntentDriftDetectedEnvelope",
    "ModelIntentOutcomeLabeledEnvelope",
    "ModelIntentPatternPromotedEnvelope",
]
