# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Parity of HandlerGmailIntentEvaluate.handle(request) with the pre-class module function.

``EXPECTED`` was recorded by running ``handle_gmail_intent_evaluate`` (omniintelligence@fa990e38),
the module function that ``HandlerGmailIntentEvaluate.handle`` replaced, through the same scenarios
with the same collaborators replaced. Each scenario is named by its ``message_id``, so the request
alone selects the collaborators' behaviour. The class is resolved inside the test, so the pre-class
tree collects the test and fails the assertion instead of failing at import.

Ticket: OMN-21536
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluator_config import (
    ModelGmailIntentEvaluatorConfig,
)

pytestmark = pytest.mark.unit

_HANDLER_MODULE = "omniintelligence.nodes.node_gmail_intent_evaluator_effect.handlers.handler_gmail_intent_evaluate"

_SURFACE = {
    "verdict": "SURFACE",
    "relevance_score": 0.85,
    "reasoning": "Novel.",
    "initial_plan": "- Step 1",
}
_HIT = {"item_id": "mem-1", "score": 0.9, "snippet": "Related prior note"}


def _config(
    message_id: str, urls: list[str] | None = None
) -> ModelGmailIntentEvaluatorConfig:
    return ModelGmailIntentEvaluatorConfig(
        message_id=message_id,
        subject="github.com/example/repo",
        body_text="Interesting project for OmniNode, contact someone@example.com",
        urls=["https://github.com/example/repo"] if urls is None else urls,
        source_label="To Read",
        sender="sender@example.com",
        received_at="2026-02-25T00:00:00Z",
    )


# message_id -> collaborator behaviour
SCENARIOS: dict[str, dict[str, Any]] = {
    "surface_sent": {"llm": (_SURFACE, "OK", [])},
    "surface_rate_limited": {"llm": (_SURFACE, "OK", []), "rate": False},
    "surface_slack_failed": {"llm": (_SURFACE, "OK", []), "slack": False},
    "skip": {"llm": ({**_SURFACE, "verdict": "SKIP", "initial_plan": None}, "OK", [])},
    "watchlist_llm_failed": {"llm": ({}, "FAILED", ["llm unavailable"])},
    "invalid_llm_verdict": {
        "llm": (
            {"verdict": "MAYBE", "relevance_score": 2.5, "reasoning": "?"},
            "RECOVERED",
            [],
        )
    },
    "surface_without_plan": {"llm": ({**_SURFACE, "initial_plan": None}, "OK", [])},
    "idempotent_replay": {
        "llm": (_SURFACE, "OK", []),
        "prior": {"verdict": "SKIP", "relevance_score": 0.2},
    },
    "no_urls_memory_error": {
        "urls": [],
        "memory": ([], "qdrant unavailable"),
        "llm": ({**_SURFACE, "verdict": "WATCHLIST", "initial_plan": None}, "OK", []),
    },
    "fetch_failed_with_hits": {
        "fetch": ("", "FAILED"),
        "memory": ([_HIT], None),
        "llm": ({**_SURFACE, "verdict": "WATCHLIST", "initial_plan": None}, "OK", []),
    },
    "store_unavailable": {"llm": (_SURFACE, "OK", []), "repository": "error"},
}


class _FakeRepository:
    def __init__(self, prior: dict[str, Any] | None) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self._prior = prior

    async def fetchrow(self, query: str, evaluation_id: str) -> dict[str, Any] | None:
        if self._prior is not None:
            return self._prior
        return self.records.get(evaluation_id)

    async def execute(
        self, query: str, evaluation_id: str, verdict: str, relevance_score: float
    ) -> None:
        self.records[evaluation_id] = {
            "verdict": verdict,
            "relevance_score": relevance_score,
        }


class _ErrorRepository:
    async def fetchrow(self, query: str, evaluation_id: str) -> None:
        raise ConnectionError("DB unavailable")

    async def execute(self, query: str, *args: Any) -> None:
        raise ConnectionError("DB unavailable")


