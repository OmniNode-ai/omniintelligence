# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit-contract tests for _reshape_daemon_hook_payload_v1.

Validates that the reshape function correctly transforms flat daemon-shaped
payloads into the nested structure expected by ModelClaudeCodeHookEvent.

The emit daemon sends a flat dict with envelope keys (event_type, session_id,
correlation_id, emitted_at) mixed alongside domain-specific payload keys.
ModelClaudeCodeHookEvent expects a nested ``payload`` sub-dict, so the reshape
function splits envelope keys from payload keys and returns the canonical shape.

Related:
    - Bus audit project: daemon emits flat dicts, reshape bridges the gap
"""

from __future__ import annotations

from typing import Any

import pytest

# Private import is intentional: _reshape_daemon_hook_payload_v1 is an internal
# helper, but we test it directly to ensure the daemon-to-model contract is
# upheld without requiring a full dispatch-engine integration test.
from omniintelligence.runtime.dispatch_handlers import (
    _reshape_daemon_hook_payload_v1,
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
    """Validate that missing required keys produce clear ValueError messages."""

    def test_reshape_missing_emitted_at(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing emitted_at raises ValueError with key name and sorted keys."""
        del daemon_wire_payload["emitted_at"]

        with pytest.raises(ValueError, match="emitted_at") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        # Error message must include sorted keys for diagnostics
        error_msg = str(exc_info.value)
        assert "keys=" in error_msg

    def test_reshape_missing_event_type(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing event_type raises ValueError with key name and sorted keys."""
        del daemon_wire_payload["event_type"]

        with pytest.raises(ValueError, match="event_type") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "keys=" in error_msg

    def test_reshape_missing_session_id(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing session_id raises ValueError with key name and sorted keys."""
        del daemon_wire_payload["session_id"]

        with pytest.raises(ValueError, match="session_id") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "keys=" in error_msg

    def test_reshape_missing_correlation_id(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload missing correlation_id raises ValueError with key name and sorted keys."""
        del daemon_wire_payload["correlation_id"]

        with pytest.raises(ValueError, match="correlation_id") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "keys=" in error_msg

    def test_reshape_empty_payload(self) -> None:
        """An empty dict raises ValueError for the first missing required key."""
        with pytest.raises(ValueError, match="missing required key") as exc_info:
            _reshape_daemon_hook_payload_v1({})

        # Error message should include the empty keys list for diagnostics
        error_msg = str(exc_info.value)
        assert "keys=" in error_msg


# =============================================================================
# Tests: Null Value for Required Keys
# =============================================================================


@pytest.mark.unit
class TestReshapeNullRequiredKeys:
    """Validate that null values for required keys produce clear ValueError messages.

    This exercises the second validation branch in _reshape_daemon_hook_payload_v1:
    the key IS present in the dict but its value is None.  This is distinct from
    the 'missing key' branch tested by TestReshapeMissingRequiredKeys.
    """

    def test_reshape_null_event_type(self, daemon_wire_payload: dict[str, Any]) -> None:
        """Payload with event_type=None raises ValueError with 'null value' message."""
        daemon_wire_payload["event_type"] = None

        with pytest.raises(ValueError, match="null value for required key") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "event_type" in error_msg
        assert "keys=" in error_msg

    def test_reshape_null_session_id(self, daemon_wire_payload: dict[str, Any]) -> None:
        """Payload with session_id=None raises ValueError with 'null value' message."""
        daemon_wire_payload["session_id"] = None

        with pytest.raises(ValueError, match="null value for required key") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "session_id" in error_msg
        assert "keys=" in error_msg

    def test_reshape_null_correlation_id(
        self, daemon_wire_payload: dict[str, Any]
    ) -> None:
        """Payload with correlation_id=None raises ValueError with 'null value' message."""
        daemon_wire_payload["correlation_id"] = None

        with pytest.raises(ValueError, match="null value for required key") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "correlation_id" in error_msg
        assert "keys=" in error_msg

    def test_reshape_null_emitted_at(self, daemon_wire_payload: dict[str, Any]) -> None:
        """Payload with emitted_at=None raises ValueError with 'null value' message."""
        daemon_wire_payload["emitted_at"] = None

        with pytest.raises(ValueError, match="null value for required key") as exc_info:
            _reshape_daemon_hook_payload_v1(daemon_wire_payload)

        error_msg = str(exc_info.value)
        assert "emitted_at" in error_msg
        assert "keys=" in error_msg


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
