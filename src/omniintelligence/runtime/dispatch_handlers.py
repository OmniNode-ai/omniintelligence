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
    - OMN-2032: Register intelligence dispatchers (now 6 handlers, 8 routes)
    - OMN-934: MessageDispatchEngine implementation
    - OMN-2339: Add node_compliance_evaluate_effect and its dispatcher
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
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
from pydantic import ValidationError

from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# =============================================================================
# Dependency Protocols (structural typing for dispatch handler deps)
# =============================================================================
# All protocols imported from the canonical location (omniintelligence.protocols).
# No circular import risk: handler modules (handler_transition.py,
# handler_claude_event.py) do not import from this module. The handler imports
# in this file are deferred (inside function bodies) to further ensure safety.

from omniintelligence.protocols import (
    ProtocolIdempotencyStore,
    ProtocolIntentClassifier,
    ProtocolKafkaPublisher,
    ProtocolPatternQueryStore,
    ProtocolPatternRepository,
    ProtocolPatternUpsertStore,
)

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

DISPATCH_ALIAS_PATTERN_LEARNING_CMD = (
    "onex.commands.omniintelligence.pattern-learning.v1"
)
"""Dispatch-compatible alias for pattern-learning canonical topic."""

DISPATCH_ALIAS_COMPLIANCE_EVALUATE = (
    "onex.commands.omniintelligence.compliance-evaluate.v1"
)
"""Dispatch-compatible alias for compliance-evaluate canonical topic (OMN-2339)."""

DISPATCH_ALIAS_PATTERN_PROMOTED = "onex.events.omniintelligence.pattern-promoted.v1"
"""Dispatch-compatible alias for pattern-promoted canonical topic (OMN-2424)."""

DISPATCH_ALIAS_PATTERN_DEPRECATED = "onex.events.omniintelligence.pattern-deprecated.v1"
"""Dispatch-compatible alias for pattern-deprecated canonical topic (OMN-2424)."""

DISPATCH_ALIAS_PATTERN_LIFECYCLE_TRANSITIONED = (
    "onex.events.omniintelligence.pattern-lifecycle-transitioned.v1"
)
"""Dispatch-compatible alias for pattern-lifecycle-transitioned canonical topic (OMN-2424)."""

_FALLBACK_TOPIC_PATTERN_STORED = "onex.evt.omniintelligence.pattern-stored.v1"
"""Fallback publish topic when contract-resolved topic is unavailable."""


# =============================================================================
# Daemon Envelope Constants
# =============================================================================

_DAEMON_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {
        "event_type",
        "session_id",
        "correlation_id",
        "emitted_at",
        "causation_id",
        "schema_version",
        "_envelope_reconstructed",
    }
)
"""Keys belonging to the daemon envelope layer.

Used by ``_reshape_daemon_hook_payload_v1`` to split envelope keys from
domain-specific payload keys.  Defined as a module-level frozenset to
avoid reconstructing the set on every call.
"""

_REQUIRED_ENVELOPE_KEYS: tuple[str, ...] = (
    "emitted_at",
    "event_type",
    "session_id",
    "correlation_id",
)
"""Daemon envelope keys used for reshape detection and envelope reconstruction.

Used by:
- ``_needs_daemon_reshape`` to detect whether a payload is a flat daemon dict
- ``_reconstruct_payload_from_envelope`` to recover keys absorbed by the envelope layer

As of OMN-2423, only ``event_type`` is hard-required in
``_reshape_daemon_hook_payload_v1``.  The other three keys
(``emitted_at``, ``session_id``, ``correlation_id``) use structured
fallbacks when absent or null.  Defined as a module-level tuple to
avoid reconstructing on every call.
"""

_MAX_DIAGNOSTIC_KEYS: int = 10
"""Maximum number of payload keys to include in error messages.

Defence-in-depth measure: future payloads may carry sensitive domain keys.
Diagnostic messages truncate the key list to this limit and append an
ellipsis indicator when truncated.
"""


def _diagnostic_key_summary(raw: dict[str, Any]) -> str:
    """Return a bounded, sorted key summary for diagnostic error messages.

    Produces a string like ``"(keys=['a', 'b', 'c'])"`` or
    ``"(keys=['a', 'b', '...'])"`` when the key count exceeds
    ``_MAX_DIAGNOSTIC_KEYS``.
    """
    all_keys = sorted(raw.keys())
    diagnostic_keys = all_keys[:_MAX_DIAGNOSTIC_KEYS]
    if len(all_keys) > _MAX_DIAGNOSTIC_KEYS:
        diagnostic_keys.append("...")
    return f"(keys={diagnostic_keys})"


# Sentinel strings raised by reshape/parse failure paths in
# create_claude_hook_dispatch_handler.  Used by _is_permanent_dispatch_failure
# to classify a dispatch result error as a permanent (structural) failure that
# should be ACK'd rather than NACK'd.  Must match substrings of the
# raise ValueError(msg) message string, which propagates through the dispatch
# engine into result.error_message.
#
# "for claude-hook-event" is intentionally specific to the claude-hook handler.
# Other handlers (session-outcome, pattern-lifecycle-transition, pattern-storage,
# compliance-evaluate) also raise ValueError("Unexpected payload type ... for
# <handler-name> ...") but those are NOT permanent failures -- the dispatch
# engine should NACK them so they can be retried.
_PERMANENT_FAILURE_MARKERS: tuple[str, ...] = (
    "Permanent reshape failure",
    "Failed to parse payload as ModelClaudeCodeHookEvent",
    "for claude-hook-event",
    "Daemon payload missing required key 'event_type'",
)
"""Substrings in dispatch result error messages that indicate a permanent failure.

A permanent failure is one that will not be resolved by retrying the message.
Structural reshape errors (missing required routing fields, wrong payload type)
fall into this category.  Transient failures (DB errors, network issues) do not.

Used by ``create_dispatch_callback`` to decide whether to ACK or NACK a failed
message (GAP-9, OMN-2423).
"""


def _is_permanent_dispatch_failure(error_msg: str) -> bool:
    """Return True if the dispatch error message indicates a permanent failure.

    Permanent failures are structural parse/reshape errors that cannot be
    resolved by retrying.  They should be ACK'd with an ERROR log instead of
    NACK'd, to prevent infinite NACK loops.

    Args:
        error_msg: The ``error_message`` from a failed ``ModelDispatchResult``.

    Returns:
        True if any ``_PERMANENT_FAILURE_MARKERS`` substring is present.
    """
    return any(marker in error_msg for marker in _PERMANENT_FAILURE_MARKERS)


