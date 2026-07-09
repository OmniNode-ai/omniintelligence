# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for Cursor IDE hook event processing.

Cursor-side peer of the Claude hook handler. To guarantee the two dispatchers
behave identically (true interchangeability), this handler does NOT reimplement
intent classification / pattern learning. Instead it adapts the Cursor input
model onto the canonical hook event and delegates to the shared Claude handler
core (``route_hook_event``), passing ``agent_source="cursor"`` so emitted
events are correctly attributed to Cursor rather than Claude.

The shared core is the single source of truth for processing semantics; this
module is a thin adapter that preserves Cursor's distinct identity (own type,
topic, and node) at the boundary.
"""

from __future__ import annotations

from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
    ModelClaudeCodeHookEvent,
)

from omniintelligence.enums import EnumAgentSource
from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    route_hook_event,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.models import (
    ModelClaudeHookResult,
    ModelCursorHookEvent,
)
from omniintelligence.protocols import (
    ProtocolIntentClassifier,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
)

_AGENT_SOURCE = EnumAgentSource.CURSOR


def _to_canonical_event(event: ModelCursorHookEvent) -> ModelClaudeCodeHookEvent:
    """Adapt a Cursor hook event onto the canonical Claude Code hook event model.

    Cursor shares Claude Code's canonical hook lifecycle vocabulary
    (``EnumCursorHookEventType`` is an alias of ``EnumClaudeCodeHookEventType``);
    OmniCursor normalizes its native hook names (``beforeSubmitPrompt`` ->
    ``UserPromptSubmit``, etc.) at emit time. ``ModelCursorHookEventPayload`` is an
    alias of ``ModelClaudeCodeHookEventPayload``, so this adaptation is a
    structural copy with no data loss.
    """
    return ModelClaudeCodeHookEvent(
        event_type=event.event_type,
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        timestamp_utc=event.timestamp_utc,
        payload=event.payload,
    )


async def route_cursor_hook_event(
    event: ModelCursorHookEvent,
    *,
    intent_classifier: ProtocolIntentClassifier | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    repository: ProtocolPatternRepository | None = None,
) -> ModelClaudeHookResult:
    """Route a Cursor hook event through the shared Claude handler core.

    Args:
        event: The Cursor hook event to process.
        intent_classifier: Optional intent classifier compute node.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full Kafka topic for publishing classified intents.
        repository: Optional database repository for PostToolUse persistence.

    Returns:
        ModelClaudeHookResult with processing outcome (metadata/emitted events
        tagged ``agent_source="cursor"``).
    """
    return await route_hook_event(
        event=_to_canonical_event(event),
        intent_classifier=intent_classifier,
        kafka_producer=kafka_producer,
        publish_topic=publish_topic,
        repository=repository,
        agent_source=_AGENT_SOURCE,
    )


class HandlerCursorHookEvent:
    """Handler for Cursor IDE hook events with constructor-injected dependencies.

    Mirrors ``HandlerClaudeHookEvent`` and delegates to the shared core so the
    Cursor and Claude dispatchers stay behaviorally identical.
    """

    def __init__(
        self,
        *,
        kafka_publisher: ProtocolKafkaPublisher | None = None,
        intent_classifier: ProtocolIntentClassifier | None = None,
        publish_topic: str | None = None,
        repository: ProtocolPatternRepository | None = None,
    ) -> None:
        """Initialize handler with explicit dependencies (all optional)."""
        self._kafka_publisher = kafka_publisher
        self._intent_classifier = intent_classifier
        self._publish_topic = publish_topic
        self._repository = repository

    @property
    def kafka_publisher(self) -> ProtocolKafkaPublisher | None:
        """Get the Kafka publisher, or None if not configured."""
        return self._kafka_publisher

    @property
    def intent_classifier(self) -> ProtocolIntentClassifier | None:
        """Get the intent classifier if configured."""
        return self._intent_classifier

    @property
    def publish_topic(self) -> str | None:
        """Get the Kafka publish topic."""
        return self._publish_topic

    @property
    def repository(self) -> ProtocolPatternRepository | None:
        """Get the database repository, or None if not configured."""
        return self._repository

    async def handle(self, event: ModelCursorHookEvent) -> ModelClaudeHookResult:
        """Handle a Cursor hook event by delegating to the shared core."""
        return await route_cursor_hook_event(
            event=event,
            intent_classifier=self._intent_classifier,
            kafka_producer=self._kafka_publisher,
            publish_topic=self._publish_topic,
            repository=self._repository,
        )


__all__ = [
    "HandlerCursorHookEvent",
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "route_cursor_hook_event",
]
