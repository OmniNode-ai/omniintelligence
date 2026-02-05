"""Handler for pattern matching compute node orchestration.

This module provides the compute handler that orchestrates pattern matching
operations at the node level. It bridges the gap between the node's typed
input/output models and the pure matching function.

The handler:
    - Accepts ModelPatternMatchingInput (Pydantic model)
    - Returns ModelPatternMatchingOutput (Pydantic model)
    - Handles error cases gracefully (returns error output, doesn't raise)
    - Manages timing and metadata

This separation allows the node.py to be a thin shell that simply delegates
to this handler, following the ONEX declarative pattern.

Example:
    from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
        handle_pattern_matching_compute,
    )
    from omniintelligence.nodes.node_pattern_matching_compute.models import (
        ModelPatternMatchingInput,
        ModelPatternMatchingOutput,
    )

    input_data = ModelPatternMatchingInput(
        code_snippet="class Foo: pass",
        patterns=[...],
    )
    output: ModelPatternMatchingOutput = handle_pattern_matching_compute(input_data)
"""

from __future__ import annotations

import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import Final

from omniintelligence.nodes.node_pattern_matching_compute.handlers.exceptions import (
    PatternMatchingComputeError,
    PatternMatchingValidationError,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_pattern_matching import (
    match_patterns,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.protocols import (
    PatternRecord,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_input import (
    ModelPatternMatchingInput,
    ModelPatternRecord,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_output import (
    ModelPatternMatch,
    ModelPatternMatchingMetadata,
    ModelPatternMatchingOutput,
)

# Module logger for exception tracking
logger = logging.getLogger(__name__)

# Status constants for metadata
STATUS_COMPLETED: Final[str] = "completed"
STATUS_NO_PATTERNS: Final[str] = "no_patterns"
STATUS_VALIDATION_ERROR: Final[str] = "validation_error"
STATUS_COMPUTE_ERROR: Final[str] = "compute_error"


def handle_pattern_matching_compute(
    input_data: ModelPatternMatchingInput,
) -> ModelPatternMatchingOutput:
    """Handle pattern matching compute operation.

    This function orchestrates the pattern matching workflow:
    1. Converts input models to handler-compatible format
    2. Calls the pure matching function
    3. Converts results to output models
    4. Handles errors gracefully

    Error Handling:
        - PatternMatchingValidationError: Returns output with validation_error status
        - PatternMatchingComputeError: Returns output with compute_error status
        - All errors are caught and returned as structured output (no exceptions raised)

    Args:
        input_data: Typed input model containing code snippet and patterns.

    Returns:
        ModelPatternMatchingOutput with matches, scores, and metadata.
        Always returns a valid output, even on errors.
    """
    start_time = time.perf_counter()

    try:
        return _execute_matching(input_data, start_time)

    except PatternMatchingValidationError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_validation_error_output(str(e), processing_time)

    except PatternMatchingComputeError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_compute_error_output(str(e), processing_time)

    except Exception as e:
        # Catch-all for any unhandled exceptions.
        # This block MUST NOT raise - use nested try/except for all operations.
        processing_time = _safe_elapsed_time_ms(start_time)

        # Extract correlation_id safely for logging
        correlation_id: str | None = None
        with contextlib.suppress(Exception):
            if hasattr(input_data, "context") and hasattr(
                input_data.context, "correlation_id"
            ):
                correlation_id = (
                    str(input_data.context.correlation_id)
                    if input_data.context.correlation_id
                    else None
                )

        # Safe logging - failures here must not propagate
        try:
            logger.exception(
                "Unhandled exception in pattern matching compute. "
                "operation=%s, patterns_count=%d, processing_time_ms=%.2f",
                getattr(input_data, "operation", "<unknown>"),
                len(getattr(input_data, "patterns", [])),
                processing_time,
                extra={"correlation_id": correlation_id},
            )
        except Exception:
            # If logging itself fails, try minimal logging
            with contextlib.suppress(Exception):
                logger.error(
                    "Pattern matching compute failed: %s",
                    e,
                    extra={"correlation_id": correlation_id},
                )

        # Safe error response creation
        return _create_safe_error_output(
            f"Unhandled error: {e}",
            processing_time,
        )


def _execute_matching(
    input_data: ModelPatternMatchingInput,
    start_time: float,
) -> ModelPatternMatchingOutput:
    """Execute the pattern matching logic.

    Args:
        input_data: Typed input model with code snippet and patterns.
        start_time: Performance counter start time for timing.

    Returns:
        ModelPatternMatchingOutput with matching results.

    Raises:
        PatternMatchingValidationError: If input validation fails.
    """
    # Convert Pydantic models to handler-compatible dicts
    patterns = _convert_patterns_to_records(input_data.patterns)

    # Extract matching parameters from context
    context = input_data.context
    min_confidence = context.min_confidence
    max_results = context.max_results
    pattern_categories = (
        context.pattern_categories if context.pattern_categories else None
    )
    language = context.language

    # Call the pure matching function
    result = match_patterns(
        code_snippet=input_data.code_snippet,
        patterns=patterns,
        min_confidence=min_confidence,
        max_results=max_results,
        operation=input_data.operation,
        language=language,
        pattern_categories=pattern_categories,
        correlation_id=str(context.correlation_id) if context.correlation_id else None,
    )

    processing_time = (time.perf_counter() - start_time) * 1000

    # Convert handler result to output model
    matches = [
        ModelPatternMatch(
            pattern_id=m["pattern_id"],
            pattern_name=m["pattern_name"],
            confidence=m["confidence"],
            category=m["category"],
            match_reason=m["match_reason"],
            algorithm_used=m["algorithm_used"],
        )
        for m in result["matches"]
    ]

    # Build patterns_matched list and pattern_scores dict for backwards compatibility
    patterns_matched = [m.pattern_name for m in matches]
    pattern_scores = {m.pattern_name: m.confidence for m in matches}

    # Determine status based on result
    if not result["success"]:
        # Check error code to differentiate validation vs compute errors
        error_code = result.get("error_code", "")
        if error_code == "PATMATCH_001":
            status = STATUS_VALIDATION_ERROR
        else:
            status = STATUS_COMPUTE_ERROR
    elif not matches:
        status = STATUS_NO_PATTERNS if not patterns else STATUS_COMPLETED
    else:
        status = STATUS_COMPLETED

    # Extract error message from result if present
    error_message = result.get("error") if not result["success"] else None

    return ModelPatternMatchingOutput(
        success=result["success"],
        patterns_matched=patterns_matched,
        pattern_scores=pattern_scores,
        matches=matches,
        metadata=ModelPatternMatchingMetadata(
            status=status,
            message=error_message or (None if result["success"] else "Matching failed"),
            operation=None,  # Output operation type differs from input
            processing_time_ms=processing_time,
            algorithm_version=result["algorithm_version"],
            input_length=len(input_data.code_snippet),
            input_line_count=input_data.code_snippet.count("\n") + 1,
            source_language=language,
            patterns_analyzed=result["patterns_analyzed"],
            patterns_filtered=result["patterns_filtered"],
            threshold_used=result["threshold_used"],
            correlation_id=(
                str(context.correlation_id) if context.correlation_id else None
            ),
            timestamp_utc=datetime.now(UTC).isoformat(),
        ),
    )


def _convert_patterns_to_records(
    patterns: list[ModelPatternRecord],
) -> list[PatternRecord]:
    """Convert Pydantic pattern models to handler-compatible dicts.

    Args:
        patterns: List of Pydantic pattern models.

    Returns:
        List of PatternRecord dicts.
    """
    return [
        PatternRecord(
            pattern_id=p.pattern_id,
            signature=p.signature,
            domain=p.domain,
            keywords=p.keywords or [],
            status=p.status or "",
            confidence=p.confidence or 0.0,
            category=p.category or "",
        )
        for p in patterns
    ]


def _create_validation_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelPatternMatchingOutput:
    """Create output for validation errors.

    Args:
        error_message: The validation error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelPatternMatchingOutput indicating validation failure.
    """
    return ModelPatternMatchingOutput(
        success=False,
        patterns_matched=[],
        pattern_scores={},
        matches=[],
        metadata=ModelPatternMatchingMetadata(
            status=STATUS_VALIDATION_ERROR,
            message=error_message,
            processing_time_ms=processing_time_ms,
        ),
    )


def _create_compute_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelPatternMatchingOutput:
    """Create output for compute errors.

    Args:
        error_message: The compute error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelPatternMatchingOutput indicating compute failure.
    """
    return ModelPatternMatchingOutput(
        success=False,
        patterns_matched=[],
        pattern_scores={},
        matches=[],
        metadata=ModelPatternMatchingMetadata(
            status=STATUS_COMPUTE_ERROR,
            message=error_message,
            processing_time_ms=processing_time_ms,
        ),
    )


def _safe_elapsed_time_ms(start_time: float) -> float:
    """Safely calculate elapsed time in milliseconds.

    Never raises - returns 0.0 if calculation fails.

    Args:
        start_time: Performance counter start time.

    Returns:
        Elapsed time in milliseconds, or 0.0 on any error.
    """
    try:
        return (time.perf_counter() - start_time) * 1000
    except Exception as e:
        # Log the exception but don't propagate - this function must never fail
        with contextlib.suppress(Exception):
            logger.warning(
                "Failed to calculate elapsed time: %s",
                e,
            )
        return 0.0


def _create_safe_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelPatternMatchingOutput:
    """Create error output that is guaranteed not to raise exceptions.

    This is the last-resort error creator used in the catch-all exception handler.

    Args:
        error_message: The error message to include.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelPatternMatchingOutput indicating failure. Always succeeds.
    """
    try:
        return _create_compute_error_output(error_message, processing_time_ms)
    except Exception as e:
        # If normal error output creation fails, log and create minimal output
        with contextlib.suppress(Exception):
            logger.error(
                "Failed to create compute error output, falling back to minimal: %s",
                e,
            )
        try:
            return ModelPatternMatchingOutput(
                success=False,
                patterns_matched=[],
                pattern_scores={},
                matches=[],
                metadata=ModelPatternMatchingMetadata(
                    status="error",
                    message="Error output creation failed",
                    processing_time_ms=0.0,
                ),
            )
        except Exception as e2:
            # Absolute last resort - should never happen
            with contextlib.suppress(Exception):
                logger.error(
                    "All error output creation failed, using bare minimum: %s",
                    e2,
                )
            return ModelPatternMatchingOutput(
                success=False,
                patterns_matched=[],
                pattern_scores={},
                matches=[],
                metadata=None,
            )


__all__ = ["handle_pattern_matching_compute"]