# =============================================================================
# Bridge Handler: Claude Hook Event
# =============================================================================

# Top-level fields that belong in ModelClaudeCodeHookEvent directly.
# Everything else is wrapped into the nested `payload` dict.
_HOOK_EVENT_TOP_LEVEL_FIELDS = {
    "event_type",
    "session_id",
    "correlation_id",
    "timestamp_utc",
}

_TOOL_CONTENT_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {"session_id", "correlation_id", "timestamp"}
)
"""Keys belonging to the tool-content envelope layer.

Used by ``_reshape_tool_content_to_hook_event`` to split envelope keys from
tool-content payload keys when building the nested payload dict.  Defined as
a module-level frozenset to avoid reconstructing the set on every call.
"""


def _reshape_flat_hook_payload(flat: dict[str, object]) -> ModelClaudeCodeHookEvent:
    """Reshape a flat omniclaude publisher payload into ModelClaudeCodeHookEvent.

    The omniclaude publisher emits events with all fields at the top level:
        {event_type, session_id, correlation_id, emitted_at, prompt_preview, ...}

    ModelClaudeCodeHookEvent expects a nested envelope:
        {event_type, session_id, correlation_id, timestamp_utc, payload: {...}}

    This function maps between the two formats.
    """
    envelope: dict[str, object] = {}
    nested_payload: dict[str, object] = {}

    for key, value in flat.items():
        if key in _HOOK_EVENT_TOP_LEVEL_FIELDS:
            envelope[key] = value
        elif key == "emitted_at":
            # Map emitted_at -> timestamp_utc, but only if an explicit
            # timestamp_utc was not already provided (explicit takes priority).
            if "timestamp_utc" not in envelope:
                envelope["timestamp_utc"] = value
        else:
            nested_payload[key] = value

    envelope["payload"] = nested_payload

    return ModelClaudeCodeHookEvent(**envelope)  # type: ignore[arg-type]


def _needs_daemon_reshape(payload: dict[str, Any]) -> bool:
    """Return True if the payload is a flat daemon dict that needs reshaping.

    The emit daemon sends a flat dict with ``emitted_at`` as its timestamp
    key, while the canonical ``ModelClaudeCodeHookEvent`` shape uses
    ``timestamp_utc``.  When ``emitted_at`` is present and ``timestamp_utc``
    is absent, the payload is treated as a flat daemon payload that must
    be reshaped.

    When **both** keys are present, the payload is treated as canonical
    (already shaped) and no reshape is needed.  See inline comment in
    ``create_claude_hook_dispatch_handler`` for the ambiguity note.
    """
    return "emitted_at" in payload and "timestamp_utc" not in payload


def _is_tool_content_payload(payload: dict[str, Any]) -> bool:
    """Return True if the payload is a ``ModelToolExecutionContent`` dict.

    Tool-content payloads arrive on the ``tool-content`` topic with fields
    like ``tool_name_raw`` and ``tool_name`` but **without** ``event_type``
    or ``timestamp_utc`` (which are ``ModelClaudeCodeHookEvent`` envelope
    fields).  This distinguishes them from both daemon flat payloads
    (which have ``emitted_at``) and canonical hook events (which have
    ``event_type``).
    """
    return "tool_name_raw" in payload and "event_type" not in payload


def _reshape_tool_content_to_hook_event(
    payload: dict[str, Any],
    envelope: ModelEventEnvelope[object],
) -> ModelClaudeCodeHookEvent:
    """Reshape a ``ModelToolExecutionContent`` dict into ``ModelClaudeCodeHookEvent``.

    Tool-content payloads are flat dicts from the ``tool-content`` topic that
    represent PostToolUse events with file/command content.  This function
    wraps them in the ``ModelClaudeCodeHookEvent`` envelope structure.

    The ``session_id`` and ``correlation_id`` fields are extracted from the
    payload (where ``ModelToolExecutionContent`` includes them as optional
    string fields).  The ``timestamp`` field is mapped to ``timestamp_utc``.
    All remaining tool-content fields become the nested payload.

    Args:
        payload: Flat dict from ``ModelToolExecutionContent.model_dump()``.
        envelope: The ``ModelEventEnvelope`` wrapping this message (used as
            fallback for ``correlation_id`` and ``timestamp``).

    Returns:
        A fully constructed ``ModelClaudeCodeHookEvent`` with
        ``event_type="PostToolUse"`` and nested payload.
    """
    # Extract envelope-level fields from the tool-content payload.
    # Use "unknown" only when session_id is missing (None), not when it's
    # explicitly set to empty string (which should be preserved).
    session_id_raw = payload.get("session_id")
    session_id: str = str(session_id_raw) if session_id_raw is not None else "unknown"

    # Correlation ID: prefer payload string, fall back to envelope UUID.
    corr_id: UUID | None = None
    raw_corr = payload.get("correlation_id")
    if raw_corr:
        try:
            corr_id = UUID(str(raw_corr))
        except ValueError:
            logger.warning(
                "tool-content payload has invalid 'correlation_id' %r; "
                "falling back to envelope correlation_id",
                raw_corr,
            )
    if corr_id is None and envelope.correlation_id is not None:
        corr_id = (
            envelope.correlation_id
            if isinstance(envelope.correlation_id, UUID)
            else UUID(str(envelope.correlation_id))
        )

    # Timestamp: prefer payload.timestamp, fall back to envelope timestamp.
    timestamp_raw = payload.get("timestamp")
    if timestamp_raw is not None:
        if isinstance(timestamp_raw, str):
            timestamp_utc = datetime.fromisoformat(timestamp_raw)
        elif isinstance(timestamp_raw, datetime):
            timestamp_utc = timestamp_raw
        else:
            timestamp_utc = datetime.now(UTC)
    else:
        timestamp_utc = envelope.envelope_timestamp

    # Ensure timezone-aware (ModelClaudeCodeHookEvent validates this).
    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=UTC)

    # Build nested payload: all fields except the ones extracted above.
    nested = {k: v for k, v in payload.items() if k not in _TOOL_CONTENT_ENVELOPE_KEYS}

    return ModelClaudeCodeHookEvent(
        event_type="PostToolUse",  # type: ignore[arg-type]
        session_id=session_id,
        correlation_id=corr_id,
        timestamp_utc=timestamp_utc,
        payload=ModelClaudeCodeHookEventPayload(**nested),
    )


