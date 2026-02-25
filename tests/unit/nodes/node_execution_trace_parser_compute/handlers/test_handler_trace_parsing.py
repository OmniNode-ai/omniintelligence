# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for trace parsing handler."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    PARSER_VERSION,
    build_span_tree,
    compute_timing_metrics,
    correlate_logs_with_span,
    extract_span_events,
    is_error_log_level,
    is_error_status,
    parse_timestamp,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceData,
    ModelTraceLog,
)

pytestmark = pytest.mark.unit


def _build_span(trace_data: ModelTraceData):
    """Helper to build span and extract from result."""
    result = build_span_tree(trace_data)
    assert result["success"], f"Build failed: {result['error_message']}"
    return result["span"]


class TestParserVersion:
    """Tests for parser version constant."""

    def test_parser_version_is_string(self) -> None:
        """Parser version should be a semantic version string."""
        assert isinstance(PARSER_VERSION, str)
        parts = PARSER_VERSION.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestBuildSpanTree:
    """Tests for build_span_tree function."""

    def test_build_span_tree_basic(self) -> None:
        """Build span tree from basic trace data."""
        trace_data = ModelTraceData(
            span_id="span-123",
            trace_id="trace-456",
            operation_name="test_operation",
            service_name="test_service",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-01T00:00:01Z",
            duration_ms=1000.0,
            status="OK",
        )

        result = build_span_tree(trace_data)

        assert result["success"] is True
        span = result["span"]
        assert span["span_id"] == "span-123"
        assert span["trace_id"] == "trace-456"
        assert span["operation_name"] == "test_operation"
        assert span["service_name"] == "test_service"
        assert span["duration_ms"] == 1000.0
        assert span["children"] == []

    def test_build_span_tree_with_logs(self) -> None:
        """Build span tree with embedded logs."""
        trace_data = ModelTraceData(
            span_id="span-123",
            logs=[
                ModelTraceLog(
                    timestamp="2026-01-01T00:00:00.5Z",
                    level="INFO",
                    message="Processing started",
                ),
            ],
        )

        result = build_span_tree(trace_data)

        assert result["success"] is True
        span = result["span"]
        assert len(span["logs"]) == 1
        assert span["logs"][0]["level"] == "INFO"
        assert span["logs"][0]["message"] == "Processing started"

    def test_build_span_tree_with_tags(self) -> None:
        """Build span tree with tags."""
        trace_data = ModelTraceData(
            span_id="span-123",
            tags={"component": "api", "version": "1.0"},
        )

        result = build_span_tree(trace_data)

        assert result["success"] is True
        span = result["span"]
        assert span["tags"]["component"] == "api"
        assert span["tags"]["version"] == "1.0"

    def test_build_span_tree_missing_span_id_returns_error(self) -> None:
        """Build span tree should return error when span_id is missing."""
        trace_data = ModelTraceData(
            trace_id="trace-456",
            operation_name="test",
        )

        result = build_span_tree(trace_data)

        assert result["success"] is False
        assert result["error_type"] == "validation"
        assert "span_id is required" in result["error_message"]
        assert result["span"] is None

    def test_build_span_tree_with_correlation_id(self) -> None:
        """Build span tree with correlation_id for tracing."""
        trace_data = ModelTraceData(
            span_id="span-123",
        )

        result = build_span_tree(trace_data, correlation_id="test-correlation-123")

        assert result["success"] is True
        assert result["span"] is not None


