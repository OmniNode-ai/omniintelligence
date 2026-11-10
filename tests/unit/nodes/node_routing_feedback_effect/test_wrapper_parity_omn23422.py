# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound routing feedback handler with the preserved function.

OMN-23422: ``HandlerProcessRoutingFeedback.handle`` must return exactly what
``process_routing_feedback`` returns for the same event and the same repository
and Kafka publisher dependencies, and must make the same database and publish
calls. The handler module's clock is patched so ``processed_at`` and the
published payloads are deterministic.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

import omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback as handler_mod
from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    process_routing_feedback,
)
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    ModelRoutingFeedbackPayload,
)

MODULE = (
    "omniintelligence.nodes.node_routing_feedback_effect.handlers."
    "handler_routing_feedback"
)
WRAPPER = "HandlerProcessRoutingFeedback"

_FIXED_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_EMITTED_AT = datetime(2025, 6, 1, 11, 59, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("00000000-0000-0000-0000-000000023422")


class _FixedDatetime(datetime):
    """``datetime`` whose ``now`` returns the fixed instant."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        del tz
        return _FIXED_NOW


class _FakeRepository:
    """In-memory repository returning a preset command status."""

    def __init__(
        self, status: str | None = "INSERT 0 1", error: Exception | None = None
    ) -> None:
        self._status = status
        self._error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> str | None:
        self.calls.append(("execute", (query, *args)))
        if self._error is not None:
            raise self._error
        return self._status

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", (query, *args)))
        return []

    async def fetchrow(self, query: str, *args: Any) -> None:
        self.calls.append(("fetchrow", (query, *args)))


class _FakePublisher:
    """In-memory Kafka publisher failing its first ``fail_first`` publishes."""

    def __init__(self, fail_first: int = 0) -> None:
        self.fail_first = fail_first
        self.calls: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail_first:
            raise RuntimeError("broker unreachable")


def _event(
    feedback_status: str = "produced",
    *,
    outcome: str = "success",
    skip_reason: str | None = None,
    session_id: str = "session-omn23422",
) -> ModelRoutingFeedbackPayload:
    return ModelRoutingFeedbackPayload(
        session_id=session_id,
        outcome=outcome,
        feedback_status=feedback_status,
        skip_reason=skip_reason,
        correlation_id=_CORRELATION_ID,
        emitted_at=_EMITTED_AT,
    )


def _deps(
    *,
    status: str | None = "INSERT 0 1",
    repo_error: Exception | None = None,
    publisher: bool = True,
    publisher_fail_first: int = 0,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {
            "repository": _FakeRepository(status, repo_error),
            "kafka_publisher": _FakePublisher(publisher_fail_first)
            if publisher
            else None,
        }

    return build


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], BaseModel | dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "produced-upserted-and-published",
        WRAPPER,
        _event,
        _deps(),
    ),
    (
        "produced-failed-outcome",
        WRAPPER,
        lambda: _event(outcome="failed"),
        _deps(status="UPDATE 1"),
    ),
    (
        "produced-no-publisher",
        WRAPPER,
        _event,
        _deps(publisher=False),
    ),
    (
        "produced-zero-rows-affected",
        WRAPPER,
        _event,
        _deps(status="INSERT 0 0"),
    ),
    (
        "produced-unparseable-status",
        WRAPPER,
        _event,
        _deps(status=None),
    ),
    (
        "skipped-not-persisted",
        WRAPPER,
        lambda: _event("skipped", outcome="abandoned", skip_reason="guardrail_blocked"),
        _deps(),
    ),
    (
        "publish-fails-routed-to-dlq",
        WRAPPER,
        _event,
        _deps(publisher_fail_first=1),
    ),
    (
        "publish-and-dlq-both-fail",
        WRAPPER,
        _event,
        _deps(publisher_fail_first=2),
    ),
    (
        "repository-raises-structured-error",
        WRAPPER,
        _event,
        _deps(repo_error=RuntimeError("connection refused")),
    ),
    (
        "empty-session-id",
        WRAPPER,
        lambda: ModelRoutingFeedbackPayload.model_construct(
            session_id="",
            outcome="unknown",
            feedback_status="produced",
            skip_reason=None,
            correlation_id=_CORRELATION_ID,
            emitted_at=_EMITTED_AT,
        ),
        _deps(),
    ),
]


def _request_json(request: BaseModel | dict[str, Any]) -> Any:
    return json.loads(json.dumps(to_jsonable_python(request), default=str))


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {"case": case_id, "wrapper": class_name, "request": _request_json(build())}
        for case_id, class_name, build, _ in PARITY_CASES
    ]


def _recorded_calls(deps: dict[str, Any]) -> dict[str, Any]:
    publisher = deps["kafka_publisher"]
    return {
        "repository": deps["repository"].calls,
        "publisher": None if publisher is None else publisher.calls,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel | dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper and the preserved function agree on result, raise and calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    monkeypatch.setattr(handler_mod, "datetime", _FixedDatetime)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    wrapper_result: Any = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc

    function_error: Exception | None = None
    function_result: Any = None
    try:
        function_result = await process_routing_feedback(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert _recorded_calls(deps_a) == _recorded_calls(deps_b)
