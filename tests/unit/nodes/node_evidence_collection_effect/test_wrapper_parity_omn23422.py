# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for the evidence collection handlers (OMN-23422).

``HandlerCollectAndEvaluate.handle`` must return exactly what the preserved
``collect_and_evaluate`` returns, and ``HandlerFireAndForgetEvaluate.handle``
must behave exactly like the preserved ``fire_and_forget_evaluate`` (returns
``None``, swallows the same errors, re-raises the same ones), for the same
request and the same injected dependencies. Both runs must drive the injected
Kafka publisher and database fakes identically. The module clock is pinned so
the event timestamp is deterministic.
"""

import asyncio
import importlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime as real_datetime
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_evidence_collection_effect.errors import (
    DisallowedEvidenceSourceError,
)
from omniintelligence.nodes.node_evidence_collection_effect.handlers import (
    handler_evidence_collection,
)
from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
    collect_and_evaluate,
    fire_and_forget_evaluate,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelGateCheckResult,
    ModelSessionCheckResults,
    ModelStaticAnalysisResult,
    ModelTestRunResult,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_gate_type import (
    EnumGateType,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelGateSpec,
    ModelObjectiveSpec,
    ModelScoreRange,
    ModelShapedTermSpec,
)

_MODULE = (
    "omniintelligence.nodes.node_evidence_collection_effect.handlers."
    "handler_evidence_collection"
)
_COLLECT = "HandlerCollectAndEvaluate"
_FORGET = "HandlerFireAndForgetEvaluate"
_COLLECTED_AT = "2025-01-01T00:00:00+00:00"

_PRESERVED: dict[str, Callable[..., Awaitable[Any]]] = {
    _COLLECT: collect_and_evaluate,
    _FORGET: fire_and_forget_evaluate,
}


class _FrozenDatetime(real_datetime):
    """``datetime`` whose ``now`` is fixed so the event timestamp is stable."""

    @classmethod
    def now(cls, tz: Any = None) -> "_FrozenDatetime":
        return cls(2025, 1, 1, 0, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _pin_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the handler module's clock for both the wrapper and function runs."""
    monkeypatch.setattr(handler_evidence_collection, "datetime", _FrozenDatetime)


