# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Dispatch bridge handlers for Intelligence domain.

This module provides bridge handlers that adapt between the MessageDispatchEngine
handler signature and existing Intelligence domain handlers. It also defines
topic alias mappings needed because ONEX canonical topic naming uses `.cmd.`
and `.evt.` segments, which EnumMessageCategory.from_topic() does not yet
recognize (it expects `.commands.` and `.events.`).

Design Decisions:
    - Topic aliases are a temporary bridge until EnumMessageCategory.from_topic()
      is updated to handle `.cmd.` / `.evt.` short forms.
    - Bridge handlers adapt (envelope, context) -> existing handler interfaces.
    - The dispatch engine is created per-plugin (not kernel-managed) for Phase 1.
    - message_types=None on handler registration accepts all message types in
      the category -- correct for Phase 1 where we route by topic, not type.

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-934: MessageDispatchEngine implementation
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from omnibase_core.enums.enum_execution_shape import EnumMessageCategory
from omnibase_core.enums.enum_node_kind import EnumNodeKind
from omnibase_core.models.core.model_envelope_metadata import ModelEnvelopeMetadata
from omnibase_core.models.dispatch.model_dispatch_route import ModelDispatchRoute
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)
from omnibase_core.runtime.runtime_message_dispatch import MessageDispatchEngine

logger = logging.getLogger(__name__)

# =============================================================================
# Topic Alias Mapping
# =============================================================================
# ONEX canonical topic naming uses `.cmd.` for commands and `.evt.` for events.
# MessageDispatchEngine.dispatch() uses EnumMessageCategory.from_topic() which
# only recognizes `.commands.` and `.events.` segments. These aliases bridge
# the naming gap until from_topic() is updated.
#
# Usage: when calling dispatch(), pass the alias instead of the raw topic.

DISPATCH_ALIAS_CLAUDE_HOOK = "onex.commands.omniintelligence.claude-hook-event.v1"
"""Dispatch-compatible alias for TOPIC_CLAUDE_HOOK_EVENT."""


# =============================================================================
# Bridge Handler: Claude Hook Event
# =============================================================================


