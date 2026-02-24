# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for _extract_prompt_from_payload with daemon payload formats.

Validates all five extraction strategies:
    1. ``prompt`` in model_fields (direct attribute on a subclass)
    2. ``prompt`` in model_extra (base class with extra="allow")
    3. ``prompt_b64`` in model_extra (daemon format, base64-encoded)
    4. ``prompt_preview`` in model_extra (daemon format, truncated fallback)
    5. Not found (empty payload)

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import base64

import pytest
from pydantic import ConfigDict

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    _extract_prompt_from_payload,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    ModelClaudeCodeHookEventPayload,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: subclass with ``prompt`` as a declared model field (Strategy 1)
# ---------------------------------------------------------------------------


class _PayloadWithPromptField(ModelClaudeCodeHookEventPayload):
    """Subclass that declares ``prompt`` as a real Pydantic field.

    Used to exercise Strategy 1 (direct_attribute) which checks
    ``model_fields`` on the payload class.
    """

    model_config = ConfigDict(frozen=True, extra="allow", from_attributes=True)

    prompt: str = ""


# ===========================================================================
# Tests
# ===========================================================================


class TestExtractPromptFromPayload:
    """Validate _extract_prompt_from_payload for all extraction strategies."""

    # -- Strategy 1: prompt as a declared model field -----------------------

    def test_extracts_prompt_from_direct_attribute(self) -> None:
        """Strategy 1: prompt declared in model_fields on a subclass."""
        payload = _PayloadWithPromptField(prompt="What does this do?")
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "What does this do?"
        assert source == "direct_attribute"

    def test_skips_empty_direct_attribute(self) -> None:
        """Strategy 1 is skipped when prompt field is empty string."""
        payload = _PayloadWithPromptField(prompt="")
        prompt, source = _extract_prompt_from_payload(payload)
        # Should fall through to strategy 5 (not_found)
        assert prompt == ""
        assert source == "not_found"

    # -- Strategy 2: prompt in model_extra ----------------------------------

    def test_extracts_prompt_from_model_extra(self) -> None:
        """Strategy 2: prompt key in model_extra via extra='allow'."""
        payload = ModelClaudeCodeHookEventPayload(prompt="What does this do?")
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "What does this do?"
        assert source == "model_extra"

    def test_skips_empty_prompt_in_model_extra(self) -> None:
        """Strategy 2 is skipped when prompt in model_extra is empty."""
        payload = ModelClaudeCodeHookEventPayload(prompt="")
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == ""
        assert source == "not_found"

    # -- Strategy 3: prompt_b64 in model_extra ------------------------------

    def test_extracts_prompt_b64_from_model_extra(self) -> None:
        """Strategy 3: base64-encoded full prompt from daemon format."""
        full_prompt = "Fix the authentication bug in login.py"
        b64 = base64.b64encode(full_prompt.encode()).decode()
        payload = ModelClaudeCodeHookEventPayload(
            prompt_b64=b64,
            prompt_preview="Fix the auth...",
            prompt_length=len(full_prompt),
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == full_prompt
        assert source == "prompt_b64"

    def test_prompt_b64_decodes_unicode(self) -> None:
        """Strategy 3 correctly decodes UTF-8 content from base64."""
        full_prompt = "Fix the bug with accents: cafe\u0301"
        b64 = base64.b64encode(full_prompt.encode("utf-8")).decode()
        payload = ModelClaudeCodeHookEventPayload(prompt_b64=b64)
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == full_prompt
        assert source == "prompt_b64"

    # -- Strategy 4: prompt_preview in model_extra --------------------------

    def test_falls_back_to_prompt_preview(self) -> None:
        """Strategy 4: when prompt_b64 is absent, use prompt_preview."""
        payload = ModelClaudeCodeHookEventPayload(
            prompt_preview="Fix the bug in...",
            prompt_length=150,
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "Fix the bug in..."
        assert source == "prompt_preview"

    def test_falls_back_to_prompt_preview_on_invalid_b64(self) -> None:
        """Strategy 4: invalid base64 in prompt_b64 falls back to prompt_preview."""
        payload = ModelClaudeCodeHookEventPayload(
            prompt_b64="not-valid-base64!!!",
            prompt_preview="Fix the bug in...",
            prompt_length=150,
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "Fix the bug in..."
        assert source == "prompt_preview"

    # -- Strategy 5: not found ----------------------------------------------

    def test_returns_not_found_for_empty_payload(self) -> None:
        """Strategy 5: no prompt fields at all."""
        payload = ModelClaudeCodeHookEventPayload()
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == ""
        assert source == "not_found"

    # -- Precedence ---------------------------------------------------------

    def test_prefers_prompt_over_prompt_b64(self) -> None:
        """Strategy 2 (prompt) takes precedence over strategy 3 (prompt_b64)."""
        full_prompt = "Fix the authentication bug"
        b64 = base64.b64encode(full_prompt.encode()).decode()
        payload = ModelClaudeCodeHookEventPayload(
            prompt="Direct prompt text",
            prompt_b64=b64,
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "Direct prompt text"
        assert source == "model_extra"

    def test_prefers_prompt_b64_over_prompt_preview(self) -> None:
        """Strategy 3 (prompt_b64) takes precedence over strategy 4 (prompt_preview)."""
        full_prompt = "Complete implementation of the feature"
        b64 = base64.b64encode(full_prompt.encode()).decode()
        payload = ModelClaudeCodeHookEventPayload(
            prompt_b64=b64,
            prompt_preview="Complete impl...",
            prompt_length=len(full_prompt),
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == full_prompt
        assert source == "prompt_b64"

    def test_direct_attribute_takes_precedence_over_everything(self) -> None:
        """Strategy 1 (direct_attribute) beats strategy 2/3/4."""
        full_prompt = "From b64"
        b64 = base64.b64encode(full_prompt.encode()).decode()
        payload = _PayloadWithPromptField(
            prompt="Direct field value",
            prompt_b64=b64,
            prompt_preview="Preview text",
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "Direct field value"
        assert source == "direct_attribute"

    # -- End-to-end daemon wire format --------------------------------------

    def test_real_daemon_wire_format(self) -> None:
        """End-to-end test with actual daemon wire payload shape."""
        full_prompt = "/parallel-solve"
        payload = ModelClaudeCodeHookEventPayload(
            prompt_preview="/parallel-solve ",
            prompt_length=16,
            prompt_b64=base64.b64encode(full_prompt.encode()).decode(),
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == full_prompt
        assert source == "prompt_b64"

    def test_daemon_format_without_b64_uses_preview(self) -> None:
        """Daemon payload that only has prompt_preview (no b64 field)."""
        payload = ModelClaudeCodeHookEventPayload(
            prompt_preview="Explain the architecture of...",
            prompt_length=245,
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == "Explain the architecture of..."
        assert source == "prompt_preview"

    def test_multiline_prompt_via_b64(self) -> None:
        """Base64 encoding preserves multi-line prompts."""
        full_prompt = "Line one\nLine two\nLine three"
        b64 = base64.b64encode(full_prompt.encode()).decode()
        payload = ModelClaudeCodeHookEventPayload(
            prompt_b64=b64,
            prompt_preview="Line one...",
        )
        prompt, source = _extract_prompt_from_payload(payload)
        assert prompt == full_prompt
        assert source == "prompt_b64"
