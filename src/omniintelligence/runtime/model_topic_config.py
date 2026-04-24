# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Topic configuration model for event bus."""

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.constants import (
    TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1,
    TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
)


class ModelTopicConfig(BaseModel):
    """Kafka topic configuration for event bus.

    Defines the command and event topics used by the intelligence runtime
    for event-driven communication. Default values are imported from
    ``omniintelligence.constants`` (single source of truth).

    Attributes:
        commands: Topic for incoming command messages.
        events: Topic for outgoing event messages.
        dlq: Optional dead letter queue topic for failed messages.
    """

    commands: str = Field(
        default=TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1,
        description="Topic for incoming command messages",
        examples=[TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1],
    )

    events: str = Field(
        default=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
        description="Topic for outgoing event messages",
        examples=[TOPIC_SUFFIX_INTENT_CLASSIFIED_V1],
    )

    dlq: str | None = Field(
        default=None,
        description="Dead letter queue topic for failed messages",
        examples=["onex.dlq.omniintelligence.v1"],  # onex-topic-doc-example
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


__all__ = ["ModelTopicConfig"]
