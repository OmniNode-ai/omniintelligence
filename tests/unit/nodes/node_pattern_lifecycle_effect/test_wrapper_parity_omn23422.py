# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerApplyTransition (OMN-23422).

``HandlerApplyTransition.handle`` splats its request mapping into the
preserved ``apply_transition`` together with the injected dependencies. It
must return exactly what the function returns for the same keyword arguments
and the same repository, idempotency store and producer, and must make
identical repository, store and publish calls. Cases cover the successful
transition (with and without producer, idempotency store, transactional
connection and each gate snapshot form), every validation and guard rejection,
a duplicate request, a missing pattern, a failed status guard, a database
failure, and a publish failure routed to the DLQ.
"""

import importlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers import (
    handler_transition as handler_module,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    apply_transition,
)

_MODULE = (
    "omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition"
)
_WRAPPER_CLASS = "HandlerApplyTransition"
_FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_TRANSITION_AT = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
_TRANSITION_ID = UUID("00000000-0000-0000-0000-0000000000f1")
_PATTERN_ID = UUID("00000000-0000-0000-0000-000000000001")
_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000002")
_CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000003")
_TOPIC = "test.onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"

_Status = EnumPatternLifecycleStatus


class FakePatternRepository:
    """In-memory ``ProtocolPatternRepository`` recording every call."""

    def __init__(
        self,
        *,
        status: str = "candidate",
        evidence_tier: str | None = "unmeasured",
        exists: bool = True,
        fail_on: str | None = None,
    ) -> None:
        self._row: dict[str, Any] | None = (
            {"id": _PATTERN_ID, "status": status, "evidence_tier": evidence_tier}
            if exists
            else None
        )
        self._fail_on = fail_on
        self.calls: list[tuple[str, tuple[str, ...], tuple[Any, ...]]] = []

    @staticmethod
    def _head(query: str) -> str:
        return " ".join(query.split())[:60]

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.calls.append(("fetch", (self._head(query),), args))
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.calls.append(("fetchrow", (self._head(query),), args))
        return self._row

    async def execute(self, query: str, *args: Any) -> str:
        """Apply the status-guarded UPDATE, then the audit INSERT."""
        self.calls.append(("execute", (self._head(query),), args))
        if "UPDATE learned_patterns" in query:
            if self._fail_on == "update":
                raise RuntimeError("update failed: connection reset")
            guard_matches = self._row is not None and self._row["status"] == args[3]
            return "UPDATE 1" if guard_matches else "UPDATE 0"
        if self._fail_on == "insert":
            raise RuntimeError("insert failed: disk full")
        return "INSERT 0 1"


class FakeIdempotencyStore:
    """In-memory ``ProtocolIdempotencyStore`` recording every call."""

    def __init__(self, seen: tuple[UUID, ...] = ()) -> None:
        self.recorded: set[UUID] = set(seen)
        self.calls: list[tuple[str, UUID]] = []

    async def check_and_record(self, request_id: UUID) -> bool:
        self.calls.append(("check_and_record", request_id))
        was_seen = request_id in self.recorded
        self.recorded.add(request_id)
        return was_seen

    async def exists(self, request_id: UUID) -> bool:
        self.calls.append(("exists", request_id))
        return request_id in self.recorded

    async def record(self, request_id: UUID) -> None:
        self.calls.append(("record", request_id))
        self.recorded.add(request_id)


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


def _request(
    from_status: EnumPatternLifecycleStatus,
    to_status: EnumPatternLifecycleStatus,
    **overrides: Any,
) -> dict[str, Any]:
    """Keyword arguments for ``apply_transition`` excluding the dependencies."""
    request: dict[str, Any] = {
        "request_id": _REQUEST_ID,
        "correlation_id": _CORRELATION_ID,
        "pattern_id": _PATTERN_ID,
        "from_status": from_status,
        "to_status": to_status,
        "trigger": "auto_promote",
        "transition_at": _TRANSITION_AT,
    }
    request.update(overrides)
    return request


def _deps(
    *,
    status: str = "candidate",
    evidence_tier: str | None = "unmeasured",
    store: bool = False,
    seen: bool = False,
    producer: FakeKafkaPublisher | None = None,
    **repo_kwargs: Any,
) -> Callable[[], dict[str, Any]]:
    """Return a builder of fresh dependency fakes on every call."""

    def build() -> dict[str, Any]:
        deps: dict[str, Any] = {
            "repository": FakePatternRepository(
                status=status, evidence_tier=evidence_tier, **repo_kwargs
            ),
            "idempotency_store": (
                FakeIdempotencyStore((_REQUEST_ID,) if seen else ()) if store else None
            ),
            "producer": None
            if producer is None
            else FakeKafkaPublisher(producer._fail_topics),
        }
        return deps

    return build


_PUBLISHING = FakeKafkaPublisher()
_PROVISIONAL_TO_VALIDATED = _request(_Status.PROVISIONAL, _Status.VALIDATED)

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Normal path: CANDIDATE -> PROVISIONAL with enough evidence, no extras.
    (
        "candidate-to-provisional",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="observed"),
    ),
    # Full path: store records the request and the producer emits the event.
    (
        "validated-with-store-and-producer",
        _WRAPPER_CLASS,
        lambda: _request(
            _Status.PROVISIONAL,
            _Status.VALIDATED,
            actor="gate-runner",
            reason="Gates passed",
            publish_topic=_TOPIC,
        ),
        _deps(
            status="provisional",
            evidence_tier="measured",
            store=True,
            producer=_PUBLISHING,
        ),
    ),
    # Verified evidence also satisfies the VALIDATED guard; plain dict snapshot.
    (
        "validated-dict-gate-snapshot",
        _WRAPPER_CLASS,
        lambda: _request(
            _Status.PROVISIONAL,
            _Status.VALIDATED,
            gate_snapshot={"success_rate_rolling_20": 0.9},
        ),
        _deps(status="provisional", evidence_tier="verified"),
    ),
    # Dict snapshot that already carries an evidence tier is not overwritten.
    (
        "dict-gate-snapshot-with-tier",
        _WRAPPER_CLASS,
        lambda: _request(
            _Status.PROVISIONAL,
            _Status.VALIDATED,
            gate_snapshot={"evidence_tier": "measured", "failure_streak": 0},
        ),
        _deps(status="provisional", evidence_tier="measured"),
    ),
    # Model snapshot is serialized and enriched with the evidence tier.
    (
        "model-gate-snapshot",
        _WRAPPER_CLASS,
        lambda: _request(
            _Status.PROVISIONAL,
            _Status.VALIDATED,
            gate_snapshot=ModelGateSnapshot(
                success_rate_rolling_20=0.95,
                injection_count_rolling_20=20,
                failure_streak=0,
            ),
        ),
        _deps(status="provisional", evidence_tier="measured"),
    ),
    # A transactional connection receives the reads and writes instead.
    (
        "uses-transactional-conn",
        _WRAPPER_CLASS,
        lambda: _request(_Status.VALIDATED, _Status.DEPRECATED, trigger="manual"),
        lambda: {
            **_deps(status="validated", evidence_tier="measured", store=True)(),
            "conn": FakePatternRepository(status="validated", evidence_tier="measured"),
        },
    ),
    # Validation: whitespace-only trigger.
    (
        "empty-trigger-rejected",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL, trigger="   "),
        _deps(evidence_tier="observed"),
    ),
    # Validation: a producer without a publish topic.
    (
        "producer-without-topic-rejected",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="observed", producer=_PUBLISHING),
    ),
    # Guard: only CANDIDATE may move to PROVISIONAL.
    (
        "provisional-guard-rejected",
        _WRAPPER_CLASS,
        lambda: _request(_Status.VALIDATED, _Status.PROVISIONAL),
        _deps(status="validated", evidence_tier="measured"),
    ),
    # Idempotency: an already processed request returns a cached success.
    (
        "duplicate-request",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="observed", store=True, seen=True),
    ),
    # Not found: the pattern row does not exist.
    (
        "pattern-not-found",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(exists=False),
    ),
    # Evidence guard: PROVISIONAL requires at least OBSERVED.
    (
        "evidence-guard-provisional",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="unmeasured"),
    ),
    # Evidence guard: VALIDATED requires at least MEASURED.
    (
        "evidence-guard-validated",
        _WRAPPER_CLASS,
        lambda: dict(_PROVISIONAL_TO_VALIDATED),
        _deps(status="provisional", evidence_tier="observed"),
    ),
    # Edge: a null evidence tier counts as UNMEASURED.
    (
        "null-evidence-tier",
        _WRAPPER_CLASS,
        lambda: dict(_PROVISIONAL_TO_VALIDATED),
        _deps(status="provisional", evidence_tier=None),
    ),
    # Edge: an unparseable evidence tier counts as UNMEASURED.
    (
        "unparseable-evidence-tier",
        _WRAPPER_CLASS,
        lambda: dict(_PROVISIONAL_TO_VALIDATED),
        _deps(status="provisional", evidence_tier="bogus-tier"),
    ),
    # Optimistic lock: the stored status differs from from_status.
    (
        "status-guard-failed",
        _WRAPPER_CLASS,
        lambda: _request(_Status.VALIDATED, _Status.DEPRECATED),
        _deps(status="provisional", evidence_tier="measured", store=True),
    ),
    # Error path: the UPDATE raises and becomes a structured failure.
    (
        "database-error-on-update",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="observed", store=True, fail_on="update"),
    ),
    # Error path: the audit INSERT raises after a successful UPDATE.
    (
        "database-error-on-insert",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL),
        _deps(evidence_tier="observed", store=True, fail_on="insert"),
    ),
    # Error path: the event publish fails and is routed to the DLQ.
    (
        "publish-failure-routes-to-dlq",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL, publish_topic=_TOPIC),
        _deps(
            evidence_tier="observed",
            producer=FakeKafkaPublisher(fail_topics=(_TOPIC,)),
        ),
    ),
    # Error path: the publish and the DLQ publish both fail.
    (
        "publish-and-dlq-failure",
        _WRAPPER_CLASS,
        lambda: _request(_Status.CANDIDATE, _Status.PROVISIONAL, publish_topic=_TOPIC),
        _deps(evidence_tier="observed", producer=FakeKafkaPublisher(fail_topics=())),
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
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved function agree on result and calls."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    # Pin only the non-deterministic inputs: the transition id and the clock.
    monkeypatch.setattr(handler_module, "uuid4", lambda: _TRANSITION_ID)
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
        function_result = await apply_transition(**request_b, **deps_b)
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


def _jsonable(value: Any) -> Any:
    """JSON default hook: pydantic models by their JSON dump, else ``str``."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)


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
                "request": json.loads(json.dumps(payload, default=_jsonable)),
            }
        )
    return rows
