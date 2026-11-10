# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the node_pattern_feedback_effect wrappers (OMN-23422).

``HandlerRecordDispatchOutcome`` must return exactly what
``record_dispatch_outcome`` returns and ``HandlerRecordSessionOutcome`` exactly
what ``record_session_outcome`` returns for the same request and the same
dependencies. Repositories and producers are in-memory fakes that record every
call; the wall clock is patched on each handler module so ``recorded_at`` is
deterministic. No database and no Kafka are used.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from omnibase_core.enums.cost import EnumUsageSource
from omnibase_core.enums.enum_dispatch_verdict import EnumDispatchVerdict
from omnibase_core.models.cost import ModelCostProvenance
from omnibase_core.models.dispatch import ModelCallRecord, ModelDispatchEvalResult
from pydantic import BaseModel

from omniintelligence.enums import EnumHeuristicMethod
from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    handler_dispatch_outcome as dispatch_module,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    handler_session_outcome as session_module,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_dispatch_outcome import (
    record_dispatch_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    record_session_outcome,
)

DISPATCH_MODULE = (
    "omniintelligence.nodes.node_pattern_feedback_effect.handlers."
    "handler_dispatch_outcome"
)
SESSION_MODULE = (
    "omniintelligence.nodes.node_pattern_feedback_effect.handlers."
    "handler_session_outcome"
)
DISPATCH_CLASS = "HandlerRecordDispatchOutcome"
SESSION_CLASS = "HandlerRecordSessionOutcome"

_FIXED_NOW = datetime(2026, 6, 1, 8, 30, tzinfo=UTC)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, _tz: Any = None) -> datetime:
        return _FIXED_NOW


