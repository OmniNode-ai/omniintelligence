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
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.exceptions import (
    TraceParsingValidationError,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceData,
    ModelTraceLog,
)


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

        assert result["span_id"] == "span-123"
        assert result["trace_id"] == "trace-456"
        assert result["operation_name"] == "test_operation"
        assert result["service_name"] == "test_service"
        assert result["duration_ms"] == 1000.0
        assert result["children"] == []

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

        assert len(result["logs"]) == 1
        assert result["logs"][0]["level"] == "INFO"
        assert result["logs"][0]["message"] == "Processing started"

    def test_build_span_tree_with_tags(self) -> None:
        """Build span tree with tags."""
        trace_data = ModelTraceData(
            span_id="span-123",
            tags={"component": "api", "version": "1.0"},
        )

        result = build_span_tree(trace_data)

        assert result["tags"]["component"] == "api"
        assert result["tags"]["version"] == "1.0"

    def test_build_span_tree_missing_span_id_raises(self) -> None:
        """Build span tree should raise when span_id is missing."""
        trace_data = ModelTraceData(
            trace_id="trace-456",
            operation_name="test",
        )

        with pytest.raises(TraceParsingValidationError) as exc_info:
            build_span_tree(trace_data)

        assert "span_id is required" in str(exc_info.value)


class TestCorrelateLogsWithSpan:
    """Tests for correlate_logs_with_span function."""

    def test_correlate_empty_external_logs(self) -> None:
        """Correlate with no external logs returns span's logs."""
        span = build_span_tree(
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

    def test_correlate_matching_trace_id(self) -> None:
        """Correlate external logs with matching trace_id."""
        span = build_span_tree(
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
                fields={"trace_id": "trace-456"},
            ),
        ]

        result = correlate_logs_with_span(span, external_logs)

        assert len(result) == 1
        assert result[0]["message"] == "External log"

    def test_correlate_non_matching_trace_id(self) -> None:
        """External logs with non-matching trace_id are excluded."""
        span = build_span_tree(
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


class TestComputeTimingMetrics:
    """Tests for compute_timing_metrics function."""

    def test_compute_timing_with_duration(self) -> None:
        """Compute timing metrics from span with duration."""
        span = build_span_tree(
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
        span = build_span_tree(
            ModelTraceData(
                span_id="span-123",
            )
        )

        result = compute_timing_metrics(span)

        assert result["total_duration_ms"] is None
        assert result["span_count"] == 1
        assert result["latency_breakdown"] == {}


class TestExtractSpanEvents:
    """Tests for extract_span_events function."""

    def test_extract_start_and_end_events(self) -> None:
        """Extract both start and end events from span."""
        span = build_span_tree(
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
        span = build_span_tree(
            ModelTraceData(
                span_id="span-123",
            )
        )

        events = extract_span_events(span)

        assert len(events) == 0


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
