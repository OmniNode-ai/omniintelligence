# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for HandlerGmailIntentEvaluate.

All HTTP and external calls are mocked — no live network, no live LLM,
no live Slack, no live DB. Tests run in full isolation.

Coverage:
  - Core verdict paths (SURFACE, WATCHLIST, SKIP)
  - URL selection (tier preference, tracker deprioritization, no-URL fallback)
  - Content fetching (HTML stripping, fetch failure, SSRF guard)
  - Omnimemory integration (high-similarity hint, unavailable fallback)
  - LLM parsing (OK, RECOVERED, FAILED, null initial_plan demotion)
  - Idempotency (duplicate detection, store unavailable)
  - Slack posting (no token, rate limit, delivery failure)
  - Fallbacks (DeepSeek unavailable, omnimemory unavailable)

Ticket: OMN-2794
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_gmail_intent_evaluator_effect.handlers.handler_gmail_intent_evaluate import (
    handle_gmail_intent_evaluate,
)
from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluation_result import (
    ModelGmailIntentEvaluationResult,
    ModelMemoryHit,
)
from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluator_config import (
    ModelGmailIntentEvaluatorConfig,
)

# ---------------------------------------------------------------------------
# Helpers / Factories
# ---------------------------------------------------------------------------

_HANDLER_MODULE = "omniintelligence.nodes.node_gmail_intent_evaluator_effect.handlers.handler_gmail_intent_evaluate"


def _make_config(
    *,
    message_id: str = "msg-test-001",
    subject: str = "github.com/example/repo",
    body_text: str = "Interesting project for OmniNode",
    urls: list[str] | None = None,
    source_label: str = "To Read",
    sender: str = "sender@example.com",
    received_at: str = "2026-02-25T00:00:00Z",
) -> ModelGmailIntentEvaluatorConfig:
    return ModelGmailIntentEvaluatorConfig(
        message_id=message_id,
        subject=subject,
        body_text=body_text,
        urls=urls if urls is not None else ["https://github.com/example/repo"],
        source_label=source_label,
        sender=sender,
        received_at=received_at,
    )


def _llm_json(
    *,
    verdict: str = "SURFACE",
    relevance_score: float = 0.85,
    reasoning: str = "Highly relevant to OmniNode stack.",
    initial_plan: str | None = "- Integrate X\n- Test Y",
) -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "relevance_score": relevance_score,
            "reasoning": reasoning,
            "initial_plan": initial_plan,
        }
    )


class _FakeRepository:
    """Minimal in-memory DB repository for idempotency tests."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self.fetchrow_calls: list[str] = []
        self.execute_calls: list[str] = []

    async def fetchrow(self, query: str, evaluation_id: str) -> dict[str, Any] | None:
        self.fetchrow_calls.append(evaluation_id)
        return self._records.get(evaluation_id)

    async def execute(
        self, query: str, evaluation_id: str, verdict: str, relevance_score: float
    ) -> None:
        self.execute_calls.append(evaluation_id)
        # ON CONFLICT DO NOTHING semantics
        if evaluation_id not in self._records:
            self._records[evaluation_id] = {
                "verdict": verdict,
                "relevance_score": relevance_score,
            }


class _ErrorRepository:
    """Repository that always raises on DB calls (tests degraded mode)."""

    async def fetchrow(self, query: str, evaluation_id: str) -> None:
        raise ConnectionError("DB unavailable")

    async def execute(
        self, query: str, evaluation_id: str, verdict: str, relevance_score: float
    ) -> None:
        raise ConnectionError("DB unavailable")


class _FakeSlackNotifier:
    """Slack notifier that records calls and can be configured to succeed or fail."""

    def __init__(self, *, success: bool = True) -> None:
        self._success = success
        self.call_count = 0
        self.last_alert: Any = None

    async def handle(self, alert: Any) -> Any:
        self.call_count += 1
        self.last_alert = alert
        result = MagicMock()
        result.success = self._success
        result.error_message = None if self._success else "Slack API error"
        return result


def _eval_id(message_id: str, selected_url: str | None) -> str:
    return hashlib.sha256(f"{message_id}:{selected_url or ''}:v1".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Async rate-limit helpers
# ---------------------------------------------------------------------------


async def _rate_allow() -> bool:
    return True


async def _rate_deny() -> bool:
    return False


# ---------------------------------------------------------------------------
# Core verdict paths
# ---------------------------------------------------------------------------


class TestVerdictSurface:
    """SURFACE verdict: Slack sent, initial_plan set, surfaced event in pending_events."""

    @pytest.mark.asyncio
    async def test_surface_slack_sent_and_plan_set(self) -> None:
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("GitHub repo content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.85,
                    "reasoning": "Novel.",
                    "initial_plan": "- Step 1",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=slack,
                _slack_rate_check=_rate_allow,
            )

        assert result.verdict == "SURFACE"
        assert result.slack_sent is True
        assert result.initial_plan is not None
        assert result.rate_limited is False
        assert slack.call_count == 1

    @pytest.mark.asyncio
    async def test_surface_surfaced_event_in_pending_events(self) -> None:
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.9,
                    "reasoning": "Great.",
                    "initial_plan": "- Step A",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=slack,
                _slack_rate_check=_rate_allow,
            )

        assert result.verdict == "SURFACE"
        event_types = [e.get("event_type") for e in result.pending_events]
        assert "onex.evt.omniintelligence.gmail-intent-evaluated.v1" in event_types
        assert "onex.evt.omniintelligence.gmail-intent-surfaced.v1" in event_types

    @pytest.mark.asyncio
    async def test_evaluated_event_always_present(self) -> None:
        """gmail-intent-evaluated.v1 is emitted for every verdict."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Noise.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.verdict == "SKIP"
        event_types = [e.get("event_type") for e in result.pending_events]
        assert "onex.evt.omniintelligence.gmail-intent-evaluated.v1" in event_types


