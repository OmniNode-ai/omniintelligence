# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerProcessEnforcementFeedback (OMN-23422).

``HandlerProcessEnforcementFeedback.handle`` must return exactly what the
preserved ``process_enforcement_feedback`` returns for the same event and the
same repository, and must issue identical repository calls. Cases cover the
no-violation, no-adjustment, success, partial-success (repository failure) and
unhandled-exception (ERROR) outcomes, plus a pattern that does not exist.
"""

import importlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_enforcement_feedback_effect.handlers import (
    handler_enforcement_feedback as handler_module,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.handlers.handler_enforcement_feedback import (
    process_enforcement_feedback,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.models import (
    ModelEnforcementEvent,
    ModelPatternViolation,
)

_MODULE = (
    "omniintelligence.nodes.node_enforcement_feedback_effect.handlers."
    "handler_enforcement_feedback"
)
_WRAPPER_CLASS = "HandlerProcessEnforcementFeedback"
_FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_CORRELATION_ID = UUID("00000000-0000-0000-0000-0000000000a1")
_SESSION_ID = UUID("00000000-0000-0000-0000-0000000000b1")
_PATTERN_1 = UUID("00000000-0000-0000-0000-000000000001")
_PATTERN_2 = UUID("00000000-0000-0000-0000-000000000002")
_PATTERN_3 = UUID("00000000-0000-0000-0000-000000000003")


class FakePatternRepository:
    """In-memory ``ProtocolPatternRepository`` recording every call."""

    def __init__(
        self,
        scores: dict[UUID, float] | None = None,
        failing: tuple[UUID, ...] = (),
    ) -> None:
        self.scores = dict(scores or {})
        self._failing = failing
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        self.calls.append(("fetch", query, args))
        return []

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        self.calls.append(("fetchrow", query, args))
        return None

    async def execute(self, query: str, *args: Any) -> str:
        """Apply the quality-score UPDATE to the in-memory scores."""
        self.calls.append(("execute", query, args))
        pattern_id, delta = args[0], args[1]
        if pattern_id in self._failing:
            raise RuntimeError(f"database unavailable for {pattern_id}")
        if pattern_id not in self.scores:
            return "UPDATE 0"
        self.scores[pattern_id] = max(0.0, min(1.0, self.scores[pattern_id] + delta))
        return "UPDATE 1"


def _violation(
    pattern_id: UUID, *, advised: bool = True, corrected: bool = True
) -> ModelPatternViolation:
    return ModelPatternViolation(
        pattern_id=pattern_id,
        pattern_name=f"pattern-{pattern_id.int}",
        was_advised=advised,
        was_corrected=corrected,
    )


def _event(
    *violations: ModelPatternViolation, patterns_checked: int = 5
) -> ModelEnforcementEvent:
    return ModelEnforcementEvent(
        correlation_id=_CORRELATION_ID,
        session_id=_SESSION_ID,
        patterns_checked=patterns_checked,
        violations_found=len(violations),
        violations=list(violations),
    )


def _repo(**kwargs: Any) -> Callable[[], dict[str, Any]]:
    return lambda: {
        "repository": FakePatternRepository(
            scores={_PATTERN_1: 0.8, _PATTERN_2: 0.5}, **kwargs
        )
    }


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelEnforcementEvent],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Normal path: one confirmed violation lowers the quality score.
    (
        "confirmed-violation",
        _WRAPPER_CLASS,
        lambda: _event(_violation(_PATTERN_1)),
        _repo(),
    ),
    # Several violations: only the advised-and-corrected ones are adjusted.
    (
        "mixed-violations",
        _WRAPPER_CLASS,
        lambda: _event(
            _violation(_PATTERN_1),
            _violation(_PATTERN_2, corrected=False),
            _violation(_PATTERN_3, advised=False),
        ),
        _repo(),
    ),
    # No violations in the event.
    (
        "no-violations",
        _WRAPPER_CLASS,
        lambda: _event(),
        _repo(),
    ),
    # Violations exist but none is confirmed.
    (
        "no-confirmed-violations",
        _WRAPPER_CLASS,
        lambda: _event(
            _violation(_PATTERN_1, corrected=False),
            _violation(_PATTERN_2, advised=False, corrected=False),
        ),
        _repo(),
    ),
    # Edge: the pattern does not exist (UPDATE 0), so no adjustment is recorded.
    (
        "pattern-not-found",
        _WRAPPER_CLASS,
        lambda: _event(_violation(_PATTERN_3)),
        _repo(),
    ),
    # Error path: the repository raises for one pattern, the other succeeds.
    (
        "partial-success-repository-error",
        _WRAPPER_CLASS,
        lambda: _event(_violation(_PATTERN_1), _violation(_PATTERN_2)),
        _repo(failing=(_PATTERN_2,)),
    ),
    # Error path: every adjustment fails.
    (
        "all-adjustments-fail",
        _WRAPPER_CLASS,
        lambda: _event(_violation(_PATTERN_1)),
        _repo(failing=(_PATTERN_1,)),
    ),
    # Error path: an unhandled exception becomes a structured ERROR result.
    (
        "unhandled-exception-error-result",
        _WRAPPER_CLASS,
        lambda: _event(_violation(_PATTERN_1)),
        _repo(),
    ),
]


def _raise_unhandled(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("unexpected infrastructure failure")


def _recorded(dependencies: dict[str, Any]) -> dict[str, Any]:
    """Return the calls and final state recorded by every fake dependency."""
    return {
        name: (dep.calls, dep.scores)
        for name, dep in dependencies.items()
        if hasattr(dep, "calls")
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
    request_builder: Callable[[], ModelEnforcementEvent],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved function agree on result and calls."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    # Pin only the wall clock used for ``processed_at``.
    class _FrozenDatetime:
        @staticmethod
        def now(tz: Any = None) -> datetime:
            return _FIXED_NOW if tz is None else _FIXED_NOW.astimezone(tz)

    monkeypatch.setattr(handler_module, "datetime", _FrozenDatetime)
    if case_id == "unhandled-exception-error-result":
        monkeypatch.setattr(
            handler_module, "_process_enforcement_feedback_inner", _raise_unhandled
        )

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await process_enforcement_feedback(request_b, **deps_b)
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
