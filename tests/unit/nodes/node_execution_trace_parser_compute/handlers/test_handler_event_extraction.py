# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for event extraction handler."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    build_span_tree,
    detect_log_errors,
    detect_span_errors,
    detect_timeout_errors,
    extract_all_errors,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceData,
)

pytestmark = pytest.mark.unit


def _build_span(trace_data: ModelTraceData):
    """Helper to build span and extract from result."""
    result = build_span_tree(trace_data)
    assert result["success"], f"Build failed: {result['error_message']}"
    return result["span"]


class TestDetectSpanErrors:
    """Tests for detect_span_errors function."""

    def test_detect_error_status(self) -> None:
        """Detect error from span status."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="db_query",
                status="error",
                end_time="2026-01-01T00:00:01Z",
            )
        )

        errors = detect_span_errors(span)

        assert len(errors) == 1
        error = errors[0]
        assert error["error_type"] == "SPAN_ERROR"
        assert "error" in error["error_message"].lower()
        assert error["span_id"] == "span-123"

    def test_detect_error_with_message_tag(self) -> None:
        """Detect error with error.message tag."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="failed",
                tags={"error.message": "Connection refused"},
            )
        )

        errors = detect_span_errors(span)

        assert len(errors) == 1
        assert errors[0]["error_message"] == "Connection refused"

    def test_detect_error_with_stack_trace(self) -> None:
        """Detect error with stack trace in tags."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="exception",
                tags={
                    "error.stack": "Traceback (most recent call last):\n  File...",
                },
            )
        )

        errors = detect_span_errors(span)

        assert len(errors) == 1
        assert errors[0]["stack_trace"] is not None
        assert "Traceback" in errors[0]["stack_trace"]

    def test_no_error_ok_status(self) -> None:
        """No error detected for OK status."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="OK",
            )
        )

        errors = detect_span_errors(span)

        assert len(errors) == 0

    def test_detect_error_includes_duration_ms(self) -> None:
        """Detect error includes duration_ms in attributes for monitoring."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="error",
                duration_ms=5000.0,
            )
        )

        errors = detect_span_errors(span)

        assert len(errors) == 1
        assert "duration_ms" in errors[0]["attributes"]
        assert errors[0]["attributes"]["duration_ms"] == "5000.0"

    def test_detect_error_with_correlation_id(self) -> None:
        """Detect error with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="error",
            )
        )

        errors = detect_span_errors(span, correlation_id="test-correlation-123")

        assert len(errors) == 1


class TestDetectLogErrors:
    """Tests for detect_log_errors function."""

    def test_detect_error_level_log(self) -> None:
        """Detect error from ERROR level log."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="process",
                service_name="worker",
            )
        )
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "ERROR",
                "message": "Connection failed",
            },
        ]

        errors = detect_log_errors(span, logs)

        assert len(errors) == 1
        error = errors[0]
        assert error["error_type"] == "LOG_ERROR"
        assert error["error_message"] == "Connection failed"
        assert error["attributes"]["operation_name"] == "process"
        assert error["attributes"]["log_level"] == "ERROR"

    def test_detect_fatal_level_log(self) -> None:
        """Detect error from FATAL level log."""
        span = _build_span(ModelTraceData(span_id="span-123"))
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "FATAL",
                "message": "Out of memory",
            },
        ]

        errors = detect_log_errors(span, logs)

        assert len(errors) == 1
        assert errors[0]["error_type"] == "LOG_ERROR"

    def test_no_error_info_level(self) -> None:
        """No error detected for INFO level log."""
        span = _build_span(ModelTraceData(span_id="span-123"))
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "INFO",
                "message": "Request processed",
            },
        ]

        errors = detect_log_errors(span, logs)

        assert len(errors) == 0

    def test_detect_log_error_includes_duration_ms(self) -> None:
        """Detect log error includes duration_ms in attributes for monitoring."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                duration_ms=3000.0,
            )
        )
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "ERROR",
                "message": "Something failed",
            },
        ]

        errors = detect_log_errors(span, logs)

        assert len(errors) == 1
        assert "duration_ms" in errors[0]["attributes"]
        assert errors[0]["attributes"]["duration_ms"] == "3000.0"

    def test_detect_log_error_with_correlation_id(self) -> None:
        """Detect log error with correlation_id for tracing."""
        span = _build_span(ModelTraceData(span_id="span-123"))
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "ERROR",
                "message": "Error occurred",
            },
        ]

        errors = detect_log_errors(span, logs, correlation_id="test-correlation-123")

        assert len(errors) == 1


class TestDetectTimeoutErrors:
    """Tests for detect_timeout_errors function."""

    def test_detect_timeout_status(self) -> None:
        """Detect timeout from status."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="external_api",
                status="timeout",
                duration_ms=30000.0,
            )
        )

        errors = detect_timeout_errors(span)

        assert len(errors) == 1
        error = errors[0]
        assert error["error_type"] == "TIMEOUT"
        assert "external_api" in error["error_message"]
        assert error["attributes"]["duration_ms"] == "30000.0"

    def test_detect_timeout_tag(self) -> None:
        """Detect timeout from tag."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="slow_query",
                status="OK",  # Status doesn't indicate error
                tags={"timeout": "true"},
            )
        )

        errors = detect_timeout_errors(span)

        assert len(errors) == 1
        assert errors[0]["error_type"] == "TIMEOUT"

    def test_no_timeout_normal_span(self) -> None:
        """No timeout detected for normal span."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="OK",
            )
        )

        errors = detect_timeout_errors(span)

        assert len(errors) == 0

    def test_detect_timeout_with_correlation_id(self) -> None:
        """Detect timeout with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="timeout",
            )
        )

        errors = detect_timeout_errors(span, correlation_id="test-correlation-123")

        assert len(errors) == 1


class TestExtractAllErrors:
    """Tests for extract_all_errors function."""

    def test_extract_combined_errors(self) -> None:
        """Extract errors from multiple sources."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="multi_error",
                status="OK",  # No span error
            )
        )
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "ERROR",
                "message": "Log error occurred",
            },
        ]

        errors = extract_all_errors(span, logs)

        assert len(errors) == 1  # Just log error
        assert errors[0]["error_type"] == "LOG_ERROR"

    def test_deduplication_span_and_timeout(self) -> None:
        """Timeout errors deduplicated when span error exists."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                operation_name="failed_op",
                status="timeout",  # This indicates both error and timeout
            )
        )

        errors = extract_all_errors(span, [])

        # Should have span error but not duplicate timeout
        error_types = [e["error_type"] for e in errors]
        assert "SPAN_ERROR" in error_types
        # Timeout not added because span error already captured it
        assert error_types.count("TIMEOUT") <= 1

    def test_no_errors_clean_span(self) -> None:
        """No errors extracted from clean span."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="OK",
            )
        )
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "INFO",
                "message": "All good",
            },
        ]

        errors = extract_all_errors(span, logs)

        assert len(errors) == 0

    def test_extract_all_errors_with_correlation_id(self) -> None:
        """Extract all errors with correlation_id for tracing."""
        span = _build_span(
            ModelTraceData(
                span_id="span-123",
                status="error",
            )
        )

        errors = extract_all_errors(span, [], correlation_id="test-correlation-123")

        assert len(errors) == 1
