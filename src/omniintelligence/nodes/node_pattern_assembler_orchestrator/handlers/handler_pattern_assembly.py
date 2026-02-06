"""Pattern assembly handler for Pattern Assembler Orchestrator.

This module implements the final step (step 4) of the workflow:
assembling the pattern from all component results.

The assembly process:
1. Generates a unique pattern ID
2. Determines pattern type from intent classification
3. Extracts trigger, actions, conditions from trace data
4. Calculates confidence and completeness scores
5. Returns AssembledPatternOutputDict
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    AssemblyContextDict,
    WorkflowResultDict,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    AssembledPatternOutputDict,
    AssemblyMetadataDict,
    ComponentResultsDict,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
        ModelPatternAssemblyInput,
    )

logger = logging.getLogger(__name__)

# Intent to pattern type mapping
INTENT_TO_PATTERN_TYPE = {
    "code_generation": "generative",
    "debugging": "diagnostic",
    "refactoring": "transformative",
    "explanation": "explanatory",
    "testing": "validation",
    "documentation": "documentation",
    "optimization": "optimization",
    "unknown": "general",
}


def assemble_pattern(
    context: AssemblyContextDict,
    workflow_result: WorkflowResultDict,
    _input_data: ModelPatternAssemblyInput,  # Reserved for future use
) -> tuple[AssembledPatternOutputDict, ComponentResultsDict, AssemblyMetadataDict]:
    """Assemble the final pattern from workflow results.

    This is the pure function implementing step 4 of the workflow.
    Returns structured error output on failure instead of raising.

    Args:
        context: Assembly context with aggregated data.
        workflow_result: Results from workflow execution.
        _input_data: Original input data (reserved for future use).

    Returns:
        Tuple of (assembled_pattern, component_results, metadata).
        On error, returns empty dicts with metadata.status="assembly_failed".
    """
    start_time = time.perf_counter()
    correlation_id = context.get("correlation_id", "")

    logger.debug(
        "Assembling pattern from workflow results",
        extra={"correlation_id": correlation_id},
    )

    try:
        # Generate pattern ID
        pattern_id = _generate_pattern_id(context)

        # Determine pattern type from intent
        primary_intent = context.get("primary_intent", "unknown")
        pattern_type = INTENT_TO_PATTERN_TYPE.get(primary_intent, "general")

        # Extract pattern structure from trace data
        trigger, actions, conditions = _extract_pattern_structure(context)

        # Determine category and tags
        category, subcategory = _determine_category(context)
        tags = _generate_tags(context)

        # Calculate quality scores
        confidence = _calculate_confidence(context)
        completeness = _calculate_completeness(context)
        validity = _validate_pattern(trigger, actions)

        # Build the assembled pattern
        assembled_pattern = AssembledPatternOutputDict(
            pattern_id=pattern_id,
            pattern_name=_generate_pattern_name(context, pattern_type),
            pattern_type=pattern_type,
            trigger=trigger,
            actions=actions,
            conditions=conditions,
            category=category,
            subcategory=subcategory,
            tags=tags,
            confidence=confidence,
            completeness=completeness,
            validity=validity,
        )

        # Build component results
        component_results = _build_component_results(context, workflow_result)

        # Build metadata
        processing_time = _elapsed_time_ms(start_time)
        metadata = _build_assembly_metadata(workflow_result, processing_time)

        logger.debug(
            "Pattern assembled successfully: pattern_id=%s, type=%s, confidence=%.2f",
            pattern_id,
            pattern_type,
            confidence,
            extra={"correlation_id": correlation_id},
        )

        return assembled_pattern, component_results, metadata

    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # Domain/data errors - return structured output per ONEX handler pattern.
        # Invariant violations (e.g., SchemaCorruptionError) and other fatal
        # exceptions are NOT caught here and will propagate to halt orchestration.
        logger.error(
            "Pattern assembly failed: %s",
            str(e),
            extra={"correlation_id": correlation_id},
        )
        processing_time = _elapsed_time_ms(start_time)
        return _create_assembly_error_output(str(e), workflow_result, processing_time)


def _generate_pattern_id(context: AssemblyContextDict) -> str:
    """Generate a unique pattern ID based on context.

    Uses content hash + UUID for uniqueness while maintaining
    some determinism for the same content.

    Args:
        context: Assembly context.

    Returns:
        Unique pattern ID string.
    """
    content = context.get("content", "")
    intent = context.get("primary_intent", "")

    # Create hash of content for determinism
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]

    # Add UUID suffix for uniqueness
    uuid_suffix = uuid4().hex[:8]

    return f"pat_{intent[:4]}_{content_hash}_{uuid_suffix}"


def _generate_pattern_name(
    context: AssemblyContextDict,
    pattern_type: str,
) -> str:
    """Generate a human-readable pattern name.

    Args:
        context: Assembly context.
        pattern_type: The pattern type.

    Returns:
        Human-readable pattern name.
    """
    intent = context.get("primary_intent", "unknown")
    language = context.get("language", "")

    parts = [pattern_type.title(), "Pattern"]
    if language:
        parts.insert(0, language.title())
    if intent != "unknown":
        parts.append(f"({intent})")

    return " ".join(parts)


def _extract_pattern_structure(
    context: AssemblyContextDict,
) -> tuple[str, list[str], list[str]]:
    """Extract trigger, actions, and conditions from context.

    Analyzes trace events and content to determine the pattern structure.

    Args:
        context: Assembly context.

    Returns:
        Tuple of (trigger, actions, conditions).
    """
    trace_events = context.get("trace_events", [])
    primary_intent = context.get("primary_intent", "unknown")

    # Extract trigger from first event or content
    trigger = "content_analysis"
    if trace_events:
        first_event = trace_events[0]
        if isinstance(first_event, dict):
            trigger = str(
                first_event.get(
                    "operation_name", first_event.get("event_type", "trace_event")
                )
                or "trace_event"
            )

    # Extract actions from intent and trace sequence
    actions = []
    if primary_intent == "code_generation":
        actions = ["parse_requirements", "generate_code", "validate_output"]
    elif primary_intent == "debugging":
        actions = ["analyze_error", "identify_cause", "suggest_fix"]
    elif primary_intent == "refactoring":
        actions = ["analyze_structure", "transform_code", "verify_behavior"]
    else:
        actions = ["analyze_content", "process_data", "produce_result"]

    # Extract conditions from trace errors and criteria
    conditions = []
    trace_errors = context.get("trace_errors", [])
    if not trace_errors:
        conditions.append("no_errors_in_trace")

    criteria_matched = context.get("criteria_matched", [])
    if criteria_matched:
        conditions.append(f"criteria_satisfied: {len(criteria_matched)}")

    intent_confidence = context.get("intent_confidence", 0.0)
    if intent_confidence >= 0.8:
        conditions.append("high_confidence_intent")
    elif intent_confidence >= 0.5:
        conditions.append("moderate_confidence_intent")

    return trigger, actions, conditions


def _determine_category(
    context: AssemblyContextDict,
) -> tuple[str, str]:
    """Determine category and subcategory for the pattern.

    Args:
        context: Assembly context.

    Returns:
        Tuple of (category, subcategory).
    """
    primary_intent = context.get("primary_intent", "unknown")
    framework = context.get("framework", "")
    language = context.get("language", "")

    # Map intent to category
    intent_categories = {
        "code_generation": ("development", "generation"),
        "debugging": ("development", "debugging"),
        "refactoring": ("development", "refactoring"),
        "explanation": ("documentation", "explanation"),
        "testing": ("quality", "testing"),
        "documentation": ("documentation", "writing"),
        "optimization": ("performance", "optimization"),
    }

    category, subcategory = intent_categories.get(primary_intent, ("general", "misc"))

    # Refine subcategory with framework/language
    if framework:
        subcategory = f"{subcategory}_{framework.lower()}"
    elif language:
        subcategory = f"{subcategory}_{language.lower()}"

    return category, subcategory


def _generate_tags(context: AssemblyContextDict) -> list[str]:
    """Generate tags for the pattern.

    Args:
        context: Assembly context.

    Returns:
        List of tags.
    """
    tags = []

    # Add intent as tag
    primary_intent = context.get("primary_intent", "")
    if primary_intent and primary_intent != "unknown":
        tags.append(primary_intent)

    # Add language as tag
    language = context.get("language", "")
    if language:
        tags.append(language.lower())

    # Add framework as tag
    framework = context.get("framework", "")
    if framework:
        tags.append(framework.lower())

    # Add secondary intents
    secondary_intents = context.get("secondary_intents", [])
    for intent in secondary_intents[:2]:  # Limit to 2
        if intent not in tags:
            tags.append(intent)

    # Add quality indicators
    match_score = context.get("match_score", 0.0)
    if match_score >= 0.9:
        tags.append("high_quality")
    elif match_score >= 0.7:
        tags.append("good_quality")

    return tags


def _calculate_confidence(context: AssemblyContextDict) -> float:
    """Calculate overall pattern confidence score.

    Combines intent confidence, criteria matching, and trace quality.

    Args:
        context: Assembly context.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    # Start with intent confidence
    intent_confidence = context.get("intent_confidence", 0.5)

    # Factor in criteria matching
    match_score = context.get("match_score", 0.5)

    # Factor in trace quality (no errors is good)
    trace_errors = context.get("trace_errors", [])
    trace_quality = 1.0 if not trace_errors else max(0.5, 1.0 - len(trace_errors) * 0.1)

    # Weighted average
    confidence = intent_confidence * 0.4 + match_score * 0.4 + trace_quality * 0.2

    return round(min(1.0, max(0.0, confidence)), 2)


