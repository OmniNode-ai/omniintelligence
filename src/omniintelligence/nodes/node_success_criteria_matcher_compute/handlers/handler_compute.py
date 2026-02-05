"""Handler for success criteria matcher compute node orchestration.

This module provides the compute handler that orchestrates criteria matching
operations at the node level. It bridges the gap between the node's typed
input/output models and the pure matching function.

The handler:
    - Accepts ModelSuccessCriteriaInput (Pydantic model)
    - Returns ModelSuccessCriteriaOutput (Pydantic model)
    - Handles error cases gracefully (returns error output, doesn't raise)
    - Manages timing and metadata

This separation allows the node.py to be a thin shell that simply delegates
to this handler, following the ONEX declarative pattern.

Example:
    from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.handler_compute import (
        handle_success_criteria_compute,
    )
    from omniintelligence.nodes.node_success_criteria_matcher_compute.models import (
        ModelSuccessCriteriaInput,
        ModelSuccessCriteriaOutput,
    )

    input_data = ModelSuccessCriteriaInput(
        execution_outcome={"status": "success", "exit_code": 0},
        criteria_set=[
            {"criterion_id": "exit_ok", "field": "exit_code", "operator": "equals", "expected_value": 0}
        ],
    )
    output: ModelSuccessCriteriaOutput = handle_success_criteria_compute(input_data)
"""

from __future__ import annotations

