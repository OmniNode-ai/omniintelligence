#!/usr/bin/env python3
"""
Execution Trace Parser Compute Node - ONEX Compliant

Parses execution traces from PostgreSQL intelligence tracking system.
Part of Track 2 Intelligence Hook System (Track 3-1.4).

Generated with DeepSeek-Lite via vLLM
Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Models
# ============================================================================


class ModelTraceParsingInput(BaseModel):
    """Input state for trace parsing."""

    trace_data: str = Field(
        ..., description="Execution trace data (JSON or structured text)"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    trace_format: str = Field(
        default="json", description="Trace format: json, log, structured"
    )
    extract_errors: bool = Field(default=True, description="Extract error information")
    extract_timing: bool = Field(default=True, description="Extract timing information")


@dataclass
class ParsedTraceEvent:
    """Parsed execution trace event."""

    event_type: str
    timestamp: Optional[str]
    correlation_id: Optional[str]
    function_name: Optional[str]
    status: Optional[str]
    error_message: Optional[str]
    duration_ms: Optional[float]
    metadata: Dict[str, Any]


class ModelTraceParsingOutput(BaseModel):
    """Output state for trace parsing."""

    events: List[Dict[str, Any]] = Field(
        default_factory=list, description="Parsed trace events"
    )
    error_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="Error events extracted"
    )
    timing_summary: Dict[str, float] = Field(
        default_factory=dict, description="Timing statistics"
    )
    execution_flow: List[str] = Field(
        default_factory=list, description="Execution flow sequence"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Parsing metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeExecutionTraceParserCompute:
    """
    ONEX-Compliant Compute Node for Execution Trace Parsing.

    Implements structured parsing of execution traces from PostgreSQL
    intelligence tracking with error extraction and timing analysis.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<100ms target for large traces)
    """

    # Trace event patterns
    EVENT_PATTERNS = {
        "function_call": r"(?:function|method|call):\s*(\w+)",
        "error": r"(?:error|exception|fail)(?:ed)?:?\s*(.+?)(?:\n|$)",
        "timing": r"(?:duration|time|took):\s*([\d.]+)\s*(?:ms|milliseconds)?",
        "status": r"(?:status|result):\s*(\w+)",
        "correlation_id": r"(?:correlation|trace)_id:\s*([a-f0-9-]+)",
    }

    # Error severity patterns
    ERROR_SEVERITIES = {
        "critical": ["critical", "fatal", "severe"],
        "error": ["error", "exception", "fail"],
        "warning": ["warning", "warn"],
        "info": ["info", "notice"],
    }

    # Performance constants
    MAX_TRACE_SIZE = 1000000  # 1MB
    DEFAULT_TIMEOUT_MS = 100

    def __init__(self) -> None:
        """Initialize trace parser with pattern matchers."""
        # Compile regex patterns for performance
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.EVENT_PATTERNS.items()
        }

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelTraceParsingInput
    ) -> ModelTraceParsingOutput:
        """
        Execute trace parsing computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with trace data and parameters

        Returns:
            ModelTraceParsingOutput: Parsed trace events with metadata
        """
        import time

        start_time = time.time()

        try:
            # Validate input
            if not input_state.trace_data.strip():
                return ModelTraceParsingOutput(
                    events=[],
                    error_events=[],
                    timing_summary={},
                    execution_flow=[],
                    metadata={"error": "Empty trace data"},
                    correlation_id=input_state.correlation_id,
                )

            # Parse trace based on format
            if input_state.trace_format == "json":
                events = self._parse_json_trace(input_state.trace_data)
            elif input_state.trace_format == "log":
                events = self._parse_log_trace(input_state.trace_data)
            else:
                events = self._parse_structured_trace(input_state.trace_data)

            # Extract error events if requested
            error_events: List[Dict[str, Any]] = []
            if input_state.extract_errors:
                error_events = self._extract_errors(events)

            # Extract timing information if requested
            timing_summary: Dict[str, float] = {}
            if input_state.extract_timing:
                timing_summary = self._extract_timing(events)

            # Build execution flow
            execution_flow = self._build_execution_flow(events)

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            return ModelTraceParsingOutput(
                events=[self._event_to_dict(e) for e in events],
                error_events=error_events,
                timing_summary=timing_summary,
                execution_flow=execution_flow,
                metadata={
                    "processing_time_ms": processing_time,
                    "trace_size": len(input_state.trace_data),
                    "trace_format": input_state.trace_format,
                    "total_events": len(events),
                    "total_errors": len(error_events),
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return ModelTraceParsingOutput(
                events=[],
                error_events=[],
                timing_summary={},
                execution_flow=[],
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Parsing Algorithms
    # ========================================================================

    def _parse_json_trace(self, trace_data: str) -> List[ParsedTraceEvent]:
        """
        Parse JSON-formatted trace data.

        Expected format:
        {
            "events": [
                {"type": "...", "timestamp": "...", ...},
                ...
            ]
        }

        Or array of events directly: [{"type": "..."}, ...]

        Args:
            trace_data: JSON trace string

        Returns:
            List of parsed trace events
        """
        try:
            data = json.loads(trace_data)

            # Handle array format
            if isinstance(data, list):
                events_data = data
            # Handle object with 'events' key
            elif isinstance(data, dict) and "events" in data:
                events_data = data["events"]
            # Single event object
            elif isinstance(data, dict):
                events_data = [data]
            else:
                return []

            events: List[ParsedTraceEvent] = []
            for event_data in events_data:
                if not isinstance(event_data, dict):
                    continue

                event = ParsedTraceEvent(
                    event_type=event_data.get("type", "unknown"),
                    timestamp=event_data.get("timestamp"),
                    correlation_id=event_data.get("correlation_id"),
                    function_name=event_data.get("function", event_data.get("name")),
                    status=event_data.get("status"),
                    error_message=event_data.get("error"),
                    duration_ms=event_data.get("duration_ms"),
                    metadata=event_data.get("metadata", {}),
                )
                events.append(event)

            return events

        except json.JSONDecodeError:
            return []

    def _parse_log_trace(self, trace_data: str) -> List[ParsedTraceEvent]:
        """
        Parse log-formatted trace data.

        Parses text logs line by line using pattern matching.

        Args:
            trace_data: Log trace string

        Returns:
            List of parsed trace events
        """
        events: List[ParsedTraceEvent] = []
        lines = trace_data.split("\n")

        for line in lines:
            if not line.strip():
                continue

            # Extract information using patterns
            function_name = self._extract_pattern(line, "function_call")
            error_message = self._extract_pattern(line, "error")
            duration_str = self._extract_pattern(line, "timing")
            status = self._extract_pattern(line, "status")
            correlation_id = self._extract_pattern(line, "correlation_id")

            # Determine event type
            event_type = "unknown"
            if error_message:
                event_type = "error"
            elif function_name:
                event_type = "function_call"
            elif status:
                event_type = "status"

            # Parse duration
            duration_ms: Optional[float] = None
            if duration_str:
                try:
                    duration_ms = float(duration_str)
                except ValueError:
                    pass

            event = ParsedTraceEvent(
                event_type=event_type,
                timestamp=None,  # Could extract from log timestamp prefix
                correlation_id=correlation_id,
                function_name=function_name,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
                metadata={"raw_line": line},
            )
            events.append(event)

        return events

    def _parse_structured_trace(self, trace_data: str) -> List[ParsedTraceEvent]:
        """
        Parse structured text trace data.

        Fallback parser for semi-structured text formats.

        Args:
            trace_data: Structured trace string

        Returns:
            List of parsed trace events
        """
        # Try JSON first
        events = self._parse_json_trace(trace_data)
        if events:
            return events

        # Fall back to log parsing
        return self._parse_log_trace(trace_data)

    # ========================================================================
    # Extraction Methods
    # ========================================================================

    def _extract_errors(self, events: List[ParsedTraceEvent]) -> List[Dict[str, Any]]:
        """
        Extract error events from parsed events.

        Args:
            events: List of parsed events

        Returns:
            List of error event dictionaries
        """
        error_events: List[Dict[str, Any]] = []

        for event in events:
            if event.event_type == "error" or event.error_message:
                severity = self._classify_error_severity(event.error_message or "")

                error_events.append(
                    {
                        "type": event.event_type,
                        "function": event.function_name,
                        "error": event.error_message,
                        "severity": severity,
                        "timestamp": event.timestamp,
                        "correlation_id": event.correlation_id,
                    }
                )

        return error_events

    def _extract_timing(self, events: List[ParsedTraceEvent]) -> Dict[str, float]:
        """
        Extract timing statistics from events.

        Args:
            events: List of parsed events

        Returns:
            Dictionary with timing statistics
        """
        durations: List[float] = []
        function_timings: Dict[str, List[float]] = {}

        for event in events:
            if event.duration_ms is not None:
                durations.append(event.duration_ms)

                if event.function_name:
                    if event.function_name not in function_timings:
                        function_timings[event.function_name] = []
                    function_timings[event.function_name].append(event.duration_ms)

        if not durations:
            return {}

        # Calculate statistics
        timing_summary: Dict[str, float] = {
            "total_duration_ms": sum(durations),
            "average_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
        }

        # Add per-function averages
        for func_name, func_durations in function_timings.items():
            avg_key = f"avg_{func_name}_ms"
            timing_summary[avg_key] = sum(func_durations) / len(func_durations)

        return timing_summary

    def _build_execution_flow(self, events: List[ParsedTraceEvent]) -> List[str]:
        """
        Build execution flow sequence from events.

        Args:
            events: List of parsed events

        Returns:
            List of function names in execution order
        """
        flow: List[str] = []

        for event in events:
            if event.function_name:
                flow.append(event.function_name)
            elif event.event_type and event.event_type != "unknown":
                flow.append(f"<{event.event_type}>")

        return flow

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _extract_pattern(self, text: str, pattern_name: str) -> Optional[str]:
        """Extract value using compiled regex pattern."""
        pattern = self._compiled_patterns.get(pattern_name)
        if not pattern:
            return None

        match = pattern.search(text)
        if match:
            return match.group(1)

        return None

    def _classify_error_severity(self, error_message: str) -> str:
        """Classify error severity based on message content."""
        error_lower = error_message.lower()

        for severity, keywords in self.ERROR_SEVERITIES.items():
            if any(keyword in error_lower for keyword in keywords):
                return severity

        return "error"  # Default

    def _event_to_dict(self, event: ParsedTraceEvent) -> Dict[str, Any]:
        """Convert ParsedTraceEvent to dictionary."""
        return {
            "type": event.event_type,
            "timestamp": event.timestamp,
            "correlation_id": event.correlation_id,
            "function": event.function_name,
            "status": event.status,
            "error": event.error_message,
            "duration_ms": event.duration_ms,
            "metadata": event.metadata,
        }

    def calculate_deterministic_hash(self, trace_data: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{trace_data}|trace_parser|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"


# ============================================================================
# Unit Test Helpers
# ============================================================================


async def test_trace_parser() -> None:
    """Test trace parser with various formats."""
    parser = NodeExecutionTraceParserCompute()

    # Test 1: JSON trace format
    json_trace = json.dumps(
        {
            "events": [
                {
                    "type": "function_call",
                    "function": "handle_request",
                    "timestamp": "2025-10-02T10:00:00Z",
                    "correlation_id": "test-123",
                    "duration_ms": 45.2,
                },
                {
                    "type": "error",
                    "function": "database_query",
                    "error": "Connection timeout",
                    "duration_ms": 120.5,
                },
                {
                    "type": "function_call",
                    "function": "send_response",
                    "duration_ms": 5.3,
                },
            ]
        }
    )

    test_input = ModelTraceParsingInput(trace_data=json_trace, trace_format="json")
    result = await parser.execute_compute(test_input)

    print("Test 1 - JSON Trace:")
    print(f"  Events: {len(result.events)}")
    print(f"  Errors: {len(result.error_events)}")
    print(f"  Timing: {result.timing_summary}")
    print(f"  Flow: {result.execution_flow}")
    print(f"  Processing time: {result.metadata.get('processing_time_ms')}ms")

    assert len(result.events) == 3
    assert len(result.error_events) == 1
    assert "total_duration_ms" in result.timing_summary

    # Test 2: Log trace format
    log_trace = """
    [INFO] Function: process_request started
    [ERROR] Error: Database connection failed - timeout after 30s
    [INFO] Status: completed with warnings
    [DEBUG] Duration: 125.5 ms
    """

    test_input = ModelTraceParsingInput(trace_data=log_trace, trace_format="log")
    result = await parser.execute_compute(test_input)

    print("\nTest 2 - Log Trace:")
    print(f"  Events: {len(result.events)}")
    print(f"  Errors: {result.error_events}")
    print(f"  Processing time: {result.metadata.get('processing_time_ms')}ms")

    # Test 3: Empty trace
    test_input = ModelTraceParsingInput(trace_data="", trace_format="json")
    result = await parser.execute_compute(test_input)
    print(f"\nTest 3 - Empty trace: {result.events}")
    assert len(result.events) == 0

    print("\nAll tests passed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_trace_parser())
