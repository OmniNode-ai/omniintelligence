# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound demotion handlers with the preserved functions.

OMN-23422: ``HandlerCheckAndDemotePatterns.handle`` must return exactly what
``check_and_demote_patterns`` returns, and ``HandlerDemotePattern.handle`` must
return exactly what ``demote_pattern`` returns, for the same request mapping
and the same repository and producer dependencies. The handler module's clock
(``datetime``) and ``uuid4`` are patched with deterministic stand-ins so that
the results and the published lifecycle events can be compared for equality.
"""

import importlib
import json
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

import omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion as handler_mod
from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
    check_and_demote_patterns,
    demote_pattern,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models import (
    ModelDemotionCheckRequest,
    ModelEffectiveThresholds,
)

MODULE = "omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion"
CHECK = "HandlerCheckAndDemotePatterns"
DEMOTE = "HandlerDemotePattern"

_PRESERVED: dict[str, Callable[..., Any]] = {
    CHECK: check_and_demote_patterns,
    DEMOTE: demote_pattern,
}

_FIXED_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("12345678-1234-1234-1234-123456789abc")


class _FixedDatetime(datetime):
    """``datetime`` whose ``now`` returns the fixed instant."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        del tz
        return _FIXED_NOW


class _UuidSequence:
    """Deterministic ``uuid4`` replacement; reset before each run."""

    def __init__(self) -> None:
        self.counter = 0

    def reset(self) -> None:
        self.counter = 0

    def __call__(self) -> UUID:
        self.counter += 1
        return UUID(int=self.counter)


