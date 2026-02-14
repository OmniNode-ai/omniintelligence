# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Dispatch bridge handlers for Intelligence domain.

This module provides bridge handlers that adapt between the MessageDispatchEngine
handler signature and existing Intelligence domain handlers. It also defines
topic alias mappings needed because ONEX canonical topic naming uses ``.cmd.``
and ``.evt.`` segments, which EnumMessageCategory.from_topic() does not yet
recognize (it expects ``.commands.`` and ``.events.``).

Design Decisions:
    - Topic aliases are a temporary bridge until EnumMessageCategory.from_topic()
      is updated to handle ``.cmd.`` / ``.evt.`` short forms.
    - Bridge handlers adapt (envelope, context) -> existing handler interfaces.
    - The dispatch engine is created per-plugin (not kernel-managed).
    - message_types=None on handler registration accepts all message types in
      the category -- correct when routing by topic, not type.
    - All required dependencies (repository, idempotency_store, intent_classifier)
      must be provided -- no fallback stubs. If deps are missing, the plugin
      must not start consumers.

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2032: Register intelligence dispatchers (now 4 handlers, 6 routes)
    - OMN-934: MessageDispatchEngine implementation
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from omnibase_core.enums.enum_execution_shape import EnumMessageCategory
from omnibase_core.enums.enum_node_kind import EnumNodeKind
from omnibase_core.integrations.claude_code import ClaudeCodeSessionOutcome
from omnibase_core.models.core.model_envelope_metadata import ModelEnvelopeMetadata
from omnibase_core.models.dispatch.model_dispatch_route import ModelDispatchRoute
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)
from omnibase_core.runtime.runtime_message_dispatch import MessageDispatchEngine

logger = logging.getLogger(__name__)

# =============================================================================
# Dependency Protocols (structural typing for dispatch handler deps)
# =============================================================================
# ProtocolPatternRepository and ProtocolKafkaPublisher are imported from the
# canonical location. ProtocolIdempotencyStore and ProtocolIntentClassifier
# are defined locally to avoid circular imports with their handler modules
# (handler_transition.py and handler_claude_event.py respectively).

from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository


@runtime_checkable
class ProtocolIdempotencyStore(Protocol):
    """Idempotency key tracking protocol."""

    async def exists(self, request_id: UUID) -> bool: ...
    async def record(self, request_id: UUID) -> None: ...
    async def check_and_record(self, request_id: UUID) -> bool: ...


@runtime_checkable
class ProtocolIntentClassifier(Protocol):
    """Intent classification protocol."""

    async def compute(
        self, input_data: Any
    ) -> Any: ...  # any-ok: protocol bridge for dynamically-typed classifier interface


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
"""Dispatch-compatible alias for claude-hook-event canonical topic."""

DISPATCH_ALIAS_SESSION_OUTCOME = "onex.commands.omniintelligence.session-outcome.v1"
"""Dispatch-compatible alias for session-outcome canonical topic."""

DISPATCH_ALIAS_PATTERN_LIFECYCLE = (
    "onex.commands.omniintelligence.pattern-lifecycle-transition.v1"
)
"""Dispatch-compatible alias for pattern-lifecycle canonical topic."""

DISPATCH_ALIAS_PATTERN_LEARNED = "onex.events.omniintelligence.pattern-learned.v1"
"""Dispatch-compatible alias for pattern-learned canonical topic."""

DISPATCH_ALIAS_PATTERN_DISCOVERED = "onex.events.pattern.discovered.v1"
"""Dispatch-compatible alias for pattern.discovered canonical topic."""

DISPATCH_ALIAS_TOOL_CONTENT = "onex.commands.omniintelligence.tool-content.v1"
"""Dispatch-compatible alias for tool-content canonical topic."""


# =============================================================================
# Bridge Handler: Claude Hook Event
# =============================================================================


