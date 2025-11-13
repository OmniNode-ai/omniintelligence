#!/usr/bin/env python3
"""
Execution Analyzer Compute Node - ONEX Compliant

Analyzes execution paths with signature hashing for pattern extraction.
Part of Pattern Learning Engine Phase 1 Foundation.

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.9
"""

import hashlib
import json
import uuid
from collections import Counter
from typing import Any, Dict, List

from pydantic import BaseModel, Field

# ============================================================================
# Models
# ============================================================================


class ModelExecutionAnalysisInput(BaseModel):
    """Input state for execution analysis."""

    execution_trace: Dict[str, Any] = Field(
        ..., description="Execution trace data with tool calls and results"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    include_timing: bool = Field(default=True, description="Include timing analysis")
    include_patterns: bool = Field(
        default=True, description="Include pattern detection"
    )


class ModelExecutionAnalysisOutput(BaseModel):
    """Output state for execution analysis."""

    execution_signature: str = Field(
        ..., description="SHA256 signature of execution path"
    )
    tool_usage_patterns: Dict[str, int] = Field(
        default_factory=dict, description="Tool usage frequency patterns"
    )
    execution_sequence: List[str] = Field(
        default_factory=list, description="Sequence of tool calls"
    )
    success_indicators: Dict[str, bool] = Field(
        default_factory=dict, description="Success/failure indicators"
    )
    timing_analysis: Dict[str, float] = Field(
        default_factory=dict, description="Timing statistics (if enabled)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Analysis metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeExecutionAnalyzerCompute:
    """
    ONEX-Compliant Compute Node for Execution Analysis.

    Implements execution path analysis with signature hashing and
    pattern detection for identifying execution patterns.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<80ms target)
    """

    # Tool categories for pattern analysis
    TOOL_CATEGORIES: Dict[str, List[str]] = {
        "file_operations": ["Read", "Write", "Edit", "Glob"],
        "code_execution": ["Bash", "BashOutput"],
        "search": ["Grep", "WebSearch"],
        "analysis": ["mcp__zen__thinkdeep", "mcp__zen__debug"],
        "coordination": ["TodoWrite", "mcp__zen__planner"],
    }

    # Success indicators (keywords in results/metadata)
    SUCCESS_KEYWORDS = {"success", "completed", "passed", "ok", "done", "finished"}

    FAILURE_KEYWORDS = {"error", "failed", "exception", "crash", "abort", "timeout"}

    # Performance constants
    MAX_TRACE_SIZE = 1000000  # 1MB limit
    DEFAULT_TIMEOUT_MS = 80

    def __init__(self) -> None:
        """Initialize execution analyzer."""
        pass

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelExecutionAnalysisInput
    ) -> ModelExecutionAnalysisOutput:
        """
        Execute execution analysis computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with execution trace data

        Returns:
            ModelExecutionAnalysisOutput: Analysis with signature and patterns
        """
        import time

        start_time = time.time()

        try:
            # Validate input
            if not input_state.execution_trace:
                return ModelExecutionAnalysisOutput(
                    execution_signature="sha256:empty",
                    tool_usage_patterns={},
                    execution_sequence=[],
                    success_indicators={"has_execution": False},
                    timing_analysis={},
                    metadata={"error": "Empty execution trace"},
                    correlation_id=input_state.correlation_id,
                )

            # Analyze execution path
            signature = self._generate_execution_signature(input_state.execution_trace)

            # Extract tool usage patterns
            tool_patterns = self._analyze_tool_usage(input_state.execution_trace)

            # Extract execution sequence
            sequence = self._extract_execution_sequence(input_state.execution_trace)

            # Detect success indicators
            success_indicators = self._detect_success_indicators(
                input_state.execution_trace
            )

            # Timing analysis if enabled
            timing_analysis: Dict[str, float] = {}
            if input_state.include_timing:
                timing_analysis = self._analyze_timing(input_state.execution_trace)

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            return ModelExecutionAnalysisOutput(
                execution_signature=signature,
                tool_usage_patterns=tool_patterns,
                execution_sequence=sequence,
                success_indicators=success_indicators,
                timing_analysis=timing_analysis,
                metadata={
                    "processing_time_ms": processing_time,
                    "trace_events": len(sequence),
                    "unique_tools": len(tool_patterns),
                    "algorithm": "sha256_signature_with_pattern_analysis",
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return ModelExecutionAnalysisOutput(
                execution_signature="sha256:error",
                tool_usage_patterns={},
                execution_sequence=[],
                success_indicators={"analysis_error": True},
                timing_analysis={},
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Analysis Algorithms
    # ========================================================================

    def _generate_execution_signature(self, trace: Dict[str, Any]) -> str:
        """
        Generate deterministic SHA256 signature of execution path.

        Algorithm:
        1. Extract execution sequence
        2. Create canonical representation
        3. Hash with SHA256
        4. Return signature with prefix

        Args:
            trace: Execution trace dictionary

        Returns:
            SHA256 signature string with "sha256:" prefix
        """
        try:
            # Extract key execution data
            sequence = self._extract_execution_sequence(trace)

            # Create canonical representation
            canonical = "|".join(sequence)

            # Generate SHA256 hash
            hash_bytes = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            return f"sha256:{hash_bytes[:32]}"  # First 32 chars

        except Exception:
            return "sha256:error_in_signature_generation"

    def _analyze_tool_usage(self, trace: Dict[str, Any]) -> Dict[str, int]:
        """
        Analyze tool usage patterns in execution trace.

        Algorithm:
        1. Extract tool calls from trace
        2. Count frequency of each tool
        3. Return usage statistics

        Args:
            trace: Execution trace dictionary

        Returns:
            Dictionary mapping tool names to usage counts
        """
        tool_calls: List[str] = []

        # Extract tool calls from various trace formats
        if "tool_calls" in trace:
            for call in trace.get("tool_calls", []):
                if isinstance(call, dict) and "tool_name" in call:
                    tool_calls.append(call["tool_name"])
                elif isinstance(call, str):
                    tool_calls.append(call)

        elif "events" in trace:
            for event in trace.get("events", []):
                if isinstance(event, dict):
                    tool_name = (
                        event.get("tool") or event.get("function") or event.get("type")
                    )
                    if tool_name:
                        tool_calls.append(str(tool_name))

        # Count tool usage
        usage_counts = Counter(tool_calls)

        return dict(usage_counts)

    def _extract_execution_sequence(self, trace: Dict[str, Any]) -> List[str]:
        """
        Extract ordered execution sequence from trace.

        Args:
            trace: Execution trace dictionary

        Returns:
            List of execution steps in order
        """
        sequence: List[str] = []

        # Try different trace formats
        if "tool_calls" in trace:
            for call in trace.get("tool_calls", []):
                if isinstance(call, dict):
                    tool_name = call.get("tool_name", "unknown")
                    sequence.append(tool_name)
                elif isinstance(call, str):
                    sequence.append(call)

        elif "events" in trace:
            for event in trace.get("events", []):
                if isinstance(event, dict):
                    event_type = (
                        event.get("tool")
                        or event.get("function")
                        or event.get("type", "unknown")
                    )
                    sequence.append(str(event_type))

        elif "steps" in trace:
            for step in trace.get("steps", []):
                if isinstance(step, dict):
                    step_name = step.get("name") or step.get("action", "unknown")
                    sequence.append(str(step_name))

        return sequence

    def _detect_success_indicators(self, trace: Dict[str, Any]) -> Dict[str, bool]:
        """
        Detect success/failure indicators in execution trace.

        Algorithm:
        1. Check for explicit success/failure flags
        2. Scan result text for success keywords
        3. Check for error events/exceptions
        4. Return indicator dictionary

        Args:
            trace: Execution trace dictionary

        Returns:
            Dictionary of boolean indicators
        """
        indicators: Dict[str, bool] = {}

        # Check explicit flags
        if "success" in trace:
            indicators["explicit_success"] = bool(trace["success"])
        if "failed" in trace:
            indicators["explicit_failure"] = bool(trace["failed"])

        # Check for errors in events
        has_errors = False
        if "events" in trace:
            for event in trace.get("events", []):
                if isinstance(event, dict):
                    if event.get("error") or event.get("exception"):
                        has_errors = True
                        break

        indicators["has_errors"] = has_errors

        # Scan result text for keywords
        result_text = str(trace.get("result", "")).lower()

        has_success_keywords = any(
            keyword in result_text for keyword in self.SUCCESS_KEYWORDS
        )
        has_failure_keywords = any(
            keyword in result_text for keyword in self.FAILURE_KEYWORDS
        )

        indicators["has_success_keywords"] = has_success_keywords
        indicators["has_failure_keywords"] = has_failure_keywords

        # Overall assessment
        indicators["likely_successful"] = (
            (has_success_keywords or indicators.get("explicit_success", False))
            and not has_errors
            and not has_failure_keywords
        )

        return indicators

    def _analyze_timing(self, trace: Dict[str, Any]) -> Dict[str, float]:
        """
        Analyze timing statistics from execution trace.

        Args:
            trace: Execution trace dictionary

        Returns:
            Dictionary with timing statistics
        """
        timing: Dict[str, float] = {}

        # Extract timing data
        durations: List[float] = []

        if "events" in trace:
            for event in trace.get("events", []):
                if isinstance(event, dict):
                    duration = event.get("duration_ms") or event.get("duration")
                    if duration is not None:
                        try:
                            durations.append(float(duration))
                        except (ValueError, TypeError):
                            pass

        # Calculate statistics
        if durations:
            timing["total_duration_ms"] = sum(durations)
            timing["avg_duration_ms"] = sum(durations) / len(durations)
            timing["min_duration_ms"] = min(durations)
            timing["max_duration_ms"] = max(durations)
            timing["event_count"] = len(durations)

        # Check for overall duration
        if "duration_ms" in trace:
            try:
                timing["total_trace_duration_ms"] = float(trace["duration_ms"])
            except (ValueError, TypeError):
                pass

        return timing

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def calculate_deterministic_hash(self, data: Dict[str, Any]) -> str:
        """Calculate deterministic hash for reproducibility."""
        # Convert to canonical JSON string
        canonical = json.dumps(data, sort_keys=True)
        hash_bytes = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"
