# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the protocol handler effect (OMN-373 / OMN-23422).

``HandlerProtocolExecute.handle`` must return exactly what the preserved
``handle_protocol_execute`` function returns for the same request and the same
handler registry, and must drive the registered protocol handler identically.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_protocol import (
    ProtocolHandlerRegistry,
    handle_protocol_execute,
)
from omniintelligence.nodes.node_protocol_handler_effect.models import (
    EnumProtocolType,
    ModelProtocolHandlerInput,
)

MODULE = "omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_protocol"
CLASS_NAME = "HandlerProtocolExecute"
_CORRELATION_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_FIXED_NOW = datetime(2026, 3, 1, 8, 0, 0, tzinfo=UTC)


class _RecordingProtocolHandler:
    """In-memory protocol handler that records calls and can raise on demand."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.execute_calls: list[tuple[str, dict[str, Any], str | None]] = []
        self._result = {"status": "ok"} if result is None else result
        self._error = error

    async def connect(self, config: dict[str, Any]) -> None:
        return None

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        self.execute_calls.append((operation, params, correlation_id))
        if self._error is not None:
            raise self._error
        return self._result

    async def disconnect(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True


def _request(
    protocol: EnumProtocolType = EnumProtocolType.HTTP_REST,
    operation: str = "GET",
    correlation_id: UUID | None = _CORRELATION_ID,
    retry_count: int = 0,
    params: dict[str, Any] | None = None,
) -> Callable[[], ModelProtocolHandlerInput]:
    return lambda: ModelProtocolHandlerInput(
        correlation_id=correlation_id,
        protocol=protocol,
        operation=operation,
        config={"base_url": "http://example.invalid"},
        params=params if params is not None else {"path": "/items", "limit": 5},
        retry_count=retry_count,
    )


def _deps(
    protocol: EnumProtocolType | None = EnumProtocolType.HTTP_REST,
    result: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        registry = ProtocolHandlerRegistry()
        if protocol is not None:
            registry.handlers[protocol] = _RecordingProtocolHandler(result, error)
        return {"handler_registry": registry}

    return build


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelProtocolHandlerInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "success-with-correlation",
        CLASS_NAME,
        _request(),
        _deps(result={"status_code": 200, "body": [1, 2, 3]}),
    ),
    (
        "success-no-correlation-retry",
        CLASS_NAME,
        _request(
            EnumProtocolType.KAFKA,
            "produce",
            correlation_id=None,
            retry_count=2,
            params={},
        ),
        _deps(EnumProtocolType.KAFKA, result={}),
    ),
    (
        "no-handler-not-connected",
        CLASS_NAME,
        _request(EnumProtocolType.BOLT, "query"),
        _deps(EnumProtocolType.POSTGRESQL),
    ),
    (
        "connection-error",
        CLASS_NAME,
        _request(EnumProtocolType.POSTGRESQL, "query", retry_count=1),
        _deps(EnumProtocolType.POSTGRESQL, error=ConnectionError("refused")),
    ),
    (
        "timeout-error",
        CLASS_NAME,
        _request(operation="POST"),
        _deps(error=TimeoutError("deadline exceeded")),
    ),
    (
        "generic-failure",
        CLASS_NAME,
        _request(EnumProtocolType.BOLT, "write", correlation_id=None),
        _deps(EnumProtocolType.BOLT, error=ValueError("bad cypher")),
    ),
    (
        "registry-none-raises",
        CLASS_NAME,
        _request(),
        lambda: {"handler_registry": None},
    ),
]


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(request_builder().model_dump(mode="json"), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, _tz: Any = None) -> datetime:
        return _FIXED_NOW


def _calls(
    deps: dict[str, Any],
) -> dict[str, list[tuple[str, dict[str, Any], str | None]]]:
    registry = deps["handler_registry"]
    if registry is None:
        return {}
    return {
        protocol.value: handler.execute_calls
        for protocol, handler in registry.handlers.items()
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
    request_builder: Callable[[], ModelProtocolHandlerInput],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return/raise alike and call the handler alike."""
    module = importlib.import_module(MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    # Mask only the non-deterministic sources: the monotonic clock and datetime.now().
    monkeypatch.setattr(module, "time", SimpleNamespace(perf_counter=lambda: 0.0))
    monkeypatch.setattr(module, "datetime", _FixedDatetime)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = None
    function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_protocol_execute(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert _calls(deps_a) == _calls(deps_b)
