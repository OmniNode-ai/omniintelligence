# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Claude Hook Event Effect - Declarative effect node for Claude Code hooks.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via direct invocation
    - Pattern: "Contract-driven, handlers wired externally"

All handler routing is 100% driven by contract.yaml, not Python code.

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Direct Dependency Injection: Handler dependencies passed at call site
    - NO custom logic: Pure declarative shell

Handlers receive their dependencies directly via parameters:
    - route_hook_event(event, intent_classifier, kafka_producer, publish_topic)
    - handle_user_prompt_submit(event, intent_classifier, kafka_producer, ...)
    - handle_no_op(event)

Related Tickets:
    - OMN-1456: Unified Claude Code hook endpoint
    - OMN-1757: Refactor to declarative pattern
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeClaudeHookEventEffect(NodeEffect):
    """Declarative effect node for Claude Code hook event handling.

    This effect node is a lightweight shell that defines the I/O contract
    for hook event processing. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - UserPromptSubmit: Classify intent, emit to Kafka
        - SessionStart, SessionEnd, PreToolUse, PostToolUse, Stop, Notification:
          No-op handlers (return success, ready for future implementation)

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (intent_classifier, kafka_producer, publish_topic). This node
        contains NO instance variables for handlers or dependencies.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_claude_hook_event_effect import (
            NodeClaudeHookEventEffect,
            route_hook_event,
            handle_user_prompt_submit,
            handle_no_op,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodeClaudeHookEventEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await route_hook_event(
            event=hook_event,
            intent_classifier=classifier_impl,
            kafka_producer=producer_impl,
            publish_topic="onex.evt.omniintelligence.intent-classified.v1",
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeClaudeHookEventEffect"]
