"""Topic configuration model for event bus."""

from pydantic import BaseModel, ConfigDict, Field


class ModelTopicConfig(BaseModel):
    """Kafka topic configuration for event bus.

    Defines the command and event topics used by the intelligence runtime
    for event-driven communication.

    Attributes:
        commands: Topic for incoming command messages.
        events: Topic for outgoing event messages.
        dlq: Optional dead letter queue topic for failed messages.
    """

    commands: str = Field(
        default="onex.cmd.omniintelligence.claude-hook-event.v1",
        description="Topic for incoming command messages",
        examples=["onex.cmd.omniintelligence.claude-hook-event.v1"],
    )

    events: str = Field(
        default="onex.evt.omniintelligence.intent-classified.v1",
        description="Topic for outgoing event messages",
        examples=["onex.evt.omniintelligence.intent-classified.v1"],
    )

    dlq: str | None = Field(
        default=None,
        description="Dead letter queue topic for failed messages",
        examples=["onex.dlq.omniintelligence.v1"],
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


__all__ = ["ModelTopicConfig"]
