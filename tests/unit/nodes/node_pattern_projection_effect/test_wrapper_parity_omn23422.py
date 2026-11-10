# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerPublishProjection (OMN-23422).

The contract-bound handler ``HandlerPublishProjection.handle`` splats the
request mapping into ``publish_projection`` exactly like the preserved function
is called, so both must return the same snapshot for the same request and the
same store and producer, and must drive the store and producer identically.
``uuid4`` and ``datetime`` in the handler module are pinned so the snapshot id
and timestamp are comparable. Cases cover a single page, pagination, malformed
rows, query failures, and the producer branches.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC
from datetime import datetime as real_datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic_core import to_jsonable_python

from omniintelligence.nodes.node_pattern_projection_effect.handlers import (
    handler_projection,
)
from omniintelligence.nodes.node_pattern_projection_effect.handlers.handler_projection import (
    publish_projection,
)

_MODULE = (
    "omniintelligence.nodes.node_pattern_projection_effect.handlers.handler_projection"
)
_WRAPPER_CLASS = "HandlerPublishProjection"
_TOPIC = "dev.onex.evt.omniintelligence.pattern-projection.v1"
_CORRELATION_ID = UUID("00000000-0000-0000-0000-00000000c0de")
_TRIGGER_PATTERN_ID = UUID("00000000-0000-0000-0000-00000000bee5")
_PAGE = 500


class _FrozenDatetime(real_datetime):
    """``datetime`` whose ``now`` is fixed so the snapshot time is stable."""

    @classmethod
    def now(cls, tz: Any = None) -> "_FrozenDatetime":
        return cls(2025, 1, 1, 0, 0, 0, tzinfo=tz)


def _deterministic_uuid4() -> Callable[[], UUID]:
    """Return a ``uuid4`` replacement yielding a fresh predictable sequence."""
    counter = iter(range(0x7000, 0x7100))

    def _next() -> UUID:
        return UUID(int=next(counter))

    return _next


@pytest.fixture(autouse=True)
def _pin_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the handler module's clock for both the wrapper and function runs."""
    monkeypatch.setattr(handler_projection, "datetime", _FrozenDatetime)


class FakePatternQueryStore:
    """In-memory pattern store paging over fixed rows and recording each query."""

    def __init__(
        self,
        rows: list[Any],
        error_on_call: int | None = None,
    ) -> None:
        self._rows = rows
        self._error_on_call = error_on_call
        self.calls: list[dict[str, Any]] = []

    async def query_patterns_projection(
        self, *, min_confidence: float, limit: int, offset: int
    ) -> list[Any]:
        self.calls.append(
            {"min_confidence": min_confidence, "limit": limit, "offset": offset}
        )
        if self._error_on_call is not None and len(self.calls) == self._error_on_call:
            raise RuntimeError("pattern store unavailable")
        return self._rows[offset : offset + limit]


class FakeProducer:
    """In-memory Kafka publisher recording each publish call."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def publish(self, topic: str, key: str, value: dict[str, object]) -> None:
        self.calls.append({"topic": topic, "key": key, "value": value})
        if self._error is not None:
            raise self._error


def _row(index: int) -> dict[str, Any]:
    return {
        "id": UUID(int=0x1000 + index),
        "pattern_signature": f"signature-{index}",
        "signature_hash": f"sha256:{index:064x}",
        "domain_id": "test-domain",
        "project_scope": "omniclaude" if index % 2 else None,
        "quality_score": 0.8 if index % 3 else None,
        "confidence": 0.9,
        "status": "validated",
        "is_current": True,
        "version": 1,
        "created_at": real_datetime(2025, 1, 1, tzinfo=UTC),
    }


def _rows(count: int) -> list[dict[str, Any]]:
    return [_row(i) for i in range(count)]


def _build_request(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "correlation_id": _CORRELATION_ID,
        "publish_topic": _TOPIC,
        "trigger_event_type": "PatternPromoted",
        "triggering_pattern_id": _TRIGGER_PATTERN_ID,
    }
    values.update(overrides)
    return values


def _deps(
    rows: list[Any] | None = None,
    *,
    error_on_call: int | None = None,
    producer: FakeProducer | None = None,
    with_producer: bool = True,
) -> dict[str, Any]:
    return {
        "pattern_query_store": FakePatternQueryStore(
            _rows(3) if rows is None else rows, error_on_call=error_on_call
        ),
        "producer": (producer or FakeProducer()) if with_producer else None,
    }


PARITY_CASES: list[
    tuple[str, str, Callable[[], dict[str, Any]], Callable[[], dict[str, Any]]]
] = [
    # Normal path: one page of patterns is published.
    ("single-page-published", _WRAPPER_CLASS, _build_request, _deps),
    # Defaults: only the required keywords, default trigger metadata.
    (
        "minimal-request",
        _WRAPPER_CLASS,
        lambda: {"correlation_id": None, "publish_topic": _TOPIC},
        _deps,
    ),
    # Edge: the store has no patterns, so an empty snapshot is published.
    ("empty-store", _WRAPPER_CLASS, _build_request, lambda: _deps([])),
    # Pagination: more than one full page is fetched.
    (
        "paginated-two-pages",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(_rows(_PAGE + 1)),
    ),
    # Pagination edge: exactly one full page forces a final empty fetch.
    (
        "exact-page-boundary",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(_rows(_PAGE)),
    ),
    # Malformed rows are skipped while valid rows are kept.
    (
        "malformed-rows-skipped",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps([_row(0), {"id": "not-a-uuid"}, "not-a-mapping", _row(1)]),
    ),
    # Producer branch: no producer, the snapshot is built but not published.
    (
        "no-producer",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(with_producer=False),
    ),
    # Producer branch: a producer without a topic skips publishing.
    (
        "producer-without-topic",
        _WRAPPER_CLASS,
        lambda: _build_request(publish_topic=None),
        _deps,
    ),
    # Error path: Kafka publish fails and is swallowed.
    (
        "publish-failure",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(producer=FakeProducer(error=RuntimeError("broker down"))),
    ),
    # Error path: the first query fails, an empty snapshot is returned unpublished.
    (
        "query-failure-first-page",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(error_on_call=1),
    ),
    # Error path: a later page fails, discarding the earlier pages.
    (
        "query-failure-second-page",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(_rows(_PAGE + 5), error_on_call=2),
    ),
    # Error path: a required keyword is missing from the request.
    (
        "missing-publish-topic",
        _WRAPPER_CLASS,
        lambda: {"correlation_id": _CORRELATION_ID},
        _deps,
    ),
]


async def _invoke_preserved(
    request: dict[str, Any], dependencies: dict[str, Any]
) -> Any:
    """Call the preserved function exactly as the wrapper's forwarding line does."""
    return await publish_projection(**request, **dependencies)


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
    """Wrapper handle() and the preserved publish_projection() agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    monkeypatch.setattr(handler_projection, "uuid4", _deterministic_uuid4())
    try:
        wrapper_result = await wrapper_cls(**deps_for_wrapper).handle(
            request_for_wrapper
        )
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    monkeypatch.setattr(handler_projection, "uuid4", _deterministic_uuid4())
    try:
        function_result = await _invoke_preserved(
            request_for_function, deps_for_function
        )
    except Exception as exc:  # captured deliberately for parity comparison
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
        payload = to_jsonable_python(request_builder())
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