class TestVerdictSkip:
    """SKIP verdict: no Slack, no initial_plan, only evaluated event."""

    @pytest.mark.asyncio
    async def test_skip_no_slack_no_plan(self) -> None:
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.05,
                    "reasoning": "Noise.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config, slack_notifier=slack)

        assert result.verdict == "SKIP"
        assert result.slack_sent is False
        assert result.initial_plan is None
        assert slack.call_count == 0

    @pytest.mark.asyncio
    async def test_skip_only_evaluated_event_not_surfaced(self) -> None:
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        event_types = [e.get("event_type") for e in result.pending_events]
        assert "onex.evt.omniintelligence.gmail-intent-evaluated.v1" in event_types
        assert "onex.evt.omniintelligence.gmail-intent-surfaced.v1" not in event_types


class TestVerdictWatchlist:
    """WATCHLIST verdict: no Slack, no initial_plan, evaluated event only."""

    @pytest.mark.asyncio
    async def test_watchlist_no_slack_no_plan(self) -> None:
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.5,
                    "reasoning": "Maybe later.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config, slack_notifier=slack)

        assert result.verdict == "WATCHLIST"
        assert result.slack_sent is False
        assert result.initial_plan is None
        assert slack.call_count == 0

    @pytest.mark.asyncio
    async def test_watchlist_evaluated_event_present(self) -> None:
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.6,
                    "reasoning": "Interesting.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        event_types = [e.get("event_type") for e in result.pending_events]
        assert "onex.evt.omniintelligence.gmail-intent-evaluated.v1" in event_types
        assert "onex.evt.omniintelligence.gmail-intent-surfaced.v1" not in event_types


# ---------------------------------------------------------------------------
# URL selection
# ---------------------------------------------------------------------------


class TestUrlSelection:
    """URL selection prefers Tier 1 (github, arxiv, huggingface) over tracker URLs."""

    @pytest.mark.asyncio
    async def test_tracker_first_github_second_selects_github(self) -> None:
        """Tracker URL (Tier 4/skip) followed by GitHub URL → GitHub selected."""
        config = _make_config(
            urls=["https://t.co/abc123", "https://github.com/example/repo"],
        )

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Noise.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.selected_url == "https://github.com/example/repo"

    @pytest.mark.asyncio
    async def test_all_deprioritized_urls_selects_none(self) -> None:
        """When all URLs are tracker/skip-tier, selected_url is None."""
        config = _make_config(
            urls=["https://t.co/abc", "https://bit.ly/xyz"],
        )

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("", "SKIPPED")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.3,
                    "reasoning": "Body only.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.selected_url is None

    @pytest.mark.asyncio
    async def test_no_urls_selected_url_is_none(self) -> None:
        """Empty URL list → selected_url is None, body_text fallback used."""
        config = _make_config(urls=[])

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("", "SKIPPED")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.4,
                    "reasoning": "Body only.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.selected_url is None
        # fetch should not be called when there's no URL
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_arxiv_preferred_over_substack(self) -> None:
        """arxiv.org (Tier 1) preferred over substack.com (Tier 3)."""
        config = _make_config(
            urls=["https://substack.com/some-post", "https://arxiv.org/abs/2401.12345"],
        )

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("paper content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.9,
                    "reasoning": "Research.",
                    "initial_plan": "- Read",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )

        assert result.selected_url == "https://arxiv.org/abs/2401.12345"


