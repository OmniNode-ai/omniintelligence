# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for handle_post_tool_use handler in Claude Hook Event Effect.

Validates that PostToolUse and PostToolUseFailure events are persisted
to omniintelligence.agent_actions via the database repository.

Related:
    - OMN-2984: Wire PostToolUse write path to omniintelligence.agent_actions
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    handle_post_tool_use,
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_post_tool_use_event(
    *,
    tool_name: str = "Bash",
    file_path: str | None = None,
    session_id: str = "test-session-abc",
    failure: bool = False,
) -> ModelClaudeCodeHookEvent:
    """Create a PostToolUse (or PostToolUseFailure) hook event for testing."""
    extra: dict[str, object] = {"tool_name": tool_name}
    if file_path is not None:
        extra["file_path"] = file_path
    if failure:
        extra["error"] = "command not found"

    event_type = (
        EnumClaudeCodeHookEventType.POST_TOOL_USE_FAILURE
        if failure
        else EnumClaudeCodeHookEventType.POST_TOOL_USE
    )
    return ModelClaudeCodeHookEvent(
        event_type=event_type,
        session_id=session_id,
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=ModelClaudeCodeHookEventPayload(**extra),
    )


class MockRepository:
    """Test double for ProtocolPatternRepository that records execute() calls."""

    def __init__(self, *, execute_side_effect: Exception | None = None) -> None:
        self._calls: list[tuple[str, tuple[object, ...]]] = []
        self._execute_side_effect = execute_side_effect

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        return []

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        return None

    async def execute(self, query: str, *args: object) -> str:
        self._calls.append((query, args))
        if self._execute_side_effect is not None:
            raise self._execute_side_effect
        return "INSERT 0 1"

    @property
    def execute_calls(self) -> list[tuple[str, tuple[object, ...]]]:
        return self._calls


# =============================================================================
# Tests: handle_post_tool_use (direct)
# =============================================================================


@pytest.mark.unit
class TestHandlePostToolUse:
    """Unit tests for handle_post_tool_use."""

    @pytest.mark.asyncio
    async def test_no_repository_returns_success_noop(self) -> None:
        """Without a repository, PostToolUse returns SUCCESS as a no-op."""
        event = _make_post_tool_use_event()
        result = await handle_post_tool_use(event=event, repository=None)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata.get("db_write") == "skipped_no_repository"

    @pytest.mark.asyncio
    async def test_writes_to_agent_actions_on_success(self) -> None:
        """PostToolUse event should INSERT one row into agent_actions."""
        repo = MockRepository()
        event = _make_post_tool_use_event(tool_name="Read", file_path="/some/file.py")

        result = await handle_post_tool_use(event=event, repository=repo)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata.get("db_write") == "ok"
        assert len(repo.execute_calls) == 1

        _query, args = repo.execute_calls[0]
        # args: (id, session_id, action_type, tool_name, file_path, status, error_message, created_at)
        assert args[1] == "test-session-abc"  # session_id
        assert args[2] == "tool_use"  # action_type
        assert args[3] == "Read"  # tool_name
        assert args[4] == "/some/file.py"  # file_path
        assert args[5] == "success"  # status
        assert args[6] is None  # error_message (no error)

    @pytest.mark.asyncio
    async def test_writes_failure_event_to_agent_actions(self) -> None:
        """PostToolUseFailure should write action_type=tool_use_failure and status=error."""
        repo = MockRepository()
        event = _make_post_tool_use_event(tool_name="Bash", failure=True)

        result = await handle_post_tool_use(event=event, repository=repo)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert len(repo.execute_calls) == 1

        _query, args = repo.execute_calls[0]
        assert args[2] == "tool_use_failure"  # action_type
        assert args[3] == "Bash"  # tool_name
        assert args[5] == "error"  # status
        assert args[6] is not None  # error_message populated

    @pytest.mark.asyncio
    async def test_null_file_path_when_not_in_payload(self) -> None:
        """When no file_path is in the payload, the column should be NULL."""
        repo = MockRepository()
        event = _make_post_tool_use_event(tool_name="Bash")  # no file_path

        await handle_post_tool_use(event=event, repository=repo)

        _query, args = repo.execute_calls[0]
        assert args[4] is None  # file_path is NULL

    @pytest.mark.asyncio
    async def test_db_error_returns_partial_status(self) -> None:
        """DB execute failure should degrade to PARTIAL, not raise."""
        repo = MockRepository(execute_side_effect=RuntimeError("connection refused"))
        event = _make_post_tool_use_event()

        result = await handle_post_tool_use(event=event, repository=repo)

        assert result.status == EnumHookProcessingStatus.PARTIAL
        assert result.metadata.get("db_write") == "failed"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_session_id_propagated(self) -> None:
        """The session_id from the event must be stored in agent_actions."""
        repo = MockRepository()
        event = _make_post_tool_use_event(session_id="unique-session-xyz-999")

        await handle_post_tool_use(event=event, repository=repo)

        _query, args = repo.execute_calls[0]
        assert args[1] == "unique-session-xyz-999"


# =============================================================================
# Tests: route_hook_event routing
# =============================================================================


@pytest.mark.unit
class TestRouteHookEventPostToolUse:
    """Tests that route_hook_event correctly routes PostToolUse events."""

    @pytest.mark.asyncio
    async def test_post_tool_use_routed_to_handler(self) -> None:
        """route_hook_event should call handle_post_tool_use for POST_TOOL_USE."""
        repo = MockRepository()
        event = _make_post_tool_use_event(tool_name="Write")

        result = await route_hook_event(event=event, repository=repo)

        # Result should indicate it went through the post_tool_use handler
        assert result.status in (
            EnumHookProcessingStatus.SUCCESS,
            EnumHookProcessingStatus.PARTIAL,
        )
        assert result.metadata.get("handler") == "post_tool_use"
        # DB should have been written
        assert len(repo.execute_calls) == 1

    @pytest.mark.asyncio
    async def test_post_tool_use_failure_routed_to_handler(self) -> None:
        """route_hook_event should call handle_post_tool_use for POST_TOOL_USE_FAILURE."""
        repo = MockRepository()
        event = _make_post_tool_use_event(tool_name="Bash", failure=True)

        result = await route_hook_event(event=event, repository=repo)

        assert result.metadata.get("handler") == "post_tool_use"
        _query, args = repo.execute_calls[0]
        assert args[2] == "tool_use_failure"

    @pytest.mark.asyncio
    async def test_post_tool_use_without_repository_is_noop(self) -> None:
        """route_hook_event without repository: PostToolUse returns no-op success."""
        event = _make_post_tool_use_event()

        result = await route_hook_event(event=event, repository=None)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata.get("db_write") == "skipped_no_repository"

    @pytest.mark.asyncio
    async def test_user_prompt_submit_unaffected_by_repository(self) -> None:
        """UserPromptSubmit routing should be unaffected by the new repository param."""
        repo = MockRepository()
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="session-prompt",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(),
        )

        result = await route_hook_event(event=event, repository=repo)

        # UserPromptSubmit handler does not use repository; DB should NOT be touched
        assert len(repo.execute_calls) == 0
        # Result status should reflect FAILED (no prompt in payload) or success
        # — the important thing is the handler ran and repo was NOT called
        assert result.event_type == str(EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT)
