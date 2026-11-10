# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerComplianceEvaluateCommand (OMN-23422).

``HandlerComplianceEvaluateCommand.handle`` must return exactly what the
preserved ``handle_compliance_evaluate_command`` returns for the same command
and the same injected dependencies, and must drive the LLM client and Kafka
producer identically. Cases cover compliant and violating results, LLM
failures, a missing LLM client, the content hash mismatch branch (with and
without a producer), a publish failure that routes to the DLQ, and a failure of
both the publish and the DLQ publish.
"""

import hashlib
import importlib
import itertools
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_compliance_evaluate_effect.handlers import (
    handler_compliance_evaluate as handler_module,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
    handle_compliance_evaluate_command,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.models import (
    ModelApplicablePatternPayload,
    ModelComplianceEvaluateCommand,
)

_MODULE = (
    "omniintelligence.nodes.node_compliance_evaluate_effect.handlers."
    "handler_compliance_evaluate"
)
_WRAPPER_CLASS = "HandlerComplianceEvaluateCommand"
_CORRELATION_ID = UUID("12345678-1234-5678-1234-567812345678")
_FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_CONTENT = "class Foo: pass"
_CONTENT_SHA256 = hashlib.sha256(_CONTENT.encode()).hexdigest()
_WRONG_SHA256 = "0" * 64


class FakeLlmClient:
    """In-memory ``ProtocolLlmClient`` returning a canned response or raising."""

    def __init__(self, response: str = "", error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Record the call, then answer or raise as configured."""
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        return self._response


class FakeKafkaProducer:
    """In-memory ``ProtocolKafkaPublisher`` recording every publish attempt."""

    def __init__(self, fail_topics: tuple[str, ...] | None = None) -> None:
        # ``None`` never fails; an empty tuple fails every topic.
        self._fail_topics = fail_topics
        self.calls: list[dict[str, Any]] = []

    async def publish(self, topic: str, key: str, value: dict[str, object]) -> None:
        """Record the attempt, then fail for the configured topics."""
        self.calls.append({"topic": topic, "key": key, "value": value})
        if self._fail_topics is not None and (
            not self._fail_topics or topic in self._fail_topics
        ):
            raise RuntimeError("broker unavailable")


class _FrozenDatetime:
    """Stand-in for the module's ``datetime`` name with a fixed ``now``."""

    @staticmethod
    def now(tz: Any = None) -> datetime:
        return _FIXED_NOW if tz is None else _FIXED_NOW.astimezone(tz)


class _FakeTime:
    """Stand-in for the module's ``time`` name with a deterministic clock."""

    def __init__(self) -> None:
        self._ticks = itertools.count()

    def perf_counter(self) -> float:
        return next(self._ticks) * 0.25


def _compliant_response() -> str:
    return json.dumps({"compliant": True, "confidence": 0.95, "violations": []})


def _violating_response() -> str:
    return json.dumps(
        {
            "compliant": False,
            "confidence": 0.85,
            "violations": [
                {
                    "pattern_id": "P001",
                    "description": "Code does not use frozen Pydantic models",
                    "severity": "major",
                    "line_reference": "line 5",
                }
            ],
        }
    )


def _pattern(pattern_id: str = "P001") -> ModelApplicablePatternPayload:
    return ModelApplicablePatternPayload(
        pattern_id=pattern_id,
        pattern_signature=f"Signature for {pattern_id}",
        domain_id="onex",
        confidence=0.9,
    )