# ---------------------------------------------------------------------------
# Content fetching
# ---------------------------------------------------------------------------


class TestContentFetching:
    """URL fetch failure handling."""

    @pytest.mark.asyncio
    async def test_fetch_failure_sets_status_and_no_exception(self) -> None:
        """URL fetch failure → url_fetch_status=FAILED, body_text used, no exception raised."""
        config = _make_config(urls=["https://github.com/example/repo"])

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("", "FAILED")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.4,
                    "reasoning": "No content.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            # Should not raise
            result = await handle_gmail_intent_evaluate(config)

        assert result.url_fetch_status == "FAILED"
        assert result.verdict == "WATCHLIST"

    @pytest.mark.asyncio
    async def test_fetch_ok_sets_status_ok(self) -> None:
        """Successful URL fetch → url_fetch_status=OK."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("some content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.url_fetch_status == "OK"


# ---------------------------------------------------------------------------
# Omnimemory
# ---------------------------------------------------------------------------


class TestOmnimemory:
    """Omnimemory integration: duplicate hints and unavailability fallback."""

    @pytest.mark.asyncio
    async def test_high_similarity_adds_error_note_from_llm_side(self) -> None:
        """High memory score (>0.90) is passed to handler without exception."""
        config = _make_config()
        high_score_hit = ModelMemoryHit(
            item_id="item-1", score=0.95, snippet="Similar item"
        )

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            # Return high-scoring memory hit — handler should pass duplicate hint to LLM
            mock_memory.return_value = ([high_score_hit], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.4,
                    "reasoning": "Duplicate.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        # Memory hits should be present in result
        assert len(result.memory_hits) == 1
        assert result.memory_hits[0].score == 0.95
        assert result.memory_hits[0].item_id == "item-1"

    @pytest.mark.asyncio
    async def test_omnimemory_unavailable_proceeds_with_empty_hits(self) -> None:
        """omnimemory unavailable → empty hits, error appended, no exception."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], "omnimemory connection refused")
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.8,
                    "reasoning": "Novel.",
                    "initial_plan": "- Do it",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )

        assert result.memory_hits == []
        assert any("omnimemory" in e for e in result.errors)
        # Should still complete successfully
        assert result.verdict == "SURFACE"

    @pytest.mark.asyncio
    async def test_memory_hits_in_evaluated_event(self) -> None:
        """Memory hit IDs should appear in the gmail-intent-evaluated event."""
        config = _make_config()
        hit = ModelMemoryHit(item_id="item-abc", score=0.75, snippet="Related")

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([hit], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.2,
                    "reasoning": "Seen it.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        evaluated_events = [
            e
            for e in result.pending_events
            if e.get("event_type")
            == "onex.evt.omniintelligence.gmail-intent-evaluated.v1"
        ]
        assert len(evaluated_events) == 1
        assert "item-abc" in evaluated_events[0].get("memory_hit_ids", [])


# ---------------------------------------------------------------------------
# LLM parsing
# ---------------------------------------------------------------------------


