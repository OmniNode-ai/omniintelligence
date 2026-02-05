"""Exception classes for Pattern Assembler Orchestrator.

Domain-specific exceptions corresponding to error types defined in contract.yaml.
All exceptions inherit from a common base for consistent error handling.

Error Code Format: PAO_XXX (Pattern Assembler Orchestrator)
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    EnumPatternAssemblerErrorCode,
)


class PatternAssemblerOrchestratorError(Exception):
    """Base exception for all pattern assembler orchestrator errors.

    Attributes:
        error_code: The PAO error code enum value.
        message: Human-readable error message.
        recoverable: Whether the error is recoverable via retry.
    """

    error_code: EnumPatternAssemblerErrorCode = (
        EnumPatternAssemblerErrorCode.PATTERN_ASSEMBLY_ERROR
    )

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    @property
    def recoverable(self) -> bool:
        """Check if this error type is recoverable via retry."""
        return self.error_code.is_recoverable


class TraceParsingError(PatternAssemblerOrchestratorError):
    """Error during execution trace parsing (PAO_001).

    Raised when the trace parser compute node fails to parse trace data.
    This is recoverable as it may be due to transient issues.
    """

    error_code = EnumPatternAssemblerErrorCode.TRACE_PARSING_ERROR


class KeywordExtractionError(PatternAssemblerOrchestratorError):
    """Error during keyword extraction (PAO_002).

    Raised when keyword extraction from traces fails.
    This is recoverable as it may be due to transient issues.
    """

    error_code = EnumPatternAssemblerErrorCode.KEYWORD_EXTRACTION_ERROR


class IntentClassificationError(PatternAssemblerOrchestratorError):
    """Error during intent classification (PAO_003).

    Raised when the intent classifier compute node fails.
    This is recoverable as it may be due to transient issues.
    """

    error_code = EnumPatternAssemblerErrorCode.INTENT_CLASSIFICATION_ERROR


class CriteriaMatchingError(PatternAssemblerOrchestratorError):
    """Error during success criteria matching (PAO_004).

    Raised when the success criteria matcher compute node fails.
    This is recoverable as it may be due to transient issues.
    """

    error_code = EnumPatternAssemblerErrorCode.CRITERIA_MATCHING_ERROR


class PatternAssemblyError(PatternAssemblerOrchestratorError):
    """Error during final pattern assembly (PAO_005).

    Raised when assembling the final pattern from component results fails.
    This is recoverable as it may be due to transient issues.
    """

    error_code = EnumPatternAssemblerErrorCode.PATTERN_ASSEMBLY_ERROR


class WorkflowTimeoutError(PatternAssemblerOrchestratorError):
    """Workflow execution exceeded timeout (PAO_006).

    Raised when the total workflow execution time exceeds the configured
    timeout (default 120 seconds). NOT recoverable - workflow must be restarted.
    """

    error_code = EnumPatternAssemblerErrorCode.WORKFLOW_TIMEOUT_ERROR


class DependencyResolutionError(PatternAssemblerOrchestratorError):
    """Error resolving workflow dependencies (PAO_007).

    Raised when a required compute node cannot be resolved or instantiated.
    This is recoverable as the node may become available on retry.
    """

    error_code = EnumPatternAssemblerErrorCode.DEPENDENCY_RESOLUTION_ERROR


class InvalidInputError(PatternAssemblerOrchestratorError):
    """Input validation failed (PAO_008).

    Raised when the input data fails validation checks.
    NOT recoverable - the input must be corrected before retrying.
    """

    error_code = EnumPatternAssemblerErrorCode.INVALID_INPUT_ERROR


__all__ = [
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
