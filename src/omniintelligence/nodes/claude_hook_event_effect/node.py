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
    1. Receive hook event (ModelClaudeCodeHookEvent)
    2. Route to handler based on event_type
    3. For UserPromptSubmit: classify intent, store in graph, emit to Kafka
    4. For other types: return success (no-op)
    5. Return structured response (ModelClaudeHookResult)

Design Decisions:
    - Single ingress for all Claude Code hook types
    - Event type routing to specialized handlers
    - No-op handlers for unimplemented event types (stable pipeline shape)
    - External adapters injected via setter methods
    - Contract-driven topic resolution (OMN-1551)

Node Responsibilities:
    - Define I/O model contract (ModelClaudeCodeHookEvent -> ModelClaudeHookResult)
    - Provide dependency injection points for adapters
    - Load publish topics from contract's event_bus subcontract
    - Delegate execution to handlers

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
    - OMN-1551: Contract-driven topic resolution
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect
from omnibase_infra.runtime.event_bus_subcontract_wiring import (
    load_event_bus_subcontract,
)

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

logger = logging.getLogger(__name__)


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
        - And more (see EnumClaudeCodeHookEventType)

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
        self._intent_classifier: ProtocolIntentClassifier | None = None
        self._kafka_producer: ProtocolKafkaPublisher | None = None
        self._topic_env_prefix: str = "dev"

        # Load publish topic suffix from contract (OMN-1551: contract-driven topic resolution)
        self._publish_topic_suffix: str | None = self._load_publish_topic_from_contract()

    def _load_publish_topic_from_contract(self) -> str | None:
        """Load the first publish topic suffix from contract.yaml.

        Reads the event_bus.publish_topics[0] from the node's contract file.
        This enables contract-driven topic resolution per OMN-1551.

        Returns:
            Topic suffix string (e.g., "onex.evt.omniintelligence.intent-classified.v1")
            or None if contract cannot be loaded.
        """
        # Contract is co-located with node.py in the same directory
        contract_path = Path(__file__).parent / "contract.yaml"

        subcontract = load_event_bus_subcontract(contract_path, logger)
        if subcontract is None:
            logger.warning(
                "Failed to load event_bus subcontract from %s, "
                "publish topic must be set explicitly via set_publish_topic_suffix()",
                contract_path,
            )
            return None

        if not subcontract.publish_topics:
            logger.warning(
                "No publish_topics in event_bus subcontract from %s",
                contract_path,
            )
            return None

        topic_suffix = subcontract.publish_topics[0]
        logger.debug(
            "Loaded publish topic suffix from contract: %s",
            topic_suffix,
        )
        return topic_suffix

    def set_intent_classifier(self, classifier: ProtocolIntentClassifier) -> None:
        """Set the intent classifier compute node.

        Args:
            classifier: Intent classifier compute node instance implementing
                ProtocolIntentClassifier.
        """
        self._intent_classifier = classifier

    def set_kafka_producer(self, producer: ProtocolKafkaPublisher) -> None:
        """Set the Kafka producer for event emission.

        Args:
            producer: Kafka producer instance implementing ProtocolKafkaPublisher.
        """
        self._kafka_producer = producer

    def set_topic_env_prefix(self, prefix: str) -> None:
        """Set the environment prefix for Kafka topics.

        Args:
            prefix: Environment prefix (e.g., "dev", "prod").
        """
        self._topic_env_prefix = prefix

    def set_publish_topic_suffix(self, suffix: str) -> None:
        """Set the publish topic suffix (override contract-loaded value).

        Args:
            suffix: Topic suffix (e.g., "onex.evt.omniintelligence.intent-classified.v1").
        """
        self._publish_topic_suffix = suffix

    @property
    def topic_env_prefix(self) -> str:
        """Get the configured Kafka topic environment prefix."""
        return self._topic_env_prefix

    @property
    def publish_topic_suffix(self) -> str | None:
        """Get the publish topic suffix from contract or explicit override."""
        return self._publish_topic_suffix

    @property
    def intent_classifier(self) -> ProtocolIntentClassifier | None:
        """Get the intent classifier if configured."""
        return self._intent_classifier

    @property
    def kafka_producer(self) -> ProtocolKafkaPublisher | None:
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

    async def execute(self, event: ModelClaudeCodeHookEvent) -> ModelClaudeHookResult:
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
            publish_topic_suffix=self._publish_topic_suffix,
        )


__all__ = ["NodeClaudeHookEventEffect"]