def create_claude_hook_dispatch_handler(
    *,
    intent_classifier: ProtocolIntentClassifier,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for Claude hook events.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    parses it as a ModelClaudeCodeHookEvent, and delegates to route_hook_event().

    Args:
        intent_classifier: REQUIRED intent classifier for user prompt analysis.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for intent classification events (from contract).
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

        result = await route_hook_event(
            event=event,
            intent_classifier=intent_classifier,
            kafka_producer=kafka_producer,
            publish_topic=publish_topic,
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
    repository: ProtocolPatternRepository,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for session outcome events.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    maps it to handler args, and delegates to record_session_outcome().

    Args:
        repository: REQUIRED database repository for pattern feedback recording.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> record_session_outcome()."""
        from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
            record_session_outcome,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for session-outcome (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Extract required fields
        raw_session_id = payload.get("session_id")
        if raw_session_id is None:
            msg = (
                f"Session outcome payload missing required field 'session_id' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            session_id = UUID(str(raw_session_id))
        except ValueError as e:
            msg = (
                f"Invalid UUID for 'session_id': {raw_session_id!r} "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e
        # Map outcome enum to success boolean.
        # Wire payload sends `outcome: "success"` (not `success: true`).
        # Fall back to legacy `success` field for backwards compatibility.
        raw_outcome = payload.get("outcome")
        if raw_outcome is not None:
            try:
                outcome_enum = ClaudeCodeSessionOutcome(raw_outcome)
            except ValueError:
                # Unknown outcome value -- treat as failed
                logger.warning(
                    "Unknown outcome value %r, treating as failed (correlation_id=%s)",
                    raw_outcome,
                    ctx_correlation_id,
                )
                outcome_enum = ClaudeCodeSessionOutcome.FAILED
            success = outcome_enum.is_successful()
        else:
            # Legacy fallback: read `success` boolean field directly
            success = bool(payload.get("success", False))

        failure_reason = payload.get("failure_reason")

        logger.info(
            "Dispatching session-outcome via MessageDispatchEngine "
            "(session_id=%s, success=%s, correlation_id=%s)",
            session_id,
            success,
            ctx_correlation_id,
        )

        result = await record_session_outcome(
            session_id=session_id,
            success=success,
            failure_reason=failure_reason,
            repository=repository,
            correlation_id=ctx_correlation_id,
        )

        logger.info(
            "Session outcome processed via dispatch engine "
            "(session_id=%s, patterns_affected=%d, correlation_id=%s)",
            session_id,
            result.patterns_updated,
            ctx_correlation_id,
        )

        return ""

    return _handle


# =============================================================================
# Bridge Handler: Pattern Lifecycle Transition
# =============================================================================


def create_pattern_lifecycle_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    idempotency_store: ProtocolIdempotencyStore,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern lifecycle transition commands.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler extracts the payload from the envelope,
    maps it to transition parameters, and delegates to apply_transition().

    Args:
        repository: REQUIRED database repository for pattern state management.
        idempotency_store: REQUIRED idempotency store for deduplication.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for transition events (from contract).
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> apply_transition()."""
        from omniintelligence.enums import EnumPatternLifecycleStatus
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers import (
            apply_transition,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for pattern-lifecycle-transition "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Extract required fields
        raw_pattern_id = payload.get("pattern_id")
        if raw_pattern_id is None:
            msg = (
                f"Pattern lifecycle payload missing required field 'pattern_id' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Parse transition fields from payload
        try:
            pattern_id = UUID(str(raw_pattern_id))
        except ValueError as e:
            msg = (
                f"Invalid UUID for 'pattern_id': {raw_pattern_id!r} "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        raw_request_id = payload.get("request_id")
        if raw_request_id is None:
            msg = (
                f"Pattern lifecycle payload missing required field 'request_id' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)
        try:
            request_id = UUID(str(raw_request_id))
        except ValueError as e:
            msg = (
                f"Invalid UUID for 'request_id': {raw_request_id!r} "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        raw_from_status = payload.get("from_status")
        if raw_from_status is None:
            msg = (
                f"Pattern lifecycle payload missing required field 'from_status' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        raw_to_status = payload.get("to_status")
        if raw_to_status is None:
            msg = (
                f"Pattern lifecycle payload missing required field 'to_status' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            from_status = EnumPatternLifecycleStatus(raw_from_status)
        except ValueError as e:
            msg = (
                f"Invalid lifecycle status for 'from_status': {raw_from_status!r} "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        try:
            to_status = EnumPatternLifecycleStatus(raw_to_status)
        except ValueError as e:
            msg = (
                f"Invalid lifecycle status for 'to_status': {raw_to_status!r} "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e
        trigger = payload.get("trigger", "dispatch")

        # Parse optional transition_at or default to now
        raw_transition_at = payload.get("transition_at")
        if raw_transition_at is not None:
            if isinstance(raw_transition_at, datetime):
                transition_at = raw_transition_at
            else:
                try:
                    transition_at = datetime.fromisoformat(str(raw_transition_at))
                except ValueError as e:
                    msg = (
                        f"Invalid ISO datetime for 'transition_at': "
                        f"{raw_transition_at!r} "
                        f"(correlation_id={ctx_correlation_id})"
                    )
                    logger.warning(msg)
                    raise ValueError(msg) from e
        else:
            transition_at = datetime.now(UTC)

        logger.info(
            "Dispatching pattern-lifecycle-transition via MessageDispatchEngine "
            "(pattern_id=%s, from=%s, to=%s, correlation_id=%s)",
            pattern_id,
            from_status,
            to_status,
            ctx_correlation_id,
        )

        result = await apply_transition(
            repository=repository,
            idempotency_store=idempotency_store,
            producer=kafka_producer,
            request_id=request_id,
            correlation_id=ctx_correlation_id,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
            actor=payload.get("actor", "dispatch"),
            reason=payload.get("reason"),
            gate_snapshot=payload.get("gate_snapshot"),
            transition_at=transition_at,
            publish_topic=publish_topic if kafka_producer else None,
        )

        logger.info(
            "Pattern lifecycle transition processed via dispatch engine "
            "(pattern_id=%s, success=%s, duplicate=%s, correlation_id=%s)",
            pattern_id,
            result.success,
            result.duplicate,
            ctx_correlation_id,
        )

        return ""

    return _handle


# =============================================================================
# Bridge Handler: Pattern Storage (pattern-learned + pattern.discovered)
# =============================================================================


def create_pattern_storage_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern storage events.

    Handles pattern-learned and pattern.discovered events by persisting
    patterns to the learned_patterns table via the repository adapter.

    For pattern-learned events: extracts pattern fields from the payload
    and inserts into learned_patterns using an upsert on
    (pattern_signature, domain_id, version).

    For pattern.discovered events: maps the discovery event payload to
    the same storage fields and inserts identically.

    Args:
        repository: REQUIRED database repository for pattern storage.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for pattern-stored events (from contract).
            Falls back to "onex.evt.omniintelligence.pattern-stored.v1" if None.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> pattern storage via repository."""
        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for pattern-storage (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Determine event type from payload
        event_type = payload.get("event_type", "")

        # Extract common fields for storage
        # Both pattern-learned and pattern.discovered share these fields
        raw_pattern_id = payload.get("pattern_id") or payload.get("discovery_id")
        if raw_pattern_id is not None:
            with contextlib.suppress(ValueError):
                raw_pattern_id = UUID(str(raw_pattern_id))
            if not isinstance(raw_pattern_id, UUID):
                logger.warning(
                    "Invalid UUID for pattern_id: %r, generating new ID "
                    "(correlation_id=%s)",
                    raw_pattern_id,
                    ctx_correlation_id,
                )
                raw_pattern_id = None

        pattern_id = raw_pattern_id or uuid4()
        signature = str(payload.get("signature", payload.get("pattern_signature", "")))
        signature_hash = str(payload.get("signature_hash", ""))
        domain_id = str(payload.get("domain_id", payload.get("domain", "general")))
        domain_version = str(payload.get("domain_version", "1.0.0"))
        try:
            raw_confidence = float(payload.get("confidence", 0.5))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid confidence value %r, defaulting to 0.5 "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                payload.get("confidence"),
                event_type,
                pattern_id,
                ctx_correlation_id,
            )
            raw_confidence = 0.5
        if raw_confidence < 0.5:
            logger.warning(
                "Pattern confidence %.3f below minimum 0.5, clamping "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                raw_confidence,
                event_type,
                pattern_id,
                ctx_correlation_id,
            )
        confidence = max(0.5, raw_confidence)
        try:
            version = int(payload.get("version", 1))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid version value %r, defaulting to 1 "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                payload.get("version"),
                event_type,
                pattern_id,
                ctx_correlation_id,
            )
            version = 1
        source_session_ids: list[UUID] = []
        raw_session_ids = payload.get("source_session_ids")
        if isinstance(raw_session_ids, list):
            for sid in raw_session_ids:
                with contextlib.suppress(ValueError):
                    source_session_ids.append(UUID(str(sid)))

        logger.info(
            "Processing pattern storage event via dispatch engine "
            "(event_type=%s, pattern_id=%s, domain_id=%s, correlation_id=%s)",
            event_type,
            pattern_id,
            domain_id,
            ctx_correlation_id,
        )

        # Reject if signature_hash is empty -- raise so the dispatch engine
        # nacks the message instead of silently acking on the empty-string path.
        if not signature_hash:
            msg = (
                f"Pattern storage event missing signature_hash, rejecting "
                f"(event_type={event_type}, pattern_id={pattern_id}, "
                f"correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        now = datetime.now(UTC)
        try:
            await repository.execute(
                _SQL_UPSERT_LEARNED_PATTERN,
                pattern_id,
                signature,
                signature_hash,
                domain_id,
                domain_version,
                confidence,
                version,
                source_session_ids,
            )
        except Exception as e:
            logger.error(
                "Failed to persist pattern via dispatch bridge "
                "(pattern_id=%s, error=%s, correlation_id=%s)",
                pattern_id,
                e,
                ctx_correlation_id,
            )
            raise

        logger.info(
            "Pattern stored via dispatch bridge "
            "(pattern_id=%s, domain_id=%s, version=%d, correlation_id=%s)",
            pattern_id,
            domain_id,
            version,
            ctx_correlation_id,
        )

        # Emit pattern-stored event to Kafka if producer available
        if kafka_producer is not None:
            try:
                await kafka_producer.publish(
                    topic=publish_topic
                    or "onex.evt.omniintelligence.pattern-stored.v1",
                    key=str(pattern_id),
                    value={
                        "event_type": "PatternStored",
                        "pattern_id": str(pattern_id),
                        "signature_hash": signature_hash,
                        "domain_id": domain_id,
                        "version": version,
                        "stored_at": now.isoformat(),
                        "correlation_id": str(ctx_correlation_id),
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to publish pattern-stored event to Kafka "
                    "(pattern_id=%s, correlation_id=%s)",
                    pattern_id,
                    ctx_correlation_id,
                    exc_info=True,
                )

        return ""

    return _handle


# SQL for upserting learned patterns via the dispatch bridge.
# Uses asyncpg positional parameters ($1...$8).
# ON CONFLICT skips duplicate (pattern_signature, domain_id, version) combinations.
_SQL_UPSERT_LEARNED_PATTERN = """\
INSERT INTO learned_patterns (
    id, pattern_signature, signature_hash, domain_id,
    domain_version, confidence, version,
    source_session_ids,
    status, is_current
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'candidate', TRUE)
ON CONFLICT (pattern_signature, domain_id, version)
DO NOTHING;
"""


# =============================================================================
# Dispatch Engine Factory
# =============================================================================


def create_intelligence_dispatch_engine(
    *,
    repository: ProtocolPatternRepository,
    idempotency_store: ProtocolIdempotencyStore,
    intent_classifier: ProtocolIntentClassifier,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topics: dict[str, str] | None = None,
) -> MessageDispatchEngine:
    """Create and configure a MessageDispatchEngine for Intelligence domain.

    Creates the engine, registers all 4 intelligence domain handlers (6 routes)
    and freezes it. The engine is ready for dispatch after this call.

    All required dependencies must be provided. If any are missing, the caller
    should not start consumers.

    Args:
        repository: REQUIRED database repository.
        idempotency_store: REQUIRED idempotency store.
        intent_classifier: REQUIRED intent classifier.
        kafka_producer: Optional Kafka publisher (graceful degradation).
        publish_topics: Optional mapping of handler name to publish topic.
            Keys: "claude_hook", "lifecycle", "pattern_storage". Values:
            full topic strings from contract event_bus.publish_topics.

    Returns:
        Frozen MessageDispatchEngine ready for dispatch.
    """
    topics = publish_topics or {}

    engine = MessageDispatchEngine(
        logger=logging.getLogger(f"{__name__}.dispatch_engine"),
    )

    # --- Handler 1: claude-hook-event ---
    claude_hook_handler = create_claude_hook_dispatch_handler(
        intent_classifier=intent_classifier,
        kafka_producer=kafka_producer,
        publish_topic=topics.get("claude_hook"),
    )
    engine.register_handler(
        handler_id="intelligence-claude-hook-handler",
        handler=claude_hook_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
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
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-tool-content-route",
            topic_pattern=DISPATCH_ALIAS_TOOL_CONTENT,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-claude-hook-handler",
            description=(
                "Routes tool-content commands to the intelligence handler "
                "(PostToolUse payloads with file/command content)."
            ),
        )
    )

    # --- Handler 2: session-outcome ---
    session_outcome_handler = create_session_outcome_dispatch_handler(
        repository=repository,
    )
    engine.register_handler(
        handler_id="intelligence-session-outcome-handler",
        handler=session_outcome_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-session-outcome-route",
            topic_pattern=DISPATCH_ALIAS_SESSION_OUTCOME,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-session-outcome-handler",
            description=(
                "Routes session-outcome commands to record_session_outcome handler."
            ),
        )
    )

    # --- Handler 3: pattern-lifecycle-transition ---
    pattern_lifecycle_handler = create_pattern_lifecycle_dispatch_handler(
        repository=repository,
        idempotency_store=idempotency_store,
        kafka_producer=kafka_producer,
        publish_topic=topics.get("lifecycle"),
    )
    engine.register_handler(
        handler_id="intelligence-pattern-lifecycle-handler",
        handler=pattern_lifecycle_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-pattern-lifecycle-route",
            topic_pattern=DISPATCH_ALIAS_PATTERN_LIFECYCLE,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-pattern-lifecycle-handler",
            description=(
                "Routes pattern-lifecycle-transition commands to apply_transition handler."
            ),
        )
    )

    # --- Handler 4: pattern-storage (pattern-learned + pattern.discovered) ---
    pattern_storage_handler = create_pattern_storage_dispatch_handler(
        repository=repository,
        kafka_producer=kafka_producer,
        publish_topic=topics.get("pattern_storage"),
    )
    engine.register_handler(
        handler_id="intelligence-pattern-storage-handler",
        handler=pattern_storage_handler,
        category=EnumMessageCategory.EVENT,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-pattern-learned-route",
            topic_pattern=DISPATCH_ALIAS_PATTERN_LEARNED,
            message_category=EnumMessageCategory.EVENT,
            handler_id="intelligence-pattern-storage-handler",
            description=("Routes pattern-learned events to pattern storage handler."),
        )
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-pattern-discovered-route",
            topic_pattern=DISPATCH_ALIAS_PATTERN_DISCOVERED,
            message_category=EnumMessageCategory.EVENT,
            handler_id="intelligence-pattern-storage-handler",
            description=(
                "Routes pattern.discovered events to pattern storage handler."
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
) -> Callable[[object], Awaitable[None]]:
    """Create an event bus callback that routes messages through the dispatch engine.

    The callback:
    1. Deserializes the raw message value from bytes to dict
    2. Wraps it in a ModelEventEnvelope with category derived from dispatch_topic
    3. Calls engine.dispatch() with the dispatch-compatible topic alias
    4. Acks the message on success, nacks on failure

    Args:
        engine: Frozen MessageDispatchEngine.
        dispatch_topic: Dispatch-compatible topic alias to pass to dispatch().
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async callback compatible with event bus subscribe(on_message=...).
    """

    async def _on_message(msg: object) -> None:
        """Event bus callback: raw message -> dispatch engine."""
        msg_correlation_id = correlation_id or uuid4()

        try:
            # Extract raw value from message
            if hasattr(msg, "value"):
                raw_value = msg.value
                if isinstance(raw_value, bytes | bytearray):
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

            # Derive message category from dispatch_topic so EVENT topics
            # produce EVENT envelopes (not hard-coded COMMAND).
            topic_category = EnumMessageCategory.from_topic(dispatch_topic)
            envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
                payload=payload_dict,
                correlation_id=msg_correlation_id,
                metadata=ModelEnvelopeMetadata(
                    tags={
                        "message_category": topic_category.value
                        if topic_category
                        else "command",
                    },
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
    "DISPATCH_ALIAS_PATTERN_DISCOVERED",
    "DISPATCH_ALIAS_PATTERN_LEARNED",
    "DISPATCH_ALIAS_PATTERN_LIFECYCLE",
    "DISPATCH_ALIAS_SESSION_OUTCOME",
    "DISPATCH_ALIAS_TOOL_CONTENT",
    "create_claude_hook_dispatch_handler",
    "create_dispatch_callback",
    "create_intelligence_dispatch_engine",
    "create_pattern_lifecycle_dispatch_handler",
    "create_pattern_storage_dispatch_handler",
    "create_session_outcome_dispatch_handler",
]
