# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for trace parsing compute handler."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    PARSER_VERSION,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    handler_compute as canonical_handler,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceData,
    ModelTraceLog,
    ModelTraceParsingInput,
)

pytestmark = pytest.mark.unit


class TestHandleTraceParsingCompute:
    """Tests for HandlerTraceParsingCompute orchestrator."""

    def test_parse_basic_trace(self) -> None:
        """Parse a basic trace and verify output structure."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                operation_name="test_operation",
                service_name="test_service",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
                duration_ms=1000.0,
                status="OK",
            ),
            correlation_id="11111111-1111-1111-1111-111111111111",
            trace_format="json",
            extract_errors=True,
            extract_timing=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.parser_version == PARSER_VERSION
        assert result.metadata.source_format == "json"
        assert result.metadata.parse_time_ms > 0

    def test_extract_span_events(self) -> None:
        """Verify span events are extracted when extract_timing=True."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
            ),
            extract_timing=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert len(result.parsed_events) == 2
        event_types = [e.event_type for e in result.parsed_events]
        assert "SPAN_START" in event_types
        assert "SPAN_END" in event_types

    def test_extract_timing_disabled(self) -> None:
        """No span events when extract_timing=False."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
            ),
            extract_timing=False,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert len(result.parsed_events) == 0

    def test_extract_error_events(self) -> None:
        """Verify error events are extracted when extract_errors=True."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                status="error",
                end_time="2026-01-01T00:00:01Z",
            ),
            extract_errors=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert len(result.error_events) >= 1
        assert result.error_events[0].error_type == "SPAN_ERROR"

    def test_extract_errors_disabled(self) -> None:
        """No error events when extract_errors=False."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                status="error",
            ),
            extract_errors=False,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert len(result.error_events) == 0

    def test_timing_data_computed(self) -> None:
        """Verify timing data is computed."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                operation_name="db_query",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:00.5Z",
                duration_ms=500.0,
            ),
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert result.timing_data.total_duration_ms == 500.0
        assert result.timing_data.span_count == 1
        assert result.timing_data.latency_breakdown.get("db_query") == 500.0

    def test_metadata_counts_match(self) -> None:
        """Verify metadata counts match list lengths."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                status="error",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
            ),
            extract_errors=True,
            extract_timing=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.event_count == len(result.parsed_events)
        assert result.metadata.error_count == len(result.error_events)

    def test_validation_error_missing_span_id(self) -> None:
        """Validation error returned when span_id is missing."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                trace_id="trace-456",
                operation_name="test",
            ),
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is False
        assert result.metadata is not None
        assert len(result.metadata.warnings) > 0
        assert "validation" in result.metadata.warnings[0].lower()

    def test_error_output_structure(self) -> None:
        """Error output has valid structure."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                # Missing span_id will cause validation error
                trace_id="trace-456",
            ),
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        # Even on error, output should be valid
        assert result.success is False
        assert result.parsed_events == []
        assert result.error_events == []
        assert result.timing_data is not None
        assert result.metadata is not None


class TestHandleTraceParsingComputeWithLogs:
    """Tests for parsing traces with embedded logs."""

    def test_parse_trace_with_embedded_logs(self) -> None:
        """Parse trace that has embedded log entries."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                operation_name="process_request",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
                logs=[
                    ModelTraceLog(
                        timestamp="2026-01-01T00:00:00.5Z",
                        level="INFO",
                        message="Processing started",
                    ),
                    ModelTraceLog(
                        timestamp="2026-01-01T00:00:00.8Z",
                        level="ERROR",
                        message="Processing failed",
                    ),
                ],
            ),
            extract_errors=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        # Should detect log-level error
        assert any(e.error_type == "LOG_ERROR" for e in result.error_events)

    def test_parse_trace_with_error_tags(self) -> None:
        """Parse trace with error information in tags."""
        input_data = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id="span-123",
                operation_name="api_call",
                status="failed",
                tags={
                    "error.message": "Connection timeout",
                    "error.stack": "Traceback...",
                },
            ),
            extract_errors=True,
        )

        result = canonical_handler.HandlerTraceParsingCompute().handle(input_data)

        assert result.success is True
        assert len(result.error_events) >= 1

        span_error = next(
            (e for e in result.error_events if e.error_type == "SPAN_ERROR"), None
        )
        assert span_error is not None
        assert span_error.error_message == "Connection timeout"
        assert span_error.stack_trace == "Traceback..."


# Shared with the coverage receipt recorder; no random input defaults.
CANONICAL_PARITY_CASES = [
    {
        "case": "basic",
        "input": {
            "trace_data": {
                "span_id": "span-1",
                "trace_id": "trace-1",
                "operation_name": "work",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:00:01Z",
                "duration_ms": 1000.0,
            },
            "correlation_id": "11111111-1111-1111-1111-111111111111",
        },
    },
    {
        "case": "error",
        "input": {
            "trace_data": {
                "span_id": "span-1",
                "trace_id": "trace-1",
                "operation_name": "work",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:00:01Z",
                "duration_ms": 1000.0,
                "status": "error",
            },
            "extract_errors": True,
        },
    },
    {
        "case": "extraction_disabled",
        "input": {
            "trace_data": {
                "span_id": "span-1",
                "trace_id": "trace-1",
                "operation_name": "work",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:00:01Z",
                "duration_ms": 1000.0,
                "status": "error",
            },
            "extract_errors": False,
            "extract_timing": False,
        },
    },
    {
        "case": "missing_span",
        "input": {"trace_data": {"trace_id": "trace-1"}, "trace_format": "json"},
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("payload", CANONICAL_PARITY_CASES, ids=lambda p: p["case"])
def test_canonical_dispatch_matches_preserved_core(payload, monkeypatch):
    """Compare canonical dispatch with the git-preserved core on branch cases.

    Resolve the class inside the test so the legacy tree collects successfully
    and fails this assertion, rather than failing import/collection.
    """
    handler_class = getattr(canonical_handler, "HandlerTraceParsingCompute", None)
    assert handler_class is not None, "canonical handle(request) class is required"
    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelTraceParsingInput,
    )

    request = ModelTraceParsingInput.model_validate(payload["input"])
    # Only nondeterministic clocks/IDs are controlled; the algorithm runs normally.
    from uuid import UUID

    monkeypatch.setattr("time.perf_counter", lambda: 100.0)
    monkeypatch.setattr(
        "uuid.uuid4", lambda: UUID("22222222-2222-2222-2222-222222222222")
    )
    expected = canonical_handler._execute_parsing(
        request, 100.0, request.correlation_id
    )
    assert handler_class().handle(request) == expected