class FakeKafkaPublisher:
    """In-memory ``ProtocolKafkaPublisher`` recording each publish call."""

    def __init__(self, error: BaseException | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def publish(self, *, topic: str, key: str, value: dict[str, Any]) -> None:
        self.calls.append({"topic": topic, "key": key, "value": value})
        if self._error is not None:
            raise self._error


class FakeDb:
    """In-memory ``ProtocolEvaluationDb`` recording each execute call."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> object:
        self.calls.append((query, args))
        if self._error is not None:
            raise self._error
        return "INSERT 0 1"


class _UnusableSpec:
    """Truthy stand-in for an objective spec that the scorer cannot evaluate."""


class _DisallowedSpec:
    """Objective spec whose truthiness check hits the free-text contract error."""

    def __bool__(self) -> bool:
        raise DisallowedEvidenceSourceError(source="chat_log", reason="not allowed")


def _full_request() -> ModelSessionCheckResults:
    return ModelSessionCheckResults(
        run_id="run-omn-23422",
        session_id="sess-omn-23422",
        correlation_id="corr-omn-23422",
        gate_results=(
            ModelGateCheckResult(
                gate_id="pre_commit",
                passed=True,
                pass_rate=1.0,
                check_count=4,
                pass_count=4,
            ),
            ModelGateCheckResult(
                gate_id="mypy_strict", passed=False, pass_rate=0.0, check_count=2
            ),
        ),
        test_results=(
            ModelTestRunResult(
                test_suite="unit",
                total_tests=10,
                passed_tests=8,
                failed_tests=2,
                pass_rate=0.8,
                duration_seconds=12.5,
            ),
        ),
        static_analysis_results=(
            ModelStaticAnalysisResult(
                tool="ruff", files_checked=30, warning_count=1, clean_rate=1.0
            ),
        ),
        cost_usd=0.125,
        latency_seconds=45.0,
        collected_at_utc=_COLLECTED_AT,
    )


def _tests_only_request() -> ModelSessionCheckResults:
    return ModelSessionCheckResults(
        run_id="run-tests-only",
        session_id="sess-tests-only",
        test_results=(
            ModelTestRunResult(
                test_suite="unit", total_tests=5, passed_tests=5, pass_rate=1.0
            ),
        ),
        collected_at_utc=_COLLECTED_AT,
    )


def _empty_request() -> ModelSessionCheckResults:
    return ModelSessionCheckResults(
        run_id="run-empty", session_id="sess-empty", collected_at_utc=_COLLECTED_AT
    )


def _malformed_request() -> ModelSessionCheckResults:
    """A request whose gate record lacks fields, so evidence collection raises."""
    return ModelSessionCheckResults.model_construct(
        run_id="run-malformed",
        session_id="sess-malformed",
        correlation_id="",
        gate_results=(ModelGateCheckResult.model_construct(gate_id="broken"),),
        test_results=(),
        static_analysis_results=(),
        cost_usd=None,
        latency_seconds=None,
        collected_at_utc=_COLLECTED_AT,
    )


def _strict_spec() -> ModelObjectiveSpec:
    """A spec whose hard gate fails for a partially passing test run."""
    return ModelObjectiveSpec(
        objective_id="strict_v1",
        version="1.0.0",
        gates=(
            ModelGateSpec(
                id="gate_tests",
                gate_type=EnumGateType.THRESHOLD,
                threshold=0.95,
                evidence_source="test_output",
            ),
        ),
        shaped_terms=(
            ModelShapedTermSpec(
                id="term_tests",
                evidence_source="test_output",
                score_dimension="correctness",
                weight=1.0,
                direction="maximize",
            ),
        ),
        score_range=ModelScoreRange(minimum=0.0, maximum=1.0),
    )


def _sinks(
    kafka_error: BaseException | None = None, db_error: Exception | None = None
) -> dict[str, Any]:
    return {
        "kafka_publisher": FakeKafkaPublisher(error=kafka_error),
        "db_conn": FakeDb(error=db_error),
    }


def _no_deps() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[
        str, str, Callable[[], ModelSessionCheckResults], Callable[[], dict[str, Any]]
    ]
] = [
    # --- collect_and_evaluate -------------------------------------------------
    # Normal path: every evidence kind, both sinks, default spec.
    (
        "collect-full-pipeline",
        _COLLECT,
        _full_request,
        lambda: {**_sinks(), "task_class": "feature", "agent_name": "agent-api"},
    ),
    # No sinks injected: nothing is emitted or stored.
    ("collect-no-sinks", _COLLECT, _tests_only_request, _no_deps),
    # Only the Kafka publisher.
    (
        "collect-kafka-only",
        _COLLECT,
        _tests_only_request,
        lambda: {"kafka_publisher": FakeKafkaPublisher()},
    ),
    # Only the database connection.
    (
        "collect-db-only",
        _COLLECT,
        _tests_only_request,
        lambda: {"db_conn": FakeDb(), "agent_name": "agent-db"},
    ),
    # Second branch: a stricter spec makes the hard gate fail.
    (
        "collect-failing-gate-spec",
        _COLLECT,
        _full_request,
        lambda: {**_sinks(), "objective_spec": _strict_spec()},
    ),
    # Edge: no evidence at all skips evaluation.
    ("collect-empty-evidence", _COLLECT, _empty_request, lambda: _sinks()),
    # Error path: the Kafka publisher raises, the failure is swallowed.
    (
        "collect-kafka-failure",
        _COLLECT,
        _full_request,
        lambda: _sinks(kafka_error=RuntimeError("broker down")),
    ),
    # Error path: the database raises, the failure is swallowed.
    (
        "collect-db-failure",
        _COLLECT,
        _full_request,
        lambda: _sinks(db_error=RuntimeError("db down")),
    ),
    # Error path: evidence collection raises on a malformed record.
    ("collect-malformed-evidence", _COLLECT, _malformed_request, lambda: _sinks()),
    # Error path: an unusable spec makes evaluation fail and be reported as skipped.
    (
        "collect-evaluation-error",
        _COLLECT,
        _tests_only_request,
        lambda: {**_sinks(), "objective_spec": _UnusableSpec()},
    ),
    # Error path: the free-text contract error propagates out of the pipeline.
    (
        "collect-disallowed-source",
        _COLLECT,
        _tests_only_request,
        lambda: {"objective_spec": _DisallowedSpec()},
    ),
    # Error path: an invalid agent name fails event validation and propagates.
    (
        "collect-invalid-agent-name",
        _COLLECT,
        _tests_only_request,
        lambda: {**_sinks(), "agent_name": 123},
    ),
    # --- fire_and_forget_evaluate ---------------------------------------------
    # Normal path: a successful evaluation returns None.
    (
        "forget-full-pipeline",
        _FORGET,
        _full_request,
        lambda: {**_sinks(), "task_class": "feature", "agent_name": "agent-api"},
    ),
    # Second branch: a skipped evaluation (no evidence) is logged and returns None.
    ("forget-empty-evidence", _FORGET, _empty_request, lambda: _sinks()),
    # Second branch: failing gate spec still returns None.
    (
        "forget-failing-gate-spec",
        _FORGET,
        _full_request,
        lambda: {**_sinks(), "objective_spec": _strict_spec()},
    ),
    # Error path: a sink failure inside the pipeline is swallowed.
    (
        "forget-kafka-failure",
        _FORGET,
        _full_request,
        lambda: _sinks(kafka_error=RuntimeError("broker down")),
    ),
    # Error path: the free-text contract error is logged and swallowed.
    (
        "forget-disallowed-source",
        _FORGET,
        _tests_only_request,
        lambda: {"objective_spec": _DisallowedSpec()},
    ),
    # Error path: any unexpected error is logged and swallowed.
    (
        "forget-invalid-agent-name",
        _FORGET,
        _tests_only_request,
        lambda: {**_sinks(), "agent_name": 123},
    ),
    # Error path: cancellation is re-raised rather than swallowed.
    (
        "forget-cancelled",
        _FORGET,
        _tests_only_request,
        lambda: {"kafka_publisher": FakeKafkaPublisher(error=asyncio.CancelledError())},
    ),
    # Error path: an unexpected dependency keyword fails the call itself.
    (
        "forget-unexpected-dependency",
        _FORGET,
        _tests_only_request,
        lambda: {"unknown_dependency": object},
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelSessionCheckResults],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper handle() and the preserved coroutine function agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    preserved = _PRESERVED[class_name]

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: BaseException | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_for_wrapper).handle(
            request_for_wrapper
        )
    except (Exception, asyncio.CancelledError) as exc:  # captured for parity
        wrapper_error = exc

    function_result: Any = None
    function_error: BaseException | None = None
    try:
        function_result = await preserved(request_for_function, **deps_for_function)
    except (Exception, asyncio.CancelledError) as exc:  # captured for parity
        function_error = exc

    if function_error is not None or wrapper_error is not None:
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

    for dep_name, function_dep in deps_for_function.items():
        function_calls = getattr(function_dep, "calls", None)
        if function_calls is not None:
            assert (
                getattr(deps_for_wrapper[dep_name], "calls", None) == function_calls
            ), f"dependency {dep_name} recorded different calls"


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
