"""ModelPatternPromotedEvent - event payload for pattern-promoted Kafka event."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternPromotedEvent(BaseModel):
    """Event payload for pattern-promoted Kafka event.

    This model is published to Kafka when a pattern is promoted, enabling
    downstream consumers to invalidate caches or update their state.
    Published to topic: onex.evt.omniintelligence.pattern-promoted.v1
    """

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(
        default="PatternPromoted",
        description="Event type identifier",
    )
    pattern_id: UUID = Field(
        ...,
        description="The promoted pattern ID",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        ...,
        description="Status before promotion",
    )
    to_status: str = Field(
        ...,
        description="Status after promotion",
    )
    success_rate_rolling_20: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Success rate at time of promotion",
    )
    promoted_at: datetime = Field(
        ...,
        description="Timestamp of promotion",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing",
    )
