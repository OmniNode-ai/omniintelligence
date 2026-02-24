# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect node.

This module exports the unified Claude Code hook event handler node and
its supporting models, handlers, and protocols. The node processes Claude
Code hook events with intent classification and Kafka emission.

Key Components:
    - NodeClaudeHookEventEffect: Pure declarative effect node (thin shell)
    - ModelClaudeCodeHookEvent: Input from hook events
    - ModelClaudeHookResult: Output with processing status and intent
    - ProtocolIntentClassifier: Interface for intent classification
    - ProtocolKafkaPublisher: Interface for Kafka publishing

Handler Functions (Direct Invocation):
    - route_hook_event: Main entry point routing to handlers
    - handle_user_prompt_submit: Process UserPromptSubmit with classification
    - handle_no_op: Default handler for unimplemented event types

Usage (Declarative Pattern):
    from omniintelligence.nodes.node_claude_hook_event_effect import (
        NodeClaudeHookEventEffect,
        route_hook_event,
        handle_user_prompt_submit,
        handle_no_op,
        ModelClaudeCodeHookEvent,
    )

    # Create node via container (pure declarative shell)
    from omnibase_core.models.container import ModelONEXContainer
    container = ModelONEXContainer()
    node = NodeClaudeHookEventEffect(container)

    # Handlers are called directly with their dependencies
    result = await route_hook_event(
        event=hook_event,
        intent_classifier=classifier_impl,
        kafka_producer=producer_impl,
        publish_topic="onex.evt.omniintelligence.intent-classified.v1",
    )

    # For event-driven execution, use RuntimeHostProcess
    # which reads handler_routing from contract.yaml

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
    - OMN-1757: Refactor to declarative pattern
"""

# Handler functions for direct invocation (primary API)
from omniintelligence.nodes.node_claude_hook_event_effect.handlers import (
    HandlerClaudeHookEvent,
    ProtocolIntentClassifier,
    ProtocolKafkaPublisher,
    handle_no_op,
    handle_user_prompt_submit,
    route_hook_event,
)

# Models for I/O contract
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeHookResult,
    ModelIntentResult,
)

# Node class (pure declarative shell)
from omniintelligence.nodes.node_claude_hook_event_effect.node import (
    NodeClaudeHookEventEffect,
)

__all__ = [
    # Enums
    "EnumClaudeCodeHookEventType",
    "EnumHookProcessingStatus",
    # Handler class (orchestration helper)
    "HandlerClaudeHookEvent",
    # Models
    "ModelClaudeCodeHookEvent",
    "ModelClaudeHookResult",
    "ModelIntentResult",
    # Node (pure declarative shell)
    "NodeClaudeHookEventEffect",
    # Protocols
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    # Handler functions (direct invocation - primary API)
    "handle_no_op",
    "handle_user_prompt_submit",
    "route_hook_event",
]
