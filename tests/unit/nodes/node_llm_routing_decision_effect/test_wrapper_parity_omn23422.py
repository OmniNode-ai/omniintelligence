# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerProcessLlmRoutingDecision (OMN-23422).

``HandlerProcessLlmRoutingDecision.handle`` must return exactly what the
preserved ``process_llm_routing_decision`` returns for the same event and the
same repository and publisher, and must make identical repository and publish
calls. Cases cover the upsert without a publisher, with a publisher, a zero
row upsert, a fallback event, a database failure (structured ERROR result), a
publish failure routed to the DLQ, and a failure of both publishes.
"""

import importlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_llm_routing_decision_effect.handlers import (
    handler_llm_routing_decision as handler_module,
)
from omniintelligence.nodes.node_llm_routing_decision_effect.handlers.handler_llm_routing_decision import (
    process_llm_routing_decision,
)
from omniintelligence.nodes.node_llm_routing_decision_effect.models import (
    ModelLlmRoutingDecisionEvent,
)

_MODULE = (
    "omniintelligence.nodes.node_llm_routing_decision_effect.handlers."
    "handler_llm_routing_decision"
)
_WRAPPER_CLASS = "HandlerProcessLlmRoutingDecision"
_FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)


class FakeRoutingRepository:
    """In-memory ``ProtocolPatternRepository`` recording every call."""

    def __init__(
        self,
        status: str = "INSERT 0 1",
        error: Exception | None = None,
    ) -> None:
        self._status = status
        self._error = error
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.calls.append(("fetch", query, args))
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.calls.append(("fetchrow", query, args))
        return None

    async def execute(self, query: str, *args: Any) -> str:
        """Record the upsert, then fail or report the configured status."""
        self.calls.append(("execute", query, args))
        if self._error is not None:
            raise self._error
        return self._status


class FakeKafkaPublisher:
    """In-memory ``ProtocolKafkaPublisher`` recording every publish attempt."""

    def __init__(self, fail_topics: tuple[str, ...] | None = None) -> None:
        # ``None`` never fails; an empty tuple fails every topic.
        self._fail_topics = fail_topics
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        """Record the attempt, then fail for the configured topics."""
        self.calls.append((topic, key, value))
        if self._fail_topics is not None and (
            not self._fail_topics or topic in self._fail_topics
        ):
            raise RuntimeError("broker unavailable")


class _FrozenDatetime:
    """Stand-in for the module's ``datetime`` name with a fixed ``now``."""

    @staticmethod
    def now(tz: Any = None) -> datetime:
        return _FIXED_NOW if tz is None else _FIXED_NOW.astimezone(tz)


def _event(
    *,
    correlation_id: str = "corr-1",
    selected_agent: str = "agent-api",
    llm_confidence: float = 0.9,
    llm_latency_ms: int = 120,
    fallback_used: bool = False,
    fuzzy_top_candidate: str | None = None,
    llm_selected_candidate: str | None = None,
    agreement: bool = False,
) -> ModelLlmRoutingDecisionEvent:
    return ModelLlmRoutingDecisionEvent(
        session_id="session-23422",
        correlation_id=correlation_id,
        selected_agent=selected_agent,
        llm_confidence=llm_confidence,
        llm_latency_ms=llm_latency_ms,
        fallback_used=fallback_used,
        model_used="http://llm.example.test/v1",
        fuzzy_top_candidate=fuzzy_top_candidate,
        llm_selected_candidate=llm_selected_candidate,
        agreement=agreement,
        routing_prompt_version="v1",
    )


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelLlmRoutingDecisionEvent],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Normal path: upsert with no Kafka publisher.
    (
        "upsert-no-publisher",
        _WRAPPER_CLASS,
        _event,
        lambda: {"repository": FakeRoutingRepository()},
    ),
    # Upsert followed by the confirmation event.
    (
        "upsert-published",
        _WRAPPER_CLASS,
        lambda: _event(
            fuzzy_top_candidate="agent-api",
            llm_selected_candidate="agent-api",
            agreement=True,
        ),
        lambda: {
            "repository": FakeRoutingRepository(),
            "kafka_publisher": FakeKafkaPublisher(),
        },
    ),
    # Second branch: the upsert affects zero rows.
    (
        "upsert-zero-rows",
        _WRAPPER_CLASS,
        lambda: _event(correlation_id="corr-2"),
        lambda: {
            "repository": FakeRoutingRepository(status="INSERT 0 0"),
            "kafka_publisher": FakeKafkaPublisher(),
        },
    ),
    # Fallback to fuzzy matching with disagreeing candidates.
    (
        "fallback-disagreement",
        _WRAPPER_CLASS,
        lambda: _event(
            correlation_id="corr-3",
            selected_agent="agent-fuzzy",
            llm_confidence=0.0,
            fallback_used=True,
            fuzzy_top_candidate="agent-fuzzy",
            llm_selected_candidate="agent-other",
            agreement=False,
        ),
        lambda: {
            "repository": FakeRoutingRepository(),
            "kafka_publisher": FakeKafkaPublisher(),
        },
    ),
    # Error path: the database raises, producing a structured ERROR result.
    (
        "database-error",
        _WRAPPER_CLASS,
        lambda: _event(correlation_id="corr-4"),
        lambda: {
            "repository": FakeRoutingRepository(error=RuntimeError("connection reset")),
            "kafka_publisher": FakeKafkaPublisher(),
        },
    ),
    # Error path: the confirmation publish fails and the envelope goes to the DLQ.
    (
        "publish-failure-routes-to-dlq",
        _WRAPPER_CLASS,
        lambda: _event(correlation_id="corr-5"),
        lambda: {
            "repository": FakeRoutingRepository(),
            "kafka_publisher": FakeKafkaPublisher(
                fail_topics=(handler_module.TOPIC_LLM_ROUTING_DECISION_PROCESSED,)
            ),
        },
    ),
    # Error path: both the publish and the DLQ publish fail and are swallowed.
    (
        "publish-and-dlq-failure",
        _WRAPPER_CLASS,
        lambda: _event(correlation_id="corr-6"),
        lambda: {
            "repository": FakeRoutingRepository(),
            "kafka_publisher": FakeKafkaPublisher(fail_topics=()),
        },
    ),
]


def _recorded(dependencies: dict[str, Any]) -> dict[str, list[Any]]:
    """Return the calls recorded by every fake dependency."""
    return {
        name: dep.calls for name, dep in dependencies.items() if hasattr(dep, "calls")
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelLlmRoutingDecisionEvent],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved function agree on result and calls."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    # Pin only the wall clock used for ``processed_at`` and the DLQ timestamp.
    monkeypatch.setattr(handler_module, "datetime", _FrozenDatetime)

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await process_llm_routing_decision(request_b, **deps_b)
    except Exception as exc:  # captured deliberately for parity comparison
        function_error = exc

    if wrapper_error is not None or function_error is not None:
        assert wrapper_error is not None, (
            f"wrapper succeeded but function raised {function_error!r}"
        )
        assert function_error is not None, (
            f"function succeeded but wrapper raised {wrapper_error!r}"
        )
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_result == function_result

    assert _recorded(deps_a) == _recorded(deps_b)


def corpus_inputs() -> list[dict[str, Any]]:
    """Return every PARITY_CASES request as a JSON-describable dict, in order."""
    rows: list[dict[str, Any]] = []
    for case_id, class_name, request_builder, _deps_builder in PARITY_CASES:
        request = request_builder()
        payload = (
            request.model_dump(mode="json")
            if isinstance(request, BaseModel)
            else request
        )
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
