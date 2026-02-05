"""Main orchestration handler for Pattern Assembler Orchestrator.

This module is the entry point for pattern assembly orchestration.
It coordinates the workflow execution and pattern assembly, returning
structured output and never raising exceptions.

Workflow:
1. Validate input
2. Execute workflow steps (parse_traces → classify_intent → match_criteria)
3. Assemble final pattern from results
4. Return structured output

Error Handling: Returns structured error output, never raises.
Correlation ID: Threaded through all operations for end-to-end tracing.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.exceptions import (
    InvalidInputError,
    PatternAssemblerOrchestratorError,
    PatternAssemblyError,
    WorkflowTimeoutError,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_pattern_assembly import (
    assemble_pattern,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_workflow_coordination import (
    build_assembly_context,
    execute_workflow_async,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    ProtocolComputeNode,
    WorkflowResultDict,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    AssembledPatternOutputDict,
    AssemblyMetadataDict,
    ComponentResultsDict,
    ModelPatternAssemblyOutput,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
        ModelPatternAssemblyInput,
    )

logger = logging.getLogger(__name__)

# Default workflow timeout in seconds (from contract.yaml)
DEFAULT_TIMEOUT_SECONDS = 120


async def handle_pattern_assembly_orchestrate(
    input_data: ModelPatternAssemblyInput,
    trace_parser_node: ProtocolComputeNode | None = None,
    intent_classifier_node: ProtocolComputeNode | None = None,
    criteria_matcher_node: ProtocolComputeNode | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ModelPatternAssemblyOutput:
    """Handle pattern assembly orchestration.

    This is the main entry point for the orchestrator node.
    It coordinates the complete workflow and returns structured output.

    Args:
        input_data: Input containing raw data and assembly parameters.
        trace_parser_node: Optional trace parser compute node.
        intent_classifier_node: Optional intent classifier compute node.
        criteria_matcher_node: Optional criteria matcher compute node.
        timeout_seconds: Maximum workflow execution time.

    Returns:
        ModelPatternAssemblyOutput with assembled pattern or error details.

    Note:
        This function never raises exceptions. All errors are captured
        and returned as structured output with success=False.
    """
    start_time = time.perf_counter()
    correlation_id = input_data.correlation_id

    logger.debug(
        "Starting pattern assembly orchestration",
        extra={"correlation_id": correlation_id},
    )

    try:
        # Validate input
        _validate_input(input_data)

        # Execute the workflow
        workflow_result = await execute_workflow_async(
            input_data=input_data,
            trace_parser_node=trace_parser_node,
            intent_classifier_node=intent_classifier_node,
            criteria_matcher_node=criteria_matcher_node,
        )

        # Check for timeout
        elapsed = _elapsed_time_seconds(start_time)
        if elapsed > timeout_seconds:
            raise WorkflowTimeoutError(
                f"Workflow exceeded timeout: {elapsed:.1f}s > {timeout_seconds}s"
            )

        # Check workflow success
        if not workflow_result.get("success", False):
            return _create_workflow_error_output(
                workflow_result=workflow_result,
                processing_time=_elapsed_time_ms(start_time),
            )

        # Build assembly context from results
        assembly_context = build_assembly_context(input_data, workflow_result)

        # Assemble the final pattern
        assembled_pattern, component_results, metadata = assemble_pattern(
            context=assembly_context,
            workflow_result=workflow_result,
            _input_data=input_data,
        )

        logger.debug(
            "Pattern assembly orchestration completed successfully: "
            "pattern_id=%s, duration_ms=%.2f",
            assembled_pattern.get("pattern_id"),
            _elapsed_time_ms(start_time),
            extra={"correlation_id": correlation_id},
        )

        return ModelPatternAssemblyOutput(
            success=True,
            assembled_pattern=assembled_pattern,
            component_results=component_results,
            metadata=metadata,
        )

    except InvalidInputError as e:
        processing_time = _elapsed_time_ms(start_time)
        logger.warning(
            "Input validation failed: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_validation_error_output(str(e), processing_time)

    except WorkflowTimeoutError as e:
        processing_time = _elapsed_time_ms(start_time)
        logger.error(
            "Workflow timeout: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_timeout_error_output(str(e), processing_time)

    except PatternAssemblyError as e:
        processing_time = _elapsed_time_ms(start_time)
        logger.error(
            "Pattern assembly error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_assembly_error_output(str(e), processing_time)

    except PatternAssemblerOrchestratorError as e:
        processing_time = _elapsed_time_ms(start_time)
        logger.error(
            "Orchestrator error (%s): %s",
            e.error_code.value,
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_domain_error_output(e, processing_time)

    except Exception as e:
        processing_time = _safe_elapsed_time_ms(start_time)
        # Log with exception info, but suppress logging failures
        with contextlib.suppress(Exception):
            logger.exception(
                "Unhandled exception in orchestration: %s",
                str(e),
                extra={"correlation_id": correlation_id},
            )
        return _create_safe_error_output(f"Unhandled error: {e}", processing_time)


def _validate_input(input_data: ModelPatternAssemblyInput) -> None:
    """Validate orchestrator input.

    Args:
        input_data: Input to validate.

    Raises:
        InvalidInputError: If validation fails.
    """
    raw_data = input_data.raw_data

    # Check that we have at least content or traces
    content = raw_data.get("content", "")
    traces = raw_data.get("execution_traces", [])

    if not content and not traces:
        raise InvalidInputError("Input must contain either content or execution_traces")


def _create_workflow_error_output(
    workflow_result: WorkflowResultDict,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for workflow execution errors.

    Args:
        workflow_result: The failed workflow result.
        processing_time: Processing time before error.

    Returns:
        ModelPatternAssemblyOutput indicating workflow failure.
    """
    error_message = workflow_result.get("error_message", "Workflow failed")
    error_code = workflow_result.get("error_code", "PAO_005")

    return ModelPatternAssemblyOutput(
        success=False,
        assembled_pattern=AssembledPatternOutputDict(),
        component_results=ComponentResultsDict(),
        metadata=AssemblyMetadataDict(
            processing_time_ms=int(processing_time),
            status="failed",
            warnings=[f"Workflow error ({error_code}): {error_message}"],
        ),
    )