def _reconstruct_payload_from_envelope(
    payload: dict[str, Any],
    envelope: ModelEventEnvelope[object],
) -> dict[str, Any]:
    """Reconstruct daemon keys stripped by envelope deserialization.

    When the Kafka consumer deserializes a flat daemon dict into a
    ``ModelEventEnvelope``, envelope-level keys (``event_type``,
    ``correlation_id``) are absorbed into the envelope object and removed
    from ``envelope.payload``.  The daemon keys ``session_id`` and
    ``emitted_at`` are not envelope fields, so they are silently discarded
    by Pydantic's default ``extra="ignore"`` policy.

    This function detects the stripped-envelope scenario and reconstructs
    the full flat dict by merging envelope fields back into the payload.
    It only fires when the payload is missing *all four* required daemon
    keys, which is the signature of envelope-level key absorption.

    If any of the four daemon keys are already present in the payload,
    the payload is returned unchanged (it was not stripped).

    Args:
        payload: The dict from ``envelope.payload`` (potentially stripped).
        envelope: The ``ModelEventEnvelope`` that may hold absorbed keys.

    Returns:
        A new dict with daemon keys restored from the envelope, or the
        original payload if reconstruction was not needed.
    """
    # Quick check: if the payload already has any of the four required
    # daemon keys, it was not stripped -- return as-is.
    if any(k in payload for k in _REQUIRED_ENVELOPE_KEYS):
        return payload

    # The payload is missing all required daemon keys.  Attempt to
    # recover them from the envelope's own fields.
    logger.debug(
        "Envelope reconstruction triggered: payload missing all required "
        "daemon keys %s, recovering from envelope fields %s",
        _REQUIRED_ENVELOPE_KEYS,
        _diagnostic_key_summary(payload),
    )
    reconstructed = dict(payload)

    # event_type: ModelEventEnvelope stores event_type as a direct top-level field.
    if envelope.event_type is not None:
        reconstructed["event_type"] = str(envelope.event_type)

    # correlation_id: envelope.correlation_id is UUID | None
    if envelope.correlation_id is not None:
        reconstructed["correlation_id"] = str(envelope.correlation_id)

    # emitted_at: envelope.envelope_timestamp is always set (default factory).
    # Use ISO format string so Pydantic can parse it downstream.
    # NOTE: envelope_timestamp defaults to deserialization time, not the
    # original daemon emission time, so this value is approximate.
    logger.debug(
        "emitted_at falling back to envelope_timestamp (approximate): %s",
        envelope.envelope_timestamp.isoformat(),
    )
    reconstructed["emitted_at"] = envelope.envelope_timestamp.isoformat()

    # session_id: ModelEventEnvelope has no session_id field, so it cannot
    # be recovered from the envelope.  However, Kafka message headers or
    # the envelope metadata tags may carry it.  Check metadata tags first.
    if "session_id" not in reconstructed:
        meta_session = envelope.get_metadata_value("session_id")
        if meta_session is not None:
            reconstructed["session_id"] = str(meta_session)
        else:
            logger.warning(
                "session_id could not be recovered from envelope metadata "
                "during payload reconstruction; it will be missing from the "
                "reconstructed payload. This is caused by envelope "
                "deserialization stripping daemon keys that have no "
                "corresponding envelope field. %s",
                _diagnostic_key_summary(reconstructed),
            )

    # Mark the payload so downstream handlers can distinguish an
    # approximate reconstructed payload from an accurate original one.
    reconstructed["_envelope_reconstructed"] = True

    # Guard: if event_type could not be recovered (envelope had None),
    # the reconstructed dict is missing the critical routing field.
    # Return the ORIGINAL payload unchanged so downstream handlers
    # see the raw payload and fail with a clearer error path instead
    # of a confusing reshape error on a half-reconstructed dict.
    if "event_type" not in reconstructed:
        logger.warning(
            "Envelope reconstruction could not recover the critical "
            "'event_type' routing field; returning original payload "
            "unchanged to avoid confusing reshape errors. %s",
            _diagnostic_key_summary(payload),
        )
        return payload

    return reconstructed


