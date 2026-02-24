# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025-2026 OmniNode Team
"""Unit-contract tests for _reshape_daemon_hook_payload_v1.

Validates that the reshape function correctly transforms flat daemon-shaped
payloads into the nested structure expected by ModelClaudeCodeHookEvent.

The emit daemon sends a flat dict with envelope keys (event_type, session_id,
correlation_id, emitted_at) mixed alongside domain-specific payload keys.
ModelClaudeCodeHookEvent expects a nested ``payload`` sub-dict, so the reshape
function splits envelope keys from payload keys and returns the canonical shape.

As of OMN-2423, only ``event_type`` is a hard required key (raises ValueError).
All other envelope fields (``session_id``, ``correlation_id``, ``emitted_at``)
use structured fallbacks to prevent NACK loops:
    - session_id missing/null  → "unknown"
    - correlation_id missing/null → generated uuid4()
    - emitted_at missing/null  → datetime.now(UTC) as ISO string

Related:
    - Bus audit project: daemon emits flat dicts, reshape bridges the gap
    - OMN-2423: Fix dispatch_handlers reshape crash — NACK loop on omniclaude hook events
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

# Private import is intentional: _reshape_daemon_hook_payload_v1 is an internal
# helper, but we test it directly to ensure the daemon-to-model contract is
# upheld without requiring a full dispatch-engine integration test.
from omniintelligence.runtime.dispatch_handlers import (
    _MAX_DIAGNOSTIC_KEYS,
    _diagnostic_key_summary,
    _is_permanent_dispatch_failure,
    _is_tool_content_payload,
    _needs_daemon_reshape,
    _reshape_daemon_hook_payload_v1,
    _reshape_tool_content_to_hook_event,
    create_claude_hook_dispatch_handler,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def daemon_wire_payload() -> dict[str, Any]:
    """Real daemon wire format payload for UserPromptSubmit.

    This mirrors exactly what the emit daemon sends over the Unix socket
    as a flat dict with envelope keys and domain-specific payload keys
    mixed together.
    """
    return {
        "session_id": "test-session-001",
        "prompt_preview": "Fix the bug in...",
        "prompt_length": 150,
        "prompt_b64": "RnVsbCBwcm9tcHQ=",
        "correlation_id": "12345678-1234-1234-1234-123456789abc",
        "event_type": "UserPromptSubmit",
        "causation_id": None,
        "emitted_at": "2026-02-15T10:30:00+00:00",
        "schema_version": "1.0.0",
    }


# =============================================================================
# Tests: Happy Path
# =============================================================================


@pytest.mark.unit
class TestReshapeDaemonPayloadHappyPath:
    """Validate correct transformation of a well-formed daemon payload."""

    def test_reshape_daemon_payload_happy_path(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Given a flat daemon payload, reshape produces the canonical shape."""
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        # Top-level envelope keys
        assert reshaped["event_type"] == "UserPromptSubmit"
        assert reshaped["session_id"] == "test-session-001"
        assert reshaped["correlation_id"] == "12345678-1234-1234-1234-123456789abc"
        assert reshaped["timestamp_utc"] == "2026-02-15T10:30:00+00:00"

        # Payload sub-dict contains domain-specific keys
        payload = reshaped["payload"]
        assert "prompt_preview" in payload
        assert "prompt_length" in payload
        assert "prompt_b64" in payload
        assert payload["prompt_preview"] == "Fix the bug in..."
        assert payload["prompt_length"] == 150
        assert payload["prompt_b64"] == "RnVsbCBwcm9tcHQ="

        # Payload must NOT contain envelope keys
        for key in (
            "event_type",
            "session_id",
            "correlation_id",
            "emitted_at",
            "causation_id",
            "schema_version",
        ):
            assert key not in payload, (
                f"Envelope key {key!r} must not leak into payload sub-dict"
            )

        # Top level must NOT contain domain-specific or stripped keys
        for key in (
            "prompt_preview",
            "prompt_length",
            "prompt_b64",
            "causation_id",
            "schema_version",
            "emitted_at",
        ):
            assert key not in reshaped, (
                f"Key {key!r} must not appear at top level of reshaped output"
            )


# =============================================================================
# Tests: Reshape then Validate into Model
# =============================================================================