def create_claude_hook_dispatch_handler(
    *,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for Claude hook events.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    parses it as a ModelClaudeCodeHookEvent, and delegates to route_hook_event().

    Dependencies (kafka_producer, intent_classifier) are not wired in Phase 1.
    The handler processes the event with classification and logging but without
    Kafka emission. This is intentional: Phase 1 validates the dispatch path,
    Phase 2 adds full dependency injection.

    Args:
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> route_hook_event()."""
        from omniintelligence.nodes.node_claude_hook_event_effect.handlers import (
            route_hook_event,
        )
        from omniintelligence.nodes.node_claude_hook_event_effect.models import (
            ModelClaudeCodeHookEvent,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        # Parse payload into ModelClaudeCodeHookEvent
        if isinstance(payload, ModelClaudeCodeHookEvent):
            event = payload
        elif isinstance(payload, dict):
            try:
                event = ModelClaudeCodeHookEvent(**payload)
            except Exception as e:
                logger.warning(
                    "Failed to parse payload as ModelClaudeCodeHookEvent: %s "
                    "(correlation_id=%s)",
                    e,
                    ctx_correlation_id,
                )
                return ""
        else:
            logger.warning(
                "Unexpected payload type %s for claude-hook-event (correlation_id=%s)",
                type(payload).__name__,
                ctx_correlation_id,
            )
            return ""

        logger.info(
            "Dispatching claude-hook-event via MessageDispatchEngine "
            "(event_type=%s, correlation_id=%s)",
            event.event_type,
            ctx_correlation_id,
        )

        # Delegate to existing handler (Phase 1: no kafka_producer, no intent_classifier)
        result = await route_hook_event(
            event=event,
            intent_classifier=None,
            kafka_producer=None,
        )

        logger.info(
            "Claude hook event processed via dispatch engine "
            "(status=%s, event_type=%s, correlation_id=%s)",
            result.status,
            result.event_type,
            ctx_correlation_id,
        )

        return ""

    return _handle


# =============================================================================
# Dispatch Engine Factory
# =============================================================================


def create_intelligence_dispatch_engine() -> MessageDispatchEngine:
    """Create and configure a MessageDispatchEngine for Intelligence domain.

    Creates the engine, registers the claude-hook-event handler and route,
    and freezes it. The engine is ready for dispatch after this call.

    Phase 1: Only claude-hook-event is routed. Session-outcome and
    pattern-lifecycle topics will be added in Phase 2.

    Returns:
        Frozen MessageDispatchEngine ready for dispatch.
    """
    engine = MessageDispatchEngine(
        logger=logging.getLogger(f"{__name__}.dispatch_engine"),
    )

    # Register handler for claude-hook-event
    handler = create_claude_hook_dispatch_handler()
    engine.register_handler(
        handler_id="intelligence-claude-hook-handler",
        handler=handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,  # Accept all message types in Phase 1
    )

    # Register route matching the dispatch alias topic
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-claude-hook-route",
            topic_pattern=DISPATCH_ALIAS_CLAUDE_HOOK,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-claude-hook-handler",
            description=(
                "Routes claude-hook-event commands to the intelligence handler. "
                "Phase 1: topic-level routing only."
            ),
        )
    )

    engine.freeze()

    logger.info(
        "Intelligence dispatch engine created and frozen (routes=%d, handlers=%d)",
        engine.route_count,
        engine.handler_count,
    )

    return engine


# =============================================================================
# Event Bus Callback Factory
# =============================================================================


def create_dispatch_callback(
    engine: MessageDispatchEngine,
    dispatch_topic: str,
    *,
    correlation_id: UUID | None = None,
) -> Callable[[Any], Awaitable[None]]:
    """Create an event bus callback that routes messages through the dispatch engine.

    The callback:
    1. Deserializes the raw message value from bytes to dict
    2. Wraps it in a ModelEventEnvelope with command category metadata
    3. Calls engine.dispatch() with the dispatch-compatible topic alias
    4. Acks the message on success, nacks on failure

    Args:
        engine: Frozen MessageDispatchEngine.
        dispatch_topic: Dispatch-compatible topic alias to pass to dispatch().
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async callback compatible with event bus subscribe(on_message=...).
    """

    async def _on_message(msg: Any) -> None:
        """Event bus callback: raw message -> dispatch engine."""
        msg_correlation_id = correlation_id or uuid4()

        try:
            # Extract raw value from message
            if hasattr(msg, "value"):
                raw_value = msg.value
                if isinstance(raw_value, (bytes, bytearray)):
                    payload_dict = json.loads(raw_value.decode("utf-8"))
                elif isinstance(raw_value, str):
                    payload_dict = json.loads(raw_value)
                elif isinstance(raw_value, dict):
                    payload_dict = raw_value
                else:
                    logger.warning(
                        "Unexpected message value type %s (correlation_id=%s)",
                        type(raw_value).__name__,
                        msg_correlation_id,
                    )
                    if hasattr(msg, "nack"):
                        await msg.nack()
                    return
            elif isinstance(msg, dict):
                payload_dict = msg
            else:
                logger.warning(
                    "Unexpected message type %s (correlation_id=%s)",
                    type(msg).__name__,
                    msg_correlation_id,
                )
                return

            # Extract correlation_id from payload if available
            payload_correlation_id = payload_dict.get("correlation_id")
            if payload_correlation_id:
                with contextlib.suppress(ValueError, AttributeError):
                    msg_correlation_id = UUID(str(payload_correlation_id))

            # Wrap in ModelEventEnvelope with command category metadata
            envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
                payload=payload_dict,
                correlation_id=msg_correlation_id,
                metadata=ModelEnvelopeMetadata(
                    tags={"message_category": "command"},
                ),
            )

            # Dispatch through the engine
            result = await engine.dispatch(
                topic=dispatch_topic,
                envelope=envelope,
            )

            logger.debug(
                "Dispatch result: status=%s, handler=%s, duration=%.2fms "
                "(correlation_id=%s)",
                result.status,
                result.handler_id,
                result.duration_ms,
                msg_correlation_id,
            )

            # Ack on success
            if hasattr(msg, "ack"):
                await msg.ack()

        except Exception as e:
            logger.exception(
                "Failed to dispatch message via engine: %s (correlation_id=%s)",
                e,
                msg_correlation_id,
            )
            if hasattr(msg, "nack"):
                await msg.nack()

    return _on_message


__all__ = [
    "DISPATCH_ALIAS_CLAUDE_HOOK",
    "create_claude_hook_dispatch_handler",
    "create_dispatch_callback",
    "create_intelligence_dispatch_engine",
]