def _reshape_daemon_hook_payload_v1(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform a flat daemon payload into ``ModelClaudeCodeHookEvent`` shape.

    The emit daemon sends a flat dict with envelope keys (``event_type``,
    ``session_id``, ``correlation_id``, ``emitted_at``, …) mixed alongside
    domain-specific payload keys.  ``ModelClaudeCodeHookEvent`` expects a
    nested ``payload`` sub-dict, so this function splits envelope keys from
    payload keys and returns the canonical shape.

    This function applies structured fallbacks for optional envelope fields
    rather than raising ``ValueError`` for missing or null values.  Only
    ``event_type`` is truly required — its absence means the message cannot
    be routed and is a permanent failure.  All other envelope fields have
    safe fallbacks to prevent NACK loops:

    - ``emitted_at`` missing or null: falls back to ``datetime.now(UTC)``
    - ``session_id`` missing or null: falls back to ``"unknown"``
    - ``correlation_id`` missing or null: generates a new ``uuid4()``

    Args:
        raw: Flat dict as emitted by the daemon.

    Returns:
        Dict matching ``ModelClaudeCodeHookEvent`` constructor kwargs::

            {
                "event_type": ...,
                "session_id": ...,
                "correlation_id": ...,
                "timestamp_utc": ...,   # from ``emitted_at``
                "payload": { ... },     # remaining keys
            }

    Raises:
        ValueError: Only if ``event_type`` is absent or null.  All other
            missing fields are filled with safe fallback values.
    """
    # --- event_type is the only truly required key ---
    # Without event_type, the message cannot be routed.  This is a
    # permanent failure: raise ValueError so the dispatch layer can
    # discard-and-log (ACK) rather than NACK into an infinite loop.
    if "event_type" not in raw or raw.get("event_type") is None:
        raise ValueError(
            f"Daemon payload missing required key 'event_type' "
            f"{_diagnostic_key_summary(raw)}"
        )
    event_type = raw["event_type"]

    # --- emitted_at: fall back to UTC now if missing or null ---
    raw_emitted_at = raw.get("emitted_at")
    if raw_emitted_at is None:
        logger.warning(
            "Daemon payload missing 'emitted_at'; using UTC now as fallback %s",
            _diagnostic_key_summary(raw),
        )
        emitted_at: str = datetime.now(UTC).isoformat()
    else:
        emitted_at = raw_emitted_at

    # --- session_id: fall back to "unknown" if missing or null ---
    raw_session_id = raw.get("session_id")
    if raw_session_id is None:
        logger.warning(
            "Daemon payload missing 'session_id'; using 'unknown' as fallback %s",
            _diagnostic_key_summary(raw),
        )
        session_id = "unknown"
    else:
        session_id = raw_session_id

    # --- correlation_id: generate uuid4() if missing or null ---
    raw_correlation_id = raw.get("correlation_id")
    if raw_correlation_id is None:
        generated_id = str(uuid4())
        logger.warning(
            "Daemon payload missing 'correlation_id'; generated fallback '%s' %s",
            generated_id,
            _diagnostic_key_summary(raw),
        )
        correlation_id_value: str = generated_id
    else:
        correlation_id_value = raw_correlation_id

    # --- collect remaining keys into payload sub-dict ---
    # Note: causation_id and schema_version are intentionally discarded here.
    # They belong to the daemon envelope layer and are not forwarded to the
    # reshaped output consumed by ModelClaudeCodeHookEvent.
    payload_fields = {k: v for k, v in raw.items() if k not in _DAEMON_ENVELOPE_KEYS}

    return {
        "event_type": event_type,
        "session_id": session_id,
        "correlation_id": correlation_id_value,
        "timestamp_utc": emitted_at,  # Pydantic parses ISO string -> datetime
        "payload": payload_fields,
    }


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

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        # Parse payload into ModelClaudeCodeHookEvent
        if isinstance(payload, ModelClaudeCodeHookEvent):
            event = payload
        elif isinstance(payload, dict):
            try:
                # OMN-2322: Reconstruct daemon keys that were stripped by
                # envelope deserialization.  When the Kafka consumer parses
                # a flat daemon dict as ModelEventEnvelope, envelope-level
                # keys (event_type, correlation_id) are absorbed into the
                # envelope object and removed from envelope.payload.  This
                # causes _needs_daemon_reshape() to return False because
                # emitted_at is no longer in the payload.  Reconstructing
                # the payload from the envelope restores those keys so
                # downstream reshape/parsing succeeds.
                payload = _reconstruct_payload_from_envelope(payload, envelope)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Claude hook payload keys before reshape: %s (correlation_id=%s)",
                        _diagnostic_key_summary(payload),
                        ctx_correlation_id,
                    )
                # Detect payload format: flat daemon (has emitted_at) vs
                # canonical (has timestamp_utc + nested payload dict).
                # NOTE: If a payload contains BOTH "emitted_at" and
                # "timestamp_utc", we treat it as canonical (no reshape).
                # This is ambiguous -- such a payload could be a daemon
                # message that happens to include "timestamp_utc" as a
                # domain key.  In practice this has not occurred; if it
                # does, Pydantic validation will surface the mismatch.
                #
                # Detection order matters: daemon reshape check runs first
                # because _reconstruct_payload_from_envelope may inject
                # emitted_at into payloads, which would match
                # _needs_daemon_reshape. Tool-content payloads lack
                # daemon-specific keys (session_id, hook_type) so they
                # won't false-match the daemon reshape path.
                if _needs_daemon_reshape(payload):
                    logger.debug(
                        "Applying daemon reshape strategy for claude-hook-event "
                        "(correlation_id=%s) %s",
                        ctx_correlation_id,
                        _diagnostic_key_summary(payload),
                    )
                    parsed = _reshape_daemon_hook_payload_v1(payload)
                    event = ModelClaudeCodeHookEvent(**parsed)
                elif _is_tool_content_payload(payload):
                    logger.debug(
                        "Applying tool-content reshape strategy for claude-hook-event "
                        "(correlation_id=%s) %s",
                        ctx_correlation_id,
                        _diagnostic_key_summary(payload),
                    )
                    event = _reshape_tool_content_to_hook_event(payload, envelope)
                else:
                    logger.debug(
                        "Applying canonical parse strategy for claude-hook-event "
                        "(correlation_id=%s) %s",
                        ctx_correlation_id,
                        _diagnostic_key_summary(payload),
                    )
                    event = ModelClaudeCodeHookEvent(**payload)
            except ValueError as e:
                if isinstance(e, ValidationError):
                    # Pydantic model validation error -- wrap with
                    # correlation context so the error is traceable in logs.
                    # Without this, ValidationError (a ValueError subclass)
                    # would propagate without the correlation_id annotation.
                    sanitized = get_log_sanitizer().sanitize(str(e))
                    msg = (
                        f"Failed to parse payload as ModelClaudeCodeHookEvent: {sanitized} "
                        f"(correlation_id={ctx_correlation_id})"
                    )
                    logger.error(
                        "Permanent reshape failure (validation error), message will be "
                        "discarded to prevent NACK loop: %s %s",
                        msg,
                        _diagnostic_key_summary(payload)
                        if isinstance(payload, dict)
                        else f"(payload_type={type(payload).__name__})",
                    )
                    raise ValueError(msg) from e
                # Reshape validation errors (from _reshape_daemon_hook_payload_v1)
                # already carry structured diagnostic context.  Log full raw
                # payload at ERROR level (sanitized) before re-raising so the
                # dispatch layer can discard-and-log (ACK) instead of NACKing.
                sanitized_err = get_log_sanitizer().sanitize(str(e))
                logger.error(
                    "Permanent reshape failure for claude-hook-event, message will be "
                    "discarded to prevent NACK loop (error=%s, correlation_id=%s) %s",
                    sanitized_err,
                    ctx_correlation_id,
                    _diagnostic_key_summary(payload)
                    if isinstance(payload, dict)
                    else f"(payload_type={type(payload).__name__})",
                )
                raise
            except Exception as e:
                sanitized_exc = get_log_sanitizer().sanitize(str(e))
                msg = (
                    f"Failed to parse payload as ModelClaudeCodeHookEvent: {sanitized_exc} "
                    f"(correlation_id={ctx_correlation_id})"
                )
                logger.error(
                    "Permanent reshape failure (unexpected error), message will be "
                    "discarded to prevent NACK loop: %s %s",
                    msg,
                    _diagnostic_key_summary(payload)
                    if isinstance(payload, dict)
                    else f"(payload_type={type(payload).__name__})",
                )
                raise ValueError(msg) from e
        else:
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for claude-hook-event (correlation_id={ctx_correlation_id})"
            )
            logger.error(
                "Permanent dispatch failure (unexpected payload type), message will be "
                "discarded to prevent NACK loop: %s",
                msg,
            )
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

        return "ok"

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
        failure_reason = str(failure_reason) if failure_reason is not None else None

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

        return "ok"

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
        trigger = str(payload.get("trigger", "dispatch"))

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
            actor=str(payload.get("actor", "dispatch")),
            reason=str(_reason)
            if (_reason := payload.get("reason")) is not None
            else None,
            # gate_snapshot contract: apply_transition accepts
            # ModelGateSnapshot | dict[str, object] | None.  Payload
            # deserialization always yields dict | None here.
            gate_snapshot=_gate
            if isinstance((_gate := payload.get("gate_snapshot")), dict)
            else None,
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

        return "ok"

    return _handle


# =============================================================================
# Bridge Handler: Pattern Storage (pattern-learned + pattern.discovered)
# =============================================================================


def create_pattern_storage_dispatch_handler(
    *,
    pattern_upsert_store: ProtocolPatternUpsertStore,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern storage events.

    Handles pattern-learned and pattern.discovered events by persisting
    patterns via the pattern upsert store (contract-driven, behind effect
    boundary).

    Args:
        pattern_upsert_store: REQUIRED store for idempotent pattern storage.
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
        """Bridge handler: envelope -> pattern storage via upsert store."""
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
        raw_pattern_id = payload.get("pattern_id")
        if raw_pattern_id is None:
            raw_pattern_id = payload.get("discovery_id")
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
        # Prefer 'signature' (omniclaude producers) over 'pattern_signature' (DB column name).
        # Bound untrusted input to 4096 chars to prevent oversized payloads.
        signature = str(payload.get("signature", payload.get("pattern_signature", "")))[
            :4096
        ]

        if not signature:
            msg = (
                f"Pattern storage event missing pattern_signature, rejecting "
                f"(event_type={event_type}, pattern_id={pattern_id}, "
                f"correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        signature_hash = str(payload.get("signature_hash", ""))
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
        # Default 'general' must exist in domain_taxonomy (FK constraint).
        # Bound untrusted input to 128 chars to prevent oversized payloads.
        domain_id = str(payload.get("domain_id", payload.get("domain", "general")))[
            :128
        ]
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
        # extra field for structured logging backends (JSON/ELK); the positional
        # arg renders in human-readable format, extra survives for machine parsing.
        if raw_confidence < 0.5:
            logger.warning(
                "Pattern confidence %.3f below minimum 0.5, clamping to 0.5 "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                raw_confidence,
                event_type,
                pattern_id,
                ctx_correlation_id,
                extra={"original_confidence": raw_confidence},
            )
        if raw_confidence > 1.0:
            logger.warning(
                "Pattern confidence %.3f above maximum 1.0, clamping to 1.0 "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                raw_confidence,
                event_type,
                pattern_id,
                ctx_correlation_id,
                extra={"original_confidence": raw_confidence},
            )
        confidence = max(0.5, min(1.0, raw_confidence))
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
        if version < 1:
            logger.warning(
                "Pattern version %d below minimum 1, clamping "
                "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                version,
                event_type,
                pattern_id,
                ctx_correlation_id,
            )
            version = max(1, version)
        source_session_ids: list[UUID] = []
        raw_session_ids = payload.get("source_session_ids")
        if isinstance(raw_session_ids, list):
            for sid in raw_session_ids:
                with contextlib.suppress(ValueError):
                    source_session_ids.append(UUID(str(sid)))
            dropped_count = len(raw_session_ids) - len(source_session_ids)
            if dropped_count > 0:
                logger.warning(
                    "Dropped %d invalid session IDs from source_session_ids "
                    "(event_type=%s, pattern_id=%s, correlation_id=%s)",
                    dropped_count,
                    event_type,
                    pattern_id,
                    ctx_correlation_id,
                )

        logger.info(
            "Processing pattern storage event via dispatch engine "
            "(event_type=%s, pattern_id=%s, domain_id=%s, correlation_id=%s)",
            event_type,
            pattern_id,
            domain_id,
            ctx_correlation_id,
        )

        try:
            stored_id = await pattern_upsert_store.upsert_pattern(
                pattern_id=pattern_id,
                signature=signature,
                signature_hash=signature_hash,
                domain_id=domain_id,
                domain_version=domain_version,
                confidence=confidence,
                version=version,
                source_session_ids=source_session_ids,
            )
        except Exception as e:
            # Catch DB-specific errors (FK violations, unique constraint)
            # that propagate through the effect boundary as generic exceptions.
            # Check for sqlstate attribute (DB errors) without importing driver.
            if hasattr(e, "sqlstate"):
                sqlstate = getattr(e, "sqlstate", "")
                # 23503 = foreign_key_violation
                if sqlstate == "23503":
                    msg = (
                        f"Unknown domain_id {domain_id!r} not found in domain_taxonomy "
                        f"(pattern_id={pattern_id}, correlation_id={ctx_correlation_id}). "
                        f"Ensure the domain is registered before publishing pattern events."
                    )
                    logger.error(msg)
                    raise ValueError(msg) from e
                # 23505 = unique_violation
                if sqlstate == "23505":
                    logger.warning(
                        "Duplicate pattern skipped due to unique constraint "
                        "(pattern_id=%s, signature_hash=%s, domain_id=%s, version=%d, "
                        "correlation_id=%s): %s",
                        pattern_id,
                        signature_hash,
                        domain_id,
                        version,
                        ctx_correlation_id,
                        get_log_sanitizer().sanitize(str(e)),
                    )
                    return "ok"
            logger.error(
                "Failed to persist pattern via dispatch bridge "
                "(pattern_id=%s, error=%s, correlation_id=%s)",
                pattern_id,
                get_log_sanitizer().sanitize(str(e)),
                ctx_correlation_id,
            )
            raise

        # ON CONFLICT DO NOTHING: stored_id is None when duplicate
        if stored_id is None:
            logger.debug(
                "Duplicate pattern skipped by ON CONFLICT DO NOTHING "
                "(pattern_signature=%s, domain_id=%s, version=%d, "
                "correlation_id=%s)",
                signature,
                domain_id,
                version,
                ctx_correlation_id,
            )
            return "ok"

        now = datetime.now(UTC)

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
                    topic=publish_topic or _FALLBACK_TOPIC_PATTERN_STORED,
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

        return "ok"

    return _handle


# =============================================================================
# Bridge Handler: Compliance Evaluate (OMN-2339)
# =============================================================================


def create_compliance_evaluate_dispatch_handler(
    *,
    llm_client: ProtocolLlmClient | None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for compliance-evaluate commands.

    Deserializes the Kafka payload into ModelComplianceEvaluateCommand,
    delegates to handle_compliance_evaluate_command(), and returns "ok".

    Args:
        llm_client: Optional LLM client (ProtocolLlmClient) for Coder-14B inference.
            When None, evaluation is skipped and a structured ``llm_error`` result
            is returned without calling the LLM.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for compliance-evaluated events (from contract).
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.

    Related:
        OMN-2339: node_compliance_evaluate_effect

    Note:
        # DEFERRED (OMN-2339): Idempotency declared in contract.yaml (strategy:
        # content_hash_tracking, key: source_path + content_sha256 + pattern_id) is
        # intentionally NOT wired here. The idempotency_store infrastructure is not
        # available in this handler factory's current scope. Duplicate commands will
        # trigger redundant LLM calls until this is addressed. Tracked in OMN-2339.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> handle_compliance_evaluate_command()."""
        # Deferred import to avoid circular dependency at module load time.
        from omniintelligence.nodes.node_compliance_evaluate_effect.handlers import (
            handle_compliance_evaluate_command,
        )
        from omniintelligence.nodes.node_compliance_evaluate_effect.models import (
            ModelComplianceEvaluateCommand,
        )

        _raw_ctx_id = correlation_id or getattr(context, "correlation_id", None)
        if isinstance(_raw_ctx_id, UUID):
            ctx_correlation_id: UUID = _raw_ctx_id
        elif _raw_ctx_id is not None:
            try:
                ctx_correlation_id = UUID(str(_raw_ctx_id))
            except (ValueError, AttributeError):
                ctx_correlation_id = uuid4()
        else:
            ctx_correlation_id = uuid4()

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for compliance-evaluate (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            command = ModelComplianceEvaluateCommand(**payload)
        except Exception as e:
            sanitized = get_log_sanitizer().sanitize(str(e))
            msg = (
                f"Failed to parse payload as ModelComplianceEvaluateCommand: "
                f"{sanitized} (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        # Guard: llm_client is required for compliance evaluation.
        # When None, return a structured error event rather than propagating
        # an AttributeError from the leaf handler. This matches the documented
        # behaviour ("will return LLM-error results when llm_client=None").
        # NOTE: This path does not route to DLQ; the leaf-level guard in
        # _execute_compliance handles DLQ routing on direct calls.
        # Duplicates leaf-level error event shape intentionally — the dispatch layer
        # short-circuits before calling handle_compliance_evaluate_command to avoid
        # the LLM call overhead. Update both sites if the error response schema changes.
        safe_source_path = get_log_sanitizer().sanitize(command.source_path)
        if llm_client is None:
            from omniintelligence.nodes.node_compliance_evaluate_effect.models.model_compliance_evaluated_event import (
                ModelComplianceEvaluatedEvent,
            )

            logger.warning(
                "compliance-evaluate command received but llm_client=None; "
                "returning llm_error result without inference "
                "(source_path=%s, correlation_id=%s)",
                safe_source_path,
                ctx_correlation_id,
            )
            result = ModelComplianceEvaluatedEvent(  # result flows through to shared post-dispatch logging below
                event_type="ComplianceEvaluated",
                correlation_id=command.correlation_id,
                source_path=safe_source_path,
                content_sha256=command.content_sha256,
                language=command.language,
                success=False,
                compliant=False,
                violations=[],
                confidence=0.0,
                patterns_checked=len(command.applicable_patterns),
                model_used=None,
                status="llm_error",
                processing_time_ms=0.0,
                evaluated_at=datetime.now(UTC).isoformat(),
                session_id=command.session_id,
            )
        else:
            logger.info(
                "Dispatching compliance-evaluate command via MessageDispatchEngine "
                "(source_path=%s, patterns=%d, correlation_id=%s)",
                safe_source_path,
                len(command.applicable_patterns),
                ctx_correlation_id,
            )

            result = await handle_compliance_evaluate_command(
                command,
                llm_client=llm_client,
                kafka_producer=kafka_producer,
                publish_topic=publish_topic
                or "onex.evt.omniintelligence.compliance-evaluated.v1",
            )

        logger.info(
            "Compliance-evaluate command processed via dispatch engine "
            "(source_path=%s, success=%s, compliant=%s, violations=%d, "
            "correlation_id=%s)",
            safe_source_path,
            result.success,
            result.compliant,
            len(result.violations),
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Bridge Handler: Pattern Projection (OMN-2424)
# =============================================================================


def create_pattern_projection_dispatch_handler(
    *,
    pattern_query_store: ProtocolPatternQueryStore,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern projection snapshot events.

    Triggered by pattern-promoted, pattern-deprecated, and
    pattern-lifecycle-transitioned events. On each trigger, queries the full
    validated pattern set and publishes a materialized snapshot to the
    pattern-projection topic.

    Args:
        pattern_query_store: REQUIRED store for querying all validated patterns.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for projection events (from contract).
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.

    Related:
        OMN-2424: Pattern projection snapshot publisher
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: lifecycle event → publish_projection()."""
        from omniintelligence.nodes.node_pattern_projection_effect.handlers import (
            publish_projection,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        # Extract optional fields for logging context — payload is any lifecycle event.
        # We don't parse the full model; we just need the routing fields for tracing.
        trigger_event_type = "unknown"
        triggering_pattern_id: UUID | None = None

        if isinstance(payload, dict):
            raw_event_type = payload.get("event_type")
            if raw_event_type is not None:
                trigger_event_type = str(raw_event_type)

            raw_pattern_id = payload.get("pattern_id")
            if raw_pattern_id is not None:
                with contextlib.suppress(ValueError, AttributeError):
                    triggering_pattern_id = UUID(str(raw_pattern_id))

            # Extract correlation_id from payload if available (override ctx fallback)
            raw_corr = payload.get("correlation_id")
            if raw_corr is not None:
                with contextlib.suppress(ValueError, AttributeError):
                    ctx_correlation_id = UUID(str(raw_corr))

        logger.info(
            "Dispatching pattern-projection via MessageDispatchEngine "
            "(trigger=%s, pattern_id=%s, correlation_id=%s)",
            trigger_event_type,
            triggering_pattern_id,
            ctx_correlation_id,
        )

        await publish_projection(
            pattern_query_store=pattern_query_store,
            producer=kafka_producer,
            correlation_id=ctx_correlation_id,
            publish_topic=publish_topic,
            trigger_event_type=trigger_event_type,
            triggering_pattern_id=triggering_pattern_id,
        )

        logger.info(
            "Pattern projection dispatch complete (trigger=%s, correlation_id=%s)",
            trigger_event_type,
            ctx_correlation_id,
        )

        return "ok"

    return _handle


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
    pattern_upsert_store: ProtocolPatternUpsertStore | None = None,
    pattern_query_store: ProtocolPatternQueryStore | None = None,
    llm_client: ProtocolLlmClient | None = None,
) -> MessageDispatchEngine:
    """Create and configure a MessageDispatchEngine for Intelligence domain.

    Creates the engine, registers all 7 intelligence domain handlers (11 routes)
    and freezes it. The engine is ready for dispatch after this call.

    All required dependencies must be provided. If any are missing, the caller
    should not start consumers.

    Args:
        repository: REQUIRED database repository.
        idempotency_store: REQUIRED idempotency store.
        intent_classifier: REQUIRED intent classifier.
        kafka_producer: Optional Kafka publisher (graceful degradation).
        publish_topics: Optional mapping of handler name to publish topic.
            Keys: "claude_hook", "lifecycle", "pattern_storage",
            "pattern_learning", "compliance_evaluate", "pattern_projection".
            Values: full topic strings from contract event_bus.publish_topics.
        pattern_upsert_store: Optional contract-driven upsert store. If None,
            falls back to repository for backwards compatibility.
        pattern_query_store: Optional store for querying validated patterns
            (ProtocolPatternQueryStore). Required by the pattern-projection
            handler (OMN-2424). When None, projection handler uses repository
            fallback if it satisfies the protocol.
        llm_client: Optional LLM client (ProtocolLlmClient) for compliance
            evaluation (OMN-2339). When None, compliance-evaluate commands
            are still registered but will return LLM-error results.

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
    # Use pattern_upsert_store (contract-driven) if available, otherwise
    # fall back to repository for backwards compatibility in tests.
    _upsert_store = (
        pattern_upsert_store if pattern_upsert_store is not None else repository
    )
    pattern_storage_handler = create_pattern_storage_dispatch_handler(
        pattern_upsert_store=_upsert_store,  # type: ignore[arg-type]
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

    # --- Handler 5: pattern-learning-cmd ---
    from omniintelligence.runtime.dispatch_handler_pattern_learning import (
        create_pattern_learning_dispatch_handler,
    )

    pattern_learning_handler = create_pattern_learning_dispatch_handler(
        repository=repository,
        kafka_producer=kafka_producer,
        publish_topic=topics.get(
            "pattern_learning",
            "onex.evt.omniintelligence.pattern-learned.v1",
        ),
    )
    engine.register_handler(
        handler_id="intelligence-pattern-learning-handler",
        handler=pattern_learning_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-pattern-learning-route",
            topic_pattern=DISPATCH_ALIAS_PATTERN_LEARNING_CMD,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-pattern-learning-handler",
            description=(
                "Routes pattern-learning commands to the pattern learning handler."
            ),
        )
    )

    # --- Handler 6: compliance-evaluate (OMN-2339) ---
    compliance_evaluate_handler = create_compliance_evaluate_dispatch_handler(
        llm_client=llm_client,
        kafka_producer=kafka_producer,
        publish_topic=topics.get("compliance_evaluate"),
    )
    engine.register_handler(
        handler_id="intelligence-compliance-evaluate-handler",
        handler=compliance_evaluate_handler,
        category=EnumMessageCategory.COMMAND,
        node_kind=EnumNodeKind.EFFECT,
        message_types=None,
    )
    engine.register_route(
        ModelDispatchRoute(
            route_id="intelligence-compliance-evaluate-route",
            topic_pattern=DISPATCH_ALIAS_COMPLIANCE_EVALUATE,
            message_category=EnumMessageCategory.COMMAND,
            handler_id="intelligence-compliance-evaluate-handler",
            description=(
                "Routes compliance-evaluate commands to handle_compliance_evaluate_command "
                "(OMN-2339). Calls Coder-14B via handle_evaluate_compliance() and emits "
                "compliance-evaluated events."
            ),
        )
    )

    # --- Handler 7: pattern-projection (OMN-2424) ---
    # Uses pattern_query_store for querying validated patterns.
    # When pattern_query_store is None, fall back to pattern_upsert_store if it satisfies
    # ProtocolPatternQueryStore (checked at runtime via isinstance), otherwise None.
    # NOTE: mypy cannot narrow Protocol isinstance checks at compile time; the runtime
    # check is sufficient because AdapterPatternStore declares query_patterns() matching
    # the protocol.
    _projection_store: ProtocolPatternQueryStore | None = pattern_query_store
    if _projection_store is None:
        # Runtime check: AdapterPatternStore implements ProtocolPatternQueryStore
        # via its query_patterns() method. Cast is safe — protocol is @runtime_checkable.
        _candidate = pattern_upsert_store if pattern_upsert_store is not None else None
        if _candidate is not None and isinstance(_candidate, ProtocolPatternQueryStore):
            _projection_store = _candidate

    if _projection_store is not None:
        pattern_projection_handler = create_pattern_projection_dispatch_handler(
            pattern_query_store=_projection_store,
            kafka_producer=kafka_producer,
            publish_topic=topics.get("pattern_projection"),
        )
        engine.register_handler(
            handler_id="intelligence-pattern-projection-handler",
            handler=pattern_projection_handler,
            category=EnumMessageCategory.EVENT,
            node_kind=EnumNodeKind.EFFECT,
            message_types=None,
        )
        engine.register_route(
            ModelDispatchRoute(
                route_id="intelligence-pattern-promoted-projection-route",
                topic_pattern=DISPATCH_ALIAS_PATTERN_PROMOTED,
                message_category=EnumMessageCategory.EVENT,
                handler_id="intelligence-pattern-projection-handler",
                description=(
                    "Routes pattern-promoted events to projection handler (OMN-2424). "
                    "Triggers a full validated-pattern snapshot publish."
                ),
            )
        )
        engine.register_route(
            ModelDispatchRoute(
                route_id="intelligence-pattern-deprecated-projection-route",
                topic_pattern=DISPATCH_ALIAS_PATTERN_DEPRECATED,
                message_category=EnumMessageCategory.EVENT,
                handler_id="intelligence-pattern-projection-handler",
                description=(
                    "Routes pattern-deprecated events to projection handler (OMN-2424). "
                    "Triggers a full validated-pattern snapshot publish."
                ),
            )
        )
        engine.register_route(
            ModelDispatchRoute(
                route_id="intelligence-pattern-lifecycle-transitioned-projection-route",
                topic_pattern=DISPATCH_ALIAS_PATTERN_LIFECYCLE_TRANSITIONED,
                message_category=EnumMessageCategory.EVENT,
                handler_id="intelligence-pattern-projection-handler",
                description=(
                    "Routes pattern-lifecycle-transitioned events to projection handler "
                    "(OMN-2424). Triggers a full validated-pattern snapshot publish."
                ),
            )
        )
    else:
        logger.warning(
            "Intelligence dispatch engine: no pattern_query_store available, "
            "pattern-projection handler not registered (OMN-2424). "
            "Provide pattern_query_store to enable projection snapshots."
        )

    engine.freeze()

    if llm_client is None:
        logger.warning(
            "Intelligence dispatch engine created with llm_client=None: "
            "compliance-evaluate commands are registered but will return "
            "LLM-error results until an llm_client is provided (OMN-2339)."
        )

    logger.info(
        "Intelligence dispatch engine created and frozen "
        "(routes=%d, handlers=%d, compliance_evaluate=%s, pattern_projection=%s)",
        engine.route_count,
        engine.handler_count,
        llm_client is not None,
        _projection_store is not None,
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
                    try:
                        decoded_value = raw_value.decode("utf-8")
                    except UnicodeDecodeError as ude:
                        # Invalid UTF-8 will never become valid on retry --
                        # ACK to prevent infinite redelivery.
                        safe_preview = get_log_sanitizer().sanitize(
                            repr(raw_value[:200])
                        )
                        logger.error(
                            "Invalid UTF-8 in message body, ACKing to "
                            "prevent infinite retry (error=%s, "
                            "raw_preview=%s, correlation_id=%s). "
                            "Message discarded (permanent parse failure).",
                            ude,
                            safe_preview,
                            msg_correlation_id,
                        )
                        if hasattr(msg, "ack"):
                            await msg.ack()
                        return
                    payload_dict = json.loads(decoded_value)
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

            # Gate ack/nack on dispatch status.
            # Distinguish permanent failures (structural reshape errors that
            # will never succeed on retry) from transient failures (DB errors,
            # network issues).  Permanent failures are ACK'd with an ERROR log
            # to prevent infinite NACK loops (GAP-9, OMN-2423).
            if result.is_successful():
                if hasattr(msg, "ack"):
                    await msg.ack()
            else:
                error_msg = result.error_message or ""
                is_permanent = _is_permanent_dispatch_failure(error_msg)
                if is_permanent:
                    logger.error(
                        "Permanent dispatch failure, ACKing to prevent NACK loop "
                        "(status=%s, error=%s, correlation_id=%s). "
                        "Message discarded (permanent parse/reshape failure).",
                        result.status,
                        error_msg,
                        msg_correlation_id,
                    )
                    if hasattr(msg, "ack"):
                        await msg.ack()
                else:
                    logger.warning(
                        "Transient dispatch failure, nacking message for retry "
                        "(status=%s, error=%s, correlation_id=%s)",
                        result.status,
                        error_msg,
                        msg_correlation_id,
                    )
                    if hasattr(msg, "nack"):
                        await msg.nack()

        except json.JSONDecodeError as e:
            # Malformed JSON will never succeed on retry -- ACK to prevent
            # infinite redelivery. Log truncated raw bytes for diagnosis.
            raw_preview = ""
            if hasattr(msg, "value"):
                raw_bytes = msg.value
                if isinstance(raw_bytes, bytes | bytearray):
                    raw_preview = repr(raw_bytes[:200])
                elif isinstance(raw_bytes, str):
                    raw_preview = raw_bytes[:200]
            sanitized_preview = get_log_sanitizer().sanitize(raw_preview)
            logger.error(
                "Malformed JSON in message body, ACKing to prevent infinite retry "
                "(error=%s, raw_preview=%s, correlation_id=%s). "
                "Message discarded (permanent parse failure).",
                e,
                sanitized_preview,
                msg_correlation_id,
            )
            if hasattr(msg, "ack"):
                await msg.ack()

        except Exception as e:
            logger.exception(
                "Failed to dispatch message via engine: %s (correlation_id=%s)",
                get_log_sanitizer().sanitize(str(e)),
                msg_correlation_id,
            )
            if hasattr(msg, "nack"):
                await msg.nack()

    return _on_message


__all__ = [
    "DISPATCH_ALIAS_CLAUDE_HOOK",
    "DISPATCH_ALIAS_COMPLIANCE_EVALUATE",
    "DISPATCH_ALIAS_PATTERN_DEPRECATED",
    "DISPATCH_ALIAS_PATTERN_DISCOVERED",
    "DISPATCH_ALIAS_PATTERN_LEARNED",
    "DISPATCH_ALIAS_PATTERN_LEARNING_CMD",
    "DISPATCH_ALIAS_PATTERN_LIFECYCLE",
    "DISPATCH_ALIAS_PATTERN_LIFECYCLE_TRANSITIONED",
    "DISPATCH_ALIAS_PATTERN_PROMOTED",
    "DISPATCH_ALIAS_SESSION_OUTCOME",
    "DISPATCH_ALIAS_TOOL_CONTENT",
    "create_claude_hook_dispatch_handler",
    "create_compliance_evaluate_dispatch_handler",
    "create_dispatch_callback",
    "create_intelligence_dispatch_engine",
    "create_pattern_lifecycle_dispatch_handler",
    "create_pattern_projection_dispatch_handler",
    "create_pattern_storage_dispatch_handler",
    "create_session_outcome_dispatch_handler",
]