def _command(
    content: str = _CONTENT,
    content_sha256: str = _CONTENT_SHA256,
    patterns: tuple[str, ...] = ("P001",),
    session_id: str | None = None,
) -> ModelComplianceEvaluateCommand:
    return ModelComplianceEvaluateCommand(
        correlation_id=_CORRELATION_ID,
        source_path="src/foo.py",
        content=content,
        content_sha256=content_sha256,
        language="python",
        applicable_patterns=[_pattern(p) for p in patterns],
        session_id=session_id,
    )


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelComplianceEvaluateCommand],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Normal path: compliant result, no producer.
    (
        "compliant-no-producer",
        _WRAPPER_CLASS,
        _command,
        lambda: {"llm_client": FakeLlmClient(_compliant_response())},
    ),
    # Compliant result published to Kafka with a session id.
    (
        "compliant-published",
        _WRAPPER_CLASS,
        lambda: _command(session_id="session-1", patterns=("P001", "P002")),
        lambda: {
            "llm_client": FakeLlmClient(_compliant_response()),
            "kafka_producer": FakeKafkaProducer(),
        },
    ),
    # Violations mapped into the event payload.
    (
        "violating-published",
        _WRAPPER_CLASS,
        _command,
        lambda: {
            "llm_client": FakeLlmClient(_violating_response()),
            "kafka_producer": FakeKafkaProducer(),
        },
    ),
    # Custom model and publish topic are forwarded.
    (
        "custom-model-and-topic",
        _WRAPPER_CLASS,
        _command,
        lambda: {
            "llm_client": FakeLlmClient(_compliant_response()),
            "model": "custom-model",
            "kafka_producer": FakeKafkaProducer(),
            "publish_topic": "test.custom.topic.v1",
        },
    ),
    # LLM client raises: structured failure event.
    (
        "llm-error",
        _WRAPPER_CLASS,
        _command,
        lambda: {
            "llm_client": FakeLlmClient(error=RuntimeError("connection refused")),
            "kafka_producer": FakeKafkaProducer(),
        },
    ),
    # LLM answers with something that is not JSON.
    (
        "llm-unparseable-response",
        _WRAPPER_CLASS,
        _command,
        lambda: {"llm_client": FakeLlmClient("this is not json")},
    ),
    # No LLM client at all.
    (
        "llm-client-missing",
        _WRAPPER_CLASS,
        _command,
        lambda: {"llm_client": None},
    ),
    # Edge: declared hash differs from the content hash, no producer.
    (
        "sha-mismatch-no-producer",
        _WRAPPER_CLASS,
        lambda: _command(content_sha256=_WRONG_SHA256),
        lambda: {"llm_client": FakeLlmClient(_compliant_response())},
    ),
    # Edge: hash mismatch routes the original envelope to the DLQ.
    (
        "sha-mismatch-dlq",
        _WRAPPER_CLASS,
        lambda: _command(content_sha256=_WRONG_SHA256, session_id="session-2"),
        lambda: {
            "llm_client": FakeLlmClient(_compliant_response()),
            "kafka_producer": FakeKafkaProducer(),
        },
    ),
    # Error: the event publish fails, so the failure goes to the DLQ topic.
    (
        "publish-failure-routes-to-dlq",
        _WRAPPER_CLASS,
        _command,
        lambda: {
            "llm_client": FakeLlmClient(_compliant_response()),
            "kafka_producer": FakeKafkaProducer(
                fail_topics=(handler_module.PUBLISH_TOPIC,)
            ),
        },
    ),
    # Error: both the event publish and the DLQ publish fail and are swallowed.
    (
        "publish-and-dlq-failure",
        _WRAPPER_CLASS,
        _command,
        lambda: {
            "llm_client": FakeLlmClient(_compliant_response()),
            "kafka_producer": FakeKafkaProducer(fail_topics=()),
        },
    ),
]


def _recorded(dependencies: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return the calls recorded by every fake dependency."""
    return {
        name: dep.calls
        for name, dep in dependencies.items()
        if getattr(dep, "calls", None) is not None
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
    request_builder: Callable[[], ModelComplianceEvaluateCommand],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved function agree on result and calls."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    # Pin only the non-deterministic inputs: the wall clock and the timer.
    monkeypatch.setattr(handler_module, "datetime", _FrozenDatetime)

    monkeypatch.setattr(handler_module, "time", _FakeTime())
    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    monkeypatch.setattr(handler_module, "time", _FakeTime())
    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await handle_compliance_evaluate_command(request_b, **deps_b)
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