def _create_validation_error_output(
    error_message: str,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for validation errors.

    Args:
        error_message: Description of the validation error.
        processing_time: Processing time before error.

    Returns:
        ModelPatternAssemblyOutput indicating validation failure.
    """
    return ModelPatternAssemblyOutput(
        success=False,
        assembled_pattern=AssembledPatternOutputDict(),
        component_results=ComponentResultsDict(),
        metadata=AssemblyMetadataDict(
            processing_time_ms=int(processing_time),
            status="validation_failed",
            warnings=[f"Validation error (PAO_008): {error_message}"],
        ),
    )


def _create_timeout_error_output(
    error_message: str,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for timeout errors.

    Args:
        error_message: Description of the timeout.
        processing_time: Processing time before timeout.

    Returns:
        ModelPatternAssemblyOutput indicating timeout failure.
    """
    return ModelPatternAssemblyOutput(
        success=False,
        assembled_pattern=AssembledPatternOutputDict(),
        component_results=ComponentResultsDict(),
        metadata=AssemblyMetadataDict(
            processing_time_ms=int(processing_time),
            status="timeout",
            warnings=[f"Timeout error (PAO_006): {error_message}"],
        ),
    )


def _create_assembly_error_output(
    error_message: str,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for pattern assembly errors.

    Args:
        error_message: Description of the assembly error.
        processing_time: Processing time before error.

    Returns:
        ModelPatternAssemblyOutput indicating assembly failure.
    """
    return ModelPatternAssemblyOutput(
        success=False,
        assembled_pattern=AssembledPatternOutputDict(),
        component_results=ComponentResultsDict(),
        metadata=AssemblyMetadataDict(
            processing_time_ms=int(processing_time),
            status="assembly_failed",
            warnings=[f"Assembly error (PAO_005): {error_message}"],
        ),
    )


def _create_domain_error_output(
    error: PatternAssemblerOrchestratorError,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for domain-specific errors.

    Args:
        error: The domain error.
        processing_time: Processing time before error.

    Returns:
        ModelPatternAssemblyOutput indicating domain error.
    """
    return ModelPatternAssemblyOutput(
        success=False,
        assembled_pattern=AssembledPatternOutputDict(),
        component_results=ComponentResultsDict(),
        metadata=AssemblyMetadataDict(
            processing_time_ms=int(processing_time),
            status="failed",
            warnings=[f"Error ({error.error_code.value}): {error.message}"],
        ),
    )


def _create_safe_error_output(
    error_message: str,
    processing_time: float,
) -> ModelPatternAssemblyOutput:
    """Create output for unexpected errors.

    This is the catch-all error handler that ensures we never raise.

    Args:
        error_message: Description of the error.
        processing_time: Processing time before error.

    Returns:
        ModelPatternAssemblyOutput indicating unexpected failure.
    """
    try:
        return ModelPatternAssemblyOutput(
            success=False,
            assembled_pattern=AssembledPatternOutputDict(),
            component_results=ComponentResultsDict(),
            metadata=AssemblyMetadataDict(
                processing_time_ms=int(processing_time),
                status="error",
                warnings=[f"Unexpected error: {error_message}"],
            ),
        )
    except Exception:
        # Absolute fallback - construct minimal valid output
        return ModelPatternAssemblyOutput(
            success=False,
            assembled_pattern=AssembledPatternOutputDict(),
            component_results=ComponentResultsDict(),
            metadata=AssemblyMetadataDict(
                processing_time_ms=int(processing_time),
                status="critical_error",
                warnings=["Critical error during output construction"],
            ),
        )


def _elapsed_time_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds."""
    return (time.perf_counter() - start_time) * 1000


def _elapsed_time_seconds(start_time: float) -> float:
    """Calculate elapsed time in seconds."""
    return time.perf_counter() - start_time


def _safe_elapsed_time_ms(start_time: float) -> float:
    """Safely calculate elapsed time, returning 0 on error."""
    try:
        return _elapsed_time_ms(start_time)
    except Exception:
        return 0.0


__all__ = [
    "handle_pattern_assembly_orchestrate",
]