class _FakeSlackNotifier:
    def __init__(self, success: bool) -> None:
        self._success = success
        self.alerts: list[Any] = []

    async def handle(self, alert: Any) -> Any:
        self.alerts.append(alert)
        result = MagicMock()
        result.success = self._success
        result.error = None if self._success else "Slack API error"
        result.error_message = result.error
        return result


Invoke = Callable[..., Awaitable[Any]]


async def run_scenario(name: str, invoke: Invoke) -> dict[str, Any]:
    """Run one scenario; ``invoke(config, **dependencies)`` calls the handler."""
    spec = SCENARIOS[name]
    config = _config(name, spec.get("urls"))
    repository: Any = None
    if spec.get("repository") == "error":
        repository = _ErrorRepository()
    else:
        repository = _FakeRepository(spec.get("prior"))
    dependencies: dict[str, Any] = {"repository": repository}
    notifier = _FakeSlackNotifier(success=spec.get("slack", True))
    dependencies["slack_notifier"] = notifier
    rate = spec.get("rate", True)

    async def rate_check() -> bool:
        return rate

    dependencies["slack_rate_check"] = rate_check
    from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluation_result import (
        ModelMemoryHit,
    )

    memory_hits, memory_error = spec.get("memory", ([], None))
    with (
        patch(f"{_HANDLER_MODULE}._fetch_url_content", new_callable=AsyncMock) as fetch,
        patch(f"{_HANDLER_MODULE}._query_omnimemory", new_callable=AsyncMock) as memory,
        patch(f"{_HANDLER_MODULE}._call_deepseek_r1", new_callable=AsyncMock) as llm,
        patch(
            f"{_HANDLER_MODULE}._make_asyncpg_repository", new_callable=AsyncMock
        ) as repository_factory,
    ):
        fetch.return_value = spec.get("fetch", ("GitHub repo content", "OK"))
        memory.return_value = ([ModelMemoryHit(**h) for h in memory_hits], memory_error)
        llm.return_value = spec["llm"]
        repository_factory.return_value = None
        result = await invoke(config, **dependencies)
    outcome = result.model_dump(mode="json")
    outcome["slack_alerts"] = len(notifier.alerts)
    outcome["fetch_calls"] = fetch.await_count
    outcome["llm_calls"] = llm.await_count
    outcome["stored"] = (
        sorted(repository.records) == [result.evaluation_id]
        if isinstance(repository, _FakeRepository) and repository.records
        else None
    )
    return outcome