def _uuid(n: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRepository:
    """Scripted repository that records every query it receives.

    Responses are chosen by substring of the SQL text so the fake does not
    depend on the handler's query constants.
    """

    def __init__(
        self,
        injection_rows: list[dict[str, Any]] | None = None,
        count_rows: list[dict[str, Any]] | None = None,
        execute_status: str = "UPDATE 1",
        score_rows: list[dict[str, Any]] | None = None,
        raise_on: str | None = None,
    ) -> None:
        self._injection_rows = injection_rows or []
        self._count_rows = count_rows if count_rows is not None else []
        self._execute_status = execute_status
        self._score_rows = score_rows or []
        self._raise_on = raise_on
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    def _maybe_raise(self, query: str) -> None:
        if self._raise_on is not None and self._raise_on in query:
            raise RuntimeError(f"db failure on {self._raise_on}")

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append(("fetch", " ".join(query.split()), args))
        self._maybe_raise(query)
        if "COUNT(*)" in query:
            return self._count_rows
        if "UPDATE learned_patterns" in query and "RETURNING" in query:
            return self._score_rows
        if "outcome_recorded = FALSE" in query:
            return self._injection_rows
        return []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.calls.append(("fetchrow", " ".join(query.split()), args))
        self._maybe_raise(query)
        return None

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", " ".join(query.split()), args))
        self._maybe_raise(query)
        return self._execute_status


class _FakeProducer:
    """Kafka publisher fake that records publishes and can fail."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, object]) -> None:
        self.calls.append((topic, key, value))
        if self._fail:
            raise RuntimeError("kafka unavailable")


# ---------------------------------------------------------------------------
# Dispatch wrapper cases
# ---------------------------------------------------------------------------


def _dispatch_event(
    dispatch_id: str = "d1",
    verdict: EnumDispatchVerdict = EnumDispatchVerdict.PASS,
    quality_score: float | None = 0.85,
    estimated: bool = False,
    with_calls: bool = True,
) -> ModelDispatchEvalResult:
    provenance = (
        ModelCostProvenance(
            usage_source=EnumUsageSource.ESTIMATED, estimation_method="rollup"
        )
        if estimated
        else ModelCostProvenance(
            usage_source=EnumUsageSource.MEASURED, source_payload_hash="a" * 64
        )
    )
    calls = (
        [
            ModelCallRecord(
                provider="anthropic",
                model="claude-test-model",
                input_tokens=10_000,
                output_tokens=2_500,
                latency_ms=750,
                cost_dollars=0.031,
                cost_provenance=ModelCostProvenance(
                    usage_source=EnumUsageSource.MEASURED,
                    source_payload_hash="b" * 64,
                ),
            )
        ]
        if with_calls
        else []
    )
    return ModelDispatchEvalResult(
        task_id="t1",
        dispatch_id=dispatch_id,
        ticket_id="OMN-10388",
        verdict=verdict,
        quality_score=quality_score,
        token_cost=12_500,
        dollars_cost=0.031,
        cost_provenance=provenance,
        model_calls=calls,
        evaluated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        eval_latency_ms=42,
    )


def _dispatch_deps(status: str = "INSERT 0 1", raise_on: str | None = None):
    return lambda: {
        "repository": _FakeRepository(execute_status=status, raise_on=raise_on)
    }


# ---------------------------------------------------------------------------
# Session wrapper cases
# ---------------------------------------------------------------------------

_SESSION = _uuid(1)
_CORRELATION = _uuid(2)
_P1, _P2, _P3 = _uuid(11), _uuid(12), _uuid(13)

_TWO_INJECTIONS = [
    {"injection_id": _uuid(101), "pattern_ids": [_P1, _P2]},
    {"injection_id": _uuid(102), "pattern_ids": [_P2, _P3]},
]


def _session_request(**overrides: Any) -> dict[str, Any]:
    request: dict[str, Any] = {
        "session_id": _SESSION,
        "success": True,
        "failure_reason": None,
        "correlation_id": _CORRELATION,
    }
    request.update(overrides)
    return request


def _session_deps(
    repo_kwargs: dict[str, Any], producer: Callable[[], Any] | None = None
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        deps: dict[str, Any] = {"repository": _FakeRepository(**repo_kwargs)}
        if producer is not None:
            deps["producer"] = producer()
        return deps

    return build


_SCORES_ALL = [
    {"id": _P1, "quality_score": 0.9},
    {"id": _P2, "quality_score": 0.5},
    {"id": _P3, "quality_score": 0.1},
]

PARITY_CASES: list[tuple[str, str, Callable[[], Any], Callable[[], dict[str, Any]]]] = [
    # --- dispatch outcome wrapper ---------------------------------------
    ("dispatch-pass-measured", DISPATCH_CLASS, _dispatch_event, _dispatch_deps()),
    (
        "dispatch-fail-estimated",
        DISPATCH_CLASS,
        lambda: _dispatch_event(
            "d2", EnumDispatchVerdict.FAIL, quality_score=None, estimated=True
        ),
        _dispatch_deps("INSERT 0 1"),
    ),
    (
        "dispatch-error-no-model-calls",
        DISPATCH_CLASS,
        lambda: _dispatch_event(
            "d3", EnumDispatchVerdict.ERROR, quality_score=None, with_calls=False
        ),
        _dispatch_deps("INSERT 0 0"),
    ),
    (
        "dispatch-unparseable-status",
        DISPATCH_CLASS,
        _dispatch_event,
        _dispatch_deps("OK"),
    ),
    (
        "dispatch-repository-raises",
        DISPATCH_CLASS,
        _dispatch_event,
        _dispatch_deps(raise_on="dispatch_eval_results"),
    ),
    # --- session outcome wrapper ----------------------------------------
    (
        "session-success-equal-split-producer",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "score_rows": _SCORES_ALL,
            },
            producer=_FakeProducer,
        ),
    ),
    (
        "session-failure-recency-weighted",
        SESSION_CLASS,
        lambda: _session_request(
            success=False,
            failure_reason="tests failed",
            heuristic_method=EnumHeuristicMethod.RECENCY_WEIGHTED,
        ),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "score_rows": _SCORES_ALL,
            }
        ),
    ),
    (
        "session-first-match-no-correlation",
        SESSION_CLASS,
        lambda: _session_request(
            heuristic_method=EnumHeuristicMethod.FIRST_MATCH, correlation_id=None
        ),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS[:1],
                "execute_status": "UPDATE 1",
                "score_rows": _SCORES_ALL[:2],
            },
            producer=_FakeProducer,
        ),
    ),
    (
        "session-success-clears-failure-reason",
        SESSION_CLASS,
        lambda: _session_request(failure_reason="stale reason"),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS[:1],
                "execute_status": "UPDATE 1",
                "score_rows": _SCORES_ALL[:2],
            }
        ),
    ),
    (
        "session-already-recorded",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps({"count_rows": [{"count": 3}]}),
    ),
    (
        "session-no-injections-found",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps({"count_rows": [{"count": 0}]}),
    ),
    (
        "session-no-injections-empty-count-result",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps({"count_rows": []}),
    ),
    (
        "session-injections-without-pattern-ids",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": [
                    {"injection_id": _uuid(103), "pattern_ids": None},
                    {"injection_id": _uuid(104), "pattern_ids": []},
                ],
                "execute_status": "UPDATE 2",
            },
            producer=_FakeProducer,
        ),
    ),
    (
        "session-heuristic-skipped-by-idempotency",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS[:1],
                "execute_status": "UPDATE 0",
                "score_rows": _SCORES_ALL[:2],
            }
        ),
    ),
    (
        "session-scoring-fails",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "raise_on": "RETURNING id, quality_score",
            },
            producer=_FakeProducer,
        ),
    ),
    (
        "session-producer-publish-fails",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "score_rows": _SCORES_ALL,
            },
            producer=lambda: _FakeProducer(fail=True),
        ),
    ),
    (
        "session-partial-scores-skip-unscored-pattern",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "score_rows": _SCORES_ALL[:1],
            },
            producer=_FakeProducer,
        ),
    ),
    (
        "session-attribution-binding-fails",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps(
            {
                "injection_rows": _TWO_INJECTIONS,
                "execute_status": "UPDATE 2",
                "score_rows": _SCORES_ALL,
                "raise_on": "run_id IS NOT NULL",
            },
        ),
    ),
    (
        "session-find-injections-raises",
        SESSION_CLASS,
        lambda: _session_request(),
        _session_deps({"raise_on": "outcome_recorded = FALSE"}),
    ),
]

_MODULES = {DISPATCH_CLASS: DISPATCH_MODULE, SESSION_CLASS: SESSION_MODULE}


def _to_json(value: Any) -> Any:
    def default(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return str(obj)

    return json.loads(json.dumps(value, default=default))


def corpus_inputs() -> list[dict[str, Any]]:
    """JSON-describable request per parity case, in PARITY_CASES order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": _to_json(request_builder()),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _observed(deps: dict[str, Any]) -> dict[str, Any]:
    producer = deps.get("producer")
    return {
        "repository_calls": deps["repository"].calls,
        "producer_calls": producer.calls if producer is not None else None,
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
    request_builder: Callable[[], Any],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return or raise alike with equal effects."""
    wrapper_cls = getattr(
        importlib.import_module(_MODULES[class_name]), class_name, None
    )
    assert wrapper_cls is not None, "contract-bound handler class is required"

    monkeypatch.setattr(dispatch_module, "datetime", _FixedDatetime)
    monkeypatch.setattr(session_module, "datetime", _FixedDatetime)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    async def call_function() -> Any:
        if class_name == DISPATCH_CLASS:
            return await record_dispatch_outcome(request_b, **deps_b)
        return await record_session_outcome(**request_b, **deps_b)

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await call_function()
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result

    assert _observed(deps_a) == _observed(deps_b)