class TestCorrelateLogsWithSpan:
    """Tests for correlate_logs_with_span function."""

    def test_correlate_empty_external_logs(self) -> None:
        """Correlate with no external logs returns span's logs."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                logs=[
                    ModelTraceLog(
                        timestamp="2026-01-01T00:00:00Z",
                        level="INFO",
                        message="Span log",
                    ),
                ],
            )
        )

        result = correlate_logs_with_span(span, [])

        assert len(result) == 1
        assert result[0]["message"] == "Span log"

    def test_correlate_matching_trace_id_within_time_window(self) -> None:
        """Correlate external logs with matching trace_id within time window."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:10Z",
            )
        )
        external_logs = [
            ModelTraceLog(
                timestamp="2026-01-01T00:00:05Z",  # Within span time window
                level="DEBUG",
                message="External log",
                fields={"trace_id": "trace-456"},
            ),
        ]

        result = correlate_logs_with_span(span, external_logs)

        assert len(result) == 1
        assert result[0]["message"] == "External log"

    def test_correlate_logs_outside_time_window_excluded(self) -> None:
        """External logs outside span time window are excluded."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:10Z",
            )
        )
        external_logs = [
            ModelTraceLog(
                timestamp="2026-01-01T00:01:00Z",  # After span end time
                level="DEBUG",
                message="External log after span",
                fields={"trace_id": "trace-456"},
            ),
        ]

        result = correlate_logs_with_span(span, external_logs)

        assert len(result) == 0

    def test_correlate_non_matching_trace_id(self) -> None:
        """External logs with non-matching trace_id are excluded."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
            )
        )
        external_logs = [
            ModelTraceLog(
                timestamp="2026-01-01T00:00:00Z",
                level="DEBUG",
                message="External log",
                fields={"trace_id": "different-trace"},
            ),
        ]

        result = correlate_logs_with_span(span, external_logs)

        assert len(result) == 0

    def test_correlate_with_correlation_id(self) -> None:
        """Correlate logs with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
            )
        )

        result = correlate_logs_with_span(
            span, [], correlation_id="test-correlation-123"
        )

        assert len(result) == 0  # No logs to correlate


class TestComputeTimingMetrics:
    """Tests for compute_timing_metrics function."""

    def test_compute_timing_with_duration(self) -> None:
        """Compute timing metrics from span with duration."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="db_query",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:00.5Z",
                duration_ms=500.0,
            )
        )

        result = compute_timing_metrics(span)

        assert result["total_duration_ms"] == 500.0
        assert result["span_count"] == 1
        assert result["critical_path_ms"] == 500.0
        assert result["latency_breakdown"]["db_query"] == 500.0

    def test_compute_timing_without_duration(self) -> None:
        """Compute timing metrics from span without duration."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
            )
        )

        result = compute_timing_metrics(span)

        assert result["total_duration_ms"] is None
        assert result["span_count"] == 1
        assert result["latency_breakdown"] == {}

    def test_compute_timing_with_correlation_id(self) -> None:
        """Compute timing with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                duration_ms=100.0,
            )
        )

        result = compute_timing_metrics(span, correlation_id="test-correlation-123")

        assert result["span_count"] == 1


class TestExtractSpanEvents:
    """Tests for extract_span_events function."""

    def test_extract_start_and_end_events(self) -> None:
        """Extract both start and end events from span."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                trace_id="trace-456",
                operation_name="process_request",
                service_name="api",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T00:00:01Z",
                duration_ms=1000.0,
                status="OK",
            )
        )

        events = extract_span_events(span)

        assert len(events) == 2

        start_event = events[0]
        assert start_event["event_type"] == "SPAN_START"
        assert start_event["span_id"] == "span-123"
        assert start_event["operation_name"] == "process_request"
        assert "status" in start_event["attributes"]

        end_event = events[1]
        assert end_event["event_type"] == "SPAN_END"
        assert "duration_ms" in end_event["attributes"]
        assert end_event["attributes"]["duration_ms"] == "1000.0"

    def test_extract_events_no_timestamps(self) -> None:
        """No events extracted when span has no timestamps."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
            )
        )

        events = extract_span_events(span)

        assert len(events) == 0

    def test_extract_events_with_correlation_id(self) -> None:
        """Extract events with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                start_time="2026-01-01T00:00:00Z",
            )
        )

        events = extract_span_events(span, correlation_id="test-correlation-123")

        assert len(events) == 1


class TestIsErrorStatus:
    """Tests for is_error_status function."""

    @pytest.mark.parametrize(
        "status",
        ["error", "ERROR", "failed", "FAILED", "failure", "exception", "timeout"],
    )
    def test_error_statuses(self, status: str) -> None:
        """Error statuses are correctly identified."""
        assert is_error_status(status) is True

    @pytest.mark.parametrize("status", ["OK", "success", "completed", "running"])
    def test_non_error_statuses(self, status: str) -> None:
        """Non-error statuses are correctly identified."""
        assert is_error_status(status) is False

    def test_none_status(self) -> None:
        """None status is not an error."""
        assert is_error_status(None) is False


class TestIsErrorLogLevel:
    """Tests for is_error_log_level function."""

    @pytest.mark.parametrize("level", ["error", "ERROR", "fatal", "critical", "severe"])
    def test_error_levels(self, level: str) -> None:
        """Error log levels are correctly identified."""
        assert is_error_log_level(level) is True

    @pytest.mark.parametrize("level", ["INFO", "DEBUG", "WARN", "WARNING"])
    def test_non_error_levels(self, level: str) -> None:
        """Non-error log levels are correctly identified."""
        assert is_error_log_level(level) is False

    def test_none_level(self) -> None:
        """None level is not an error."""
        assert is_error_log_level(None) is False


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_iso_format_with_z(self) -> None:
        """Parse ISO format with Z suffix."""
        result = parse_timestamp("2026-01-01T12:30:45Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.hour == 12

    def test_parse_iso_format_with_microseconds(self) -> None:
        """Parse ISO format with microseconds."""
        result = parse_timestamp("2026-01-01T12:30:45.123456Z")
        assert result is not None
        assert result.microsecond == 123456

    def test_parse_none(self) -> None:
        """Parse None returns None."""
        assert parse_timestamp(None) is None

    def test_parse_invalid_format(self) -> None:
        """Parse invalid format returns None."""
        assert parse_timestamp("not-a-timestamp") is None
