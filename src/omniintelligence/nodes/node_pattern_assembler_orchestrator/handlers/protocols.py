"""Protocol definitions and TypedDicts for Pattern Assembler Orchestrator.

This module defines typed structures for intermediate results, step execution,
and workflow coordination to enable strong typing throughout the orchestration.
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class StepResultDict(TypedDict, total=False):
    """Typed structure for individual step execution results.

    Used to track the outcome of each workflow step.
    """

    step_id: str
    node_name: str
    success: bool
    duration_ms: float
    error_message: str
    error_code: str
    output: dict[str, object]  # Step-specific output data


class TraceParsingResultDict(TypedDict, total=False):
    """Typed structure for trace parsing step results.

    Captures the output from execution_trace_parser_compute.
    """

    success: bool
    parsed_events: list[dict[str, object]]
    error_events: list[dict[str, object]]
    timing_data: dict[str, object]
    metadata: dict[str, object]
    duration_ms: float
    error_message: str


class IntentClassificationResultDict(TypedDict, total=False):
    """Typed structure for intent classification step results.

    Captures the output from node_intent_classifier_compute.
    """

    success: bool
    primary_intent: str
    confidence: float
    secondary_intents: list[str]
    classification_metadata: dict[str, object]
    duration_ms: float
    error_message: str


class CriteriaMatchingResultDict(TypedDict, total=False):
    """Typed structure for criteria matching step results.

    Captures the output from success_criteria_matcher_compute.
    """

    success: bool
    criteria_matched: list[str]
    criteria_failed: list[str]
    match_score: float
    overall_success: bool
    metadata: dict[str, object]
    duration_ms: float
    error_message: str


class WorkflowResultDict(TypedDict, total=False):
    """Typed structure for complete workflow execution results.

    Aggregates results from all workflow steps.
    """

    success: bool
    total_duration_ms: float
    step_results: dict[str, StepResultDict]
    trace_result: TraceParsingResultDict
    intent_result: IntentClassificationResultDict
    criteria_result: CriteriaMatchingResultDict
    error_message: str
    error_code: str


class AssemblyContextDict(TypedDict, total=False):
    """Typed structure for assembly context passed to pattern assembly.

    Contains all the data needed to assemble the final pattern.
    """

    content: str
    language: str
    framework: str
    trace_events: list[dict[str, object]]
    trace_errors: list[dict[str, object]]
    primary_intent: str
    intent_confidence: float
    secondary_intents: list[str]
    criteria_matched: list[str]
    criteria_failed: list[str]
    match_score: float
    correlation_id: str


@runtime_checkable
class ProtocolComputeNode(Protocol):
    """Protocol for compute nodes that can be called by the orchestrator.

    This protocol defines the interface that compute nodes must implement
    to be orchestrated.
    """

    async def compute(self, input_data: object) -> object:
        """Execute computation on input data.

        Args:
            input_data: Node-specific input model.

        Returns:
            Node-specific output model.
        """
        ...


def create_empty_step_result(step_id: str, node_name: str) -> StepResultDict:
    """Create an empty step result structure.

    Args:
        step_id: The workflow step identifier.
        node_name: The compute node name.

    Returns:
        StepResultDict with initial values.
    """
    return StepResultDict(
        step_id=step_id,
        node_name=node_name,
        success=False,
        duration_ms=0.0,
        error_message="",
        error_code="",
        output={},
    )


def create_workflow_result(
    success: bool,
    total_duration_ms: float,
    step_results: dict[str, StepResultDict],
    error_message: str = "",
    error_code: str = "",
) -> WorkflowResultDict:
    """Create a workflow result structure.

    Args:
        success: Whether the workflow succeeded.
        total_duration_ms: Total workflow duration.
        step_results: Results from each step.
        error_message: Error message if failed.
        error_code: Error code if failed.

    Returns:
        WorkflowResultDict with all fields populated.
    """
    return WorkflowResultDict(
        success=success,
        total_duration_ms=total_duration_ms,
        step_results=step_results,
        trace_result=TraceParsingResultDict(),
        intent_result=IntentClassificationResultDict(),
        criteria_result=CriteriaMatchingResultDict(),
        error_message=error_message,
        error_code=error_code,
    )


__all__ = [
    "AssemblyContextDict",
    "CriteriaMatchingResultDict",
    "IntentClassificationResultDict",
    "ProtocolComputeNode",
    "StepResultDict",
    "TraceParsingResultDict",
    "WorkflowResultDict",
    "create_empty_step_result",
    "create_workflow_result",
]
