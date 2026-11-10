# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound intent-reception wrappers match the preserved functions.

``HandlerReceiveIntent`` and ``HandlerReceiveIntents`` forward to
``handle_receive_intent`` and ``handle_receive_intents``. Each wrapper is run
against identical requests and dependencies and must return (or raise) exactly
what the preserved function does. The receipt timestamp is pinned by patching
the receipt model module's clock.

Ticket: OMN-23422
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.payloads import (
    ModelPayloadExtension,
    ModelPayloadLogEvent,
)

from omniintelligence.nodes.node_intelligence_orchestrator.handlers.handler_receive_intent import (
    handle_receive_intent,
    handle_receive_intents,
)

MODULE = (
    "omniintelligence.nodes.node_intelligence_orchestrator.handlers."
    "handler_receive_intent"
)
RECEIPT_MODULE = (
    "omniintelligence.nodes.node_intelligence_orchestrator.models.model_intent_receipt"
)
SINGLE = "HandlerReceiveIntent"
BATCH = "HandlerReceiveIntents"

_PRESERVED: dict[str, Callable[..., Any]] = {
    SINGLE: handle_receive_intent,
    BATCH: handle_receive_intents,
}

_FIXED_TIME = datetime(2025, 1, 1, tzinfo=UTC)
_CORRELATION_ID = UUID("12345678-1234-5678-1234-567812345678")
_PATTERN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _extension_intent(
    n: int = 1, *, priority: int = 1, lease: bool = False
) -> ModelIntent:
    return ModelIntent(
        intent_id=UUID(f"00000000-0000-0000-0000-{n:012d}"),
        intent_type="extension",
        target=f"postgres://patterns/{_PATTERN_ID}",
        payload=ModelPayloadExtension(
            extension_type="omniintelligence.pattern_lifecycle_update",
            plugin_name="omniintelligence",
            data={
                "pattern_id": _PATTERN_ID,
                "from_status": "candidate",
                "to_status": "validated",
            },
        ),
        priority=priority,
        lease_id=UUID("00000000-0000-0000-0000-0000000000ee") if lease else None,
        epoch=7 if lease else None,
    )


def _log_intent(n: int = 9) -> ModelIntent:
    return ModelIntent(
        intent_id=UUID(f"00000000-0000-0000-0000-{n:012d}"),
        intent_type="log_event",
        target="log://orchestrator",
        payload=ModelPayloadLogEvent(level="INFO", message="hello", context={}),
        priority=3,
    )


def _no_deps() -> dict[str, Any]:
    return {}


def _with_correlation() -> dict[str, Any]:
    return {"correlation_id": _CORRELATION_ID}


def _with_bad_correlation() -> dict[str, Any]:
    return {"correlation_id": "not-a-uuid"}


PARITY_CASES: list[tuple[str, str, Callable[[], Any], Callable[[], dict[str, Any]]]] = [
    ("single-extension", SINGLE, _extension_intent, _no_deps),
    (
        "single-with-correlation-lease-epoch",
        SINGLE,
        lambda: _extension_intent(2, priority=5, lease=True),
        _with_correlation,
    ),
    ("single-log-payload", SINGLE, _log_intent, _with_correlation),
    (
        "single-explicit-none-correlation",
        SINGLE,
        _extension_intent,
        lambda: {"correlation_id": None},
    ),
    ("single-invalid-correlation", SINGLE, _extension_intent, _with_bad_correlation),
    ("batch-empty", BATCH, lambda: (), _no_deps),
    ("batch-empty-with-correlation", BATCH, lambda: (), _with_correlation),
    (
        "batch-mixed",
        BATCH,
        lambda: (_extension_intent(1), _log_intent(), _extension_intent(3, lease=True)),
        _with_correlation,
    ),
    ("batch-single-no-correlation", BATCH, lambda: (_extension_intent(4),), _no_deps),
    (
        "batch-invalid-correlation",
        BATCH,
        lambda: (_extension_intent(5), _log_intent()),
        _with_bad_correlation,
    ),
]


def _describe(request: Any) -> Any:
    if isinstance(request, tuple):
        return [intent.model_dump(mode="json") for intent in request]
    return request.model_dump(mode="json")


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(_describe(request_builder()), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], Any],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper returns (or raises) exactly what the preserved function does."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, *_args: Any, **_kwargs: Any) -> datetime:
            return _FIXED_TIME

    monkeypatch.setattr(
        importlib.import_module(RECEIPT_MODULE), "datetime", _FixedDatetime
    )

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()
    preserved = _PRESERVED[class_name]

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = preserved(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
        assert wrapper_result is not None
    if case_id.endswith("invalid-correlation"):
        assert function_error is not None
    if class_name == BATCH and not request_a:
        assert function_result == []
