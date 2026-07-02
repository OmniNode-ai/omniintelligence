# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Registry for Cursor Hook Event Effect Node Dependencies.

RegistryCursorHookEventEffect creates and registers handler instances for the
NodeCursorHookEventEffect node. Mirrors RegistryClaudeHookEventEffect.

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryCursorHookEventEffect.clear()`` in setup and teardown fixtures to
    prevent test pollution between test cases.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

    from omniintelligence.nodes.node_cursor_hook_event_effect.handlers.handler_cursor_event import (
        HandlerCursorHookEvent,
        ProtocolIntentClassifier,
        ProtocolKafkaPublisher,
        ProtocolPatternRepository,
    )

__all__ = ["RegistryCursorHookEventEffect"]

# Module-level storage for handlers, protected by a lock for thread safety.
_HANDLER_STORAGE: dict[str, object] = {}
_HANDLER_STORAGE_LOCK: threading.Lock = threading.Lock()


class RegistryCursorHookEventEffect:
    """Registry for Cursor Hook Event Effect node dependencies.

    Creates and registers handler instances with explicit dependency injection.
    Both Kafka publisher and intent classifier are optional.
    """

    HANDLER_KEY = "handler_cursor_hook_event"

    @staticmethod
    def create_handler(
        *,
        kafka_publisher: ProtocolKafkaPublisher | None = None,
        intent_classifier: ProtocolIntentClassifier | None = None,
        publish_topic: str | None = None,
        repository: ProtocolPatternRepository | None = None,
    ) -> HandlerCursorHookEvent:
        """Create a handler with explicit dependencies.

        Args:
            kafka_publisher: Optional Kafka publisher for event emission.
            intent_classifier: Optional intent classifier compute node.
            publish_topic: Full Kafka topic for publishing classified intents.
            repository: Optional database repository for tool-use persistence.

        Returns:
            Configured HandlerCursorHookEvent instance.
        """
        from omniintelligence.nodes.node_cursor_hook_event_effect.handlers.handler_cursor_event import (
            HandlerCursorHookEvent,
        )

        return HandlerCursorHookEvent(
            kafka_publisher=kafka_publisher,
            intent_classifier=intent_classifier,
            publish_topic=publish_topic,
            repository=repository,
        )

    @staticmethod
    def register_handler(
        _container: ModelONEXContainer,
        handler: HandlerCursorHookEvent,
    ) -> None:
        """Register a handler instance with the container.

        Args:
            _container: ONEX dependency injection container (reserved for future use).
            handler: HandlerCursorHookEvent instance to register.

        Raises:
            ValueError: If handler does not have required methods.
        """
        if not callable(getattr(handler, "handle", None)):
            raise ValueError(
                f"Handler missing required 'handle' method. "
                f"Got {type(handler).__name__}"
            )

        with _HANDLER_STORAGE_LOCK:
            if RegistryCursorHookEventEffect.HANDLER_KEY in _HANDLER_STORAGE:
                logger.warning(
                    "Re-registering handler '%s'. This may indicate container lifecycle "
                    "issues or missing clear() calls in tests.",
                    RegistryCursorHookEventEffect.HANDLER_KEY,
                )

            _HANDLER_STORAGE[RegistryCursorHookEventEffect.HANDLER_KEY] = handler

    @staticmethod
    def get_handler(
        _container: ModelONEXContainer,
    ) -> HandlerCursorHookEvent | None:
        """Retrieve the registered handler.

        Args:
            _container: ONEX dependency injection container (reserved for future use).

        Returns:
            The registered HandlerCursorHookEvent, or None if not found.
        """
        from omniintelligence.nodes.node_cursor_hook_event_effect.handlers.handler_cursor_event import (
            HandlerCursorHookEvent,
        )

        with _HANDLER_STORAGE_LOCK:
            result = _HANDLER_STORAGE.get(RegistryCursorHookEventEffect.HANDLER_KEY)
            if result is not None and not isinstance(result, HandlerCursorHookEvent):
                logger.warning(
                    "Handler type mismatch: expected HandlerCursorHookEvent, got %s",
                    type(result).__name__,
                )
                return None
            return result

    @staticmethod
    def clear() -> None:
        """Clear all registered handlers. Essential for test isolation."""
        with _HANDLER_STORAGE_LOCK:
            _HANDLER_STORAGE.clear()