def _calculate_completeness(context: AssemblyContextDict) -> float:
    """Calculate pattern completeness score.

    Measures how complete the pattern data is.

    Args:
        context: Assembly context.

    Returns:
        Completeness score between 0.0 and 1.0.
    """
    total_fields = 8
    present_fields = 0

    if context.get("content"):
        present_fields += 1
    if context.get("language"):
        present_fields += 1
    if context.get("primary_intent") and context.get("primary_intent") != "unknown":
        present_fields += 1
    if context.get("trace_events"):
        present_fields += 1
    if context.get("criteria_matched") or context.get("criteria_failed"):
        present_fields += 1
    if context.get("intent_confidence", 0.0) > 0.0:
        present_fields += 1
    if context.get("match_score", 0.0) > 0.0:
        present_fields += 1
    if context.get("correlation_id"):
        present_fields += 1

    return round(present_fields / total_fields, 2)


def _validate_pattern(trigger: str, actions: list[str]) -> bool:
    """Validate that the pattern has required structure.

    Args:
        trigger: Pattern trigger.
        actions: Pattern actions.

    Returns:
        True if valid, False otherwise.
    """
    return bool(trigger) and len(actions) > 0


def _build_component_results(
    context: AssemblyContextDict,
    workflow_result: WorkflowResultDict,
) -> ComponentResultsDict:
    """Build component results from context and workflow.

    Args:
        context: Assembly context.
        workflow_result: Workflow execution results.

    Returns:
        ComponentResultsDict with all component results.
    """
    # Note: workflow_result contains raw step outputs while context contains
    # aggregated/processed data. We use context here since it has the normalized
    # values we need. The workflow_result parameter is kept for future extensibility.
    _ = workflow_result  # Explicitly mark as intentionally unused

    return ComponentResultsDict(
        # Trace parsing results
        trace_events_parsed=len(context.get("trace_events", [])),
        trace_errors=[str(e) for e in context.get("trace_errors", [])],
        # Keyword extraction results (not implemented yet)
        keywords_extracted=0,
        keyword_categories=[],
        # Intent classification results
        primary_intent=context.get("primary_intent", ""),
        intent_confidence=context.get("intent_confidence", 0.0),
        secondary_intents=context.get("secondary_intents", []),
        # Criteria matching results
        criteria_matched=len(context.get("criteria_matched", [])),
        criteria_unmatched=len(context.get("criteria_failed", [])),
        match_score=context.get("match_score", 0.0),
    )


