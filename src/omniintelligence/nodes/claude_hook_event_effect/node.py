# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect - Unified handler for Claude Code hook events.

This node follows the ONEX declarative pattern:
    - 100% Contract-Driven: All topics/routing defined in YAML, not Python
    - Zero Contract Loading: Runtime wires everything from contract.yaml
    - Declarative Execution: Thin shell that delegates to handlers

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
Handler routing is initialized by the RUNTIME (not this module).

Design Decisions:
    - Single ingress for all Claude Code hook types
    - Event type routing to specialized handlers
    - No-op handlers for unimplemented event types (stable pipeline shape)
    - Dependencies wired by runtime via container or direct injection
    - Contract-driven topic resolution (OMN-1551)

Node Responsibilities:
    - Define I/O model contract (ModelClaudeCodeHookEvent -> ModelClaudeHookResult)
    - Delegate execution to handlers with runtime-wired dependencies

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
    - OMN-1551: Contract-driven topic resolution
    - NodeRegistrationOrchestrator pattern (omnibase_infra)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.claude_hook_event_effect.handlers import (
    ProtocolIntentClassifier,
    ProtocolKafkaPublisher,
    route_hook_event,
)
from omniintelligence.nodes.claude_hook_event_effect.models import (
    ModelClaudeCodeHookEvent,
    ModelClaudeHookResult,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeClaudeHookEventEffect(NodeEffect):
    """Effect node for unified Claude Code hook event handling.

    This is a thin declarative shell - all behavior is defined in contract.yaml.
    Topic wiring, handler routing, and dependency injection are initialized
    by the RUNTIME, not this module.

    Supported Event Types (from Claude Code hook lifecycle):
        - SessionStart: Session begins
        - UserPromptSubmit: User submits a prompt (routes to intent classification)
        - PreToolUse: Before tool execution
        - PostToolUse: After tool execution
        - Stop: Stop signal
        - SessionEnd: Session ends
        - Notification: Async notifications
        - And more (see EnumClaudeCodeHookEventType)

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.claude_hook_event_effect import (
            NodeClaudeHookEventEffect,
        )

        # Create effect node with container (runtime wires dependencies)
        container = ModelONEXContainer()
        effect = NodeClaudeHookEventEffect(container)

        # Execute - dependencies are wired by runtime or passed directly
        result = await effect.execute(
            event=hook_event,
            intent_classifier=classifier,  # Runtime-wired
            kafka_producer=producer,        # Runtime-wired
            topic_env_prefix="dev",         # From contract
            publish_topic_suffix="onex.evt.omniintelligence.intent-classified.v1",
        )
        ```
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize with container dependency injection.

        Args:
            container: ONEX dependency injection container.
        """
        super().__init__(container)

    async def execute(
        self,
        event: ModelClaudeCodeHookEvent,
        *,
        intent_classifier: ProtocolIntentClassifier | None = None,
        kafka_producer: ProtocolKafkaPublisher | None = None,
        topic_env_prefix: str = "dev",
        publish_topic_suffix: str | None = None,
    ) -> ModelClaudeHookResult:
        """Execute the effect node on a hook event.

        Routes the event to the appropriate handler based on event_type
        and returns the processing result. Dependencies are wired by
        the runtime from contract.yaml.

        Args:
            event: The Claude Code hook event to process.
            intent_classifier: Intent classifier compute node (runtime-wired).
            kafka_producer: Kafka producer for event emission (runtime-wired).
            topic_env_prefix: Environment prefix for Kafka topic (from contract).
            publish_topic_suffix: Topic suffix from contract's event_bus.publish_topics.

        Returns:
            ModelClaudeHookResult with processing outcome.
        """
        return await route_hook_event(
            event=event,
            intent_classifier=intent_classifier,
            kafka_producer=kafka_producer,
            topic_env_prefix=topic_env_prefix,
            publish_topic_suffix=publish_topic_suffix,
        )


__all__ = ["NodeClaudeHookEventEffect"]
