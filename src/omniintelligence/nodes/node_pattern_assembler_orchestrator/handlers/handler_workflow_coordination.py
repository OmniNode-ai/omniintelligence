"""Workflow coordination handler for Pattern Assembler Orchestrator.

This module coordinates the 4-step workflow execution:
1. Parse traces (execution_trace_parser_compute)
2. Classify intent (node_intent_classifier_compute)
3. Match criteria (success_criteria_matcher_compute)
4. Assemble pattern (internal)

Each step transforms data for the next step in the pipeline.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.exceptions import (
    CriteriaMatchingError,
    IntentClassificationError,
    TraceParsingError,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    AssemblyContextDict,
    CriteriaMatchingResultDict,
    IntentClassificationResultDict,
    ProtocolComputeNode,
    StepResultDict,
    TraceParsingResultDict,
    WorkflowResultDict,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
        ModelPatternAssemblyInput,
    )

logger = logging.getLogger(__name__)

# Step identifiers matching contract.yaml
STEP_PARSE_TRACES = "parse_traces"
STEP_CLASSIFY_INTENT = "classify_intent"
STEP_MATCH_CRITERIA = "match_criteria"
STEP_ASSEMBLE_PATTERN = "assemble_pattern"


def execute_workflow(
    input_data: ModelPatternAssemblyInput,
    trace_parser_node: ProtocolComputeNode | None = None,
    intent_classifier_node: ProtocolComputeNode | None = None,
    criteria_matcher_node: ProtocolComputeNode | None = None,
) -> WorkflowResultDict:
    """Execute the complete workflow synchronously.

    This is a synchronous wrapper that coordinates all steps.
    For async execution, use execute_workflow_async.

    Args:
        input_data: The orchestrator input data.
        trace_parser_node: Optional trace parser compute node.
        intent_classifier_node: Optional intent classifier compute node.
        criteria_matcher_node: Optional criteria matcher compute node.

    Returns:
        WorkflowResultDict with results from all steps.
    """
    import asyncio

    return asyncio.run(
        execute_workflow_async(
            input_data,
            trace_parser_node,
            intent_classifier_node,
            criteria_matcher_node,
        )
    )


async def execute_workflow_async(
    input_data: ModelPatternAssemblyInput,
    trace_parser_node: ProtocolComputeNode | None = None,
    intent_classifier_node: ProtocolComputeNode | None = None,
    criteria_matcher_node: ProtocolComputeNode | None = None,
) -> WorkflowResultDict:
    """Execute the complete workflow asynchronously.

    Executes steps in dependency order:
    1. parse_traces (no dependencies)
    2. classify_intent (depends on parse_traces)
    3. match_criteria (depends on classify_intent)

    Args:
        input_data: The orchestrator input data.
        trace_parser_node: Optional trace parser compute node.
        intent_classifier_node: Optional intent classifier compute node.
        criteria_matcher_node: Optional criteria matcher compute node.

    Returns:
        WorkflowResultDict with results from all steps.
    """
    start_time = time.perf_counter()
    correlation_id = input_data.correlation_id
    step_results: dict[str, StepResultDict] = {}

    logger.debug(
        "Starting workflow execution",
        extra={"correlation_id": correlation_id},
    )

    # Initialize result containers
    trace_result = TraceParsingResultDict(success=False)
    intent_result = IntentClassificationResultDict(success=False)
    criteria_result = CriteriaMatchingResultDict(success=False)

    try:
        # Step 1: Parse traces (if enabled)
        if input_data.include_trace_parsing:
            trace_result = await _execute_trace_parsing(
                input_data=input_data,
                trace_parser_node=trace_parser_node,
                correlation_id=correlation_id,
            )
            step_results[STEP_PARSE_TRACES] = _create_step_result_from_trace(
                trace_result
            )

            if not trace_result.get("success", False):
                return _create_failed_workflow_result(
                    start_time=start_time,
                    step_results=step_results,
                    trace_result=trace_result,
                    intent_result=intent_result,
                    criteria_result=criteria_result,
                    error_message=str(
                        trace_result.get("error_message", "Trace parsing failed")
                    ),
                    error_code="PAO_001",
                )

        # Step 2: Classify intent (if enabled)
        if input_data.include_intent_classification:
            intent_result = await _execute_intent_classification(
                input_data=input_data,
                _trace_result=trace_result,
                intent_classifier_node=intent_classifier_node,
                correlation_id=correlation_id,
            )
            step_results[STEP_CLASSIFY_INTENT] = _create_step_result_from_intent(
                intent_result
            )

            if not intent_result.get("success", False):
                return _create_failed_workflow_result(
                    start_time=start_time,
                    step_results=step_results,
                    trace_result=trace_result,
                    intent_result=intent_result,
                    criteria_result=criteria_result,
                    error_message=str(
                        intent_result.get(
                            "error_message", "Intent classification failed"
                        )
                    ),
                    error_code="PAO_003",
                )

        # Step 3: Match criteria
        criteria_result = await _execute_criteria_matching(
            input_data=input_data,
            trace_result=trace_result,
            _intent_result=intent_result,
            criteria_matcher_node=criteria_matcher_node,
            correlation_id=correlation_id,
        )
        step_results[STEP_MATCH_CRITERIA] = _create_step_result_from_criteria(
            criteria_result
        )

        if not criteria_result.get("success", False):
            return _create_failed_workflow_result(
                start_time=start_time,
                step_results=step_results,
                trace_result=trace_result,
                intent_result=intent_result,
                criteria_result=criteria_result,
                error_message=str(
                    criteria_result.get("error_message", "Criteria matching failed")
                ),
                error_code="PAO_004",
            )

        # All steps succeeded
        total_duration = _elapsed_time_ms(start_time)

        logger.debug(
            "Workflow execution completed successfully: duration_ms=%.2f",
            total_duration,
            extra={"correlation_id": correlation_id},
        )

        return WorkflowResultDict(
            success=True,
            total_duration_ms=total_duration,
            step_results=step_results,
            trace_result=trace_result,
            intent_result=intent_result,
            criteria_result=criteria_result,
            error_message="",
            error_code="",
        )

    except TraceParsingError as e:
        logger.error(
            "Trace parsing error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_failed_workflow_result(
            start_time=start_time,
            step_results=step_results,
            trace_result=trace_result,
            intent_result=intent_result,
            criteria_result=criteria_result,
            error_message=str(e),
            error_code=e.error_code.value,
        )

    except IntentClassificationError as e:
        logger.error(
            "Intent classification error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_failed_workflow_result(
            start_time=start_time,
            step_results=step_results,
            trace_result=trace_result,
            intent_result=intent_result,
            criteria_result=criteria_result,
            error_message=str(e),
            error_code=e.error_code.value,
        )

    except CriteriaMatchingError as e:
        logger.error(
            "Criteria matching error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_failed_workflow_result(
            start_time=start_time,
            step_results=step_results,
            trace_result=trace_result,
            intent_result=intent_result,
            criteria_result=criteria_result,
            error_message=str(e),
            error_code=e.error_code.value,
        )

    except Exception as e:
        logger.exception(
            "Unexpected workflow error: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        return _create_failed_workflow_result(
            start_time=start_time,
            step_results=step_results,
            trace_result=trace_result,
            intent_result=intent_result,
            criteria_result=criteria_result,
            error_message=f"Unexpected error: {e}",
            error_code="PAO_005",
        )


async def _execute_trace_parsing(
    input_data: ModelPatternAssemblyInput,
    trace_parser_node: ProtocolComputeNode | None,
    correlation_id: str | None,
) -> TraceParsingResultDict:
    """Execute trace parsing step.

    Transforms orchestrator input to trace parser input and executes.

    Args:
        input_data: The orchestrator input.
        trace_parser_node: The trace parser compute node.
        correlation_id: Correlation ID for tracing.

    Returns:
        TraceParsingResultDict with parsing results.
    """
    start_time = time.perf_counter()

    logger.debug(
        "Executing trace parsing step",
        extra={"correlation_id": correlation_id},
    )

    # Get traces from input
    raw_data = input_data.raw_data
    traces = raw_data.get("execution_traces", [])

    if not traces:
        # No traces to parse - return empty success
        return TraceParsingResultDict(
            success=True,
            parsed_events=[],
            error_events=[],
            timing_data={},
            metadata={"event_count": 0, "error_count": 0},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # If we have a trace parser node, use it
    if trace_parser_node is not None:
        # Import here to avoid circular imports
        from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
            ModelTraceData,
            ModelTraceParsingInput,
        )

        # Process each trace (or first trace for simplicity)
        first_trace = traces[0] if traces else {}
        trace_input = ModelTraceParsingInput(
            trace_data=ModelTraceData(
                span_id=first_trace.get("span_id"),
                trace_id=first_trace.get("trace_id"),
                parent_span_id=first_trace.get("parent_span_id"),
                operation_name=first_trace.get("operation_name"),
                service_name=first_trace.get("service_name"),
                start_time=first_trace.get("start_time"),
                end_time=first_trace.get("end_time"),
                duration_ms=first_trace.get("duration_ms"),
                status=first_trace.get("status"),
                tags=first_trace.get("tags", {}),
                logs=[],
            ),
            correlation_id=correlation_id,
            trace_format="json",
            extract_errors=True,
            extract_timing=True,
        )

        # Call the compute node
        result = await trace_parser_node.compute(trace_input)

        return TraceParsingResultDict(
            success=result.success,
            parsed_events=[e.model_dump() for e in result.parsed_events],
            error_events=[e.model_dump() for e in result.error_events],
            timing_data=result.timing_data.model_dump() if result.timing_data else {},
            metadata=result.metadata.model_dump() if result.metadata else {},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # No node available - simulate success with input data as events
    return TraceParsingResultDict(
        success=True,
        parsed_events=[{"trace_data": t} for t in traces],
        error_events=[],
        timing_data={},
        metadata={"event_count": len(traces), "error_count": 0, "simulated": True},
        duration_ms=_elapsed_time_ms(start_time),
    )


async def _execute_intent_classification(
    input_data: ModelPatternAssemblyInput,
    _trace_result: TraceParsingResultDict,  # Reserved for future context enrichment
    intent_classifier_node: ProtocolComputeNode | None,
    correlation_id: str | None,
) -> IntentClassificationResultDict:
    """Execute intent classification step.

    Uses content from input data to classify user intent.

    Args:
        input_data: The orchestrator input.
        trace_result: Results from trace parsing.
        intent_classifier_node: The intent classifier compute node.
        correlation_id: Correlation ID for tracing.

    Returns:
        IntentClassificationResultDict with classification results.
    """
    start_time = time.perf_counter()

    logger.debug(
        "Executing intent classification step",
        extra={"correlation_id": correlation_id},
    )

    # Get content for classification
    raw_data = input_data.raw_data
    content = raw_data.get("content", "")

    if not content:
        # No content to classify
        return IntentClassificationResultDict(
            success=True,
            primary_intent="unknown",
            confidence=0.0,
            secondary_intents=[],
            classification_metadata={"empty_content": True},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # If we have an intent classifier node, use it
    if intent_classifier_node is not None:
        from uuid import UUID as UUID_TYPE

        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            IntentContextDict,
            ModelIntentClassificationInput,
        )

        # Build context from trace results
        context = IntentContextDict(
            language=raw_data.get("language", "unknown"),
            domain=raw_data.get("framework", "general"),
        )

        # Parse correlation_id to UUID if needed
        corr_uuid = None
        if correlation_id:
            with contextlib.suppress(ValueError):
                corr_uuid = UUID_TYPE(correlation_id)

        intent_input = ModelIntentClassificationInput(
            content=content,
            correlation_id=corr_uuid,
            context=context,
        )

        # Call the compute node
        result = await intent_classifier_node.compute(intent_input)

        return IntentClassificationResultDict(
            success=result.success,
            primary_intent=result.primary_intent or "unknown",
            confidence=result.confidence or 0.0,
            secondary_intents=result.secondary_intents or [],
            classification_metadata=result.metadata or {},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # No node available - simulate success with default intent
    return IntentClassificationResultDict(
        success=True,
        primary_intent="code_generation",
        confidence=0.8,
        secondary_intents=["debugging"],
        classification_metadata={"simulated": True},
        duration_ms=_elapsed_time_ms(start_time),
    )


async def _execute_criteria_matching(
    input_data: ModelPatternAssemblyInput,
    trace_result: TraceParsingResultDict,
    _intent_result: IntentClassificationResultDict,  # Reserved for future context enrichment
    criteria_matcher_node: ProtocolComputeNode | None,
    correlation_id: str | None,
) -> CriteriaMatchingResultDict:
    """Execute criteria matching step.

    Matches execution outcomes against success criteria.

    Args:
        input_data: The orchestrator input.
        trace_result: Results from trace parsing.
        intent_result: Results from intent classification.
        criteria_matcher_node: The criteria matcher compute node.
        correlation_id: Correlation ID for tracing.

    Returns:
        CriteriaMatchingResultDict with matching results.
    """
    start_time = time.perf_counter()

    logger.debug(
        "Executing criteria matching step",
        extra={"correlation_id": correlation_id},
    )

    # Get success criteria from input
    criteria_list = input_data.success_criteria

    if not criteria_list:
        # No criteria to match - return success with no matches
        return CriteriaMatchingResultDict(
            success=True,
            criteria_matched=[],
            criteria_failed=[],
            match_score=1.0,  # No criteria means no failures
            overall_success=True,
            metadata={"no_criteria": True},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # If we have a criteria matcher node, use it
    if criteria_matcher_node is not None:
        from omniintelligence.nodes.node_success_criteria_matcher_compute.models import (
            ExecutionOutcomeDict,
            ModelSuccessCriteriaInput,
        )

        # Build execution outcome from trace results
        execution_outcome = ExecutionOutcomeDict(
            status="success" if trace_result.get("success", False) else "failure",
            duration_ms=int(trace_result.get("duration_ms", 0)),
            output_type="pattern_assembly",
        )

        # Convert criteria to expected format
        criteria_input = ModelSuccessCriteriaInput(
            execution_outcome=execution_outcome,
            correlation_id=correlation_id,
            criteria_set=criteria_list,
        )

        # Call the compute node
        result = await criteria_matcher_node.compute(criteria_input)

        return CriteriaMatchingResultDict(
            success=True,  # The matching itself succeeded
            criteria_matched=result.criteria_matched or [],
            criteria_failed=result.criteria_failed or [],
            match_score=result.match_score or 0.0,
            overall_success=result.overall_success or False,
            metadata=result.metadata or {},
            duration_ms=_elapsed_time_ms(start_time),
        )

    # No node available - simulate success
    return CriteriaMatchingResultDict(
        success=True,
        criteria_matched=[
            c.get("criterion_id", f"criterion_{i}") for i, c in enumerate(criteria_list)
        ],
        criteria_failed=[],
        match_score=1.0,
        overall_success=True,
        metadata={"simulated": True},
        duration_ms=_elapsed_time_ms(start_time),
    )


def build_assembly_context(
    input_data: ModelPatternAssemblyInput,
    workflow_result: WorkflowResultDict,
) -> AssemblyContextDict:
    """Build context for pattern assembly from workflow results.

    Aggregates all data needed for the final pattern assembly step.

    Args:
        input_data: The original orchestrator input.
        workflow_result: Results from workflow execution.

    Returns:
        AssemblyContextDict with all assembly data.
    """
    raw_data = input_data.raw_data
    trace_result = workflow_result.get("trace_result", {})
    intent_result = workflow_result.get("intent_result", {})
    criteria_result = workflow_result.get("criteria_result", {})

    return AssemblyContextDict(
        content=raw_data.get("content", ""),
        language=raw_data.get("language", ""),
        framework=raw_data.get("framework", ""),
        trace_events=trace_result.get("parsed_events", []),
        trace_errors=trace_result.get("error_events", []),
        primary_intent=intent_result.get("primary_intent", "unknown"),
        intent_confidence=intent_result.get("confidence", 0.0),
        secondary_intents=intent_result.get("secondary_intents", []),
        criteria_matched=criteria_result.get("criteria_matched", []),
        criteria_failed=criteria_result.get("criteria_failed", []),
        match_score=criteria_result.get("match_score", 0.0),
        correlation_id=input_data.correlation_id or "",
    )


def _create_step_result_from_trace(
    trace_result: TraceParsingResultDict,
) -> StepResultDict:
    """Create step result from trace parsing result."""
    return StepResultDict(
        step_id=STEP_PARSE_TRACES,
        node_name="execution_trace_parser_compute",
        success=trace_result.get("success", False),
        duration_ms=trace_result.get("duration_ms", 0.0),
        error_message="",
        error_code="",
        output={"event_count": len(trace_result.get("parsed_events", []))},
    )


def _create_step_result_from_intent(
    intent_result: IntentClassificationResultDict,
) -> StepResultDict:
    """Create step result from intent classification result."""
    return StepResultDict(
        step_id=STEP_CLASSIFY_INTENT,
        node_name="node_intent_classifier_compute",
        success=intent_result.get("success", False),
        duration_ms=intent_result.get("duration_ms", 0.0),
        error_message="",
        error_code="",
        output={"primary_intent": intent_result.get("primary_intent", "")},
    )


def _create_step_result_from_criteria(
    criteria_result: CriteriaMatchingResultDict,
) -> StepResultDict:
    """Create step result from criteria matching result."""
    return StepResultDict(
        step_id=STEP_MATCH_CRITERIA,
        node_name="success_criteria_matcher_compute",
        success=criteria_result.get("success", False),
        duration_ms=criteria_result.get("duration_ms", 0.0),
        error_message="",
        error_code="",
        output={"match_score": criteria_result.get("match_score", 0.0)},
    )


def _create_failed_workflow_result(
    start_time: float,
    step_results: dict[str, StepResultDict],
    trace_result: TraceParsingResultDict,
    intent_result: IntentClassificationResultDict,
    criteria_result: CriteriaMatchingResultDict,
    error_message: str,
    error_code: str,
) -> WorkflowResultDict:
    """Create a failed workflow result.

    Args:
        start_time: Workflow start time.
        step_results: Results from completed steps.
        trace_result: Trace parsing results.
        intent_result: Intent classification results.
        criteria_result: Criteria matching results.
        error_message: Error description.
        error_code: Error code.

    Returns:
        WorkflowResultDict indicating failure.
    """
    return WorkflowResultDict(
        success=False,
        total_duration_ms=_elapsed_time_ms(start_time),
        step_results=step_results,
        trace_result=trace_result,
        intent_result=intent_result,
        criteria_result=criteria_result,
        error_message=error_message,
        error_code=error_code,
    )


def _elapsed_time_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds."""
    return (time.perf_counter() - start_time) * 1000


__all__ = [
    "STEP_ASSEMBLE_PATTERN",
    "STEP_CLASSIFY_INTENT",
    "STEP_MATCH_CRITERIA",
    "STEP_PARSE_TRACES",
    "build_assembly_context",
    "execute_workflow",
    "execute_workflow_async",
]
