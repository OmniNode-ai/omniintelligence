# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerRouteStorage (OMN-23422).

``HandlerRouteStorage.handle`` must return exactly what the preserved
``handle_route_storage`` returns for the same event and the same storage
client registry and DLQ publisher, and must make identical store and DLQ
calls. Cases cover each routed backend, an unroutable event type, a missing
client, a storage failure with retries remaining, and a storage failure with
retries exhausted (with a DLQ publisher, without one, and with a failing one).
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_storage_router_effect.handlers import (
    handler_route_storage as handler_module,
)
from omniintelligence.nodes.node_storage_router_effect.handlers.handler_route_storage import (
    MAX_RETRIES,
    StorageClientRegistry,
    handle_route_storage,
)
from omniintelligence.nodes.node_storage_router_effect.models import (
    EnumStorageBackend,
    ModelStorageRouteInput,
)

_MODULE = (
    "omniintelligence.nodes.node_storage_router_effect.handlers.handler_route_storage"
)
_WRAPPER_CLASS = "HandlerRouteStorage"
_FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_PRODUCED_AT = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
_EVENT_ID = UUID("00000000-0000-0000-0000-000000000001")
_CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")


class FakeStorageClient:
    """In-memory ``ProtocolStorageClient`` recording each store call."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def store(
        self,
        *,
        event_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
    ) -> None:
        """Record the call, then raise if this fake was configured to fail."""
        self.calls.append(
            {
                "event_id": event_id,
                "payload": payload,
                "correlation_id": correlation_id,
            }
        )
        if self._error is not None:
            raise self._error


class FakeDlqPublisher:
    """In-memory ``ProtocolDlqPublisher`` recording each DLQ publish."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def publish_to_dlq(
        self,
        *,
        event_id: UUID,
        original_event: dict[str, Any],
        error_message: str,
        retry_count: int,
        correlation_id: UUID | None = None,
    ) -> None:
        """Record the call, then raise if this fake was configured to fail."""
        self.calls.append(
            {
                "event_id": event_id,
                "original_event": original_event,
                "error_message": error_message,
                "retry_count": retry_count,
                "correlation_id": correlation_id,
            }
        )
        if self._error is not None:
            raise self._error


class _FrozenDatetime:
    """Stand-in for the module's ``datetime`` name with a fixed ``now``."""

    @staticmethod
    def now(tz: Any = None) -> datetime:
        return _FIXED_NOW if tz is None else _FIXED_NOW.astimezone(tz)


def _event(
    event_type: str = "vectorization.completed",
    *,
    retry_count: int = 0,
    correlation_id: UUID | None = _CORRELATION_ID,
) -> ModelStorageRouteInput:
    return ModelStorageRouteInput(
        event_id=_EVENT_ID,
        event_type=event_type,
        correlation_id=correlation_id,
        payload={"document": "doc-1", "vector": [0.1, 0.2], "count": 2},
        source_node="node_test_compute",
        produced_at=_PRODUCED_AT,
        retry_count=retry_count,
    )


def _deps(
    *,
    backends: tuple[EnumStorageBackend, ...] = (
        EnumStorageBackend.QDRANT,
        EnumStorageBackend.MEMGRAPH,
        EnumStorageBackend.POSTGRESQL,
    ),
    store_error: Exception | None = None,
    dlq: FakeDlqPublisher | None = None,
) -> Callable[[], dict[str, Any]]:
    """Return a builder of fresh registry and publisher fakes on every call."""

    def build() -> dict[str, Any]:
        deps: dict[str, Any] = {
            "client_registry": StorageClientRegistry(
                clients={b: FakeStorageClient(store_error) for b in backends}
            )
        }
        if dlq is not None:
            deps["dlq_publisher"] = FakeDlqPublisher(dlq._error)
        return deps

    return build


_STORE_ERROR = RuntimeError("backend unavailable")
_DLQ = FakeDlqPublisher()

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelStorageRouteInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Normal path: vectorization events are stored in Qdrant.
    ("route-qdrant", _WRAPPER_CLASS, _event, _deps()),
    # Entity extraction events are stored in Memgraph.
    (
        "route-memgraph",
        _WRAPPER_CLASS,
        lambda: _event("entity.extraction-completed"),
        _deps(),
    ),
    # Pattern events are stored in PostgreSQL, without a correlation id.
    (
        "route-postgresql-no-correlation",
        _WRAPPER_CLASS,
        lambda: _event("pattern.matched", correlation_id=None),
        _deps(),
    ),
    # Edge: no routing rule for the event type.
    (
        "unroutable-event-type",
        _WRAPPER_CLASS,
        lambda: _event("unknown.event"),
        _deps(),
    ),
    # Edge: no client registered for the resolved backend.
    (
        "client-not-registered",
        _WRAPPER_CLASS,
        lambda: _event("pattern.matched"),
        _deps(backends=(EnumStorageBackend.QDRANT,)),
    ),
    # Error path: storage fails with retries remaining.
    (
        "storage-failure-retry-remaining",
        _WRAPPER_CLASS,
        lambda: _event(retry_count=1),
        _deps(store_error=_STORE_ERROR, dlq=_DLQ),
    ),
    # Error path: retries exhausted and the failure is published to the DLQ.
    (
        "storage-failure-routes-to-dlq",
        _WRAPPER_CLASS,
        lambda: _event(retry_count=MAX_RETRIES),
        _deps(store_error=_STORE_ERROR, dlq=_DLQ),
    ),
    # Error path: retries exhausted and no DLQ publisher is configured.
    (
        "storage-failure-dlq-publisher-missing",
        _WRAPPER_CLASS,
        lambda: _event("entity.extraction-completed", retry_count=MAX_RETRIES + 2),
        _deps(store_error=_STORE_ERROR),
    ),
    # Error path: retries exhausted and the DLQ publish itself fails.
    (
        "storage-and-dlq-failure",
        _WRAPPER_CLASS,
        lambda: _event("pattern.matched", retry_count=MAX_RETRIES),
        _deps(
            store_error=_STORE_ERROR,
            dlq=FakeDlqPublisher(error=RuntimeError("dlq unavailable")),
        ),
    ),
]


def _recorded(dependencies: dict[str, Any]) -> dict[str, Any]:
    """Return the calls recorded by every fake client and publisher."""
    recorded: dict[str, Any] = {}
    for name, dep in dependencies.items():
        if isinstance(dep, StorageClientRegistry):
            recorded[name] = {
                backend.value: client.calls for backend, client in dep.clients.items()
            }
        elif hasattr(dep, "calls"):
            recorded[name] = dep.calls
    return recorded


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelStorageRouteInput],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved function agree on result and calls."""
    wrapper_cls = getattr(importlib.import_module(_MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    # Pin only the wall clock used for ``routed_at``.
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
        function_result = await handle_route_storage(request_b, **deps_b)
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
