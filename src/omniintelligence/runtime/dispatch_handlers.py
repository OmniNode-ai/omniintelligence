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
    - Session-outcome and pattern-lifecycle handlers are Phase 1 stubs that
      validate the payload shape and log receipt. Full dependency injection
      (database repository, kafka producer) is deferred to Phase 2.

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2032: Register all 3 intelligence dispatchers
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

DISPATCH_ALIAS_SESSION_OUTCOME = "onex.commands.omniintelligence.session-outcome.v1"
"""Dispatch-compatible alias for TOPIC_SESSION_OUTCOME."""

DISPATCH_ALIAS_PATTERN_LIFECYCLE = (
    "onex.commands.omniintelligence.pattern-lifecycle-transition.v1"
)
"""Dispatch-compatible alias for TOPIC_PATTERN_LIFECYCLE."""


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
                msg = (
                    f"Failed to parse payload as ModelClaudeCodeHookEvent: {e} "
                    f"(correlation_id={ctx_correlation_id})"
                )
                logger.warning(msg)
                raise ValueError(msg) from e
        else:
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for claude-hook-event (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

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
# Bridge Handler: Session Outcome
# =============================================================================


def create_session_outcome_dispatch_handler(
    *,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for session outcome events.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    validates its shape, and logs the session outcome for tracing.

    Phase 1 (OMN-2032): No database repository is injected. The handler
    validates the dispatch path and logs receipt. Full dependency injection
    (repository for record_session_outcome) is deferred to Phase 2.

    Args:
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> session outcome logging (Phase 1)."""
        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if isinstance(payload, dict):
            session_id = payload.get("session_id")
            success = payload.get("success")
            logger.info(
                "Session outcome received via dispatch engine "
                "(session_id=%s, success=%s, correlation_id=%s)",
                session_id,
                success,
                ctx_correlation_id,
            )
        else:
            logger.info(
                "Session outcome received via dispatch engine "
                "(payload_type=%s, correlation_id=%s)",
                type(payload).__name__,
                ctx_correlation_id,
            )

        return ""

    return _handle


# =============================================================================
# Bridge Handler: Pattern Lifecycle Transition
# =============================================================================


def create_pattern_lifecycle_dispatch_handler(
    *,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern lifecycle transition commands.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    validates its shape, and logs the transition for tracing.

    Phase 1 (OMN-2032): No database repository or idempotency store is
    injected. The handler validates the dispatch path and logs receipt.
    Full dependency injection (repository for apply_transition) is deferred
    to Phase 2.

    Args:
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> pattern lifecycle logging (Phase 1)."""
        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if isinstance(payload, dict):
            pattern_id = payload.get("pattern_id")
            from_status = payload.get("from_status")
            to_status = payload.get("to_status")
            logger.info(
                "Pattern lifecycle transition received via dispatch engine "
                "(pattern_id=%s, from=%s, to=%s, correlation_id=%s)",
                pattern_id,
                from_status,
                to_status,
                ctx_correlation_id,
            )
        else:
            logger.info(
                "Pattern lifecycle transition received via dispatch engine "
                "(payload_type=%s, correlation_id=%s)",
                type(payload).__name__,
                ctx_correlation_id,
            )

        return ""

    return _handle


# =============================================================================
# Dispatch Engine Factory
# =============================================================================


def create_intelligence_dispatch_engine() -> MessageDispatchEngine:
    """Create and configure a MessageDispatchEngine for Intelligence domain.

    Creates the engine, registers all 3 intelligence domain handlers and
    routes, and freezes it. The engine is ready for dispatch after this call.

    Dispatchers registered (OMN-2032):
        1. claude-hook-event: Claude Code hook event processing
        2. session-outcome: Session feedback recording (Phase 1 stub)
        3. pattern-lifecycle-transition: Pattern lifecycle transitions (Phase 1 stub)

    Returns:
        Frozen MessageDispatchEngine ready for dispatch.
    """
    engine = MessageDispatchEngine(
        logger=logging.getLogger(f"{__name__}.dispatch_engine"),
    )

    # --- Handler 1: claude-hook-event ---
    claude_hook_handler = create_claude_hook_dispatch_handler()
    engine.register_handler(
        handler_id="intelligence-claude-hook-handler",
        handler=claude_hook_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,  # Accept all message types in Phase 1
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-claude-hook-route",
            topic_pattern=DISPATCH_ALIAS_CLAUDE_HOOK,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-claude-hook-handler",
            description=(
                "Routes claude-hook-event commands to the intelligence handler."
            ),
        )
    )

    # --- Handler 2: session-outcome ---
    session_outcome_handler = create_session_outcome_dispatch_handler()
    engine.register_handler(
        handler_id="intelligence-session-outcome-handler",
        handler=session_outcome_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,  # Accept all message types in Phase 1
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-session-outcome-route",
            topic_pattern=DISPATCH_ALIAS_SESSION_OUTCOME,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-session-outcome-handler",
            description=(
                "Routes session-outcome commands to the intelligence handler. "
                "Phase 1: logging stub. Phase 2: full record_session_outcome."
            ),
        )
    )

    # --- Handler 3: pattern-lifecycle-transition ---
    pattern_lifecycle_handler = create_pattern_lifecycle_dispatch_handler()
    engine.register_handler(
        handler_id="intelligence-pattern-lifecycle-handler",
        handler=pattern_lifecycle_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,  # Accept all message types in Phase 1
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-pattern-lifecycle-route",
            topic_pattern=DISPATCH_ALIAS_PATTERN_LIFECYCLE,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-pattern-lifecycle-handler",
            description=(
                "Routes pattern-lifecycle-transition commands to the intelligence "
                "handler. Phase 1: logging stub. Phase 2: full apply_transition."
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
                if hasattr(msg, "nack"):
                    await msg.nack()
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

            # Gate ack/nack on dispatch status
            if result.is_successful():
                if hasattr(msg, "ack"):
                    await msg.ack()
            else:
                logger.warning(
                    "Dispatch failed (status=%s, error=%s), nacking message "
                    "(correlation_id=%s)",
                    result.status,
                    result.error_message,
                    msg_correlation_id,
                )
                if hasattr(msg, "nack"):
                    await msg.nack()

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
    "DISPATCH_ALIAS_PATTERN_LIFECYCLE",
    "DISPATCH_ALIAS_SESSION_OUTCOME",
    "create_claude_hook_dispatch_handler",
    "create_dispatch_callback",
    "create_intelligence_dispatch_engine",
    "create_pattern_lifecycle_dispatch_handler",
    "create_session_outcome_dispatch_handler",
]