EXPECTED: dict[str, dict[str, Any]] = {
    "fetch_failed_with_hits": {
        "errors": [],
        "evaluation_id": "1899caccc295b6a3430386761c4c0dddaa03860cba3ddb16a3ce6ec44dd5f517",
        "fetch_calls": 1,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [
            {"item_id": "mem-1", "score": 0.9, "snippet": "Related prior note"}
        ],
        "pending_events": [
            {
                "evaluation_id": "1899caccc295b6a3430386761c4c0dddaa03860cba3ddb16a3ce6ec44dd5f517",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": ["mem-1"],
                "message_id": "fetch_failed_with_hits",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "WATCHLIST",
            }
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "FAILED",
        "verdict": "WATCHLIST",
    },
    "idempotent_replay": {
        "errors": [],
        "evaluation_id": "2b380cee972178512ccd8ede93e685982fbd574ff98c1049208d9ce139b056b0",
        "fetch_calls": 0,
        "initial_plan": None,
        "llm_calls": 0,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [],
        "rate_limited": False,
        "reasoning": "Idempotent: evaluation already processed",
        "relevance_score": 0.2,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": None,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "SKIPPED",
        "verdict": "SKIP",
    },
    "invalid_llm_verdict": {
        "errors": [
            "LLM returned invalid verdict: 'MAYBE'; defaulting to WATCHLIST",
            "relevance_score 2.5 > 1.0; clamped to 1.0",
        ],
        "evaluation_id": "e5af6194477fd748502fdafbe544a3b2e979cb3aedd05f49539955b41b486d31",
        "fetch_calls": 1,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "RECOVERED",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "e5af6194477fd748502fdafbe544a3b2e979cb3aedd05f49539955b41b486d31",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "RECOVERED",
                "memory_hit_ids": [],
                "message_id": "invalid_llm_verdict",
                "relevance_score": 1.0,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "WATCHLIST",
            }
        ],
        "rate_limited": False,
        "reasoning": "?",
        "relevance_score": 1.0,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "WATCHLIST",
    },
    "no_urls_memory_error": {
        "errors": ["omnimemory query error: qdrant unavailable"],
        "evaluation_id": "0d1ee407f28a78cde31bed1950a295e9cb63a44542622657e127111a192ffe64",
        "fetch_calls": 0,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "0d1ee407f28a78cde31bed1950a295e9cb63a44542622657e127111a192ffe64",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "no_urls_memory_error",
                "relevance_score": 0.85,
                "selected_url": None,
                "slack_sent": False,
                "verdict": "WATCHLIST",
            }
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": None,
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": [],
        "url_fetch_status": "SKIPPED",
        "verdict": "WATCHLIST",
    },
    "skip": {
        "errors": [],
        "evaluation_id": "7738796540bb067e2d9d75d803531b8ab15ad77ee2a73973b72f48c5c28c297c",
        "fetch_calls": 1,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "7738796540bb067e2d9d75d803531b8ab15ad77ee2a73973b72f48c5c28c297c",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "skip",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "SKIP",
            }
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "SKIP",
    },
    "store_unavailable": {
        "errors": [],
        "evaluation_id": "c188e7fadb989e8db1fb812e5e2103104dfbc56e51f24b6264000c6f4fe67614",
        "fetch_calls": 1,
        "initial_plan": "- Step 1",
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "c188e7fadb989e8db1fb812e5e2103104dfbc56e51f24b6264000c6f4fe67614",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "store_unavailable",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": True,
                "verdict": "SURFACE",
            },
            {
                "evaluation_id": "c188e7fadb989e8db1fb812e5e2103104dfbc56e51f24b6264000c6f4fe67614",
                "event_type": "onex.evt.omniintelligence.gmail-intent-surfaced.v1",
                "initial_plan": "- Step 1",
                "message_id": "store_unavailable",
                "reasoning": "Novel.",
                "selected_url": "https://github.com/example/repo",
                "subject": "github.com/example/repo",
            },
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 1,
        "slack_sent": True,
        "stored": None,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "SURFACE",
    },
    "surface_rate_limited": {
        "errors": [],
        "evaluation_id": "6e31cdd9943514b8c6d59198d3650b31824fbf0dffc1059cd07e8444db807c28",
        "fetch_calls": 1,
        "initial_plan": "- Step 1",
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "6e31cdd9943514b8c6d59198d3650b31824fbf0dffc1059cd07e8444db807c28",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "surface_rate_limited",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "SURFACE",
            },
            {
                "evaluation_id": "6e31cdd9943514b8c6d59198d3650b31824fbf0dffc1059cd07e8444db807c28",
                "event_type": "onex.evt.omniintelligence.gmail-intent-surfaced.v1",
                "initial_plan": "- Step 1",
                "message_id": "surface_rate_limited",
                "reasoning": "Novel.",
                "selected_url": "https://github.com/example/repo",
                "subject": "github.com/example/repo",
            },
        ],
        "rate_limited": True,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "SURFACE",
    },
    "surface_sent": {
        "errors": [],
        "evaluation_id": "a3dbda9777d32e6f5e306d0b68517cb5281e7db4e037038a30c52f67ba7b9f83",
        "fetch_calls": 1,
        "initial_plan": "- Step 1",
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "a3dbda9777d32e6f5e306d0b68517cb5281e7db4e037038a30c52f67ba7b9f83",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "surface_sent",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": True,
                "verdict": "SURFACE",
            },
            {
                "evaluation_id": "a3dbda9777d32e6f5e306d0b68517cb5281e7db4e037038a30c52f67ba7b9f83",
                "event_type": "onex.evt.omniintelligence.gmail-intent-surfaced.v1",
                "initial_plan": "- Step 1",
                "message_id": "surface_sent",
                "reasoning": "Novel.",
                "selected_url": "https://github.com/example/repo",
                "subject": "github.com/example/repo",
            },
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 1,
        "slack_sent": True,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "SURFACE",
    },
    "surface_slack_failed": {
        "errors": ["Slack delivery failed: Slack API error"],
        "evaluation_id": "6a795e01dc806a60b1525b737ecffd946105975ac0c87dc89e811cc0afe07307",
        "fetch_calls": 1,
        "initial_plan": "- Step 1",
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "6a795e01dc806a60b1525b737ecffd946105975ac0c87dc89e811cc0afe07307",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "surface_slack_failed",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "SURFACE",
            },
            {
                "evaluation_id": "6a795e01dc806a60b1525b737ecffd946105975ac0c87dc89e811cc0afe07307",
                "event_type": "onex.evt.omniintelligence.gmail-intent-surfaced.v1",
                "initial_plan": "- Step 1",
                "message_id": "surface_slack_failed",
                "reasoning": "Novel.",
                "selected_url": "https://github.com/example/repo",
                "subject": "github.com/example/repo",
            },
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 1,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "SURFACE",
    },
    "surface_without_plan": {
        "errors": [
            "SURFACE verdict requires non-null initial_plan; demoting to WATCHLIST"
        ],
        "evaluation_id": "1c30d96c9b9a18be516a546c757c2827c3f100c528f6bdfc284f50f2260cb6c8",
        "fetch_calls": 1,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "OK",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "1c30d96c9b9a18be516a546c757c2827c3f100c528f6bdfc284f50f2260cb6c8",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "OK",
                "memory_hit_ids": [],
                "message_id": "surface_without_plan",
                "relevance_score": 0.85,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "WATCHLIST",
            }
        ],
        "rate_limited": False,
        "reasoning": "Novel.",
        "relevance_score": 0.85,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "WATCHLIST",
    },
    "watchlist_llm_failed": {
        "errors": ["llm unavailable"],
        "evaluation_id": "919141c5dfed46e7c60cb823d6898f7340e504f417e25804b744ff057b44a7dc",
        "fetch_calls": 1,
        "initial_plan": None,
        "llm_calls": 1,
        "llm_parse_status": "FAILED",
        "memory_hits": [],
        "pending_events": [
            {
                "evaluation_id": "919141c5dfed46e7c60cb823d6898f7340e504f417e25804b744ff057b44a7dc",
                "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
                "llm_parse_status": "FAILED",
                "memory_hit_ids": [],
                "message_id": "watchlist_llm_failed",
                "relevance_score": 0.0,
                "selected_url": "https://github.com/example/repo",
                "slack_sent": False,
                "verdict": "WATCHLIST",
            }
        ],
        "rate_limited": False,
        "reasoning": "LLM parse failed",
        "relevance_score": 0.0,
        "selected_url": "https://github.com/example/repo",
        "slack_alerts": 0,
        "slack_sent": False,
        "stored": True,
        "url_candidates": ["https://github.com/example/repo"],
        "url_fetch_status": "OK",
        "verdict": "WATCHLIST",
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(SCENARIOS))
async def test_canonical_handle_matches_preserved_function(name: str) -> None:
    handler_class = getattr(
        importlib.import_module(_HANDLER_MODULE), "HandlerGmailIntentEvaluate", None
    )
    assert handler_class is not None, "canonical handle(request) class is required"

    async def invoke(
        config: ModelGmailIntentEvaluatorConfig, **dependencies: Any
    ) -> Any:
        return await handler_class(**dependencies).handle(config)

    assert await run_scenario(name, invoke) == EXPECTED[name]
