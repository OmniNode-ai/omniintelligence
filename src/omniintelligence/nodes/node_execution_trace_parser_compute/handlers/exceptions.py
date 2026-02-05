"""Domain-specific exceptions for Execution Trace Parser Compute."""

from __future__ import annotations


class TraceParsingValidationError(Exception):
    """Raised when input validation fails.

    Examples:
        - Empty trace data
        - Invalid trace format
        - Missing required fields (trace_id, span_id)
    """

    pass


class TraceParsingComputeError(Exception):
    """Raised when trace parsing computation fails.

    Examples:
        - Cyclic span relationships
        - Invalid timestamp formats
        - Inconsistent parent-child references
    """

    pass


__all__ = [
    "TraceParsingComputeError",
    "TraceParsingValidationError",
]
