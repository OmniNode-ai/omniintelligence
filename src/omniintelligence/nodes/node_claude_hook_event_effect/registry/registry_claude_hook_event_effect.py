# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Registry for Claude Hook Event Effect Node Dependencies.

This module provides RegistryClaudeHookEventEffect, which creates and registers
handler instances for the NodeClaudeHookEventEffect node.

Architecture:
    The registry follows ONEX declarative pattern:
    - Static factory creates handler with explicit dependencies
    - Dependencies injected via constructor (NO setters)
    - Kafka publisher is OPTIONAL (graceful degradation when unavailable)
    - Intent classifier is OPTIONAL
    - Returns configured handler ready for use

Related:
    - NodeClaudeHookEventEffect: Effect node that uses this registry
    - HandlerClaudeHookEvent: Handler that processes hook events
    - ProtocolIntentClassifier: Protocol for intent classification
    - ProtocolKafkaPublisher: Protocol for Kafka publishing

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryClaudeHookEventEffect.clear()`` in setup and teardown fixtures
    to prevent test pollution between test cases.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

    from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
        HandlerClaudeHookEvent,
        ProtocolIntentClassifier,
        ProtocolKafkaPublisher,
    )

__all__ = ["RegistryClaudeHookEventEffect"]

# Module-level storage for handlers, protected by a lock for thread safety.
# Safe under CPython GIL but using an explicit lock ensures correctness under
# uvloop and other alternative event loops where concurrent access is possible.
_HANDLER_STORAGE: dict[str, object] = {}
_HANDLER_STORAGE_LOCK: threading.Lock = threading.Lock()


class RegistryClaudeHookEventEffect:
    """Registry for Claude Hook Event Effect node dependencies.

    Creates and registers handler instances with explicit dependency injection.
    Both Kafka publisher and intent classifier are optional.

    Usage:
        .. code-block:: python

            from omnibase_core.models.container import ModelONEXContainer
            from omniintelligence.nodes.node_claude_hook_event_effect.registry import (
                RegistryClaudeHookEventEffect,
            )

            # Create handler with dependencies
            handler = RegistryClaudeHookEventEffect.create_handler(
                kafka_publisher=kafka_producer,
                intent_classifier=intent_classifier,  # optional
                publish_topic="onex.evt.omniintelligence.intent-classified.v1",
            )

            # Register handler for later retrieval
            container = ModelONEXContainer()
            RegistryClaudeHookEventEffect.register_handler(container, handler)

            # Or retrieve existing handler
            handler = RegistryClaudeHookEventEffect.get_handler(container)

    Note:
        This registry creates handler instances with optional dependencies.
        When Kafka publisher is not provided, the handler operates in degraded
        mode (intent classification runs but events are not emitted).
    """

    HANDLER_KEY = "handler_claude_hook_event"

    @staticmethod
    def create_handler(
        *,
        kafka_publisher: ProtocolKafkaPublisher | None = None,
        intent_classifier: ProtocolIntentClassifier | None = None,
        publish_topic: str | None = None,
    ) -> HandlerClaudeHookEvent:
        """Create a handler with explicit dependencies.

        This factory creates a configured handler ready for use. When
        kafka_publisher is None, the handler operates in degraded mode:
        intent classification still runs but events are not emitted to Kafka.

        Args:
            kafka_publisher: Optional Kafka publisher for event emission.
                When None, the handler gracefully degrades (no Kafka emission).
            intent_classifier: Optional intent classifier compute node.
            publish_topic: Full Kafka topic for publishing classified intents.
                Source of truth is the contract's event_bus.publish_topics.

        Returns:
            Configured HandlerClaudeHookEvent instance.

        Example:
            >>> handler = RegistryClaudeHookEventEffect.create_handler(
            ...     kafka_publisher=kafka_producer,
            ...     intent_classifier=classifier,
            ...     publish_topic="onex.evt.omniintelligence.intent-classified.v1",
            ... )
        """
        # Import here to avoid circular imports
        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            HandlerClaudeHookEvent,
        )

        # Create handler with explicit constructor injection
        return HandlerClaudeHookEvent(
            kafka_publisher=kafka_publisher,
            intent_classifier=intent_classifier,
            publish_topic=publish_topic,
        )

    @staticmethod
    def register_handler(
        _container: ModelONEXContainer,
        handler: HandlerClaudeHookEvent,
    ) -> None:
        """Register a handler instance with the container.

        Args:
            _container: ONEX dependency injection container (reserved for future use).
            handler: HandlerClaudeHookEvent instance to register.

        Raises:
            ValueError: If handler does not have required methods.
        """
        # Validate handler has required method
        if not callable(getattr(handler, "handle", None)):
            raise ValueError(
                f"Handler missing required 'handle' method. "
                f"Got {type(handler).__name__}"
            )

        with _HANDLER_STORAGE_LOCK:
            # Warn if re-registering
            if RegistryClaudeHookEventEffect.HANDLER_KEY in _HANDLER_STORAGE:
                logger.warning(
                    "Re-registering handler '%s'. This may indicate container lifecycle "
                    "issues or missing clear() calls in tests.",
                    RegistryClaudeHookEventEffect.HANDLER_KEY,
                )

            _HANDLER_STORAGE[RegistryClaudeHookEventEffect.HANDLER_KEY] = handler

    @staticmethod
    def get_handler(
        _container: ModelONEXContainer,
    ) -> HandlerClaudeHookEvent | None:
        """Retrieve the registered handler.

        Args:
            _container: ONEX dependency injection container (reserved for future use).

        Returns:
            The registered HandlerClaudeHookEvent, or None if not found.
        """
        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            HandlerClaudeHookEvent,
        )

        with _HANDLER_STORAGE_LOCK:
            result = _HANDLER_STORAGE.get(RegistryClaudeHookEventEffect.HANDLER_KEY)
            if result is not None and not isinstance(result, HandlerClaudeHookEvent):
                # Type safety: ensure we return the correct type
                logger.warning(
                    "Handler type mismatch: expected HandlerClaudeHookEvent, got %s",
                    type(result).__name__,
                )
                return None
            return result

    @staticmethod
    def clear() -> None:
        """Clear all registered handlers.

        Essential for test isolation. Call in test setup and teardown.

        Example:
            .. code-block:: python

                @pytest.fixture(autouse=True)
                def clear_registry():
                    RegistryClaudeHookEventEffect.clear()
                    yield
                    RegistryClaudeHookEventEffect.clear()
        """
        with _HANDLER_STORAGE_LOCK:
            _HANDLER_STORAGE.clear()