@pytest.mark.unit
class TestReshapeThenValidateIntoModel:
    """Validate that reshaped output parses into ModelClaudeCodeHookEvent."""

    def test_reshape_then_validate_into_model(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Reshaped dict must parse into ModelClaudeCodeHookEvent without errors."""
        from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
            ModelClaudeCodeHookEvent,
        )
        from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event_payload import (
            ModelClaudeCodeHookEventPayload,
        )

        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)
        event = ModelClaudeCodeHookEvent(**reshaped)

        # event_type is parsed into the enum
        assert event.event_type.value == "UserPromptSubmit"

        # timestamp_utc is timezone-aware
        assert event.timestamp_utc.tzinfo is not None

        # payload is the correct type
        assert isinstance(event.payload, ModelClaudeCodeHookEventPayload)

        # Domain-specific keys are stored as model_extra on the payload
        # (ModelClaudeCodeHookEventPayload uses extra="allow")
        assert event.payload.model_extra is not None
        assert "prompt_preview" in event.payload.model_extra
        assert "prompt_length" in event.payload.model_extra
        assert "prompt_b64" in event.payload.model_extra


# =============================================================================
# Tests: Missing Required Keys
# =============================================================================


@pytest.mark.unit
class TestReshapeMissingRequiredKeys:
    """Validate fallback behaviour when optional envelope keys are absent.

    As of OMN-2423, only ``event_type`` is hard-required (raises ValueError).
    All other envelope fields use structured fallbacks to prevent NACK loops.
    V1 (OMN-2423): reshape handles missing correlation_id.
    V2 (OMN-2423): reshape handles missing emitted_at with UTC fallback.
    """

    def test_reshape_missing_emitted_at_uses_utc_fallback(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing emitted_at produces a valid reshape with UTC now fallback.

        V2 (OMN-2423): reshape handles missing emitted_at with UTC fallback.
        """
        del daemon_wire_payload["emitted_at"]

        # Must NOT raise; should fall back to datetime.now(UTC)
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        # timestamp_utc must be present and non-null
        assert "timestamp_utc" in reshaped
        assert reshaped["timestamp_utc"] is not None

        # Other fields must be preserved
        assert reshaped["event_type"] == "UserPromptSubmit"
        assert reshaped["session_id"] == "test-session-001"
        assert reshaped["correlation_id"] == "12345678-1234-1234-1234-123456789abc"

    def test_reshape_missing_event_type(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing event_type raises ValueError (only hard-required field)."""
        del daemon_wire_payload["event_type"]

        with pytest.raises(ValueError, match="event_type") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "keys=" in error_msg

    def test_reshape_missing_session_id_uses_unknown_fallback(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing session_id produces a valid reshape with 'unknown' fallback.

        V1 (OMN-2423): reshape handles missing session_id.
        """
        del daemon_wire_payload["session_id"]

        # Must NOT raise; should fall back to "unknown"
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        assert reshaped["session_id"] == "unknown"
        assert reshaped["event_type"] == "UserPromptSubmit"

    def test_reshape_missing_correlation_id_generates_uuid(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing correlation_id produces a valid reshape with generated UUID.

        V1 (OMN-2423): reshape handles missing correlation_id.
        """
        del daemon_wire_payload["correlation_id"]

        # Must NOT raise; should generate a new UUID
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        assert "correlation_id" in reshaped
        # Generated value must be a non-empty string (UUID format)
        assert isinstance(reshaped["correlation_id"], str)
        assert len(reshaped["correlation_id"]) == 36  # UUID string length
        assert reshaped["event_type"] == "UserPromptSubmit"

    def test_reshape_empty_payload_raises_for_event_type(self) -> None:
        """An empty dict raises ValueError because event_type is the hard-required field."""
        with pytest.raises(
            ValueError, match="missing required key 'event_type'"
        ) as exc_info:
            _reshape_daemon_hook_payload_v1({})

        # Error message should include the empty keys list for diagnostics
        error_msg = str(exc_info.value)
        assert "keys=" in error_msg


# =============================================================================
# Tests: Null Value for Required Keys
# =============================================================================


@pytest.mark.unit
class TestReshapeNullRequiredKeys:
    """Validate fallback behaviour when optional envelope keys have null values.

    As of OMN-2423, only ``event_type=None`` raises ValueError.  All other
    null values use structured fallbacks to prevent NACK loops:
    - session_id=None  → "unknown"
    - correlation_id=None → generated uuid4()
    - emitted_at=None  → datetime.now(UTC) as ISO string
    """

    def test_reshape_null_event_type_raises(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload with event_type=None raises ValueError (only hard-required field)."""
        daemon_wire_payload["event_type"] = None

        with pytest.raises(
            ValueError, match="missing required key 'event_type'"
        ) as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "event_type" in error_msg
        assert "keys=" in error_msg

    def test_reshape_null_session_id_uses_unknown_fallback(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload with session_id=None uses 'unknown' fallback instead of raising."""
        daemon_wire_payload["session_id"] = None

        # Must NOT raise
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        assert reshaped["session_id"] == "unknown"
        assert reshaped["event_type"] == "UserPromptSubmit"

    def test_reshape_null_correlation_id_generates_uuid(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload with correlation_id=None generates a UUID fallback instead of raising."""
        daemon_wire_payload["correlation_id"] = None

        # Must NOT raise
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        assert "correlation_id" in reshaped
        assert isinstance(reshaped["correlation_id"], str)
        assert len(reshaped["correlation_id"]) == 36  # UUID string length

    def test_reshape_null_emitted_at_uses_utc_fallback(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload with emitted_at=None uses UTC now fallback instead of raising.

        V2 (OMN-2423): reshape handles null emitted_at with UTC fallback.
        """
        daemon_wire_payload["emitted_at"] = None

        # Must NOT raise
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        assert "timestamp_utc" in reshaped
        assert reshaped["timestamp_utc"] is not None
        assert reshaped["event_type"] == "UserPromptSubmit"


# =============================================================================
# Tests: _needs_daemon_reshape Heuristic
# =============================================================================


@pytest.mark.unit
class TestNeedsDaemonReshape:
    """Validate _needs_daemon_reshape detection heuristic for all three cases.

    The heuristic returns True when ``emitted_at`` is present and
    ``timestamp_utc`` is absent (flat daemon shape).  It returns False
    for canonical payloads (has ``timestamp_utc``) and for unrelated
    payloads (neither key present).
    """

    def test_daemon_shaped_payload_returns_true(self) -> None:
        """Payload with emitted_at but no timestamp_utc is daemon-shaped."""
        payload: dict[str, Any] = {"emitted_at": "2026-02-15T10:30:00+00:00"}
        assert _needs_daemon_reshape(payload) is True

    def test_canonical_shaped_payload_returns_false(self) -> None:
        """Payload with timestamp_utc but no emitted_at is canonical-shaped."""
        payload: dict[str, Any] = {"timestamp_utc": "2026-02-15T10:30:00+00:00"}
        assert _needs_daemon_reshape(payload) is False

    def test_unrelated_payload_returns_false(self) -> None:
        """Payload with neither timestamp key is unrelated."""
        payload: dict[str, Any] = {"event_type": "UserPromptSubmit"}
        assert _needs_daemon_reshape(payload) is False


# =============================================================================
# Tests: Both emitted_at and timestamp_utc Present (Canonical Path)
# =============================================================================


@pytest.mark.unit
class TestReshapeBothTimestampKeys:
    """Validate reshape behaviour when both emitted_at and timestamp_utc are present.

    The dispatch handler uses a heuristic to detect flat daemon payloads:
    ``'emitted_at' in payload and 'timestamp_utc' not in payload``.  When
    both keys are present, the payload is treated as canonical (already
    shaped) and passed directly to ``ModelClaudeCodeHookEvent`` without
    the caller triggering reshape.

    However, _reshape_daemon_hook_payload_v1 itself operates purely on the
    dict it receives.  This test verifies that when a payload containing
    both ``emitted_at`` and ``timestamp_utc`` is passed directly, the
    function still reshapes it (it does not skip), confirming that the
    no-reshape decision must be made by the caller, not by the function.
    """

    def test_payload_with_both_keys_is_not_skipped_by_caller_heuristic(
        self,
        daemon_wire_payload: dict[str, Any],
    ) -> None:
        """Payload with BOTH emitted_at and timestamp_utc is treated as canonical.

        The caller heuristic (``_needs_daemon_reshape``) should evaluate to
        False when both keys are present, meaning
        _reshape_daemon_hook_payload_v1 is never called.  We verify the
        heuristic through the extracted helper function.
        """
        # Add timestamp_utc alongside existing emitted_at
        daemon_wire_payload["timestamp_utc"] = "2026-02-15T10:30:00+00:00"

        assert _needs_daemon_reshape(daemon_wire_payload) is False, (
            "When both emitted_at and timestamp_utc are present, "
            "the caller must NOT trigger reshape"
        )

    def test_payload_with_both_keys_passed_through_unchanged(
        self,
        daemon_wire_payload: dict[str, Any],
    ) -> None:
        """When the caller skips reshape, the original dict is used as-is.

        Simulates the canonical (no-reshape) path: the payload already
        contains timestamp_utc and a nested payload dict, so it should
        be forwarded directly to ModelClaudeCodeHookEvent without
        transformation.
        """
        # Build a canonical-shaped payload that has both keys
        canonical_payload: dict[str, Any] = {
            "event_type": "UserPromptSubmit",
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
            "timestamp_utc": "2026-02-15T10:30:00+00:00",
            "emitted_at": "2026-02-15T10:30:00+00:00",  # extra key
            "payload": {
                "prompt_preview": "Fix the bug in...",
                "prompt_length": 150,
            },
        }

        # Caller heuristic skips reshape
        assert _needs_daemon_reshape(canonical_payload) is False

        # When not reshaped, the dict is used as-is -- verify structure
        # is preserved (no mutation)
        assert canonical_payload["timestamp_utc"] == "2026-02-15T10:30:00+00:00"
        assert canonical_payload["event_type"] == "UserPromptSubmit"
        assert isinstance(canonical_payload["payload"], dict)
        assert canonical_payload["payload"]["prompt_preview"] == "Fix the bug in..."


# =============================================================================
# Tests: Extra / Unknown Keys
# =============================================================================


@pytest.mark.unit
class TestReshapeUnknownKeys:
    """Validate that extra keys not in the envelope set land in the payload sub-dict."""

    def test_unknown_keys_placed_into_payload(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Keys not in the daemon envelope set must appear in the payload sub-dict.

        This covers the case where the daemon sends an unexpected key
        (e.g., ``trace_id``) alongside the standard envelope keys.
        """
        daemon_wire_payload["trace_id"] = "abc-trace-999"
        daemon_wire_payload["custom_metric"] = 42

        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        payload = reshaped["payload"]
        assert payload["trace_id"] == "abc-trace-999"
        assert payload["custom_metric"] == 42

        # Unknown keys must NOT appear at the top level
        assert "trace_id" not in reshaped
        assert "custom_metric" not in reshaped


# =============================================================================
# Tests: Daemon Metadata Stripping
# =============================================================================


@pytest.mark.unit
class TestReshapeStripsDaemonMetadata:
    """Validate that schema_version and causation_id are fully stripped."""

    def test_reshape_strips_all_daemon_metadata(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """schema_version and causation_id must NOT appear in reshaped output at any level."""
        reshaped = _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        # Not at top level
        assert "schema_version" not in reshaped
        assert "causation_id" not in reshaped

        # Not in payload sub-dict
        assert "schema_version" not in reshaped["payload"]
        assert "causation_id" not in reshaped["payload"]


# =============================================================================
# Tests: Diagnostic Key Truncation
# =============================================================================


@pytest.mark.unit
class TestDiagnosticKeyTruncation:
    """Validate that payloads with >_MAX_DIAGNOSTIC_KEYS produce truncated diagnostics."""

    def test_truncation_indicator_in_error_message(self) -> None:
        """Payload with >_MAX_DIAGNOSTIC_KEYS keys includes '...' in error message.

        Builds a flat daemon payload with 15 unknown keys but MISSING the
        required ``event_type`` key to trigger the error path.  The error
        message must contain the ``'...'`` truncation indicator and must
        NOT enumerate all 15 key names.
        """
        total_keys = _MAX_DIAGNOSTIC_KEYS + 5  # 15 keys total
        payload: dict[str, Any] = {
            # Include required keys except event_type to trigger ValueError
            "emitted_at": "2026-02-15T10:30:00+00:00",
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
        }
        # Add enough extra keys to exceed _MAX_DIAGNOSTIC_KEYS
        for i in range(total_keys - len(payload)):
            payload[f"extra_key_{i:03d}"] = f"value_{i}"

        assert len(payload) > _MAX_DIAGNOSTIC_KEYS, (
            f"Test setup error: need >{_MAX_DIAGNOSTIC_KEYS} keys, got {len(payload)}"
        )

        with pytest.raises(ValueError, match="event_type") as exc_info:
            _reshape_daemon_hook_payload_v1(payload)

        error_msg = str(exc_info.value)

        # Must contain the truncation indicator as a list element
        assert "'...'" in error_msg, (
            f"Error message must contain truncation indicator '...', got: {error_msg}"
        )

        # Must NOT contain all key names -- verify at least one extra key
        # beyond the truncation limit is absent from the message
        all_keys_sorted = sorted(payload.keys())
        keys_beyond_limit = all_keys_sorted[_MAX_DIAGNOSTIC_KEYS:]
        assert len(keys_beyond_limit) > 0, "Test setup error: no keys beyond limit"
        for key in keys_beyond_limit:
            assert key not in error_msg, (
                f"Key {key!r} beyond truncation limit should not appear in error message"
            )

    def test_truncation_indicator_in_null_event_type_error_message(self) -> None:
        """Payload with >_MAX_DIAGNOSTIC_KEYS keys and event_type=None.

        Builds a flat daemon payload with all other required keys present,
        but sets ``event_type`` to None to trigger the error path.  Adds
        enough extra keys to exceed _MAX_DIAGNOSTIC_KEYS so the diagnostic
        key summary is truncated.  The error message must contain the
        ``'...'`` truncation indicator and mention 'event_type'.

        As of OMN-2423, the error message says 'missing required key' for
        both absent and null event_type (unified check).
        """
        total_keys = _MAX_DIAGNOSTIC_KEYS + 5  # 15 keys total
        payload: dict[str, Any] = {
            # All keys present, but event_type is null
            "emitted_at": "2026-02-15T10:30:00+00:00",
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
            "event_type": None,
        }
        # Add enough extra keys to exceed _MAX_DIAGNOSTIC_KEYS
        for i in range(total_keys - len(payload)):
            payload[f"extra_key_{i:03d}"] = f"value_{i}"

        assert len(payload) > _MAX_DIAGNOSTIC_KEYS, (
            f"Test setup error: need >{_MAX_DIAGNOSTIC_KEYS} keys, got {len(payload)}"
        )

        with pytest.raises(ValueError, match="event_type") as exc_info:
            _reshape_daemon_hook_payload_v1(payload)

        error_msg = str(exc_info.value)

        # Must mention the offending key
        assert "event_type" in error_msg, (
            f"Error message must mention 'event_type', got: {error_msg}"
        )

        # Must contain the truncation indicator as a list element
        assert "'...'" in error_msg, (
            f"Error message must contain truncation indicator '...', got: {error_msg}"
        )

        # Must NOT contain all key names -- verify at least one extra key
        # beyond the truncation limit is absent from the message
        all_keys_sorted = sorted(payload.keys())
        keys_beyond_limit = all_keys_sorted[_MAX_DIAGNOSTIC_KEYS:]
        assert len(keys_beyond_limit) > 0, "Test setup error: no keys beyond limit"
        for key in keys_beyond_limit:
            assert key not in error_msg, (
                f"Key {key!r} beyond truncation limit should not appear in error message"
            )


# =============================================================================
# Tests: _diagnostic_key_summary Direct Unit Tests
# =============================================================================


@pytest.mark.unit
class TestDiagnosticKeySummary:
    """Validate _diagnostic_key_summary output for various dict sizes."""

    def test_empty_dict_returns_empty_keys(self) -> None:
        """Empty dict produces '(keys=[])'."""
        assert _diagnostic_key_summary({}) == "(keys=[])"

    def test_few_keys_returns_sorted(self) -> None:
        """Dict with a few keys returns them sorted alphabetically."""
        result = _diagnostic_key_summary({"zebra": 1, "alpha": 2, "middle": 3})
        assert result == "(keys=['alpha', 'middle', 'zebra'])"

    def test_exceeding_max_keys_shows_truncation(self) -> None:
        """Dict with more than _MAX_DIAGNOSTIC_KEYS keys appends '...' indicator."""
        oversized = {f"key_{i:03d}": i for i in range(_MAX_DIAGNOSTIC_KEYS + 5)}
        result = _diagnostic_key_summary(oversized)

        # Must end with the ellipsis indicator inside the list
        assert "'...'" in result

        # Only _MAX_DIAGNOSTIC_KEYS real keys plus the '...' sentinel
        all_keys_sorted = sorted(oversized.keys())
        for key in all_keys_sorted[:_MAX_DIAGNOSTIC_KEYS]:
            assert key in result
        for key in all_keys_sorted[_MAX_DIAGNOSTIC_KEYS:]:
            assert key not in result


# =============================================================================
# Tests: Dispatch Handler Wiring (daemon reshape integration)
# =============================================================================


@pytest.mark.unit
class TestDispatchHandlerDaemonReshapeWiring:
    """Verify create_claude_hook_dispatch_handler reshapes daemon payloads.

    The standalone _needs_daemon_reshape and _reshape_daemon_hook_payload_v1
    functions are thoroughly tested above.  This test class proves the wiring:
    that create_claude_hook_dispatch_handler's internal _handle closure
    correctly detects and reshapes a daemon-shaped dict before passing a
    properly-typed ModelClaudeCodeHookEvent to route_hook_event.
    """

    @pytest.mark.asyncio
    async def test_daemon_payload_is_reshaped_and_routed(
        self,
        daemon_wire_payload: dict[str, Any],
    ) -> None:
        """A daemon-shaped dict payload is reshaped and parsed into ModelClaudeCodeHookEvent.

        Mocks route_hook_event to capture the event object it receives,
        then asserts it is a well-formed ModelClaudeCodeHookEvent with the
        correct envelope fields.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import UUID

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )
        from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
            ModelClaudeCodeHookEvent,
        )

        # --- Mock dependencies ---
        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock()

        correlation_id = UUID("12345678-1234-1234-1234-123456789abc")

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_classifier,
            correlation_id=correlation_id,
        )

        # Wrap daemon payload in an envelope (as the dispatch callback would)
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=daemon_wire_payload,
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=UUID("00000000-0000-0000-0000-000000000001"),
        )

        # Patch route_hook_event to capture the event it receives
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.event_type = "UserPromptSubmit"

        with patch(
            "omniintelligence.nodes.node_claude_hook_event_effect.handlers"
            ".route_hook_event",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            result = await handler(envelope, context)

            # Handler returns "ok" on success
            assert result == "ok"

            # route_hook_event must have been called exactly once
            mock_route.assert_called_once()

            # Extract the event kwarg passed to route_hook_event
            call_kwargs = mock_route.call_args.kwargs
            event = call_kwargs["event"]

            # The event must be a properly-parsed ModelClaudeCodeHookEvent
            assert isinstance(event, ModelClaudeCodeHookEvent)
            assert event.event_type.value == "UserPromptSubmit"
            assert str(event.session_id) == "test-session-001"
            assert event.timestamp_utc is not None
            assert event.timestamp_utc.tzinfo is not None

            # Domain-specific keys must be inside the payload, not at top level
            assert event.payload is not None
            assert event.payload.model_extra is not None
            assert "prompt_preview" in event.payload.model_extra
            assert event.payload.model_extra["prompt_preview"] == "Fix the bug in..."


# =============================================================================
# Tests: _is_tool_content_payload Detection
# =============================================================================


@pytest.mark.unit
class TestIsToolContentPayload:
    """Validate _is_tool_content_payload detection for all payload formats.

    Tool-content payloads are identified by the presence of ``tool_name_raw``
    and the absence of ``event_type``.  This distinguishes them from daemon
    flat payloads (which have both) and canonical hook events (which have
    ``event_type``).
    """

    def test_tool_content_payload_returns_true(self) -> None:
        """Flat tool-content dict with tool_name_raw and no event_type."""
        payload: dict[str, Any] = {
            "tool_name_raw": "Write",
            "tool_name": "Write",
            "file_path": "/workspace/src/main.py",
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
            "timestamp": "2026-02-16T10:30:00Z",
        }
        assert _is_tool_content_payload(payload) is True

    def test_daemon_payload_returns_false(self) -> None:
        """Daemon flat payload has event_type, so not tool-content."""
        payload: dict[str, Any] = {
            "event_type": "UserPromptSubmit",
            "session_id": "test-session-001",
            "emitted_at": "2026-02-16T10:30:00Z",
            "tool_name_raw": "Read",
        }
        assert _is_tool_content_payload(payload) is False

    def test_canonical_payload_returns_false(self) -> None:
        """Canonical ModelClaudeCodeHookEvent shape has event_type."""
        payload: dict[str, Any] = {
            "event_type": "PostToolUse",
            "session_id": "test-session-001",
            "timestamp_utc": "2026-02-16T10:30:00Z",
            "payload": {"tool_name_raw": "Write"},
        }
        assert _is_tool_content_payload(payload) is False

    def test_empty_payload_returns_false(self) -> None:
        """Empty dict is not a tool-content payload."""
        assert _is_tool_content_payload({}) is False

    def test_payload_without_tool_name_raw_returns_false(self) -> None:
        """Dict without tool_name_raw is not tool-content even without event_type."""
        payload: dict[str, Any] = {"some_key": "some_value"}
        assert _is_tool_content_payload(payload) is False

    def test_shared_keys_do_not_bypass_detection(self) -> None:
        """Payload with session_id and correlation_id but also tool_name_raw
        is correctly detected as tool-content, not misidentified as a hook
        envelope due to shared key overlap.
        """
        payload: dict[str, Any] = {
            "tool_name_raw": "Write",
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
        }
        assert _is_tool_content_payload(payload) is True


# =============================================================================
# Tests: _reshape_tool_content_to_hook_event
# =============================================================================


@pytest.mark.unit
class TestReshapeToolContentToHookEvent:
    """Validate _reshape_tool_content_to_hook_event for tool-content payloads.

    The function wraps a flat ModelToolExecutionContent dict into a
    ModelClaudeCodeHookEvent with event_type=PostToolUse.
    """

    @pytest.fixture
    def tool_content_payload(self) -> dict[str, Any]:
        """Real tool-content wire format payload.

        Mirrors what omniclaude's _emit_tool_content sends to Kafka:
        ModelToolExecutionContent.model_dump_json() deserialized.
        """
        return {
            "tool_name_raw": "Write",
            "tool_name": "Write",
            "file_path": "/workspace/src/main.py",
            "language": "python",
            "content_preview": "def main():\n    pass",
            "content_length": 42,
            "content_hash": "sha256:abc123",
            "is_content_redacted": False,
            "redaction_policy_version": None,
            "success": True,
            "error_type": None,
            "error_message": None,
            "duration_ms": 15.3,
            "session_id": "test-session-001",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
            "timestamp": "2026-02-16T10:30:00+00:00",
        }

    @pytest.fixture
    def mock_envelope(self) -> ModelEventEnvelope[object]:
        from uuid import UUID

        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        return ModelEventEnvelope(
            payload={},
            correlation_id=UUID("99999999-9999-9999-9999-999999999999"),
        )

    def test_reshape_produces_valid_hook_event(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """Reshape produces a valid ModelClaudeCodeHookEvent with PostToolUse type."""
        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)

        assert event.event_type.value == "PostToolUse"
        assert event.session_id == "test-session-001"
        assert event.timestamp_utc.tzinfo is not None

    def test_reshape_preserves_correlation_id_from_payload(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """Correlation ID from tool-content payload takes precedence over envelope."""
        from uuid import UUID

        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)
        assert event.correlation_id == UUID("12345678-1234-1234-1234-123456789abc")

    def test_reshape_nests_tool_fields_in_payload(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """Tool-content fields end up in the nested payload, not at top level."""
        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)

        # Access extra fields via model_extra (extra="allow")
        assert event.payload.model_extra["tool_name_raw"] == "Write"
        assert event.payload.model_extra["tool_name"] == "Write"
        assert event.payload.model_extra["file_path"] == "/workspace/src/main.py"
        assert event.payload.model_extra["content_length"] == 42

    def test_reshape_excludes_envelope_keys_from_nested_payload(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """session_id, correlation_id, timestamp are NOT in nested payload."""
        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)

        assert "session_id" not in event.payload.model_extra
        assert "correlation_id" not in event.payload.model_extra
        assert "timestamp" not in event.payload.model_extra

    def test_reshape_with_missing_session_id_uses_unknown(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """When session_id is None, falls back to 'unknown'."""
        tool_content_payload["session_id"] = None

        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)
        assert event.session_id == "unknown"

    def test_reshape_with_missing_correlation_id_uses_envelope(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """When correlation_id is None in payload, falls back to envelope."""
        from uuid import UUID

        tool_content_payload["correlation_id"] = None

        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)
        assert event.correlation_id == UUID("99999999-9999-9999-9999-999999999999")

    def test_reshape_with_missing_timestamp_uses_envelope(
        self,
        tool_content_payload: dict[str, Any],
        mock_envelope: ModelEventEnvelope[object],
    ) -> None:
        """When timestamp is None, falls back to envelope_timestamp."""
        tool_content_payload["timestamp"] = None

        event = _reshape_tool_content_to_hook_event(tool_content_payload, mock_envelope)
        assert event.timestamp_utc is not None
        assert event.timestamp_utc.tzinfo is not None


# =============================================================================
# Tests: Dispatch Handler Wiring (tool-content integration)
# =============================================================================


@pytest.mark.unit
class TestDispatchHandlerToolContentWiring:
    """Verify create_claude_hook_dispatch_handler reshapes tool-content payloads.

    This proves the wiring: that the handler's _handle closure correctly
    detects and reshapes a tool-content dict before passing a properly-typed
    ModelClaudeCodeHookEvent to route_hook_event.
    """

    @pytest.mark.asyncio
    async def test_tool_content_payload_is_reshaped_and_routed(self) -> None:
        """A tool-content dict payload is reshaped as PostToolUse and routed.

        Mocks route_hook_event to capture the event object it receives,
        then asserts it is a well-formed ModelClaudeCodeHookEvent with
        event_type=PostToolUse and nested tool fields.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import UUID

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )
        from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
            ModelClaudeCodeHookEvent,
        )

        # --- Real wire payload from omniclaude tool-content topic ---
        tool_content_wire = {
            "tool_name_raw": "Write",
            "tool_name": "Write",
            "file_path": "/workspace/src/main.py",
            "language": "python",
            "content_preview": "def main():\n    pass",
            "content_length": 42,
            "content_hash": None,
            "is_content_redacted": False,
            "redaction_policy_version": None,
            "success": True,
            "error_type": None,
            "error_message": None,
            "duration_ms": 15.3,
            "session_id": "test-session-tool",
            "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "timestamp": "2026-02-16T10:30:00+00:00",
        }

        # --- Mock dependencies ---
        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock()

        correlation_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_classifier,
            correlation_id=correlation_id,
        )

        # Wrap in envelope (as create_dispatch_callback would)
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=tool_content_wire,
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=UUID("00000000-0000-0000-0000-000000000002"),
        )

        # Patch route_hook_event to capture the event
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.event_type = "PostToolUse"

        with patch(
            "omniintelligence.nodes.node_claude_hook_event_effect.handlers"
            ".route_hook_event",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            result = await handler(envelope, context)

            # Handler returns "ok" on success
            assert result == "ok"

            # route_hook_event must have been called exactly once
            mock_route.assert_called_once()

            # Extract the event kwarg passed to route_hook_event
            call_kwargs = mock_route.call_args.kwargs
            event = call_kwargs["event"]

            # The event must be a properly-parsed ModelClaudeCodeHookEvent
            assert isinstance(event, ModelClaudeCodeHookEvent)
            assert event.event_type.value == "PostToolUse"
            assert event.session_id == "test-session-tool"
            assert event.timestamp_utc is not None
            assert event.timestamp_utc.tzinfo is not None

            # Tool fields must be inside the nested payload
            assert event.payload is not None
            assert event.payload.model_extra is not None
            assert event.payload.model_extra["tool_name_raw"] == "Write"
            assert event.payload.model_extra["file_path"] == "/workspace/src/main.py"

            # Envelope keys must NOT be in the nested payload
            assert "session_id" not in event.payload.model_extra
            assert "correlation_id" not in event.payload.model_extra
            assert "timestamp" not in event.payload.model_extra

    @pytest.mark.asyncio
    async def test_hook_event_payload_still_parses_unchanged(self) -> None:
        """A canonical hook-event payload still works after the tool-content fix.

        Ensures the new tool-content reshape path does not interfere with
        the existing canonical (already-structured) payload path.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import UUID

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )
        from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
            ModelClaudeCodeHookEvent,
        )

        # --- Canonical hook-event payload (already structured) ---
        canonical_payload = {
            "event_type": "UserPromptSubmit",
            "session_id": "test-session-canonical",
            "correlation_id": "12345678-1234-1234-1234-123456789abc",
            "timestamp_utc": "2026-02-16T10:30:00+00:00",
            "payload": {"prompt": "What does this function do?"},
        }

        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock()
        correlation_id = UUID("12345678-1234-1234-1234-123456789abc")

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_classifier,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=canonical_payload,
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=UUID("00000000-0000-0000-0000-000000000003"),
        )

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.event_type = "UserPromptSubmit"

        with patch(
            "omniintelligence.nodes.node_claude_hook_event_effect.handlers"
            ".route_hook_event",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            result = await handler(envelope, context)

            assert result == "ok"
            mock_route.assert_called_once()

            event = mock_route.call_args.kwargs["event"]
            assert isinstance(event, ModelClaudeCodeHookEvent)
            assert event.event_type.value == "UserPromptSubmit"
            assert event.session_id == "test-session-canonical"


# =============================================================================
# Tests: OMN-2423 — Permanent Failure Classification (V4 verification)
# =============================================================================


@pytest.mark.unit
class TestIsPermanentDispatchFailure:
    """Validate _is_permanent_dispatch_failure correctly classifies error messages.

    V4 (OMN-2423): No infinite NACK loop on malformed payload (dead-letter or
    discard).  Permanent failures are ACK'd; transient failures are NACK'd.
    """

    def test_reshape_failure_marker_is_permanent(self) -> None:
        """'Permanent reshape failure' in error message is classified as permanent."""
        assert _is_permanent_dispatch_failure(
            "Handler 'x' failed: ValueError: Permanent reshape failure for claude-hook-event"
        )

    def test_reshape_failure_marker_survives_dispatch_engine_wrapping(self) -> None:
        """Substring match survives the dispatch-engine's handler wrapping prefix.

        The dispatch engine wraps handler exceptions as:
            "Handler '<name>' failed: <ExcType>: <original message>"
        This test verifies that PERMANENT_FAILURE_MARKERS substrings are still
        detected after that wrapping, proving the runtime NACK-prevention logic
        works end-to-end with real dispatch-engine-formatted error strings.
        """
        assert _is_permanent_dispatch_failure(
            "Handler 'claude-hook-event' failed: ValueError: Permanent reshape failure for claude-hook-event"
        )

    def test_parse_failure_marker_is_permanent(self) -> None:
        """'Failed to parse payload' marker is classified as permanent."""
        assert _is_permanent_dispatch_failure(
            "Failed to parse payload as ModelClaudeCodeHookEvent: validation error"
        )

    def test_unexpected_payload_type_marker_is_permanent(self) -> None:
        """'Unexpected payload type' marker is classified as permanent."""
        assert _is_permanent_dispatch_failure(
            "Unexpected payload type NoneType for claude-hook-event"
        )

    def test_missing_event_type_marker_is_permanent(self) -> None:
        """'Daemon payload missing required key event_type' is permanent."""
        assert _is_permanent_dispatch_failure(
            "Daemon payload missing required key 'event_type' (keys=['session_id'])"
        )

    def test_db_error_is_not_permanent(self) -> None:
        """A database connection error is NOT a permanent failure."""
        assert not _is_permanent_dispatch_failure(
            "Handler 'x' failed: asyncpg.exceptions.TooManyConnectionsError: too many clients"
        )

    def test_generic_error_is_not_permanent(self) -> None:
        """A generic runtime error is NOT a permanent failure."""
        assert not _is_permanent_dispatch_failure("RuntimeError: something went wrong")

    def test_empty_error_message_is_not_permanent(self) -> None:
        """An empty error message is NOT classified as permanent."""
        assert not _is_permanent_dispatch_failure("")

    def test_network_error_is_not_permanent(self) -> None:
        """A Kafka network error is NOT a permanent failure."""
        assert not _is_permanent_dispatch_failure(
            "KafkaConnectionError: Broker not available"
        )


# =============================================================================
# Tests: OMN-2423 — NACK loop prevention (V1 + V2 end-to-end verification)
# =============================================================================


@pytest.mark.unit
class TestNACKLoopPrevention:
    """End-to-end verification that missing envelope fields don't cause NACK loops.

    V1 (OMN-2423): reshape handles missing correlation_id.
    V2 (OMN-2423): reshape handles missing emitted_at with UTC fallback.

    These tests prove that when omniclaude sends a hook event where the Kafka
    consumer strips session_id and/or correlation_id from the envelope payload,
    the reshape pipeline still produces a valid ModelClaudeCodeHookEvent rather
    than raising ValueError (which caused infinite NACK loops).
    """

    @pytest.mark.asyncio
    async def test_missing_correlation_id_does_not_raise(self) -> None:
        """V1: Daemon payload with missing correlation_id reshapes without ValueError.

        Simulates the scenario where _reconstruct_payload_from_envelope cannot
        recover correlation_id from the envelope (because ModelEventEnvelope
        absorbed it but did not set it on the payload dict).
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import UUID

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import ModelEffectContext
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        # Daemon payload that reaches _handle WITHOUT correlation_id
        # (stripped by envelope deserialization and not recoverable from metadata)
        daemon_payload_no_corr_id: dict[str, Any] = {
            "event_type": "UserPromptSubmit",
            "session_id": "test-session-nack-v1",
            "emitted_at": "2026-02-20T12:00:00+00:00",
            "prompt_preview": "Fix the NACK loop",
        }

        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock()
        test_correlation_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_classifier,
            correlation_id=test_correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=daemon_payload_no_corr_id,
            correlation_id=test_correlation_id,
            metadata=ModelEnvelopeMetadata(tags={"message_category": "command"}),
        )
        context = ModelEffectContext(
            correlation_id=test_correlation_id,
            envelope_id=UUID("00000000-0000-0000-0000-000000000010"),
        )

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.event_type = "UserPromptSubmit"

        with patch(
            "omniintelligence.nodes.node_claude_hook_event_effect.handlers.route_hook_event",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            # Must NOT raise ValueError — that was the bug causing NACK loops
            result = await handler(envelope, context)

            assert result == "ok"
            mock_route.assert_called_once()

            event = mock_route.call_args.kwargs["event"]
            assert event.event_type.value == "UserPromptSubmit"
            assert event.session_id == "test-session-nack-v1"

    @pytest.mark.asyncio
    async def test_missing_session_id_and_correlation_id_does_not_raise(self) -> None:
        """V2: Daemon payload with missing session_id and correlation_id reshapes without ValueError.

        Simulates the envelope stripping scenario where session_id and
        correlation_id are absent (stripped by the envelope deserializer or never
        present).  emitted_at is present so _needs_daemon_reshape() selects the
        daemon reshape path.  The reshape must fall back to 'unknown' for
        session_id and generate a new uuid4() for correlation_id.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import UUID

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import ModelEffectContext
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        # Daemon payload with emitted_at present but session_id and correlation_id absent.
        # emitted_at is required for _needs_daemon_reshape() to select the daemon path.
        # session_id and correlation_id are stripped by the envelope deserializer.
        minimal_daemon_payload: dict[str, Any] = {
            "event_type": "Stop",
            "emitted_at": "2026-02-20T12:00:00+00:00",
            # session_id absent -- must fall back to "unknown"
            # correlation_id absent -- must generate uuid4()
        }

        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock()
        test_correlation_id = UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_classifier,
            correlation_id=test_correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=minimal_daemon_payload,
            correlation_id=test_correlation_id,
            metadata=ModelEnvelopeMetadata(tags={"message_category": "command"}),
        )
        context = ModelEffectContext(
            correlation_id=test_correlation_id,
            envelope_id=UUID("00000000-0000-0000-0000-000000000011"),
        )

        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.event_type = "Stop"

        with patch(
            "omniintelligence.nodes.node_claude_hook_event_effect.handlers.route_hook_event",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            # Must NOT raise ValueError — that was the bug causing NACK loops
            result = await handler(envelope, context)

            assert result == "ok"
            mock_route.assert_called_once()

            event = mock_route.call_args.kwargs["event"]
            assert event.event_type.value == "Stop"
            # session_id falls back to "unknown"
            assert event.session_id == "unknown"