import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import Final

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.exceptions import (
    CriteriaMatchingComputeError,
    CriteriaMatchingValidationError,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.handler_criteria_matching import (
    match_criteria,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.models.model_success_criteria_input import (
    ModelSuccessCriteriaInput,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.models.model_success_criteria_output import (
    CriteriaMatchMetadataDict,
    ModelSuccessCriteriaOutput,
)


# Module logger for exception tracking
logger = logging.getLogger(__name__)

# Status constants for metadata
STATUS_COMPLETED: Final[str] = "completed"
STATUS_VALIDATION_ERROR: Final[str] = "validation_error"
STATUS_COMPUTE_ERROR: Final[str] = "compute_error"


def handle_success_criteria_compute(
    input_data: ModelSuccessCriteriaInput,
) -> ModelSuccessCriteriaOutput:
    """Handle success criteria matching compute operation.

    This function orchestrates the criteria matching workflow:
    1. Extracts execution outcome and criteria from input
    2. Calls the pure matching function
    3. Constructs the output model with metadata

    Error Handling:
        - CriteriaMatchingValidationError: Returns output with validation_error status
        - CriteriaMatchingComputeError: Returns output with compute_error status
        - All errors are caught and returned as structured output (no exceptions raised)

    Args:
        input_data: Typed input model containing execution outcome and criteria.

    Returns:
        ModelSuccessCriteriaOutput with match results, scores, and metadata.
        Always returns a valid output, even on errors.
    """
    start_time = time.perf_counter()

    try:
        return _execute_matching(input_data, start_time)

    except CriteriaMatchingValidationError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_validation_error_output(str(e), processing_time)

    except CriteriaMatchingComputeError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_compute_error_output(str(e), processing_time)

    except Exception as e:
        # Catch-all for any unhandled exceptions.
        # This block MUST NOT raise - use nested try/except for all operations.
        processing_time = _safe_elapsed_time_ms(start_time)

        # Safe logging - failures here must not propagate
        try:
            logger.exception(
                "Unhandled exception in success criteria matching compute. "
                "correlation_id=%s, criteria_count=%d, processing_time_ms=%.2f",
                getattr(input_data, "correlation_id", "<unknown>"),
                len(getattr(input_data, "criteria_set", [])),
                processing_time,
            )
        except Exception:
            # If logging itself fails, try minimal logging
            with contextlib.suppress(Exception):
                logger.error("Success criteria matching compute failed: %s", e)

        # Safe error response creation
        return _create_safe_error_output(
            f"Unhandled error: {e}",
            processing_time,
        )


def _execute_matching(
    input_data: ModelSuccessCriteriaInput,
    start_time: float,
) -> ModelSuccessCriteriaOutput:
    """Execute the criteria matching logic.

    Args:
        input_data: Typed input model with execution outcome and criteria.
        start_time: Performance counter start time for timing.

    Returns:
        ModelSuccessCriteriaOutput with matching results.

    Raises:
        CriteriaMatchingValidationError: If input validation fails.
        CriteriaMatchingComputeError: If matching computation fails.
    """
    # Extract data from input model
    # execution_outcome is a TypedDict, convert to plain dict for matching
    outcome = dict(input_data.execution_outcome)
    criteria = list(input_data.criteria_set)

    # Perform matching
    result = match_criteria(outcome, criteria)

    processing_time = (time.perf_counter() - start_time) * 1000

    # Build match details strings for metadata
    match_detail_strings = [
        f"{d['criterion_id']}: {d['reason']}" for d in result["match_details"]
    ]

    # Create metadata
    metadata = CriteriaMatchMetadataDict(
        processing_time_ms=int(processing_time),
        timestamp=datetime.now(UTC).isoformat(),
        total_criteria=len(criteria),
        matched_count=len(result["matched_criteria"]),
        unmatched_count=len(result["unmatched_criteria"]),
        skipped_count=0,  # No skipping in current implementation
        weighted_score=result["match_score"],
        required_criteria_met=result["success"],
        match_details=match_detail_strings,
    )

    return ModelSuccessCriteriaOutput(
        success=result["success"],
        matched_criteria=result["matched_criteria"],
        match_score=result["match_score"],
        unmatched_criteria=result["unmatched_criteria"],
        metadata=metadata,
    )


def _create_validation_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelSuccessCriteriaOutput:
    """Create output for validation errors.

    Args:
        error_message: The validation error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelSuccessCriteriaOutput indicating validation failure.
    """
    return ModelSuccessCriteriaOutput(
        success=False,
        matched_criteria=[],
        match_score=0.0,
        unmatched_criteria=[],
        metadata=CriteriaMatchMetadataDict(
            processing_time_ms=int(processing_time_ms),
            timestamp=datetime.now(UTC).isoformat(),
            total_criteria=0,
            matched_count=0,
            unmatched_count=0,
            skipped_count=0,
            weighted_score=0.0,
            required_criteria_met=False,
            match_details=[f"[{STATUS_VALIDATION_ERROR}] {error_message}"],
        ),
    )


def _create_compute_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelSuccessCriteriaOutput:
    """Create output for compute errors.

    Args:
        error_message: The compute error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelSuccessCriteriaOutput indicating compute failure.
    """
    return ModelSuccessCriteriaOutput(
        success=False,
        matched_criteria=[],
        match_score=0.0,
        unmatched_criteria=[],
        metadata=CriteriaMatchMetadataDict(
            processing_time_ms=int(processing_time_ms),
            timestamp=datetime.now(UTC).isoformat(),
            total_criteria=0,
            matched_count=0,
            unmatched_count=0,
            skipped_count=0,
            weighted_score=0.0,
            required_criteria_met=False,
            match_details=[f"[{STATUS_COMPUTE_ERROR}] {error_message}"],
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
    except Exception:
        return 0.0


def _create_safe_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelSuccessCriteriaOutput:
    """Create error output that is guaranteed not to raise exceptions.

    This is the last-resort error creator used in the catch-all exception handler.
    It uses nested try/except to ensure we always return a valid output object,
    even if model creation fails for some reason.

    Args:
        error_message: The error message to include.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelSuccessCriteriaOutput indicating failure. Always succeeds.
    """
    try:
        return _create_compute_error_output(error_message, processing_time_ms)
    except Exception:
        # If normal error output creation fails, create minimal output
        # This should never happen, but ensures the no-exception contract
        try:
            return ModelSuccessCriteriaOutput(
                success=False,
                matched_criteria=[],
                match_score=0.0,
                unmatched_criteria=[],
                metadata=CriteriaMatchMetadataDict(
                    processing_time_ms=0,
                    timestamp="",
                    total_criteria=0,
                    matched_count=0,
                    unmatched_count=0,
                    skipped_count=0,
                    weighted_score=0.0,
                    required_criteria_met=False,
                    match_details=["Error output creation failed"],
                ),
            )
        except Exception:
            # Absolute last resort - return minimal valid object
            return ModelSuccessCriteriaOutput(
                success=False,
                matched_criteria=[],
                match_score=0.0,
                unmatched_criteria=[],
                metadata=None,
            )


__all__ = ["handle_success_criteria_compute"]
