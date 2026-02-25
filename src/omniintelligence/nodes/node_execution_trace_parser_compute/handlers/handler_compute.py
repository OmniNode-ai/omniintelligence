# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Orchestration handler for Execution Trace Parser Compute.

This module coordinates the trace parsing workflow:
1. Validates input
2. Builds span tree
3. Correlates logs
4. Extracts events and errors
5. Computes timing metrics
6. Constructs output model

Error Handling: Returns structured error output, never raises.
Correlation ID: Threaded through all operations for end-to-end tracing.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.exceptions import (
    TraceParsingComputeError,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_event_extraction import (
    extract_all_errors,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_trace_parsing import (
    PARSER_VERSION,
    build_span_tree,
    compute_timing_metrics,
    correlate_logs_with_span,
    extract_span_events,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    ErrorEventDict,
    ParsedEventDict,
    TimingDataDict,
    TraceMetadataDict,
    create_empty_timing_data,
    create_error_metadata,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelErrorEvent,
    ModelParsedEvent,
    ModelTimingData,
    ModelTraceMetadata,
    ModelTraceParsingOutput,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelTraceParsingInput,
    )

logger = logging.getLogger(__name__)


def handle_trace_parsing_compute(
    input_data: ModelTraceParsingInput,
) -> ModelTraceParsingOutput:
    """Handle trace parsing compute operation.

    This function orchestrates the trace parsing workflow:
    1. Validates input data
    2. Builds span tree from trace data
    3. Correlates external logs with spans
    4. Extracts span lifecycle events
    5. Detects error events
    6. Computes timing metrics
    7. Constructs output model with metadata

    Args:
        input_data: Input containing trace data and parsing options.

    Returns:
        ModelTraceParsingOutput with parsed events, errors, and timing.

    Note:
        This function never raises exceptions. All errors are captured
        and returned as structured output with success=False.
    """
    start_time = time.perf_counter()
    correlation_id = input_data.correlation_id

    logger.debug(
        "Starting trace parsing compute",
        extra={"correlation_id": correlation_id},
    )

    try:
        return _execute_parsing(input_data, start_time, correlation_id)

    except TraceParsingComputeError as e:
        processing_time = _elapsed_time_ms(start_time)
        logger.error(
            "Trace parsing compute error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_compute_error_output(
            str(e), processing_time, input_data.trace_format
        )

    except Exception as e:
        processing_time = _safe_elapsed_time_ms(start_time)
        # Log with exception info, but suppress logging failures
        with contextlib.suppress(Exception):
            logger.exception(
                "Unhandled exception in trace parsing: %s",
                str(e),
                extra={"correlation_id": correlation_id},
            )
        return _create_safe_error_output(
            f"Unhandled error: {e}", processing_time, input_data.trace_format
        )


def _execute_parsing(
    input_data: ModelTraceParsingInput,
    start_time: float,
    correlation_id: str | None,
) -> ModelTraceParsingOutput:
    """Execute the core trace parsing logic.

    Args:
        input_data: Validated input data.
        start_time: Start time for timing calculation.
        correlation_id: Correlation ID for tracing.

    Returns:
        ModelTraceParsingOutput with parsed results.

    Raises:
        TraceParsingComputeError: If computation fails.
    """
    trace_data = input_data.trace_data

    logger.debug(
        "Building span tree",
        extra={"correlation_id": correlation_id},
    )

    # Build span tree - now returns structured result instead of raising
    build_result = build_span_tree(trace_data, correlation_id=correlation_id)

    # Handle validation/compute errors from build_span_tree
    if not build_result["success"]:
        processing_time = _elapsed_time_ms(start_time)
        error_message = build_result["error_message"] or "Unknown error"
        error_type = build_result["error_type"]

        logger.warning(
            "Span tree build failed (%s): %s",
            error_type,
            error_message,
            extra={"correlation_id": correlation_id},
        )

        if error_type == "validation":
            return _create_validation_error_output(
                error_message, processing_time, input_data.trace_format
            )
        else:
            return _create_compute_error_output(
                error_message, processing_time, input_data.trace_format
            )

    span = build_result["span"]
    if span is None:
        # Defensive check - should not happen if success=True
        processing_time = _elapsed_time_ms(start_time)
        return _create_compute_error_output(
            "Span is None despite successful build",
            processing_time,
            input_data.trace_format,
        )

    logger.debug(
        "Correlating logs with span",
        extra={"correlation_id": correlation_id},
    )

    # Correlate external logs with span (empty list for now - single trace model)
    correlated_logs = correlate_logs_with_span(span, [], correlation_id=correlation_id)

    # Extract events based on options
    parsed_events = []
    if input_data.extract_timing:
        logger.debug(
            "Extracting span events",
            extra={"correlation_id": correlation_id},
        )
        parsed_events.extend(extract_span_events(span, correlation_id=correlation_id))

    # Extract errors based on options
    error_events = []
    if input_data.extract_errors:
        logger.debug(
            "Extracting error events",
            extra={"correlation_id": correlation_id},
        )
        error_events.extend(
            extract_all_errors(span, correlated_logs, correlation_id=correlation_id)
        )

    logger.debug(
        "Computing timing metrics",
        extra={"correlation_id": correlation_id},
    )

    # Compute timing metrics
    timing_data = compute_timing_metrics(span, correlation_id=correlation_id)

    # Calculate processing time
    processing_time = _elapsed_time_ms(start_time)

    # Build metadata
    metadata = TraceMetadataDict(
        parser_version=PARSER_VERSION,
        parse_time_ms=processing_time,
        source_format=input_data.trace_format,
        event_count=len(parsed_events),
        error_count=len(error_events),
        warnings=[],
    )

    logger.debug(
        "Trace parsing complete: events=%d, errors=%d, time_ms=%.2f",
        len(parsed_events),
        len(error_events),
        processing_time,
        extra={"correlation_id": correlation_id},
    )

    # Convert to Pydantic output models
    return _build_output(
        success=True,
        parsed_events=parsed_events,
        error_events=error_events,
        timing_data=timing_data,
        metadata=metadata,
    )


def _build_output(
    success: bool,
    parsed_events: list[ParsedEventDict],
    error_events: list[ErrorEventDict],
    timing_data: TimingDataDict,
    metadata: TraceMetadataDict,
) -> ModelTraceParsingOutput:
    """Build the Pydantic output model from TypedDict results.

    Args:
        success: Whether parsing succeeded.
        parsed_events: List of parsed event dicts.
        error_events: List of error event dicts.
        timing_data: Timing data dict.
        metadata: Metadata dict.

    Returns:
        ModelTraceParsingOutput constructed from the dicts.
    """
    return ModelTraceParsingOutput(
        success=success,
        parsed_events=[
            ModelParsedEvent(
                event_id=e.get("event_id"),
                event_type=e.get("event_type"),
                timestamp=e.get("timestamp"),
                span_id=e.get("span_id"),
                trace_id=e.get("trace_id"),
                operation_name=e.get("operation_name"),
                service_name=e.get("service_name"),
                attributes=e.get("attributes", {}),
            )
            for e in parsed_events
        ],
        error_events=[
            ModelErrorEvent(
                error_id=e.get("error_id"),
                error_type=e.get("error_type"),
                error_message=e.get("error_message"),
                timestamp=e.get("timestamp"),
                span_id=e.get("span_id"),
                stack_trace=e.get("stack_trace"),
                attributes=e.get("attributes", {}),
            )
            for e in error_events
        ],
        timing_data=ModelTimingData(
            total_duration_ms=timing_data.get("total_duration_ms"),
            start_time=timing_data.get("start_time"),
            end_time=timing_data.get("end_time"),
            span_count=timing_data.get("span_count"),
            critical_path_ms=timing_data.get("critical_path_ms"),
            latency_breakdown=timing_data.get("latency_breakdown", {}),
        ),
        metadata=ModelTraceMetadata(
            parser_version=metadata.get("parser_version"),
            parse_time_ms=metadata.get("parse_time_ms"),
            source_format=metadata.get("source_format"),
            event_count=metadata.get("event_count"),
            error_count=metadata.get("error_count"),
            warnings=metadata.get("warnings", []),
        ),
    )


def _elapsed_time_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds.

    Args:
        start_time: Start time from time.perf_counter().

    Returns:
        Elapsed time in milliseconds.
    """
    return (time.perf_counter() - start_time) * 1000


def _safe_elapsed_time_ms(start_time: float) -> float:
    """Safely calculate elapsed time, returning 0 on error.

    Args:
        start_time: Start time from time.perf_counter().

    Returns:
        Elapsed time in milliseconds, or 0.0 on error.
    """
    try:
        return _elapsed_time_ms(start_time)
    except Exception:
        return 0.0


def _create_validation_error_output(
    error_message: str,
    processing_time: float,
    source_format: str,
) -> ModelTraceParsingOutput:
    """Create output for validation errors.

    Args:
        error_message: Description of the validation error.
        processing_time: Time spent before error.
        source_format: Source format from input.

    Returns:
        ModelTraceParsingOutput indicating validation failure.
    """
    metadata = create_error_metadata(
        parse_time_ms=processing_time,
        source_format=source_format,
        warnings=[f"Validation error: {error_message}"],
    )
    timing_data = create_empty_timing_data()

    return _build_output(
        success=False,
        parsed_events=[],
        error_events=[],
        timing_data=timing_data,
        metadata=metadata,
    )


def _create_compute_error_output(
    error_message: str,
    processing_time: float,
    source_format: str,
) -> ModelTraceParsingOutput:
    """Create output for compute errors.

    Args:
        error_message: Description of the compute error.
        processing_time: Time spent before error.
        source_format: Source format from input.

    Returns:
        ModelTraceParsingOutput indicating compute failure.
    """
    metadata = create_error_metadata(
        parse_time_ms=processing_time,
        source_format=source_format,
        warnings=[f"Compute error: {error_message}"],
    )
    timing_data = create_empty_timing_data()

    return _build_output(
        success=False,
        parsed_events=[],
        error_events=[],
        timing_data=timing_data,
        metadata=metadata,
    )


def _create_safe_error_output(
    error_message: str,
    processing_time: float,
    source_format: str,
) -> ModelTraceParsingOutput:
    """Create output for unexpected errors.

    This is the catch-all error handler that ensures we never raise.

    Args:
        error_message: Description of the error.
        processing_time: Time spent before error.
        source_format: Source format from input.

    Returns:
        ModelTraceParsingOutput indicating unexpected failure.
    """
    try:
        metadata = create_error_metadata(
            parse_time_ms=processing_time,
            source_format=source_format,
            warnings=[f"Unexpected error: {error_message}"],
        )
        timing_data = create_empty_timing_data()

        return _build_output(
            success=False,
            parsed_events=[],
            error_events=[],
            timing_data=timing_data,
            metadata=metadata,
        )
    except Exception:
        # Absolute fallback - construct minimal valid output
        return ModelTraceParsingOutput(
            success=False,
            parsed_events=[],
            error_events=[],
            timing_data=ModelTimingData(),
            metadata=ModelTraceMetadata(
                parser_version=PARSER_VERSION,
                parse_time_ms=processing_time,
                source_format=source_format,
                event_count=0,
                error_count=0,
                warnings=["Critical error during output construction"],
            ),
        )


__all__ = [
    "handle_trace_parsing_compute",
]