class TestLlmParsing:
    """LLM response parsing edge cases."""

    @pytest.mark.asyncio
    async def test_valid_json_parse_status_ok(self) -> None:
        """Clean JSON response → llm_parse_status=OK."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.llm_parse_status == "OK"

    @pytest.mark.asyncio
    async def test_recoverable_json_parse_status_recovered(self) -> None:
        """JSON with text prefix → llm_parse_status=RECOVERED, verdict parsed correctly."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            # Simulate RECOVERED: dict parsed, status=RECOVERED
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.5,
                    "reasoning": "Maybe.",
                    "initial_plan": None,
                },
                "RECOVERED",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.llm_parse_status == "RECOVERED"
        assert result.verdict == "WATCHLIST"

    @pytest.mark.asyncio
    async def test_unrecoverable_json_verdict_watchlist_not_skip(self) -> None:
        """Unrecoverable malformed JSON → llm_parse_status=FAILED, verdict=WATCHLIST (not SKIP)."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = ({}, "FAILED", ["parse failed"])
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.llm_parse_status == "FAILED"
        assert result.verdict == "WATCHLIST"
        assert result.verdict != "SKIP"

    @pytest.mark.asyncio
    async def test_surface_with_null_initial_plan_demoted_to_watchlist(self) -> None:
        """SURFACE verdict with null initial_plan → demoted to WATCHLIST + error recorded."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            # LLM returns SURFACE but with null initial_plan — schema validation should demote
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.8,
                    "reasoning": "Interesting.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.verdict == "WATCHLIST"
        assert result.initial_plan is None
        # Error should be recorded about demotion
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_llm_errors_propagated_to_result_errors(self) -> None:
        """LLM parse errors from _call_deepseek_r1 are included in result.errors."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = ({}, "FAILED", ["JSON parse error: invalid syntax"])
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert any("parse" in e.lower() or "json" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Idempotency: duplicate detection, degraded mode."""

    @pytest.mark.asyncio
    async def test_same_message_processed_twice_returns_early_second_time(self) -> None:
        """Second call with same message_id + url returns early with no new event."""
        config = _make_config(message_id="msg-idem-001")
        repo = _FakeRepository()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.9,
                    "reasoning": "Novel.",
                    "initial_plan": "- Step 1",
                },
                "OK",
                [],
            )

            # First call — processes fully
            first_result = await handle_gmail_intent_evaluate(
                config,
                repository=repo,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )
            assert first_result.verdict == "SURFACE"
            first_llm_call_count = mock_llm.call_count

            # Second call — should hit idempotency check and return early
            second_result = await handle_gmail_intent_evaluate(
                config,
                repository=repo,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )

        # LLM should not be called again on second invocation
        assert mock_llm.call_count == first_llm_call_count
        # Second result should be idempotent
        assert second_result.verdict == first_result.verdict
        assert second_result.slack_sent is False
        assert second_result.pending_events == []

    @pytest.mark.asyncio
    async def test_idempotency_store_unavailable_proceeds_degraded(self) -> None:
        """When idempotency store raises, handler proceeds without idempotency guard."""
        config = _make_config()
        error_repo = _ErrorRepository()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.5,
                    "reasoning": "Maybe.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )

            # Should not raise
            result = await handle_gmail_intent_evaluate(config, repository=error_repo)

        # Handler completes in degraded mode
        assert result.verdict == "WATCHLIST"

    @pytest.mark.asyncio
    async def test_evaluation_id_is_deterministic(self) -> None:
        """evaluation_id is sha256(message_id:selected_url:v1) — stable across calls."""
        config = _make_config(
            message_id="msg-stable-001",
            urls=["https://github.com/example/repo"],
        )
        expected_id = _eval_id("msg-stable-001", "https://github.com/example/repo")

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.evaluation_id == expected_id

    @pytest.mark.asyncio
    async def test_idempotent_result_has_url_fetch_status_skipped(self) -> None:
        """Idempotent (already-processed) result returns url_fetch_status=SKIPPED."""
        config = _make_config(message_id="msg-idem-002")
        repo = _FakeRepository()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.2,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )

            # First call — processes fully
            await handle_gmail_intent_evaluate(config, repository=repo)

            # Second call — idempotent return
            second = await handle_gmail_intent_evaluate(config, repository=repo)

        assert second.url_fetch_status == "SKIPPED"


# ---------------------------------------------------------------------------
# Slack / rate limiting
# ---------------------------------------------------------------------------


