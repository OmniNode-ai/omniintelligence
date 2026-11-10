# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound retrieval handler with the preserved function.

OMN-23422: ``HandlerQueryFixRecordsWithDecay.handle`` must return exactly what
``query_fix_records_with_decay`` returns for the same request mapping and the
same store, and must make the same store calls.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_debug_retrieval_compute.handlers.handler_retrieval import (
    query_fix_records_with_decay,
)

MODULE = (
    "omniintelligence.nodes.node_debug_retrieval_compute.handlers.handler_retrieval"
)
WRAPPER = "HandlerQueryFixRecordsWithDecay"

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_FINGERPRINT = "f" * 64


class _FakeStore:
    """In-memory debug store that records every query."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._records = records or []
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def query_fix_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return [dict(r) for r in self._records]


def _records() -> list[dict[str, Any]]:
    return [
        {"id": "r1", "created_at_utc": _NOW - timedelta(days=1), "fix": "a"},
        {"id": "r2", "created_at_utc": _NOW - timedelta(days=30), "fix": "b"},
        {"id": "r3", "created_at_utc": _NOW - timedelta(days=90), "fix": "c"},
    ]


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], BaseModel | dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "decay-weights",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "limit": 5, "now": _NOW},
        lambda: {"store": _FakeStore(_records())},
    ),
    (
        "default-limit-future-record",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "now": _NOW},
        lambda: {
            "store": _FakeStore(
                [{"id": "r9", "created_at_utc": _NOW + timedelta(days=2)}]
            )
        },
    ),
    (
        "naive-and-missing-timestamp",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "limit": 3, "now": _NOW},
        lambda: {
            "store": _FakeStore(
                [
                    {"id": "n1", "created_at_utc": datetime(2025, 5, 2, 12, 0, 0)},
                    {"id": "n2"},
                    {"id": "n3", "created_at_utc": "2025-05-01T00:00:00Z"},
                    {"id": "n4", "created_at_utc": None},
                ]
            )
        },
    ),
    (
        "clock-default-now",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "limit": 2},
        lambda: {
            "store": _FakeStore(
                [{"id": "c1", "created_at_utc": datetime(2999, 1, 1, tzinfo=UTC)}]
            )
        },
    ),
    (
        "no-records",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "limit": 10, "now": _NOW},
        lambda: {"store": _FakeStore([])},
    ),
    (
        "empty-fingerprint",
        WRAPPER,
        lambda: {"failure_fingerprint": "", "limit": 1, "now": _NOW},
        lambda: {"store": _FakeStore([])},
    ),
    (
        "store-raises",
        WRAPPER,
        lambda: {"failure_fingerprint": _FINGERPRINT, "limit": 4, "now": _NOW},
        lambda: {"store": _FakeStore(error=RuntimeError("store unavailable"))},
    ),
    (
        "missing-fingerprint",
        WRAPPER,
        lambda: {"limit": 4, "now": _NOW},
        lambda: {"store": _FakeStore(_records())},
    ),
]


def _request_json(request: BaseModel | dict[str, Any]) -> Any:
    raw = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
    return json.loads(json.dumps(raw, default=str))


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {"case": case_id, "wrapper": class_name, "request": _request_json(build())}
        for case_id, class_name, build, _ in PARITY_CASES
    ]


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
) -> None:
    """The wrapper and the preserved function agree on result, raise and calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

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
        function_result = await query_fix_records_with_decay(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert deps_a["store"].calls == deps_b["store"].calls
