# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic parity proof for canonical wrappers and preserved functions."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    build_span_tree,
    extract_all_errors,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    handler_trace_parsing as parsing_module,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceData,
    ModelTraceLog,
)

pytestmark = pytest.mark.unit

CORRELATION_ID = "11111111-1111-1111-1111-111111111111"


def _trace_data(
    *,
    span_id: str | None = "span-123",
    status: str = "OK",
    tags: dict[str, str] | None = None,
    logs: list[ModelTraceLog] | None = None,
) -> ModelTraceData:
    """Build a trace with fixed context and timestamps."""
    return ModelTraceData(
        span_id=span_id,
        trace_id="trace-456",
        operation_name="parse_trace",
        service_name="parser",
        start_time="2026-01-01T00:00:00Z",
        end_time="2026-01-01T00:00:01Z",
        duration_ms=1000.0,
        status=status,
        tags=tags or {},
        logs=logs or [],
    )


def _event_request(
    *,
    status: str = "OK",
    tags: dict[str, str] | None = None,
    correlated_logs: list[dict[str, str | None]] | None = None,
) -> BaseModel:
    """Build an independent span for each error extraction case."""
    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelEventExtractionRequest,
    )

    span = build_span_tree(_trace_data(status=status, tags=tags))["span"]
    assert span is not None
    return ModelEventExtractionRequest(
        span=span,
        correlated_logs=correlated_logs or [],
        correlation_id=CORRELATION_ID,
    )


def _span_tree_request(trace_data: ModelTraceData) -> BaseModel:
    """Load the canonical request model only when building a case."""
    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelSpanTreeRequest,
    )

    return ModelSpanTreeRequest(trace_data=trace_data, correlation_id=CORRELATION_ID)


PARITY_CASES: list[tuple[str, Callable[[], BaseModel]]] = [
    (
        "span-tree-with-logs",
        lambda: _span_tree_request(
            _trace_data(
                tags={"component": "parser"},
                logs=[
                    ModelTraceLog(
                        timestamp="2026-01-01T00:00:00Z",
                        level="INFO",
                        message="Processing started",
                    )
                ],
            ),
        ),
    ),
    (
        "span-tree-missing-id",
        lambda: _span_tree_request(_trace_data(span_id=None)),
    ),
    (
        "span-tree-empty-id",
        lambda: _span_tree_request(_trace_data(span_id="")),
    ),
    ("events-no-errors", _event_request),
    (
        "events-log-error",
        lambda: _event_request(
            correlated_logs=[
                {
                    "level": "ERROR",
                    "message": "Connection failed",
                    "timestamp": "2026-01-01T00:00:01Z",
                },
                {
                    "level": "INFO",
                    "message": "Processing",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
            ]
        ),
    ),
    (
        "events-span-error",
        lambda: _event_request(
            status="error", tags={"error.message": "Connection refused"}
        ),
    ),
    ("events-timeout-deduplicated", lambda: _event_request(status="timeout")),
    ("events-timeout-tag", lambda: _event_request(tags={"timeout": "true"})),
]


@pytest.fixture(autouse=True)
def deterministic_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix generated IDs for exact comparisons on independent inputs."""
    monkeypatch.setattr(
        parsing_module.uuid,
        "uuid4",
        lambda: UUID("22222222-2222-2222-2222-222222222222"),
    )


@pytest.mark.parametrize(
    ("case_id", "build_request"),
    PARITY_CASES,
    ids=[case_id for case_id, _ in PARITY_CASES],
)
def test_canonical_dispatch_matches_preserved_core(
    case_id: str,
    build_request: Callable[[], BaseModel],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Match results and correlation-aware logs using fresh requests."""
    if case_id.startswith("span-tree-"):
        module_name = "handler_trace_parsing"
        class_name = "HandlerTraceParsing"
    else:
        module_name = "handler_event_extraction"
        class_name = "HandlerEventExtraction"
    module = importlib.import_module(
        f"omniintelligence.nodes.node_execution_trace_parser_compute.handlers.{module_name}"
    )
    handler_cls = getattr(module, class_name, None)
    assert handler_cls is not None, f"{class_name} is missing from {module.__name__}"

    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelEventExtractionRequest,
        ModelSpanTreeRequest,
    )

    parity_request = build_request()
    class_request = parity_request.model_copy(deep=True)
    core_request = parity_request.model_copy(deep=True)
    with caplog.at_level(
        "DEBUG", logger="omniintelligence.nodes.node_execution_trace_parser_compute"
    ):
        actual = handler_cls().handle(class_request).model_dump()
        class_logs = [
            (record.getMessage(), record.__dict__["correlation_id"])
            for record in caplog.records
        ]
        caplog.clear()

        if isinstance(core_request, ModelSpanTreeRequest):
            result = build_span_tree(
                core_request.trace_data, correlation_id=core_request.correlation_id
            )
            expected = {"result": result}
            assert result["success"] is (case_id == "span-tree-with-logs")
        else:
            assert isinstance(core_request, ModelEventExtractionRequest)
            errors = extract_all_errors(
                core_request.span,
                core_request.correlated_logs,
                correlation_id=core_request.correlation_id,
            )
            expected = {"error_events": errors}
            expected_types = {
                "events-no-errors": [],
                "events-log-error": ["LOG_ERROR"],
                "events-span-error": ["SPAN_ERROR"],
                "events-timeout-deduplicated": ["SPAN_ERROR"],
                "events-timeout-tag": ["TIMEOUT"],
            }
            assert [error["error_type"] for error in errors] == expected_types[case_id]
        core_logs = [
            (record.getMessage(), record.__dict__["correlation_id"])
            for record in caplog.records
        ]

    assert actual == expected
    assert class_request == core_request == parity_request
    assert class_logs == core_logs
    assert class_logs
    assert all(context == CORRELATION_ID for _, context in class_logs)