def _build_assembly_metadata(
    workflow_result: WorkflowResultDict,
    assembly_time_ms: float,
) -> AssemblyMetadataDict:
    """Build assembly metadata from workflow results.

    Args:
        workflow_result: Workflow execution results.
        assembly_time_ms: Time for pattern assembly step.

    Returns:
        AssemblyMetadataDict with timing and status.
    """
    step_results = workflow_result.get("step_results", {})

    # Extract step timings
    trace_parsing_ms = 0
    intent_classification_ms = 0
    criteria_matching_ms = 0

    if "parse_traces" in step_results:
        trace_parsing_ms = int(step_results["parse_traces"].get("duration_ms", 0))
    if "classify_intent" in step_results:
        intent_classification_ms = int(
            step_results["classify_intent"].get("duration_ms", 0)
        )
    if "match_criteria" in step_results:
        criteria_matching_ms = int(step_results["match_criteria"].get("duration_ms", 0))

    total_time = workflow_result.get("total_duration_ms", 0.0) + assembly_time_ms

    return AssemblyMetadataDict(
        processing_time_ms=int(total_time),
        timestamp=datetime.now(UTC).isoformat(),
        trace_parsing_ms=trace_parsing_ms,
        keyword_extraction_ms=0,  # Not implemented
        intent_classification_ms=intent_classification_ms,
        criteria_matching_ms=criteria_matching_ms,
        status="completed" if workflow_result.get("success", False) else "failed",
        warnings=[],
    )


def _elapsed_time_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds."""
    return (time.perf_counter() - start_time) * 1000


def _create_assembly_error_output(
    error_message: str,
    workflow_result: WorkflowResultDict,
    processing_time_ms: float,
) -> tuple[AssembledPatternOutputDict, ComponentResultsDict, AssemblyMetadataDict]:
    """Create structured error output for assembly failures.

    Returns empty dicts for pattern/component results with error details
    in metadata, following the ONEX pattern of returning structured
    errors instead of raising domain exceptions.

    Args:
        error_message: Description of the assembly error.
        workflow_result: The workflow result (used for timing).
        processing_time_ms: Processing time before error.

    Returns:
        Tuple of (empty_pattern, empty_components, error_metadata).
    """
    total_time = workflow_result.get("total_duration_ms", 0.0) + processing_time_ms

    return (
        AssembledPatternOutputDict(),
        ComponentResultsDict(),
        AssemblyMetadataDict(
            processing_time_ms=int(total_time),
            timestamp=datetime.now(UTC).isoformat(),
            trace_parsing_ms=0,
            keyword_extraction_ms=0,
            intent_classification_ms=0,
            criteria_matching_ms=0,
            status="assembly_failed",
            warnings=[f"Assembly error (PAO_005): {error_message}"],
        ),
    )


__all__ = [
    "assemble_pattern",
]
