# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect - Unified handler for Claude Code hook events.

This node follows the ONEX declarative pattern:
    - EFFECT node for receiving and routing Claude Code hook events
    - Routes by event_type to appropriate handlers
    - Lightweight shell that delegates to handlers via dependency injection
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
Handler routing is driven by event_type matching.

Handler Routing Pattern:
    1. Receive hook event (ModelClaudeHookEvent)
    2. Route to handler based on event_type
    3. For UserPromptSubmit: classify intent, store in graph, emit to Kafka
    4. For other types: return success (no-op)
    5. Return structured response (ModelClaudeHookResult)

Design Decisions:
    - Single ingress for all Claude Code hook types
    - Event type routing to specialized handlers
    - No-op handlers for unimplemented event types (stable pipeline shape)
    - External adapters injected via setter methods

Node Responsibilities:
    - Define I/O model contract (ModelClaudeHookEvent -> ModelClaudeHookResult)
    - Provide dependency injection points for adapters
    - Delegate execution to handlers

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.claude_hook_event_effect.handlers import route_hook_event
from omniintelligence.nodes.claude_hook_event_effect.models import (
    ModelClaudeHookEvent,
    ModelClaudeHookResult,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeClaudeHookEventEffect(NodeEffect):
    """Effect node for unified Claude Code hook event handling.

    This effect node receives all Claude Code hook events and routes them
    to appropriate handlers based on event_type. It is a lightweight shell
    that delegates actual processing to handler functions.

    Supported Event Types (from Claude Code hook lifecycle):
        - SessionStart: Session begins
        - UserPromptSubmit: User submits a prompt (routes to intent classification)
        - PreToolUse: Before tool execution
        - PostToolUse: After tool execution
        - Stop: Stop signal
        - SessionEnd: Session ends
        - Notification: Async notifications
        - And more (see EnumClaudeHookEventType)

    Dependency Injection:
        Adapters and compute nodes are injected via setter methods:
        - set_intent_classifier(): Intent classifier compute node
        - set_kafka_producer(): Kafka producer for event emission

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.claude_hook_event_effect import (
            NodeClaudeHookEventEffect,
        )

        # Create effect node
        container = ModelONEXContainer()
        effect = NodeClaudeHookEventEffect(container)

        # Wire dependencies
        effect.set_intent_classifier(intent_classifier)
        effect.set_kafka_producer(kafka_producer)

        # Process a hook event
        result = await effect.execute(hook_event)
        ```
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the effect node.

        Args:
            container: ONEX dependency injection container.
        """
        super().__init__(container)

        # Injected dependencies (optional - node works without them)
        self._intent_classifier: Any | None = None
        self._kafka_producer: Any | None = None
        self._topic_env_prefix: str = "dev"

    def set_intent_classifier(self, classifier: Any) -> None:
        """Set the intent classifier compute node.

        Args:
            classifier: Intent classifier compute node instance.
        """
        self._intent_classifier = classifier

    def set_kafka_producer(self, producer: Any) -> None:
        """Set the Kafka producer for event emission.

        Args:
            producer: Kafka producer instance.
        """
        self._kafka_producer = producer

    def set_topic_env_prefix(self, prefix: str) -> None:
        """Set the environment prefix for Kafka topics.

        Args:
            prefix: Environment prefix (e.g., "dev", "prod").
        """
        self._topic_env_prefix = prefix

    @property
    def topic_env_prefix(self) -> str:
        """Get the configured Kafka topic environment prefix."""
        return self._topic_env_prefix

    @property
    def intent_classifier(self) -> Any | None:
        """Get the intent classifier if configured."""
        return self._intent_classifier

    @property
    def kafka_producer(self) -> Any | None:
        """Get the Kafka producer if configured."""
        return self._kafka_producer

    @property
    def has_intent_classifier(self) -> bool:
        """Check if intent classifier is configured."""
        return self._intent_classifier is not None

    @property
    def has_kafka_producer(self) -> bool:
        """Check if Kafka producer is configured."""
        return self._kafka_producer is not None

    async def execute(self, event: ModelClaudeHookEvent) -> ModelClaudeHookResult:
        """Execute the effect node on a hook event.

        Routes the event to the appropriate handler based on event_type
        and returns the processing result.

        Args:
            event: The Claude Code hook event to process.

        Returns:
            ModelClaudeHookResult with processing outcome.
        """
        return await route_hook_event(
            event=event,
            intent_classifier=self._intent_classifier,
            kafka_producer=self._kafka_producer,
            topic_env_prefix=self._topic_env_prefix,
        )


__all__ = ["NodeClaudeHookEventEffect"]
