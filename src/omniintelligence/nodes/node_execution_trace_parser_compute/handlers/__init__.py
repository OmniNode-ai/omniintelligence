"""Handlers for Execution Trace Parser Compute Node.

This module re-exports all public functions and types from the handler
submodules, providing a clean API for the node.

Architecture:
    - handler_compute: Orchestration layer (Pydantic ↔ TypedDict)
    - handler_trace_parsing: Pure trace parsing logic
    - handler_event_extraction: Error and event detection
    - protocols: TypedDict contracts
    - exceptions: Domain-specific errors
"""

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.exceptions import (
    TraceParsingComputeError,
    TraceParsingValidationError,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_compute import (
    handle_trace_parsing_compute,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_event_extraction import (
    detect_log_errors,
    detect_span_errors,
    detect_timeout_errors,
    extract_all_errors,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_trace_parsing import (
    PARSER_VERSION,
    build_span_tree,
    compute_timing_metrics,
    correlate_logs_with_span,
    extract_span_events,
    generate_event_id,
    is_error_log_level,
    is_error_status,
    parse_timestamp,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    ErrorEventDict,
    ParsedEventDict,
    SpanNodeDict,
    TimingDataDict,
    TraceMetadataDict,
    TraceParsingResult,
    create_empty_timing_data,
    create_error_metadata,
)

__all__ = [
    "PARSER_VERSION",
    "ErrorEventDict",
    "ParsedEventDict",
    "SpanNodeDict",
    "TimingDataDict",
    "TraceMetadataDict",
    "TraceParsingComputeError",
    "TraceParsingResult",
    "TraceParsingValidationError",
    "build_span_tree",
    "compute_timing_metrics",
    "correlate_logs_with_span",
    "create_empty_timing_data",
    "create_error_metadata",
    "detect_log_errors",
    "detect_span_errors",
    "detect_timeout_errors",
    "extract_all_errors",
    "extract_span_events",
    "generate_event_id",
    "handle_trace_parsing_compute",
    "is_error_log_level",
    "is_error_status",
    "parse_timestamp",
]