class _FakeRepository:
    """In-memory pattern repository recording every call."""

    def __init__(
        self,
        patterns: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._patterns = patterns or []
        self._error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append(("fetch", (query, *args)))
        if self._error is not None:
            raise self._error
        return deepcopy(self._patterns)

    async def fetchrow(self, query: str, *args: Any) -> None:
        self.calls.append(("fetchrow", (query, *args)))

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", (query, *args)))
        return "UPDATE 0"


class _FakeProducer:
    """In-memory Kafka publisher recording every publish."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("kafka down")


def _uid(n: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


def _pattern(
    n: int,
    *,
    injections: int | None = 20,
    successes: int | None = 18,
    failures: int | None = 2,
    streak: int | None = 0,
    promoted_hours_ago: float | None = 48,
    disabled: bool = False,
    signature: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": _uid(n),
        "pattern_signature": signature or f"sig-{n}",
        "injection_count_rolling_20": injections,
        "success_count_rolling_20": successes,
        "failure_count_rolling_20": failures,
        "failure_streak": streak,
        "promoted_at": None
        if promoted_hours_ago is None
        else _FIXED_NOW - timedelta(hours=promoted_hours_ago),
        "is_disabled": disabled,
    }
    return record


def _mixed_patterns() -> list[dict[str, Any]]:
    return [
        _pattern(1),  # healthy, no drift
        _pattern(2, injections=15, successes=3, failures=12, streak=2),  # low rate
        _pattern(3, injections=8, successes=3, failures=5, streak=6),  # streak
        _pattern(4, streak=7, promoted_hours_ago=2),  # streak but in cooldown
        _pattern(5, disabled=True, promoted_hours_ago=1),  # manual, bypasses cooldown
        _pattern(6, injections=None, successes=None, failures=None, streak=None),
        _pattern(7, injections=12, successes=0, failures=0, streak=0),  # zero outcomes
        _pattern(8, streak=9, promoted_hours_ago=None),  # no promoted_at
    ]


def _check_request(**overrides: Any) -> dict[str, Any]:
    return {
        "request": ModelDemotionCheckRequest(
            correlation_id=_CORRELATION_ID, **overrides
        )
    }


def _deps(
    patterns: list[dict[str, Any]] | None = None,
    *,
    producer: bool = True,
    producer_fails: bool = False,
    fetch_error: Exception | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {
            "repository": _FakeRepository(patterns, fetch_error),
            "producer": _FakeProducer(producer_fails) if producer else None,
        }

    return build


_DEFAULT_THRESHOLDS = ModelEffectiveThresholds(
    max_success_rate=0.4,
    min_failure_streak=5,
    min_injection_count=10,
    cooldown_hours=24,
    overrides_applied=False,
)


def _demote_request(
    reason: str,
    pattern: dict[str, Any],
    *,
    correlation_id: UUID | None = _CORRELATION_ID,
) -> dict[str, Any]:
    return {
        "pattern_id": pattern["id"],
        "pattern_data": pattern,
        "reason": reason,
        "thresholds": _DEFAULT_THRESHOLDS,
        "correlation_id": correlation_id,
    }


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], BaseModel | dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "check-mixed-live",
        CHECK,
        _check_request,
        _deps(_mixed_patterns()),
    ),
    (
        "check-mixed-dry-run",
        CHECK,
        lambda: _check_request(dry_run=True),
        _deps(_mixed_patterns()),
    ),
    (
        "check-no-patterns",
        CHECK,
        _check_request,
        _deps([]),
    ),
    (
        "check-no-producer",
        CHECK,
        _check_request,
        _deps(_mixed_patterns(), producer=False),
    ),
    (
        "check-publish-failure",
        CHECK,
        _check_request,
        _deps(_mixed_patterns(), producer_fails=True),
    ),
    (
        "check-allowed-overrides",
        CHECK,
        lambda: _check_request(
            max_success_rate=0.55,
            min_failure_streak=3,
            min_injection_count=2,
            cooldown_hours=0,
            allow_threshold_override=True,
        ),
        _deps(_mixed_patterns()),
    ),
    (
        "check-skips-record-without-required-fields",
        CHECK,
        _check_request,
        _deps([{"injection_count_rolling_20": 30}, _pattern(2, streak=8)]),
    ),
    (
        "check-overrides-without-allow-raises",
        CHECK,
        lambda: _check_request(min_failure_streak=3),
        _deps(_mixed_patterns()),
    ),
    (
        "check-success-rate-out-of-bounds-raises",
        CHECK,
        lambda: {
            "request": ModelDemotionCheckRequest.model_construct(
                max_success_rate=0.95, allow_threshold_override=True
            )
        },
        _deps(_mixed_patterns()),
    ),
    (
        "check-failure-streak-out-of-bounds-raises",
        CHECK,
        lambda: {
            "request": ModelDemotionCheckRequest.model_construct(
                min_failure_streak=50, allow_threshold_override=True
            )
        },
        _deps(_mixed_patterns()),
    ),
    (
        "check-injection-count-below-one-raises",
        CHECK,
        lambda: {
            "request": ModelDemotionCheckRequest.model_construct(
                min_injection_count=0, allow_threshold_override=True
            )
        },
        _deps(_mixed_patterns()),
    ),
    (
        "check-negative-cooldown-raises",
        CHECK,
        lambda: {
            "request": ModelDemotionCheckRequest.model_construct(
                cooldown_hours=-1, allow_threshold_override=True
            )
        },
        _deps(_mixed_patterns()),
    ),
    (
        "check-fetch-raises",
        CHECK,
        _check_request,
        _deps(fetch_error=RuntimeError("database unavailable")),
    ),
    (
        "check-invalid-snapshot-raises",
        CHECK,
        _check_request,
        _deps([_pattern(3, streak=-1, disabled=True)]),
    ),
    (
        "demote-failure-streak",
        DEMOTE,
        lambda: _demote_request(
            "failure_streak: 6 consecutive failures", _pattern(3, streak=6)
        ),
        _deps(),
    ),
    (
        "demote-manual-disable",
        DEMOTE,
        lambda: _demote_request(
            "manual_disable", _pattern(5, disabled=True, promoted_hours_ago=1)
        ),
        _deps(),
    ),
    (
        "demote-low-success-rate-no-correlation",
        DEMOTE,
        lambda: _demote_request(
            "low_success_rate: 20.0%",
            _pattern(2, injections=15, successes=3, failures=12),
            correlation_id=None,
        ),
        _deps(),
    ),
    (
        "demote-no-producer",
        DEMOTE,
        lambda: _demote_request("manual_disable", _pattern(5, disabled=True)),
        _deps(producer=False),
    ),
    (
        "demote-publish-failure",
        DEMOTE,
        lambda: _demote_request("failure_streak: 5", _pattern(3, streak=5)),
        _deps(producer_fails=True),
    ),
    (
        "demote-sparse-pattern-data",
        DEMOTE,
        lambda: _demote_request(
            "failure_streak: 5", {"id": _uid(9), "pattern_signature": "sparse"}
        ),
        _deps(),
    ),
    (
        "demote-invalid-snapshot-raises",
        DEMOTE,
        lambda: _demote_request("manual_disable", _pattern(3, streak=-1)),
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
    producer = deps["producer"]
    return {
        "repository": deps["repository"].calls,
        "producer": None if producer is None else producer.calls,
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
    uuids = _UuidSequence()
    monkeypatch.setattr(handler_mod, "datetime", _FixedDatetime)
    monkeypatch.setattr(handler_mod, "uuid4", uuids)
    preserved = _PRESERVED[class_name]

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    uuids.reset()
    wrapper_error: Exception | None = None
    wrapper_result: Any = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc

    uuids.reset()
    function_error: Exception | None = None
    function_result: Any = None
    try:
        function_result = await preserved(**request_b, **deps_b)
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
