"""Handler for quality scoring compute node orchestration.

This module provides the compute handler that orchestrates quality scoring
operations at the node level. It bridges the gap between the node's typed
input/output models and the pure scoring function.

The handler:
    - Accepts ModelQualityScoringInput (Pydantic model)
    - Returns ModelQualityScoringOutput (Pydantic model)
    - Handles error cases gracefully (returns error output, doesn't raise)
    - Manages timing and metadata

This separation allows the node.py to be a thin shell that simply delegates
to this handler, following the ONEX declarative pattern.

Example:
    from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_compute import (
        handle_quality_scoring_compute,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.models import (
        ModelQualityScoringInput,
        ModelQualityScoringOutput,
    )

    input_data = ModelQualityScoringInput(
        source_path="test.py",
        content="class Foo: pass",
        language="python",
    )
    output: ModelQualityScoringOutput = handle_quality_scoring_compute(input_data)
"""

from __future__ import annotations

import logging
import time
from typing import Final

from omniintelligence.nodes.node_quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
    QualityScoringValidationError,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
    score_code_quality,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.protocols import (
    create_error_dimensions,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_input import (
    ModelQualityScoringInput,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_output import (
    ModelQualityScoringMetadata,
    ModelQualityScoringOutput,
)

# Module logger for exception tracking
logger = logging.getLogger(__name__)

# Status constants for metadata
STATUS_COMPLETED: Final[str] = "completed"
STATUS_BELOW_THRESHOLD: Final[str] = "below_threshold"
STATUS_VALIDATION_ERROR: Final[str] = "validation_error"
STATUS_COMPUTE_ERROR: Final[str] = "compute_error"


def handle_quality_scoring_compute(
    input_data: ModelQualityScoringInput,
) -> ModelQualityScoringOutput:
    """Handle quality scoring compute operation.

    This function orchestrates the quality scoring workflow:
    1. Prepares configuration (handles preset vs manual weights)
    2. Calls the pure scoring function
    3. Checks against thresholds
    4. Constructs the output model with metadata

    Error Handling:
        - QualityScoringValidationError: Returns output with validation_error status
        - QualityScoringComputeError: Returns output with compute_error status
        - All errors are caught and returned as structured output (no exceptions raised)

    Args:
        input_data: Typed input model containing source code and scoring configuration.

    Returns:
        ModelQualityScoringOutput with quality score, dimensions, compliance status,
        and recommendations. Always returns a valid output, even on errors.
    """
    start_time = time.perf_counter()

    try:
        return _execute_scoring(input_data, start_time)

    except QualityScoringValidationError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_validation_error_output(str(e), processing_time)

    except QualityScoringComputeError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return _create_compute_error_output(str(e), processing_time)

    except Exception as e:
        # Log unhandled exceptions with full traceback for debugging
        # This ensures we have diagnostic information while still honoring
        # the no-exception contract by returning an error response
        processing_time = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "Unhandled exception in quality scoring compute. "
            "source_path=%s, language=%s, processing_time_ms=%.2f",
            input_data.source_path,
            input_data.language,
            processing_time,
        )
        return _create_compute_error_output(f"Unhandled error: {e}", processing_time)


def _execute_scoring(
    input_data: ModelQualityScoringInput,
    start_time: float,
) -> ModelQualityScoringOutput:
    """Execute the quality scoring logic.

    Args:
        input_data: Typed input model with source code and configuration.
        start_time: Performance counter start time for timing.

    Returns:
        ModelQualityScoringOutput with scoring results.

    Raises:
        QualityScoringValidationError: If input validation fails.
        QualityScoringComputeError: If scoring computation fails.
    """
    # Determine scoring parameters based on preset or manual config
    if input_data.onex_preset is not None:
        # Preset takes precedence - call handler with preset
        result = score_code_quality(
            content=input_data.content,
            language=input_data.language,
            preset=input_data.onex_preset,
        )
    else:
        # Manual configuration - prepare weights dict if provided
        weights = _extract_weights_dict(input_data)
        result = score_code_quality(
            content=input_data.content,
            language=input_data.language,
            weights=weights,
            onex_threshold=input_data.onex_compliance_threshold,
        )

    processing_time = (time.perf_counter() - start_time) * 1000

    # Check against minimum quality threshold
    meets_threshold = result["quality_score"] >= input_data.min_quality_threshold

    return ModelQualityScoringOutput(
        success=result["success"] and meets_threshold,
        quality_score=result["quality_score"],
        dimensions=result["dimensions"],
        onex_compliant=result["onex_compliant"],
        recommendations=result["recommendations"],
        metadata=ModelQualityScoringMetadata(
            status=STATUS_COMPLETED if meets_threshold else STATUS_BELOW_THRESHOLD,
            message=(
                None
                if meets_threshold
                else f"Quality score {result['quality_score']:.2f} below threshold {input_data.min_quality_threshold}"
            ),
            source_language=result["source_language"],
            analysis_version=result["analysis_version"],
            processing_time_ms=processing_time,
        ),
    )


def _extract_weights_dict(input_data: ModelQualityScoringInput) -> dict[str, float] | None:
    """Extract weights dictionary from input model.

    Args:
        input_data: Input model potentially containing dimension weights.

    Returns:
        Dictionary of weights or None if no custom weights specified.
    """
    if input_data.dimension_weights is None:
        return None

    return {
        "complexity": input_data.dimension_weights.complexity,
        "maintainability": input_data.dimension_weights.maintainability,
        "documentation": input_data.dimension_weights.documentation,
        "temporal_relevance": input_data.dimension_weights.temporal_relevance,
        "patterns": input_data.dimension_weights.patterns,
        "architectural": input_data.dimension_weights.architectural,
    }


def _create_validation_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelQualityScoringOutput:
    """Create output for validation errors.

    Args:
        error_message: The validation error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelQualityScoringOutput indicating validation failure.
    """
    return ModelQualityScoringOutput(
        success=False,
        quality_score=0.0,
        dimensions=create_error_dimensions(),
        onex_compliant=False,
        recommendations=[],
        metadata=ModelQualityScoringMetadata(
            status=STATUS_VALIDATION_ERROR,
            message=error_message,
            processing_time_ms=processing_time_ms,
        ),
    )


def _create_compute_error_output(
    error_message: str,
    processing_time_ms: float,
) -> ModelQualityScoringOutput:
    """Create output for compute errors.

    Args:
        error_message: The compute error message.
        processing_time_ms: Time spent before the error occurred.

    Returns:
        ModelQualityScoringOutput indicating compute failure.
    """
    return ModelQualityScoringOutput(
        success=False,
        quality_score=0.0,
        dimensions=create_error_dimensions(),
        onex_compliant=False,
        recommendations=[],
        metadata=ModelQualityScoringMetadata(
            status=STATUS_COMPUTE_ERROR,
            message=error_message,
            processing_time_ms=processing_time_ms,
        ),
    )


__all__ = ["handle_quality_scoring_compute"]
