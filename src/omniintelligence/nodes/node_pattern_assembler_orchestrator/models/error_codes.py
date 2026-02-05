"""Error codes for Pattern Assembler Orchestrator Node.

This module defines the error codes used by the pattern_assembler_orchestrator
node for standardized error handling and reporting.

Error Code Format: PAO_XXX
- PAO: Pattern Assembler Orchestrator prefix
- XXX: Three-digit numeric identifier

ONEX Compliance:
- Enum inherits from str for JSON serialization
- Error codes match contract.yaml error_types
- Descriptions provide actionable context
"""

from enum import Enum


class EnumPatternAssemblerErrorCode(str, Enum):
    """
    Error codes for the Pattern Assembler Orchestrator node.

    Each error code corresponds to an error_type defined in contract.yaml
    and provides a unique identifier for error tracking and debugging.
    """

    # PAO_001: Trace Parsing Error
    TRACE_PARSING_ERROR = "PAO_001"
    """Error during execution trace parsing."""

    # PAO_002: Keyword Extraction Error
    KEYWORD_EXTRACTION_ERROR = "PAO_002"
    """Error during keyword extraction from traces."""

    # PAO_003: Intent Classification Error
    INTENT_CLASSIFICATION_ERROR = "PAO_003"
    """Error during user intent classification."""

    # PAO_004: Criteria Matching Error
    CRITERIA_MATCHING_ERROR = "PAO_004"
    """Error during success criteria matching."""

    # PAO_005: Pattern Assembly Error
    PATTERN_ASSEMBLY_ERROR = "PAO_005"
    """Error during final pattern assembly from components."""

    # PAO_006: Workflow Timeout Error
    WORKFLOW_TIMEOUT_ERROR = "PAO_006"
    """Workflow execution exceeded configured timeout."""

    # PAO_007: Dependency Resolution Error
    DEPENDENCY_RESOLUTION_ERROR = "PAO_007"
    """Error resolving workflow step dependencies."""

    # PAO_008: Invalid Input Error
    INVALID_INPUT_ERROR = "PAO_008"
    """Input validation failed - invalid or missing required fields."""

    @classmethod
    def from_error_name(cls, error_name: str) -> "EnumPatternAssemblerErrorCode":
        """
        Get error code from error type name.

        Args:
            error_name: The error type name (e.g., "TraceParsingError")

        Returns:
            The corresponding error code enum value.

        Raises:
            ValueError: If error_name is not recognized.
        """
        name_mapping = {
            "TraceParsingError": cls.TRACE_PARSING_ERROR,
            "KeywordExtractionError": cls.KEYWORD_EXTRACTION_ERROR,
            "IntentClassificationError": cls.INTENT_CLASSIFICATION_ERROR,
            "CriteriaMatchingError": cls.CRITERIA_MATCHING_ERROR,
            "PatternAssemblyError": cls.PATTERN_ASSEMBLY_ERROR,
            "WorkflowTimeoutError": cls.WORKFLOW_TIMEOUT_ERROR,
            "DependencyResolutionError": cls.DEPENDENCY_RESOLUTION_ERROR,
            "InvalidInputError": cls.INVALID_INPUT_ERROR,
        }
        if error_name not in name_mapping:
            raise ValueError(f"Unknown error name: {error_name}")
        return name_mapping[error_name]

    @property
    def is_recoverable(self) -> bool:
        """Check if this error type is recoverable via retry."""
        non_recoverable = {
            self.WORKFLOW_TIMEOUT_ERROR,
            self.INVALID_INPUT_ERROR,
        }
        return self not in non_recoverable


__all__ = ["EnumPatternAssemblerErrorCode"]
