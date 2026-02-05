"""Handlers for Pattern Assembler Orchestrator Node.

This package contains the business logic for the pattern assembler orchestrator,
following the ONEX declarative pattern where the node.py is a thin shell
delegating to handlers.

Modules:
    handler_orchestrate: Main entry point for orchestration
    handler_workflow_coordination: Step execution and data transformation
    handler_pattern_assembly: Final pattern assembly logic
    exceptions: Domain-specific error classes
    protocols: TypedDicts and protocols for intermediate results
"""

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.exceptions import (
    CriteriaMatchingError,
    DependencyResolutionError,
    IntentClassificationError,
    InvalidInputError,
    KeywordExtractionError,
    PatternAssemblerOrchestratorError,
    PatternAssemblyError,
    TraceParsingError,
    WorkflowTimeoutError,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_orchestrate import (
    handle_pattern_assembly_orchestrate,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_pattern_assembly import (
    assemble_pattern,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_workflow_coordination import (
    STEP_ASSEMBLE_PATTERN,
    STEP_CLASSIFY_INTENT,
    STEP_MATCH_CRITERIA,
    STEP_PARSE_TRACES,
    build_assembly_context,
    execute_workflow_async,
)

__all__ = [
    # Main entry point
    "handle_pattern_assembly_orchestrate",
    # Workflow coordination
    "execute_workflow_async",
    "build_assembly_context",
    "STEP_PARSE_TRACES",
    "STEP_CLASSIFY_INTENT",
    "STEP_MATCH_CRITERIA",
    "STEP_ASSEMBLE_PATTERN",
    # Pattern assembly
    "assemble_pattern",
    # Exceptions
    "CriteriaMatchingError",
    "DependencyResolutionError",
    "IntentClassificationError",
    "InvalidInputError",
    "KeywordExtractionError",
    "PatternAssemblerOrchestratorError",
    "PatternAssemblyError",
    "TraceParsingError",
    "WorkflowTimeoutError",
]
