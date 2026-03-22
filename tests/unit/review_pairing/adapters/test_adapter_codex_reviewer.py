# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the Codex CLI adapter.

Covers: NDJSON parsing, subprocess mocking, timeout, missing binary,
interleaved events, happy path.

Reference: OMN-5792
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.review_pairing.adapters.adapter_codex_reviewer import (
    _extract_assistant_content,
    async_parse_raw,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
)


def _make_ndjson_event(event_type: str, role: str = "", content: str = "") -> str:
    """Build an NDJSON event matching real Codex CLI output format.

    Codex uses: {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
    """
    if event_type == "item.completed" and role == "assistant":
        # Real Codex format for agent messages.
        return json.dumps(
            {
                "type": "item.completed",
                "item": {"id": "item_0", "type": "agent_message", "text": content},
            }
        )
    # Non-agent events (thread.started, turn.started, etc.)
    event: dict[str, object] = {"type": event_type}
    if role:
        event["role"] = role
    if content:
        event["content"] = content
    return json.dumps(event)


def _well_formed_findings_json() -> str:
    return json.dumps(
        [
            {
                "category": "architecture",
                "severity": "critical",
                "title": "Missing retry logic",
                "description": "No backoff on failure",
                "evidence": "Task 3 step 2",
                "proposed_fix": "Add exponential backoff",
                "location": "task-3",
            },
        ]
    )


# ---------------------------------------------------------------------------
# _extract_assistant_content
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractAssistantContent:
    def test_extracts_last_assistant_message(self) -> None:
        ndjson = "\n".join(
            [
                _make_ndjson_event("thread.started", "", "Starting"),
                _make_ndjson_event("item.completed", "assistant", "First response"),
                _make_ndjson_event(
                    "item.completed", "assistant", _well_formed_findings_json()
                ),
            ]
        )
        content = _extract_assistant_content(ndjson)
        assert content == _well_formed_findings_json()

    def test_returns_none_for_no_assistant_events(self) -> None:
        ndjson = "\n".join(
            [
                _make_ndjson_event("thread.started", "", "Starting"),
                _make_ndjson_event("tool_use", "", "Running tool"),
            ]
        )
        assert _extract_assistant_content(ndjson) is None

    def test_ignores_tool_use_events(self) -> None:
        ndjson = "\n".join(
            [
                _make_ndjson_event("item.completed", "", "tool output"),
                _make_ndjson_event(
                    "item.completed", "assistant", _well_formed_findings_json()
                ),
                _make_ndjson_event("turn.started", "", "result"),
            ]
        )
        content = _extract_assistant_content(ndjson)
        assert content == _well_formed_findings_json()

    def test_skips_empty_assistant_content(self) -> None:
        ndjson = "\n".join(
            [
                _make_ndjson_event("item.completed", "assistant", ""),
                _make_ndjson_event("item.completed", "assistant", "Real content"),
            ]
        )
        content = _extract_assistant_content(ndjson)
        assert content == "Real content"

    def test_handles_malformed_ndjson_lines(self) -> None:
        ndjson = "not json\n" + _make_ndjson_event(
            "item.completed", "assistant", "Valid"
        )
        content = _extract_assistant_content(ndjson)
        assert content == "Valid"

    def test_handles_empty_input(self) -> None:
        assert _extract_assistant_content("") is None

    def test_handles_whitespace_only(self) -> None:
        assert _extract_assistant_content("   \n  \n  ") is None


# ---------------------------------------------------------------------------
# async_parse_raw
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAsyncParseRaw:
    @pytest.mark.asyncio
    async def test_missing_codex_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            result = await async_parse_raw("# Test Plan")

        assert isinstance(result, ModelExternalReviewResult)
        assert result.success is False
        assert result.error == "codex CLI not found"
        assert result.model == "codex"

    @pytest.mark.asyncio
    async def test_happy_path_with_findings(self) -> None:
        ndjson_output = _make_ndjson_event(
            "item.completed", "assistant", _well_formed_findings_json()
        )

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(ndjson_output.encode(), b""))

        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ),
        ):
            result = await async_parse_raw("# Test Plan")

        assert result.success is True
        assert result.model == "codex"
        assert result.prompt_version == PROMPT_VERSION
        assert result.result_count == 1
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "ai-reviewer:codex:architecture"

    @pytest.mark.asyncio
    async def test_no_assistant_completion(self) -> None:
        ndjson_output = _make_ndjson_event("thread.started", "", "Starting")

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(ndjson_output.encode(), b""))

        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ),
        ):
            result = await async_parse_raw("# Test Plan")

        assert result.success is False
        assert "No recoverable assistant completion" in (result.error or "")

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=TimeoutError())
        mock_process.kill = MagicMock()

        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ),
            patch("asyncio.wait_for", side_effect=TimeoutError()),
        ):
            result = await async_parse_raw(
                "# Test Plan",
                timeout_seconds=180.0,
            )

        assert result.success is False
        assert "timed out after 180s" in (result.error or "")

    @pytest.mark.asyncio
    async def test_interleaved_tool_events(self) -> None:
        """Only assistant message events should be considered."""
        ndjson_output = "\n".join(
            [
                _make_ndjson_event("item.completed", "", "tool stuff"),
                _make_ndjson_event("turn.started", "", "result data"),
                _make_ndjson_event(
                    "item.completed", "assistant", _well_formed_findings_json()
                ),
                _make_ndjson_event("item.completed", "", "more tool"),
            ]
        )

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(ndjson_output.encode(), b""))

        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ),
        ):
            result = await async_parse_raw("# Plan")

        assert result.success is True
        assert result.result_count == 1

    @pytest.mark.asyncio
    async def test_subprocess_exception(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=OSError("Permission denied"),
            ),
        ):
            result = await async_parse_raw("# Plan")

        assert result.success is False
        assert "Permission denied" in (result.error or "")

    @pytest.mark.asyncio
    async def test_prompt_version_in_result(self) -> None:
        with patch("shutil.which", return_value=None):
            result = await async_parse_raw("# Plan")
        assert result.prompt_version == PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_malformed_assistant_content(self) -> None:
        """Assistant returns text, not JSON; findings should be empty."""
        ndjson_output = _make_ndjson_event(
            "item.completed", "assistant", "I found some issues but not in JSON"
        )

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(ndjson_output.encode(), b""))

        with (
            patch("shutil.which", return_value="/usr/bin/codex"),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ),
        ):
            result = await async_parse_raw("# Plan")

        assert result.success is True
        assert result.result_count == 0
        assert result.findings == []