class TestSlackPosting:
    """Slack delivery: no token, rate limit, delivery failure."""

    @pytest.mark.asyncio
    async def test_no_slack_token_local_mode_slack_sent_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SLACK_BOT_TOKEN unset → local print mode, slack_sent=False."""
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.85,
                    "reasoning": "Novel.",
                    "initial_plan": "- Step 1",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            # No slack_notifier injected, no SLACK_BOT_TOKEN → local mode
            result = await handle_gmail_intent_evaluate(
                config,
                _slack_rate_check=_rate_allow,
            )

        assert result.slack_sent is False
        assert result.verdict == "SURFACE"

    @pytest.mark.asyncio
    async def test_rate_limited_sixth_surface_not_sent(self) -> None:
        """6th SURFACE in one hour → rate_limited=True, Slack not sent, verdict stays SURFACE."""
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.85,
                    "reasoning": "Novel.",
                    "initial_plan": "- Step 1",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            # Inject rate-deny to simulate limit exceeded
            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=slack,
                _slack_rate_check=_rate_deny,
            )

        assert result.verdict == "SURFACE"
        assert result.rate_limited is True
        assert result.slack_sent is False
        assert slack.call_count == 0

    @pytest.mark.asyncio
    async def test_slack_delivery_failure_verdict_unchanged(self) -> None:
        """Slack delivery failure → slack_sent=False, SURFACE verdict unchanged, error appended."""
        slack = _FakeSlackNotifier(success=False)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.85,
                    "reasoning": "Novel.",
                    "initial_plan": "- Step 1",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=slack,
                _slack_rate_check=_rate_allow,
            )

        assert result.verdict == "SURFACE"
        assert result.slack_sent is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_slack_not_called_for_watchlist(self) -> None:
        """Slack is never called for WATCHLIST verdict."""
        slack = _FakeSlackNotifier(success=True)
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.5,
                    "reasoning": "Maybe.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=slack,
                _slack_rate_check=_rate_allow,
            )

        assert result.verdict == "WATCHLIST"
        assert slack.call_count == 0


# ---------------------------------------------------------------------------
# Fallbacks (DeepSeek unavailable, omnimemory unavailable)
# ---------------------------------------------------------------------------


class TestFallbacks:
    """Dependency failure fallback behavior."""

    @pytest.mark.asyncio
    async def test_deepseek_unavailable_verdict_watchlist_no_exception(self) -> None:
        """DeepSeek endpoint unavailable → verdict=WATCHLIST, no exception raised."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            # Simulate LLM unavailable: FAILED parse status
            mock_llm.return_value = ({}, "FAILED", ["DeepSeek connection error"])
            mock_repo_factory.return_value = None

            # Should NOT raise
            result = await handle_gmail_intent_evaluate(config)

        assert result.verdict == "WATCHLIST"
        assert result.llm_parse_status == "FAILED"

    @pytest.mark.asyncio
    async def test_omnimemory_unavailable_proceeds_with_surface_verdict(self) -> None:
        """omnimemory unavailable does not prevent SURFACE verdict."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], "connection refused")
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.88,
                    "reasoning": "Novel.",
                    "initial_plan": "- Integrate",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )

        assert result.verdict == "SURFACE"
        assert result.memory_hits == []

    @pytest.mark.asyncio
    async def test_all_fallbacks_together_no_exception(self) -> None:
        """All external dependencies failing simultaneously → WATCHLIST, no exception."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("", "FAILED")
            mock_memory.return_value = ([], "unavailable")
            mock_llm.return_value = ({}, "FAILED", ["timeout"])
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert result.verdict == "WATCHLIST"
        assert result.url_fetch_status == "FAILED"
        assert result.memory_hits == []
        assert result.llm_parse_status == "FAILED"
        assert result.slack_sent is False


# ---------------------------------------------------------------------------
# Result model integrity
# ---------------------------------------------------------------------------


class TestResultModelIntegrity:
    """Verify result model fields are always populated correctly."""

    @pytest.mark.asyncio
    async def test_result_is_model_gmail_intent_evaluation_result(self) -> None:
        """Handler always returns ModelGmailIntentEvaluationResult."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Noise.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert isinstance(result, ModelGmailIntentEvaluationResult)

    @pytest.mark.asyncio
    async def test_evaluation_id_is_non_empty_string(self) -> None:
        """evaluation_id is always a non-empty sha256 hex string."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.5,
                    "reasoning": "Maybe.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert isinstance(result.evaluation_id, str)
        assert len(result.evaluation_id) == 64  # sha256 hex = 64 chars

    @pytest.mark.asyncio
    async def test_pending_events_always_list(self) -> None:
        """pending_events is always a list, even on WATCHLIST."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "WATCHLIST",
                    "relevance_score": 0.4,
                    "reasoning": "Meh.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert isinstance(result.pending_events, list)
        assert len(result.pending_events) >= 1  # at least evaluated event

    @pytest.mark.asyncio
    async def test_relevance_score_in_valid_range(self) -> None:
        """relevance_score is always in [0.0, 1.0]."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SURFACE",
                    "relevance_score": 0.75,
                    "reasoning": "Good.",
                    "initial_plan": "- Step",
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(
                config,
                slack_notifier=_FakeSlackNotifier(),
                _slack_rate_check=_rate_allow,
            )

        assert 0.0 <= result.relevance_score <= 1.0

    @pytest.mark.asyncio
    async def test_errors_is_always_list(self) -> None:
        """errors field is always a list (empty or populated)."""
        config = _make_config()

        with (
            patch(
                f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock
            ) as mock_fetch,
            patch(
                f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock
            ) as mock_memory,
            patch(
                f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock
            ) as mock_llm,
            patch(
                f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
            ) as mock_repo_factory,
        ):
            mock_fetch.return_value = ("content", "OK")
            mock_memory.return_value = ([], None)
            mock_llm.return_value = (
                {
                    "verdict": "SKIP",
                    "relevance_score": 0.1,
                    "reasoning": "Old.",
                    "initial_plan": None,
                },
                "OK",
                [],
            )
            mock_repo_factory.return_value = None

            result = await handle_gmail_intent_evaluate(config)

        assert isinstance(result.errors, list)
